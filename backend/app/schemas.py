from __future__ import annotations

from datetime import datetime, time

from pydantic import BaseModel, Field, model_validator


class ScheduleSlot(BaseModel):
    weekday: int = Field(ge=1, le=7)
    start_time: str = Field(min_length=4, max_length=5)
    end_time: str = Field(min_length=4, max_length=5)

    @model_validator(mode="after")
    def validate_time_range(self) -> "ScheduleSlot":
        try:
            start = time.fromisoformat(self.start_time.zfill(5))
            end = time.fromisoformat(self.end_time.zfill(5))
        except ValueError as exc:
            raise ValueError("上课时间应为 HH:MM 格式") from exc
        if start >= end:
            raise ValueError("结束时间必须晚于开始时间")
        return self


class CourseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    aliases: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    schedule: list[ScheduleSlot] = Field(default_factory=list)
    watch_path: str | None = Field(default=None, max_length=1000)


class CourseUpdate(BaseModel):
    aliases: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    schedule: list[ScheduleSlot] = Field(default_factory=list)


class CourseRead(BaseModel):
    id: int
    name: str
    aliases: list[str]
    keywords: list[str]
    schedule: list[ScheduleSlot]
    watch_path: str | None
    created_at: datetime | None
    material_count: int = 0


class MaterialRead(BaseModel):
    id: int
    course_id: int | None
    lesson_session_id: int | None
    material_type: str
    status: str
    classification_status: str
    classification_confidence: int
    classification_reason: str
    original_filename: str
    stored_path: str
    file_size: int
    extracted_text: str | None = None
    created_at: datetime | None


class JobRead(BaseModel):
    id: int
    material_id: int
    material_filename: str | None = None
    course_name: str | None = None
    job_type: str
    status: str
    stage: str
    progress: int
    message: str
    attempts: int
    created_at: datetime | None


class CustomExportRequest(BaseModel):
    material_ids: list[int] = Field(default_factory=list)
    include_source: bool = True
    include_text: bool = True



class OverviewRead(BaseModel):
    course_count: int
    material_count: int
    pending_jobs: int
    awaiting_recognition: int
    needs_review: int


class ScanResult(BaseModel):
    imported_count: int
    materials: list[MaterialRead]


class LibrarySettingsRead(BaseModel):
    input_directory: str | None
    output_directory: str | None


class LibrarySettingsUpdate(BaseModel):
    input_directory: str | None = Field(default=None, max_length=1000)
    output_directory: str | None = Field(default=None, max_length=1000)


class MaterialAssignment(BaseModel):
    course_id: int


class AdaptersStatusRead(BaseModel):
    asr_provider: str
    vision_provider: str
    asr_ready: bool
    vision_ready: bool


class MaterialUploadResponse(BaseModel):
    conflict: bool
    message: str
    material: MaterialRead | None = None
    existing_material: MaterialRead | None = None


class DuplicateGroupRead(BaseModel):
    sha256: str
    file_size: int
    count: int
    materials: list[MaterialRead]


class DeduplicateResult(BaseModel):
    cleaned_count: int
    retained_count: int
    freed_bytes: int


class BatchDeleteRequest(BaseModel):
    material_ids: list[int]
    delete_files: bool = True


class BatchDeleteResponse(BaseModel):
    deleted_count: int
    deleted_ids: list[int]
    freed_bytes: int


class ResolveDuplicateGroupRequest(BaseModel):
    sha256: str
    keeper_material_id: int


class ResolveDuplicateGroupResponse(BaseModel):
    success: bool
    retained_id: int
    cleaned_ids: list[int]
    freed_bytes: int


class StorageAuditRead(BaseModel):
    total_materials_count: int
    valid_files_count: int = 0
    missing_files_count: int = 0
    orphan_files_count: int = 0
    orphan_files_bytes: int = 0
    orphan_sample_paths: list[str] = Field(default_factory=list)
    total_materials_bytes: int = 0
    orphan_files: list[str] = Field(default_factory=list)
    temp_export_files_bytes: int = 0


class CleanOrphansResponse(BaseModel):
    cleaned_orphans_count: int
    freed_bytes: int
    removed_paths: list[str] = Field(default_factory=list)
    deleted_files_count: int | None = None

    @model_validator(mode="after")
    def populate_compat_fields(self) -> "CleanOrphansResponse":
        if self.deleted_files_count is None:
            self.deleted_files_count = self.cleaned_orphans_count
        return self


# --- 系统设置中心 Schema ---

class AsrSettingsConfig(BaseModel):
    provider: str = Field(default="zhixin_ws", description="zhixin_ws | dashscope | openai | mock")
    # DashScope 配置
    dashscope_api_key: str | None = None
    dashscope_model: str = "qwen-audio-turbo"
    # 本地或兼容 OpenAI Whisper / HTTP 端口配置
    openai_base_url: str = "http://127.0.0.1:8000/v1"
    openai_api_key: str = "local"
    openai_model: str = "whisper-1"
    # Zhixin WS 本地端口配置
    zhixin_ws_url: str = "ws://127.0.0.1:9001/v1/stream"
    zhixin_token: str = "change-me"


class VisionSettingsConfig(BaseModel):
    provider: str = Field(default="dashscope", description="dashscope | openai | mock")
    api_key: str | None = None
    base_url: str | None = None
    model: str = "qwen-vl-max"


class SystemSettingsRead(BaseModel):
    input_directory: str | None = None
    output_directory: str | None = None
    asr: AsrSettingsConfig
    vision: VisionSettingsConfig


class SystemSettingsUpdate(BaseModel):
    input_directory: str | None = None
    output_directory: str | None = None
    asr: AsrSettingsConfig | None = None
    vision: VisionSettingsConfig | None = None


class AsrTestRequest(BaseModel):
    asr: AsrSettingsConfig | None = None


class AsrTestResponse(BaseModel):
    success: bool
    message: str
    latency_ms: int = 0


# --- 日历日程与博弈论 (Tokii) Schema ---

class CalendarWorkspaceRead(BaseModel):
    id: str
    name: str
    color: str
    is_active: bool
    data: dict
    updated_at: datetime | None = None


class CalendarWorkspaceCreate(BaseModel):
    id: str | None = None
    name: str
    color: str = "#627cf7"
    is_active: bool = False
    data: dict = Field(default_factory=dict)


class CalendarWorkspaceUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    is_active: bool | None = None
    data: dict | None = None


class StrategyBoardRead(BaseModel):
    id: str
    items: list[dict]
    updated_at: datetime | None = None


class StrategyBoardUpdate(BaseModel):
    items: list[dict]


class SyncCoursesToCalendarRequest(BaseModel):
    workspace_id: str | None = None
    start_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$", description="开始日期 YYYY-MM-DD")
    end_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$", description="结束日期 YYYY-MM-DD")
    course_ids: list[int] = Field(default_factory=list, description="要同步的课程ID列表，空表示全部课程")
    sync_to_events: bool = Field(default=True, description="是否同步生成具体的日历事件")
    sync_to_tray: bool = Field(default=False, description="是否同步到待安排托盘")
    sync_to_strategy: bool = Field(default=False, description="是否同步到博弈论看板收集箱")


class SyncCoursesToCalendarResponse(BaseModel):
    created_events_count: int
    created_tray_count: int
    created_strategy_count: int
    target_workspace_name: str
    affected_course_names: list[str]



# --- 任务规划工作流 (有绪) Schema ---

class WorkflowProjectRead(BaseModel):
    id: str
    name: str
    description: str
    color: int
    is_active: bool
    viewport: dict | None = None
    nodes: list[dict]
    edges: list[dict]
    updated_at: datetime | None = None


class WorkflowProjectCreate(BaseModel):
    id: str | None = None
    name: str
    description: str = ""
    color: int = 0
    is_active: bool = False
    viewport: dict | None = None
    nodes: list[dict] = Field(default_factory=list)
    edges: list[dict] = Field(default_factory=list)


class WorkflowProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: int | None = None
    is_active: bool | None = None
    viewport: dict | None = None
    nodes: list[dict] | None = None
    edges: list[dict] | None = None



