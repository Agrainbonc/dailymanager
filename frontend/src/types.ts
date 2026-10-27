export interface Course {
  id: number
  name: string
  aliases: string[]
  keywords: string[]
  schedule: ScheduleSlot[]
  watch_path: string | null
  created_at: string | null
  material_count: number
}

export interface ScheduleSlot {
  weekday: number
  start_time: string
  end_time: string
}

export interface Material {
  id: number
  course_id: number | null
  lesson_session_id: number | null
  material_type: 'audio' | 'presentation' | 'other'
  status: string
  classification_status: string
  classification_confidence: number
  classification_reason: string
  original_filename: string
  stored_path: string
  file_size: number
  extracted_text: string | null
  created_at: string | null
}

export interface ProcessingJob {
  id: number
  material_id: number
  job_type: string
  status: string
  stage: string
  progress: number
  message: string
  attempts: number
  created_at: string | null
  material_filename?: string | null
  course_name?: string | null
}

export interface CustomExportPayload {
  material_ids: number[]
  include_source: boolean
  include_text: boolean
}

export interface Overview {
  course_count: number
  material_count: number
  pending_jobs: number
  awaiting_recognition: number
  needs_review: number
}

export interface LibrarySettings {
  input_directory: string | null
  output_directory: string | null
}

export interface TimetableCandidateItem {
  course_name: string
  weekday: number
  start_time: string
  end_time: string
  location: string | null
  confidence: number
  warnings: string[]
}

export interface TimetableRecognitionResult {
  image_hash: string
  filename: string
  candidates: TimetableCandidateItem[]
  warnings: string[]
}

export interface TimetableApplyResult {
  created_courses_count: number
  updated_courses_count: number
  total_slots_count: number
  course_names: string[]
}

export interface AdaptersStatus {
  asr_provider: string
  vision_provider: string
  asr_ready: boolean
  vision_ready: boolean
}

export type SortOrder = 'time_desc' | 'time_asc' | 'name_asc' | 'size_desc'
export type GroupMode = 'date' | 'type' | 'course' | 'none'
export type ViewMode = 'list' | 'grid'
export type TypeFilter = 'all' | 'audio' | 'presentation' | 'needs_review'

export interface MaterialGroup {
  key: string
  title: string
  subtitle?: string
  badge?: string
  materials: Material[]
}

export type SearchScope = 'all' | 'filename' | 'content'

export interface TextHighlightPart {
  text: string
  isHighlight: boolean
}

export interface MatchedSentenceSnippet {
  sentence: string
  charIndex: number
  parts: TextHighlightPart[]
}

export interface MaterialSearchResult {
  material: Material
  matchCount: number
  filenameParts: TextHighlightPart[]
  snippets: MatchedSentenceSnippet[]
}

export interface MaterialUploadResponse {
  conflict: boolean
  message: string
  material: Material | null
  existing_material: Material | null
}

export interface DuplicateGroup {
  sha256: string
  file_size: number
  count: number
  materials: Material[]
}

export interface DeduplicateResult {
  cleaned_count: number
  retained_count: number
  freed_bytes: number
}

export interface BatchDeleteRequest {
  material_ids: number[]
  delete_files?: boolean
}

export interface BatchDeleteResponse {
  deleted_count: number
  deleted_material_ids: number[]
  freed_bytes: number
}

export interface ResolveDuplicateGroupRequest {
  sha256: string
  keeper_id: number
}

export interface ResolveDuplicateGroupResponse {
  sha256: string
  keeper_id: number
  removed_ids: number[]
  freed_bytes: number
}

export interface StorageAudit {
  total_materials_count: number
  valid_files_count: number
  missing_files_count: number
  orphan_files_count: number
  orphan_files_bytes: number
  orphan_sample_paths: string[]
}

export interface CleanOrphansResponse {
  cleaned_orphans_count: number
  freed_bytes: number
  removed_paths: string[]
}

// --- 顶级导航与系统设置中心 ---

export type ActiveTab = 'materials' | 'calendar' | 'workflow' | 'settings'

export interface AsrSettingsConfig {
  provider: 'zhixin_ws' | 'dashscope' | 'openai' | 'mock'
  dashscope_api_key?: string | null
  dashscope_model: string
  openai_base_url: string
  openai_api_key: string
  openai_model: string
  zhixin_ws_url: string
  zhixin_token: string
}

export interface VisionSettingsConfig {
  provider: 'dashscope' | 'openai' | 'mock'
  api_key?: string | null
  base_url?: string | null
  model: string
}

export interface SystemSettings {
  input_directory: string | null
  output_directory: string | null
  asr: AsrSettingsConfig
  vision: VisionSettingsConfig
}

export interface AsrTestResponse {
  success: boolean
  message: string
  latency_ms: number
}

// --- 日历日程与博弈论 (Tokii) ---

export interface CalendarEventItem {
  id: string
  date: string
  title: string
  start: string
  end?: string
  note?: string
}

export interface CalendarMarkItem {
  id: string
  text: string
  color: string
  start: string
  end: string
}

export interface CalendarTaskCard {
  id: string
  text: string
  month?: string
  start?: string
  end?: string
}

export interface CalendarWorkspaceData {
  tray: Array<{ id: string; text: string }>
  events: CalendarEventItem[]
  marks: CalendarMarkItem[]
  global: CalendarTaskCard[]
  monthly: CalendarTaskCard[]
}

export interface CalendarWorkspace {
  id: string
  name: string
  color: string
  is_active: boolean
  data: CalendarWorkspaceData
  updated_at?: string | null
}

export type StrategyZone = 'inbox' | 'must' | 'later' | 'calm'

export interface StrategyItem {
  id: string
  text: string
  zone: StrategyZone
}

export interface StrategyBoard {
  id: string
  items: StrategyItem[]
  updated_at?: string | null
}

// --- 任务规划工作流 (有绪) ---

export type NodeStatus = 'todo' | 'doing' | 'done'
export type NodeOwner = 'self' | 'delegate'
export type PriorityLevel = 'high' | 'medium' | 'low'

export interface WorkflowNode {
  id: string
  title: string
  description: string
  x: number
  y: number
  color: number
  owner: NodeOwner
  assignee: string
  urgency: PriorityLevel
  importance: PriorityLevel
  status: NodeStatus
  start: string
  end: string
}

export interface WorkflowEdge {
  id: string
  from: string
  to: string
  label: string
}

export interface WorkflowViewport {
  x: number
  y: number
  z: number
}

export interface WorkflowProject {
  id: string
  name: string
  description: string
  color: number
  is_active: boolean
  viewport?: WorkflowViewport | null
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  updated_at?: string | null
}


