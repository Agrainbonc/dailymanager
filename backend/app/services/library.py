from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import LIBRARY_DIR, SUPPORTED_EXTENSIONS
from app.models import AppSetting, Course, LessonSession, Material, ProcessingJob
from app.services.inference import ClassificationDecision, classify_material, infer_lesson_date, infer_material_type


INPUT_DIRECTORY_KEY = "library_input_directory"
OUTPUT_DIRECTORY_KEY = "library_output_directory"


def _safe_folder_name(value: str) -> str:
    clean = re.sub(r'[<>:"/\\|?*]+', "-", value).strip(". ")
    return clean or "untitled-course"


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _get_or_create_lesson(session: Session, course: Course, lesson_date) -> LessonSession:
    lesson = session.scalar(
        select(LessonSession).where(
            LessonSession.course_id == course.id,
            LessonSession.lesson_date == lesson_date,
        )
    )
    if lesson:
        return lesson
    lesson = LessonSession(course_id=course.id, lesson_date=lesson_date)
    session.add(lesson)
    session.flush()
    return lesson


def _setting_value(session: Session, key: str) -> str | None:
    setting = session.get(AppSetting, key)
    return setting.value if setting and setting.value.strip() else None


def get_library_settings(session: Session) -> dict[str, str | None]:
    return {
        "input_directory": _setting_value(session, INPUT_DIRECTORY_KEY),
        "output_directory": _setting_value(session, OUTPUT_DIRECTORY_KEY),
    }


def update_library_settings(session: Session, *, input_directory: str | None, output_directory: str | None) -> dict[str, str | None]:
    values = {
        INPUT_DIRECTORY_KEY: input_directory.strip() if input_directory else "",
        OUTPUT_DIRECTORY_KEY: output_directory.strip() if output_directory else "",
    }
    if values[INPUT_DIRECTORY_KEY]:
        source = Path(values[INPUT_DIRECTORY_KEY]).expanduser().resolve()
        if not source.is_dir():
            raise ValueError("统一投递目录不存在或不可访问")
        values[INPUT_DIRECTORY_KEY] = str(source)
    if values[OUTPUT_DIRECTORY_KEY]:
        target = Path(values[OUTPUT_DIRECTORY_KEY]).expanduser().resolve()
        target.mkdir(parents=True, exist_ok=True)
        values[OUTPUT_DIRECTORY_KEY] = str(target)
    for key, value in values.items():
        setting = session.get(AppSetting, key)
        if setting:
            setting.value = value
        else:
            session.add(AppSetting(key=key, value=value))
    session.flush()
    return get_library_settings(session)


def get_input_directory(session: Session) -> Path | None:
    value = _setting_value(session, INPUT_DIRECTORY_KEY)
    return Path(value) if value else None


def _library_root(session: Session) -> Path:
    import app.config
    value = _setting_value(session, OUTPUT_DIRECTORY_KEY)
    root = Path(value).expanduser().resolve() if value else app.config.LIBRARY_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def _unique_destination(destination_root: Path, filename: str) -> Path:
    original = Path(filename)
    stem = original.stem
    ext = original.suffix
    destination = destination_root / f"{stem}{ext}"
    suffix = 1
    while destination.exists():
        destination = destination_root / f"{stem} ({suffix}){ext}"
        suffix += 1
    return destination


def _archive_root(session: Session, course: Course | None, lesson_date) -> Path:
    root = _library_root(session)
    if not course:
        return root / "needs-review" / lesson_date.isoformat() / "source"
    return root / _safe_folder_name(course.name) / lesson_date.isoformat() / "source"


def _is_archived_path(path: Path, archive_root: Path | None) -> bool:
    """Avoid treating files in our own course/date/source structure as fresh inbox files."""
    if not archive_root:
        return False
    try:
        relative_parts = path.resolve().relative_to(archive_root.resolve()).parts
    except ValueError:
        return False
    return len(relative_parts) >= 4 and relative_parts[-2].casefold() == "source"


def _clean_empty_folders(root: Path) -> None:
    """Remove empty subdirectories left after files have been moved."""
    if not root.is_dir():
        return
    for item in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if item.is_dir() and item != root:
            try:
                item.rmdir()
            except OSError:
                pass


def import_material(
    session: Session,
    path: Path,
    course: Course | None,
    *,
    inferred_by: str,
    classification: ClassificationDecision | None = None,
    relocate_source: bool = False,
) -> Material | None:
    resolved = path.resolve()
    if not resolved.is_file() or resolved.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return None

    digest = _file_hash(resolved)
    existing = session.scalar(select(Material).where(Material.sha256 == digest))
    if existing:
        if relocate_source and resolved != Path(existing.stored_path).resolve():
            try:
                resolved.unlink(missing_ok=True)
            except OSError:
                pass
        return existing
    file_size = resolved.stat().st_size

    lesson_date = classification.lesson_date if classification else infer_lesson_date(resolved)
    lesson = None
    if course:
        lesson = _get_or_create_lesson(session, course, lesson_date)
    destination_root = _archive_root(session, course, lesson_date)
    destination_root.mkdir(parents=True, exist_ok=True)
    destination = _unique_destination(destination_root, resolved.name)
    if relocate_source:
        shutil.move(str(resolved), str(destination))
    else:
        shutil.copy2(resolved, destination)

    decision = classification or ClassificationDecision(
        course=course,
        lesson_date=lesson_date,
        confidence=100 if course else 0,
        status="classified" if course else "needs_review",
        method=inferred_by,
        reason="课程专属投递目录" if course else "未指定课程",
        candidates=[],
    )
    metadata = {
        "extension": resolved.suffix.lower(),
        "classification": decision.metadata(),
    }

    material = Material(
        course_id=course.id if course else None,
        lesson_session_id=lesson.id if lesson else None,
        material_type=infer_material_type(resolved),
        original_filename=resolved.name,
        source_path=str(resolved),
        stored_path=str(destination),
        sha256=digest,
        file_size=file_size,
        inferred_by=inferred_by,
        classification_status=decision.status,
        classification_confidence=decision.confidence,
        classification_reason=decision.reason,
        metadata_json=json.dumps(metadata, ensure_ascii=False),
    )
    session.add(material)
    session.flush()
    session.add(
        ProcessingJob(
            material_id=material.id,
            job_type="material.prepare",
            message="文件已归档，等待基础解析",
        )
    )
    return material


def scan_course_watch_path(session: Session, course: Course) -> list[Material]:
    if not course.watch_path:
        raise ValueError("该课程尚未设置投递目录")
    watch_path = Path(course.watch_path).expanduser().resolve()
    if not watch_path.is_dir():
        raise ValueError("投递目录不存在或不可访问")

    imported: list[Material] = []
    for path in watch_path.rglob("*"):
        material = import_material(session, path, course, inferred_by="course_watch_path")
        if material and material not in imported:
            imported.append(material)
    return imported


def scan_all_courses(session: Session) -> list[Material]:
    courses = list(session.scalars(select(Course)).all())
    imported: list[Material] = []
    for course in courses:
        if not course.watch_path:
            continue
        imported.extend(scan_course_watch_path(session, course))
    return imported


def import_from_inbox(session: Session, path: Path, *, inferred_by: str = "inbox_scanner") -> Material | None:
    if _is_archived_path(path, _library_root(session)):
        return None
    courses = list(session.scalars(select(Course)).all())
    decision = classify_material(path, courses)
    return import_material(
        session,
        path,
        decision.course,
        inferred_by=inferred_by,
        classification=decision,
        relocate_source=True,
    )


def scan_input_directory(session: Session) -> list[Material]:
    input_directory = get_input_directory(session)
    if not input_directory or not input_directory.is_dir():
        raise ValueError("请先设置可访问的统一投递目录")
    imported: list[Material] = []
    file_paths = [p for p in input_directory.rglob("*") if p.is_file()]
    for path in file_paths:
        material = import_from_inbox(session, path)
        if material and material not in imported:
            imported.append(material)
    _clean_empty_folders(input_directory)
    return imported


def assign_material_to_course(session: Session, material: Material, course: Course) -> Material:
    current_path = Path(material.stored_path)
    if not current_path.is_file():
        raise ValueError("归档文件不存在，无法重新归类")
    lesson_date = infer_lesson_date(current_path)
    lesson = _get_or_create_lesson(session, course, lesson_date)
    destination_root = _archive_root(session, course, lesson_date)
    destination_root.mkdir(parents=True, exist_ok=True)
    destination = _unique_destination(destination_root, material.original_filename)
    shutil.move(str(current_path), str(destination))
    metadata = json.loads(material.metadata_json or "{}")
    metadata["classification"] = {
        "status": "manual_assigned",
        "confidence": 100,
        "method": "manual_assignment",
        "reason": f"用户指定为“{course.name}”",
        "lesson_date": lesson_date.isoformat(),
    }
    material.course_id = course.id
    material.lesson_session_id = lesson.id
    material.stored_path = str(destination)
    material.inferred_by = "manual_assignment"
    material.classification_status = "manual_assigned"
    material.classification_confidence = 100
    material.classification_reason = f"用户指定为“{course.name}”"
    material.metadata_json = json.dumps(metadata, ensure_ascii=False)
    session.flush()
    return material


def save_uploaded_material(
    session: Session,
    file_bytes: bytes,
    filename: str,
    course: Course | None = None,
    *,
    force_keep: bool = False,
) -> tuple[bool, Material, Material | None]:
    """保存用户直接上传的文件。

    返回 (is_conflict, material_or_created, existing_material)
    - 若存在相同 SHA-256 且 force_keep=False：返回 (True, existing, existing)
    - 否则正常写入存储并创建 Material，返回 (False, new_material, None)
    """
    clean_name = Path(filename).name
    if not clean_name:
        clean_name = "uploaded_file"
    ext = Path(clean_name).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"不支持的文件格式：{ext}。支持的格式包括音频与幻灯片文件")

    digest = hashlib.sha256(file_bytes).hexdigest()
    existing = session.scalar(
        select(Material).where(Material.sha256 == digest).order_by(Material.id.asc()).limit(1)
    )

    if existing and not force_keep:
        return True, existing, existing

    # 确定保存路径
    lesson_date = infer_lesson_date(Path(clean_name))
    lesson = None
    if course:
        lesson = _get_or_create_lesson(session, course, lesson_date)
    destination_root = _archive_root(session, course, lesson_date)
    destination_root.mkdir(parents=True, exist_ok=True)
    destination = _unique_destination(destination_root, clean_name)
    destination.write_bytes(file_bytes)

    decision = ClassificationDecision(
        course=course,
        lesson_date=lesson_date,
        confidence=100 if course else 0,
        status="classified" if course else "needs_review",
        method="web_upload",
        reason=f"用户网页端直接上传（课程：{course.name}）" if course else "用户网页端上传，未指定课程",
        candidates=[],
    )
    metadata = {
        "extension": ext,
        "classification": decision.metadata(),
        "uploaded_by": "user_web",
    }

    material = Material(
        course_id=course.id if course else None,
        lesson_session_id=lesson.id if lesson else None,
        material_type=infer_material_type(destination),
        original_filename=clean_name,
        source_path=str(destination),
        stored_path=str(destination),
        sha256=digest,
        file_size=len(file_bytes),
        inferred_by="web_upload",
        classification_status=decision.status,
        classification_confidence=decision.confidence,
        classification_reason=decision.reason,
        metadata_json=json.dumps(metadata, ensure_ascii=False),
    )
    session.add(material)
    session.flush()

    session.add(
        ProcessingJob(
            material_id=material.id,
            job_type="material.prepare",
            message="用户上传文件已就绪，等待基础解析",
        )
    )
    session.flush()
    return False, material, None


def find_duplicate_materials(session: Session) -> list[dict]:
    """查询工作区中具有相同哈希（SHA-256）的所有重复文件分组。"""
    materials = list(
        session.scalars(
            select(Material).order_by(Material.sha256, Material.id.asc())
        ).all()
    )
    from collections import defaultdict

    groups = defaultdict(list)
    for m in materials:
        groups[m.sha256].append(m)

    result = []
    for sha, group in groups.items():
        if len(group) > 1:
            result.append({
                "sha256": sha,
                "file_size": group[0].file_size,
                "count": len(group),
                "materials": group,
            })
    return result


def deduplicate_materials(session: Session) -> tuple[int, int, int]:
    """合并并清理工作区现存的重复文件。

    规则：
    - 针对相同 SHA256 的多条记录：
      优先保留：状态为 ready 或有提取文本 extracted_text 的记录；若状态相同则保留最早创建的 ID。
    - 其它冗余记录：清理其 ProcessingJob，若冗余文件的 stored_path 与保留文件不同且存在，则从磁盘删除以释放空间；
    - 从数据库 materials 中删除冗余记录。
    返回 (cleaned_count, retained_count, freed_bytes)
    """
    duplicates = find_duplicate_materials(session)
    if not duplicates:
        return 0, 0, 0

    cleaned_count = 0
    retained_count = 0
    freed_bytes = 0

    for group_info in duplicates:
        group: list[Material] = group_info["materials"]

        def score(m: Material):
            has_text = 1 if (m.extracted_text and len(m.extracted_text.strip()) > 0) else 0
            is_ready = 1 if m.status == "ready" else 0
            return (has_text, is_ready, -m.id)

        sorted_group = sorted(group, key=score, reverse=True)
        keeper = sorted_group[0]
        retained_count += 1
        keeper_path = Path(keeper.stored_path).resolve() if keeper.stored_path else None

        for redundant in sorted_group[1:]:
            # 1. 删除其关联的所有 ProcessingJob
            session.query(ProcessingJob).filter(ProcessingJob.material_id == redundant.id).delete(synchronize_session=False)

            # 2. 如果磁盘路径不同于 keeper，清理物理文件释放空间
            if redundant.stored_path:
                red_path = Path(redundant.stored_path).resolve()
                if red_path.is_file() and (keeper_path is None or red_path != keeper_path):
                    try:
                        file_size = red_path.stat().st_size
                        red_path.unlink(missing_ok=True)
                        freed_bytes += file_size
                    except OSError:
                        pass

            # 3. 从数据库中删除冗余记录
            session.delete(redundant)
            cleaned_count += 1

    session.commit()
    return cleaned_count, retained_count, freed_bytes


def delete_material(session: Session, material_id: int, delete_file: bool = True) -> tuple[bool, int]:
    """安全删除单个资料。

    执行步骤：
    1. 级联删除关联的 ProcessingJob；
    2. 检查引用计数（若无其它资料共享同一存储路径，且 delete_file=True，则物理删除文件）；
    3. 从数据库删除 Material 记录并提交。
    返回 (是否成功, 释放字节数)
    """
    material = session.get(Material, material_id)
    if not material:
        return False, 0

    freed_bytes = 0
    stored_path_str = material.stored_path

    # 1. 级联删除 ProcessingJob
    for job in list(session.scalars(select(ProcessingJob).where(ProcessingJob.material_id == material.id)).all()):
        session.delete(job)

    # 2. 引用计数保护检测
    if delete_file and stored_path_str:
        shared_count = session.scalar(
            select(func.count(Material.id)).where(
                Material.stored_path == stored_path_str,
                Material.id != material.id,
            )
        ) or 0
        if shared_count == 0:
            phys_path = Path(stored_path_str).resolve()
            if phys_path.is_file():
                try:
                    freed_bytes = phys_path.stat().st_size
                    phys_path.unlink(missing_ok=True)
                except OSError:
                    pass

    # 3. 删除数据库记录
    session.delete(material)
    session.commit()
    return {
        "material_id": material_id,
        "file_deleted": (freed_bytes > 0),
        "freed_bytes": freed_bytes,
    }


def delete_materials_batch(
    session: Session, material_ids: list[int], delete_files: bool = True
) -> dict:
    """批量删除资料，具备原子性保护与引用计数检查。"""
    deleted_count = 0
    deleted_ids: list[int] = []
    freed_bytes_total = 0

    for m_id in material_ids:
        res = delete_material(session, m_id, delete_file=delete_files)
        if res.get("material_id"):
            deleted_count += 1
            deleted_ids.append(m_id)
            freed_bytes_total += res.get("freed_bytes", 0)

    return {
        "deleted_count": deleted_count,
        "deleted_material_ids": deleted_ids,
        "freed_bytes": freed_bytes_total,
    }


def resolve_duplicate_group(
    session: Session, sha256: str, keeper_id: int
) -> tuple[bool, int, list[int], int]:
    """针对单个重复分组进行精准治理：保留用户指定的 keeper_id 主项，清理其余副本。"""
    group_materials = list(
        session.scalars(select(Material).where(Material.sha256 == sha256)).all()
    )
    if not group_materials:
        return False, 0, [], 0

    keeper = next((m for m in group_materials if m.id == keeper_id), None)
    if not keeper:
        return False, 0, [], 0

    cleaned_ids: list[int] = []
    freed_bytes = 0
    keeper_path = Path(keeper.stored_path).resolve() if keeper.stored_path else None

    for m in group_materials:
        if m.id == keeper.id:
            continue

        for job in list(session.scalars(select(ProcessingJob).where(ProcessingJob.material_id == m.id)).all()):
            session.delete(job)

        if m.stored_path:
            red_path = Path(m.stored_path).resolve()
            if red_path.is_file() and (keeper_path is None or red_path != keeper_path):
                shared = session.scalar(
                    select(func.count(Material.id)).where(
                        Material.stored_path == m.stored_path,
                        Material.id != m.id,
                        Material.id != keeper.id,
                    )
                ) or 0
                if shared == 0:
                    try:
                        freed_bytes += red_path.stat().st_size
                        red_path.unlink(missing_ok=True)
                    except OSError:
                        pass

        session.delete(m)
        cleaned_ids.append(m.id)

    session.commit()
    return {
        "sha256": sha256,
        "keeper_id": keeper.id,
        "removed_ids": cleaned_ids,
        "freed_bytes": freed_bytes,
    }


def audit_storage(session: Session) -> dict:
    """审计工作区存储，扫描孤儿文件与垃圾占用。"""
    lib_root = _library_root(session)

    materials = list(session.scalars(select(Material)).all())
    total_materials_count = len(materials)
    valid_files_count = 0
    missing_files_count = 0

    known_paths = set()
    for m in materials:
        if m.stored_path:
            p = Path(m.stored_path)
            if p.is_file():
                valid_files_count += 1
                known_paths.add(p.resolve())
            else:
                missing_files_count += 1

    orphan_files: list[str] = []
    orphan_files_bytes = 0

    if lib_root.is_dir():
        for p in lib_root.rglob("*"):
            if p.is_file() and p.resolve() not in known_paths:
                orphan_files.append(str(p))
                try:
                    orphan_files_bytes += p.stat().st_size
                except OSError:
                    pass

    return {
        "total_materials_count": total_materials_count,
        "valid_files_count": valid_files_count,
        "missing_files_count": missing_files_count,
        "orphan_files_count": len(orphan_files),
        "orphan_files_bytes": orphan_files_bytes,
        "orphan_sample_paths": orphan_files[:20],
    }


def clean_orphan_files(session: Session) -> dict:
    """清理工作区中的孤儿物理文件与残留空目录。"""
    lib_root = _library_root(session)
    materials = list(session.scalars(select(Material)).all())
    known_paths = {Path(m.stored_path).resolve() for m in materials if m.stored_path and Path(m.stored_path).is_file()}

    cleaned_count = 0
    freed_bytes = 0
    removed_paths: list[str] = []

    if lib_root.is_dir():
        for p in lib_root.rglob("*"):
            if p.is_file() and p.resolve() not in known_paths:
                try:
                    size = p.stat().st_size
                    p.unlink(missing_ok=True)
                    cleaned_count += 1
                    freed_bytes += size
                    removed_paths.append(str(p))
                except OSError:
                    pass
        _clean_empty_folders(lib_root)

    return {
        "cleaned_orphans_count": cleaned_count,
        "freed_bytes": freed_bytes,
        "removed_paths": removed_paths[:50],
    }
