from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.asr import get_asr_provider
from app.adapters.vision import get_vision_provider
from app.database import get_session
from app.models import Course, Material, ProcessingJob
from app.schemas import (
    AdaptersStatusRead,
    AsrSettingsConfig,
    AsrTestRequest,
    AsrTestResponse,
    BatchDeleteRequest,
    BatchDeleteResponse,
    CalendarWorkspaceCreate,
    CalendarWorkspaceRead,
    CalendarWorkspaceUpdate,
    CleanOrphansResponse,
    CourseCreate,
    CourseRead,
    CourseUpdate,
    CustomExportRequest,
    DeduplicateResult,
    DuplicateGroupRead,
    JobRead,
    LibrarySettingsRead,
    LibrarySettingsUpdate,
    MaterialAssignment,
    MaterialRead,
    MaterialUploadResponse,
    OverviewRead,
    ResolveDuplicateGroupRequest,
    ResolveDuplicateGroupResponse,
    ScanResult,
    StorageAuditRead,
    StrategyBoardRead,
    StrategyBoardUpdate,
    SyncCoursesToCalendarRequest,
    SyncCoursesToCalendarResponse,
    SystemSettingsRead,
    SystemSettingsUpdate,
    WorkflowProjectCreate,
    WorkflowProjectRead,
    WorkflowProjectUpdate,
)
from app.services.calendar_service import (
    create_calendar_workspace,
    delete_calendar_workspace,
    get_strategy_board,
    list_calendar_workspaces,
    sync_courses_to_calendar,
    update_calendar_workspace,
    update_strategy_board,
)
from app.services.settings_service import (
    load_system_settings,
    save_system_settings,
    test_asr_connection,
)
from app.services.workflow_service import (
    create_workflow,
    delete_workflow,
    list_workflows,
    update_workflow,
)
from app.services.library import (
    assign_material_to_course,
    audit_storage,
    clean_orphan_files,
    deduplicate_materials,
    delete_material,
    delete_materials_batch,
    find_duplicate_materials,
    get_library_settings,
    resolve_duplicate_group,
    save_uploaded_material,
    scan_course_watch_path,
    scan_input_directory as scan_library_input,
    update_library_settings,
)
from app.services.exports import (
    EXPORT_KINDS,
    create_course_export,
    create_custom_course_export,
    remove_export,
)
from app.services.timetable_recognition import (
    TimetableApplyPayload,
    TimetableApplyResult,
    TimetableRecognitionResult,
    apply_timetable_candidates,
    recognize_timetable_image,
)
from app.services.watch_service import directory_watch_service
from app.services.job_runner import job_runner


router = APIRouter(prefix="/api")


def course_read(course: Course, material_count: int = 0) -> CourseRead:
    try:
        aliases = json.loads(course.aliases_json or "[]")
    except (TypeError, ValueError):
        aliases = []
    try:
        keywords = json.loads(course.keywords_json or "[]")
    except (TypeError, ValueError):
        keywords = []
    try:
        schedule = json.loads(course.schedule_json or "[]")
    except (TypeError, ValueError):
        schedule = []
    return CourseRead(
        id=course.id,
        name=course.name,
        aliases=aliases,
        keywords=keywords,
        schedule=schedule,
        watch_path=course.watch_path,
        created_at=course.created_at,
        material_count=material_count,
    )


def _clean_terms(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        term = value.strip()
        key = term.casefold()
        if term and key not in seen:
            cleaned.append(term)
            seen.add(key)
    return cleaned


def material_read(material: Material) -> MaterialRead:
    return MaterialRead(
        id=material.id,
        course_id=material.course_id,
        lesson_session_id=material.lesson_session_id,
        material_type=material.material_type,
        status=material.status,
        classification_status=material.classification_status,
        classification_confidence=material.classification_confidence,
        classification_reason=material.classification_reason,
        original_filename=material.original_filename,
        stored_path=material.stored_path,
        file_size=material.file_size,
        extracted_text=material.extracted_text,
        created_at=material.created_at,
    )


def job_read(
    job: ProcessingJob,
    material_filename: str | None = None,
    course_name: str | None = None,
) -> JobRead:
    return JobRead(
        id=job.id,
        material_id=job.material_id,
        job_type=job.job_type,
        status=job.status,
        stage=job.stage,
        progress=job.progress,
        message=job.message,
        attempts=job.attempts,
        created_at=job.created_at,
        material_filename=material_filename,
        course_name=course_name,
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "local"}


@router.get("/overview", response_model=OverviewRead)
def get_overview(session: Session = Depends(get_session)) -> OverviewRead:
    return OverviewRead(
        course_count=session.scalar(select(func.count(Course.id))) or 0,
        material_count=session.scalar(select(func.count(Material.id))) or 0,
        pending_jobs=session.scalar(
            select(func.count(ProcessingJob.id)).where(ProcessingJob.status.in_(["queued", "running"]))
        )
        or 0,
        awaiting_recognition=session.scalar(
            select(func.count(Material.id)).where(Material.status == "awaiting_recognition")
        )
        or 0,
        needs_review=session.scalar(
            select(func.count(Material.id)).where(Material.classification_status == "needs_review")
        )
        or 0,
    )


@router.get("/courses", response_model=list[CourseRead])
def list_courses(session: Session = Depends(get_session)) -> list[CourseRead]:
    courses = list(session.scalars(select(Course).order_by(Course.name)).all())
    counts = dict(
        session.execute(select(Material.course_id, func.count(Material.id)).group_by(Material.course_id)).all()
    )
    return [course_read(course, int(counts.get(course.id, 0))) for course in courses]


@router.post("/courses", response_model=CourseRead, status_code=201)
def create_course(payload: CourseCreate, session: Session = Depends(get_session)) -> CourseRead:
    watch_path = str(Path(payload.watch_path).expanduser()) if payload.watch_path else None
    course = Course(
        name=payload.name.strip(),
        aliases_json=json.dumps(_clean_terms(payload.aliases), ensure_ascii=False),
        keywords_json=json.dumps(_clean_terms(payload.keywords), ensure_ascii=False),
        schedule_json=json.dumps([item.model_dump() for item in payload.schedule], ensure_ascii=False),
        watch_path=watch_path,
    )
    session.add(course)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="课程名称已存在") from None
    session.refresh(course)
    directory_watch_service.refresh()
    return course_read(course)


@router.put("/courses/{course_id}", response_model=CourseRead)
def update_course(
    course_id: int,
    payload: CourseUpdate,
    session: Session = Depends(get_session),
) -> CourseRead:
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    course.aliases_json = json.dumps(_clean_terms(payload.aliases), ensure_ascii=False)
    course.keywords_json = json.dumps(_clean_terms(payload.keywords), ensure_ascii=False)
    course.schedule_json = json.dumps([item.model_dump() for item in payload.schedule], ensure_ascii=False)
    session.commit()
    session.refresh(course)
    return course_read(course)


@router.get("/courses/{course_id}/export/{export_kind}")
def export_course(
    course_id: int,
    export_kind: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> FileResponse:
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    if export_kind not in EXPORT_KINDS:
        raise HTTPException(status_code=400, detail="导出类型应为 source 或 text")
    archive_path = create_course_export(session, course, export_kind)
    background_tasks.add_task(remove_export, archive_path)
    label = "源文件" if export_kind == "source" else "识别文本"
    return FileResponse(
        archive_path,
        media_type="application/zip",
        filename=f"{course.name}-{label}.zip",
        background=background_tasks,
    )


@router.post("/courses/{course_id}/export/custom")
def export_course_custom(
    course_id: int,
    payload: CustomExportRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> FileResponse:
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    if not payload.material_ids:
        raise HTTPException(status_code=400, detail="请至少选择一个待导出的文件")
    if not payload.include_source and not payload.include_text:
        raise HTTPException(status_code=400, detail="至少勾选包含源文件或包含识别文本")

    try:
        archive_path = create_custom_course_export(
            session=session,
            course=course,
            material_ids=payload.material_ids,
            include_source=payload.include_source,
            include_text=payload.include_text,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    background_tasks.add_task(remove_export, archive_path)
    return FileResponse(
        archive_path,
        media_type="application/zip",
        filename=f"{course.name}-自定义资料导出.zip",
        background=background_tasks,
    )


@router.get("/library/settings", response_model=LibrarySettingsRead)
def read_library_settings(session: Session = Depends(get_session)) -> LibrarySettingsRead:
    return LibrarySettingsRead(**get_library_settings(session))


@router.put("/library/settings", response_model=LibrarySettingsRead)
def save_library_settings(
    payload: LibrarySettingsUpdate,
    session: Session = Depends(get_session),
) -> LibrarySettingsRead:
    try:
        settings = update_library_settings(
            session,
            input_directory=payload.input_directory,
            output_directory=payload.output_directory,
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    directory_watch_service.refresh()
    return LibrarySettingsRead(**settings)


@router.post("/library/scan", response_model=ScanResult)
def scan_input_directory(session: Session = Depends(get_session)) -> ScanResult:
    try:
        materials = scan_library_input(session)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ScanResult(imported_count=len(materials), materials=[material_read(item) for item in materials])


@router.post("/courses/{course_id}/scan", response_model=ScanResult)
def scan_course(course_id: int, session: Session = Depends(get_session)) -> ScanResult:
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    try:
        materials = scan_course_watch_path(session, course)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ScanResult(imported_count=len(materials), materials=[material_read(item) for item in materials])


@router.get("/materials", response_model=list[MaterialRead])
def list_materials(
    course_id: int | None = None,
    review_needed: bool = False,
    q: str | None = None,
    session: Session = Depends(get_session),
) -> list[MaterialRead]:
    statement = select(Material).order_by(Material.created_at.desc(), Material.id.desc())
    if course_id is not None:
        statement = statement.where(Material.course_id == course_id)
    if review_needed:
        statement = statement.where(Material.classification_status == "needs_review")
    if q and q.strip():
        search_pattern = f"%{q.strip()}%"
        statement = statement.where(
            Material.original_filename.like(search_pattern) | Material.extracted_text.like(search_pattern)
        )
    return [material_read(item) for item in session.scalars(statement).all()]


@router.post("/materials/{material_id}/assign", response_model=MaterialRead)
def assign_material(
    material_id: int,
    payload: MaterialAssignment,
    session: Session = Depends(get_session),
) -> MaterialRead:
    material = session.get(Material, material_id)
    course = session.get(Course, payload.course_id)
    if not material or not course:
        raise HTTPException(status_code=404, detail="资料或课程不存在")
    try:
        assign_material_to_course(session, material, course)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return material_read(material)


@router.post("/materials/upload", response_model=MaterialUploadResponse)
async def upload_material(
    file: UploadFile = File(...),
    course_id: int | None = None,
    force_keep: bool = False,
    session: Session = Depends(get_session),
) -> MaterialUploadResponse:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件内容为空")
    filename = file.filename or "uploaded_file"
    course = session.get(Course, course_id) if course_id else None

    try:
        is_conflict, material_or_existing, conflict_existing = save_uploaded_material(
            session=session,
            file_bytes=content,
            filename=filename,
            course=course,
            force_keep=force_keep,
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if is_conflict:
        return MaterialUploadResponse(
            conflict=True,
            message="检测到相同内容的文件已存在于工作区中",
            existing_material=material_read(conflict_existing) if conflict_existing else None,
            material=None,
        )

    return MaterialUploadResponse(
        conflict=False,
        message="文件上传成功，已加入工作区并建立解析任务",
        material=material_read(material_or_existing),
        existing_material=None,
    )


@router.get("/materials/duplicates", response_model=list[DuplicateGroupRead])
def get_duplicate_materials(session: Session = Depends(get_session)) -> list[DuplicateGroupRead]:
    groups = find_duplicate_materials(session)
    result = []
    for g in groups:
        result.append(
            DuplicateGroupRead(
                sha256=g["sha256"],
                file_size=g["file_size"],
                count=g["count"],
                materials=[material_read(m) for m in g["materials"]],
            )
        )
    return result


@router.post("/materials/deduplicate", response_model=DeduplicateResult)
def clean_duplicate_materials(session: Session = Depends(get_session)) -> DeduplicateResult:
    cleaned, retained, freed = deduplicate_materials(session)
    return DeduplicateResult(
        cleaned_count=cleaned,
        retained_count=retained,
        freed_bytes=freed,
    )


@router.post("/materials/duplicates/resolve-group", response_model=ResolveDuplicateGroupResponse)
def resolve_duplicate_group_endpoint(
    payload: ResolveDuplicateGroupRequest,
    session: Session = Depends(get_session),
) -> ResolveDuplicateGroupResponse:
    try:
        result = resolve_duplicate_group(
            session,
            sha256=payload.sha256,
            keeper_id=payload.keeper_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ResolveDuplicateGroupResponse(
        sha256=result["sha256"],
        keeper_id=result["keeper_id"],
        removed_ids=result["removed_ids"],
        freed_bytes=result["freed_bytes"],
    )


@router.delete("/materials/{material_id}")
def remove_material(
    material_id: int,
    delete_file: bool = True,
    session: Session = Depends(get_session),
) -> dict:
    try:
        result = delete_material(session, material_id=material_id, delete_file=delete_file)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"message": "资料已删除", **result}


@router.post("/materials/batch-delete", response_model=BatchDeleteResponse)
def batch_delete_materials_endpoint(
    payload: BatchDeleteRequest,
    session: Session = Depends(get_session),
) -> BatchDeleteResponse:
    result = delete_materials_batch(
        session,
        material_ids=payload.material_ids,
        delete_files=payload.delete_files,
    )
    return BatchDeleteResponse(**result)


@router.get("/system/storage/audit", response_model=StorageAuditRead)
def get_storage_audit(session: Session = Depends(get_session)) -> StorageAuditRead:
    result = audit_storage(session)
    return StorageAuditRead(**result)


@router.post("/system/storage/clean-orphans", response_model=CleanOrphansResponse)
def run_clean_orphans(session: Session = Depends(get_session)) -> CleanOrphansResponse:
    result = clean_orphan_files(session)
    return CleanOrphansResponse(**result)


@router.get("/materials/{material_id}/file")
async def get_material_file(
    material_id: int,
    download: bool = False,
    session: Session = Depends(get_session),
) -> FileResponse:
    material = session.get(Material, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="资料不存在")
    path = Path(material.stored_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="本地文件未找到或已被移除")

    suffix = path.suffix.lower()
    media_type = None
    if suffix == ".mp3":
        media_type = "audio/mpeg"
    elif suffix in [".m4a", ".mp4"]:
        media_type = "audio/mp4"
    elif suffix == ".wav":
        media_type = "audio/wav"
    elif suffix == ".aac":
        media_type = "audio/aac"
    elif suffix == ".flac":
        media_type = "audio/flac"
    elif suffix == ".pdf":
        media_type = "application/pdf"
    elif suffix in [".ppt", ".pptx"]:
        media_type = "application/vnd.ms-powerpoint"

    stat_result = path.stat()

    # 在线试听/浏览模式：不设置 Content-Disposition 避免浏览器音频管道与特殊字符冲突，纯流式返回
    if not download:
        return FileResponse(
            str(path),
            media_type=media_type,
            stat_result=stat_result,
        )

    # 显式下载模式：清理特殊字符与不可打印字符，确保符合 HTTP 标头规范
    raw_name = material.original_filename or path.name
    cleaned_name = "".join(c for c in raw_name if c.isprintable() and c not in '<>:"/\\|?*').strip() or "material"
    if not Path(cleaned_name).suffix and suffix:
        cleaned_name += suffix

    return FileResponse(
        str(path),
        filename=cleaned_name,
        media_type=media_type,
        content_disposition_type="attachment",
        stat_result=stat_result,
    )


@router.get("/jobs", response_model=list[JobRead])
def list_jobs(course_id: int | None = None, session: Session = Depends(get_session)) -> list[JobRead]:
    statement = (
        select(ProcessingJob, Material.original_filename, Course.name)
        .join(Material, ProcessingJob.material_id == Material.id)
        .outerjoin(Course, Material.course_id == Course.id)
        .order_by(ProcessingJob.created_at.desc(), ProcessingJob.id.desc())
    )
    if course_id is not None:
        statement = statement.where(Material.course_id == course_id)
    results = session.execute(statement).all()
    return [
        job_read(job, material_filename=filename, course_name=course_name)
        for job, filename, course_name in results
    ]


@router.get("/adapters/status", response_model=AdaptersStatusRead)
def get_adapters_status() -> AdaptersStatusRead:
    asr = get_asr_provider()
    vision = get_vision_provider()
    return AdaptersStatusRead(
        asr_provider=asr.name,
        vision_provider=vision.name,
        asr_ready=True,
        vision_ready=True,
    )


@router.post("/materials/{material_id}/transcribe", response_model=JobRead)
def trigger_material_transcribe(
    material_id: int,
    session: Session = Depends(get_session),
) -> JobRead:
    material = session.get(Material, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="资料不存在")
    if material.material_type != "audio":
        raise HTTPException(status_code=400, detail="仅音频资料支持语音转写")

    asr = get_asr_provider()
    # 查找是否已有尚未完成（queued 或 running）的任务
    existing_job = session.scalar(
        select(ProcessingJob)
        .where(
            ProcessingJob.material_id == material.id,
            ProcessingJob.job_type == "audio.transcribe",
            ProcessingJob.status.in_(["queued", "running"]),
        )
        .order_by(ProcessingJob.id.desc())
        .limit(1)
    )

    if existing_job:
        existing_job.status = "queued"
        existing_job.stage = "queued"
        existing_job.progress = 0
        existing_job.message = f"等待语音转写（重新排队，使用 {asr.name}）"
        material.status = "queued"
        session.commit()
        session.refresh(existing_job)
        job = existing_job
    else:
        job = ProcessingJob(
            material_id=material.id,
            job_type="audio.transcribe",
            message=f"等待语音转写（使用 {asr.name}）",
        )
        material.status = "queued"
        session.add(job)
        session.commit()
        session.refresh(job)

    course = session.get(Course, material.course_id) if material.course_id else None
    return job_read(
        job,
        material_filename=material.original_filename,
        course_name=course.name if course else None,
    )


@router.post("/jobs/recover")
def recover_processing_jobs() -> dict[str, int]:
    """一键扫描并恢复因服务中断或热重载导致挂起的孤儿任务。"""
    recovered_count = job_runner.recover_stale_jobs(requeue=True)
    return {"recovered_count": recovered_count}


@router.post("/jobs/{job_id}/retry", response_model=JobRead)
def retry_processing_job(job_id: int, session: Session = Depends(get_session)) -> JobRead:
    """手动重试指定的失败或中断任务。"""
    ok = job_runner.retry_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="任务不存在")
    job = session.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    material = session.get(Material, job.material_id)
    course = session.get(Course, material.course_id) if (material and material.course_id) else None
    return job_read(
        job,
        material_filename=material.original_filename if material else None,
        course_name=course.name if course else None,
    )


@router.post("/timetable/recognize", response_model=TimetableRecognitionResult)
async def recognize_timetable(
    file: UploadFile = File(...),
) -> TimetableRecognitionResult:
    import inspect

    read_val = file.read()
    content = await read_val if inspect.isawaitable(read_val) else read_val
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")
    filename = file.filename or "timetable.png"
    return recognize_timetable_image(content, filename)


@router.post("/timetable/apply", response_model=TimetableApplyResult)
def apply_timetable(
    payload: TimetableApplyPayload,
    session: Session = Depends(get_session),
) -> TimetableApplyResult:
    if not payload.items:
        raise HTTPException(status_code=400, detail="待应用的课表项不能为空")
    result = apply_timetable_candidates(session, payload.items)
    session.commit()
    return result


# --- 系统设置中心路由 ---

@router.get("/system/settings", response_model=SystemSettingsRead)
def get_system_settings_api(session: Session = Depends(get_session)) -> SystemSettingsRead:
    return load_system_settings(session)


@router.put("/system/settings", response_model=SystemSettingsRead)
def update_system_settings_api(
    payload: SystemSettingsUpdate, session: Session = Depends(get_session)
) -> SystemSettingsRead:
    updated = save_system_settings(payload, session)
    # 若更新了投递目录，同步更新 watch_service
    if payload.input_directory is not None:
        directory_watch_service.update_watch_path(payload.input_directory.strip() or None)
    return updated


@router.post("/system/settings/asr/test", response_model=AsrTestResponse)
def test_asr_settings_api(payload: AsrTestRequest, session: Session = Depends(get_session)) -> AsrTestResponse:
    config = payload.asr
    if config is None:
        current = load_system_settings(session)
        config = current.asr
    success, message, latency = test_asr_connection(config)
    return AsrTestResponse(success=success, message=message, latency_ms=latency)


# --- 日历日程与博弈论 (Tokii) 路由 ---

@router.get("/calendar/workspaces", response_model=list[CalendarWorkspaceRead])
def list_calendar_workspaces_api(session: Session = Depends(get_session)) -> list[CalendarWorkspaceRead]:
    return list_calendar_workspaces(session)


@router.post("/calendar/workspaces", response_model=CalendarWorkspaceRead)
def create_calendar_workspace_api(
    payload: CalendarWorkspaceCreate, session: Session = Depends(get_session)
) -> CalendarWorkspaceRead:
    return create_calendar_workspace(payload, session)


@router.put("/calendar/workspaces/{workspace_id}", response_model=CalendarWorkspaceRead)
def update_calendar_workspace_api(
    workspace_id: str, payload: CalendarWorkspaceUpdate, session: Session = Depends(get_session)
) -> CalendarWorkspaceRead:
    try:
        return update_calendar_workspace(workspace_id, payload, session)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/calendar/workspaces/{workspace_id}")
def delete_calendar_workspace_api(
    workspace_id: str, session: Session = Depends(get_session)
) -> dict[str, bool]:
    try:
        ok = delete_calendar_workspace(workspace_id, session)
        if not ok:
            raise HTTPException(status_code=404, detail="日历工作区不存在")
        return {"success": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/calendar/strategy", response_model=StrategyBoardRead)
def get_strategy_board_api(session: Session = Depends(get_session)) -> StrategyBoardRead:
    return get_strategy_board(session)


@router.put("/calendar/strategy", response_model=StrategyBoardRead)
def update_strategy_board_api(
    payload: StrategyBoardUpdate, session: Session = Depends(get_session)
) -> StrategyBoardRead:
    return update_strategy_board(payload, session)


@router.post("/calendar/sync-courses", response_model=SyncCoursesToCalendarResponse)
def sync_courses_to_calendar_api(
    payload: SyncCoursesToCalendarRequest, session: Session = Depends(get_session)
) -> SyncCoursesToCalendarResponse:
    try:
        return sync_courses_to_calendar(payload, session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))



# --- 任务规划工作流 (有绪) 路由 ---

@router.get("/workflows", response_model=list[WorkflowProjectRead])
def list_workflows_api(session: Session = Depends(get_session)) -> list[WorkflowProjectRead]:
    return list_workflows(session)


@router.post("/workflows", response_model=WorkflowProjectRead)
def create_workflow_api(
    payload: WorkflowProjectCreate, session: Session = Depends(get_session)
) -> WorkflowProjectRead:
    return create_workflow(payload, session)


@router.put("/workflows/{flow_id}", response_model=WorkflowProjectRead)
def update_workflow_api(
    flow_id: str, payload: WorkflowProjectUpdate, session: Session = Depends(get_session)
) -> WorkflowProjectRead:
    try:
        return update_workflow(flow_id, payload, session)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/workflows/{flow_id}")
def delete_workflow_api(
    flow_id: str, session: Session = Depends(get_session)
) -> dict[str, bool]:
    try:
        ok = delete_workflow(flow_id, session)
        if not ok:
            raise HTTPException(status_code=404, detail="任务流不存在")
        return {"success": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


