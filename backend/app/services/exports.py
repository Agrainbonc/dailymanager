from __future__ import annotations

import json
import re
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ARTIFACTS_DIR
from app.models import Course, Material


EXPORT_KINDS = {"source", "text"}


def _safe_component(value: str, fallback: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", value).strip(". ")
    return cleaned or fallback


def _material_record(material: Material) -> dict[str, object]:
    return {
        "id": material.id,
        "filename": material.original_filename,
        "material_type": material.material_type,
        "classification_status": material.classification_status,
        "classification_confidence": material.classification_confidence,
        "classification_reason": material.classification_reason,
        "status": material.status,
        "file_size": material.file_size,
        "created_at": material.created_at.isoformat() if material.created_at else None,
    }


def _text_document(material: Material) -> str:
    header = [
        f"# {material.original_filename}",
        "",
        f"- 资料类型：{material.material_type}",
        f"- 处理状态：{material.status}",
        f"- 课程归类：{material.classification_status}",
        "",
        "## 识别文本",
        "",
    ]
    if material.extracted_text:
        return "\n".join(header) + material.extracted_text.strip() + "\n"
    return "\n".join(header) + "该资料尚未产生可导出的识别文本。录音需要配置 ASR，PPT/PDF 需要完成解析。\n"


def create_course_export(session: Session, course: Course, export_kind: str) -> Path:
    """Build a disposable local ZIP for a course without modifying its library files."""
    if export_kind not in EXPORT_KINDS:
        raise ValueError("不支持的导出类型")

    materials = list(
        session.scalars(
            select(Material)
            .where(Material.course_id == course.id)
            .order_by(Material.created_at, Material.id)
        ).all()
    )
    export_directory = ARTIFACTS_DIR / "exports"
    export_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive_path = export_directory / f"course-{course.id}-{export_kind}-{timestamp}-{uuid.uuid4().hex[:8]}.zip"
    manifest = {
        "format": "daily-manager-course-export/v1",
        "course": {"id": course.id, "name": course.name},
        "export_kind": export_kind,
        "exported_at": datetime.now().astimezone().isoformat(),
        "material_count": len(materials),
        "materials": [_material_record(material) for material in materials],
    }

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        if export_kind == "source":
            for material in materials:
                source = Path(material.stored_path)
                if not source.is_file():
                    continue
                filename = _safe_component(material.original_filename, f"material-{material.id}")
                archive.write(source, f"source/{material.id:04d}_{filename}")
        else:
            archive.writestr(
                "README.md",
                "# 课程文本导出\n\n"
                "每份资料的可用识别文本位于 `texts/`。未接入识别模型的资料会保留状态说明，"
                "不会生成虚构内容。`manifest.json` 包含来源资料与分类元数据。\n",
            )
            for material in materials:
                stem = _safe_component(Path(material.original_filename).stem, f"material-{material.id}")
                archive.writestr(f"texts/{material.id:04d}_{stem}.md", _text_document(material))
    return archive_path


def create_custom_course_export(
    session: Session,
    course: Course,
    *,
    material_ids: list[int] | None = None,
    include_source: bool = True,
    include_text: bool = True,
) -> Path:
    """按用户所选资料及选项，打包导出课程源文件与 ASR/大纲文本。"""
    query = select(Material).where(Material.course_id == course.id)
    if material_ids:
        query = query.where(Material.id.in_(material_ids))
    materials = list(session.scalars(query.order_by(Material.created_at, Material.id)).all())

    if not materials:
        raise ValueError("未找到符合条件的导出资料")

    export_directory = ARTIFACTS_DIR / "exports"
    export_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive_path = export_directory / f"course-{course.id}-custom-{timestamp}-{uuid.uuid4().hex[:8]}.zip"

    manifest = {
        "format": "daily-manager-course-export/v2",
        "course": {"id": course.id, "name": course.name},
        "exported_at": datetime.now().astimezone().isoformat(),
        "include_source": include_source,
        "include_text": include_text,
        "material_count": len(materials),
        "materials": [_material_record(material) for material in materials],
    }

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr(
            "README.md",
            f"# {course.name} - 课程资料自定义导出\n\n"
            f"- 导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"- 资料项数：{len(materials)}\n"
            f"- 包含源文件：{'是' if include_source else '否'}\n"
            f"- 包含识别文本(ASR/大纲)：{'是' if include_text else '否'}\n\n"
            "## 目录结构说明\n"
            "- `source/`: 原始录音音频及课件文件（若勾选）\n"
            "- `texts/`: 对应的 ASR 语音转写文本与幻灯片解析大纲（若勾选）\n",
        )

        for material in materials:
            filename = _safe_component(material.original_filename, f"material-{material.id}")
            prefix = f"{material.id:04d}_{filename}"
            # 1. 导出源文件
            if include_source:
                source = Path(material.stored_path)
                if source.is_file():
                    archive.write(source, f"source/{prefix}")

            # 2. 导出 ASR 识别/提取文本
            if include_text:
                stem = _safe_component(Path(material.original_filename).stem, f"material-{material.id}")
                text_name = f"texts/{material.id:04d}_{stem}_转写文本.md"
                archive.writestr(text_name, _text_document(material))

    return archive_path


def remove_export(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        # A periodic cleanup is optional for the local MVP; never fail an HTTP response over cleanup.
        return

