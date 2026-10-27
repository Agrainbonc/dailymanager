import type {
  AdaptersStatus,
  AsrSettingsConfig,
  AsrTestResponse,
  BatchDeleteRequest,
  BatchDeleteResponse,
  CalendarWorkspace,
  CalendarWorkspaceData,
  CleanOrphansResponse,
  Course,
  CustomExportPayload,
  DeduplicateResult,
  DuplicateGroup,
  LibrarySettings,
  Material,
  MaterialUploadResponse,
  Overview,
  ProcessingJob,
  ResolveDuplicateGroupRequest,
  ResolveDuplicateGroupResponse,
  ScheduleSlot,
  StorageAudit,
  StrategyBoard,
  StrategyItem,
  SyncCoursesPayload,
  SyncCoursesResult,
  SystemSettings,
  TimetableApplyResult,
  TimetableCandidateItem,
  TimetableRecognitionResult,
  WorkflowProject,
} from './types'

const apiBase = import.meta.env.VITE_API_BASE ?? ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '请求失败' }))
    throw new Error(error.detail ?? '请求失败')
  }
  return response.json() as Promise<T>
}

export const api = {
  overview: () => request<Overview>('/api/overview'),
  courses: () => request<Course[]>('/api/courses'),
  createCourse: (payload: { name: string; aliases: string[]; keywords: string[]; schedule: ScheduleSlot[]; watch_path: string | null }) =>
    request<Course>('/api/courses', { method: 'POST', body: JSON.stringify(payload) }),
  updateCourse: (courseId: number, payload: { aliases: string[]; keywords: string[]; schedule: ScheduleSlot[] }) =>
    request<Course>(`/api/courses/${courseId}`, { method: 'PUT', body: JSON.stringify(payload) }),
  courseExportUrl: (courseId: number, exportKind: 'source' | 'text') =>
    `${apiBase}/api/courses/${courseId}/export/${exportKind}`,
  customCourseExport: async (courseId: number, payload: CustomExportPayload, defaultFilename = '课程资料导出.zip') => {
    const response = await fetch(`${apiBase}/api/courses/${courseId}/export/custom`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: '导出失败' }))
      throw new Error(error.detail ?? '导出失败')
    }
    const blob = await response.blob()
    const contentDisposition = response.headers.get('content-disposition')
    let filename = defaultFilename
    if (contentDisposition) {
      const match = /filename\*?=(?:UTF-8'')?([^;]+)/i.exec(contentDisposition)
      if (match && match[1]) {
        filename = decodeURIComponent(match[1].replace(/["']/g, '').trim())
      }
    }
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  },
  librarySettings: () => request<LibrarySettings>('/api/library/settings'),
  saveLibrarySettings: (payload: LibrarySettings) =>
    request<LibrarySettings>('/api/library/settings', { method: 'PUT', body: JSON.stringify(payload) }),
  scanInputDirectory: () => request('/api/library/scan', { method: 'POST' }),
  scanCourse: (courseId: number) => request(`/api/courses/${courseId}/scan`, { method: 'POST' }),
  materials: (courseId?: number, q?: string) => {
    const params = new URLSearchParams()
    if (courseId !== undefined && courseId !== null) params.set('course_id', String(courseId))
    if (q && q.trim()) params.set('q', q.trim())
    const qs = params.toString()
    return request<Material[]>(`/api/materials${qs ? `?${qs}` : ''}`)
  },

  reviewMaterials: () => request<Material[]>('/api/materials?review_needed=true'),
  assignMaterial: (materialId: number, courseId: number) =>
    request<Material>(`/api/materials/${materialId}/assign`, { method: 'POST', body: JSON.stringify({ course_id: courseId }) }),
  jobs: (courseId?: number) => request<ProcessingJob[]>(`/api/jobs${courseId ? `?course_id=${courseId}` : ''}`),
  recoverJobs: () => request<{ recovered_count: number }>('/api/jobs/recover', { method: 'POST' }),
  retryJob: (jobId: number) => request<ProcessingJob>(`/api/jobs/${jobId}/retry`, { method: 'POST' }),
  adaptersStatus: () => request<AdaptersStatus>('/api/adapters/status'),
  uploadMaterial: async (file: File, courseId?: number, forceKeep = false): Promise<MaterialUploadResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    const params = new URLSearchParams()
    if (courseId !== undefined && courseId !== null) params.append('course_id', courseId.toString())
    if (forceKeep) params.append('force_keep', 'true')
    const query = params.toString() ? `?${params.toString()}` : ''

    const response = await fetch(`${apiBase}/api/materials/upload${query}`, {
      method: 'POST',
      body: formData,
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: '上传资料失败' }))
      throw new Error(error.detail ?? '上传资料失败')
    }
    return response.json() as Promise<MaterialUploadResponse>
  },
  duplicateMaterials: () => request<DuplicateGroup[]>('/api/materials/duplicates'),
  deduplicateMaterials: () => request<DeduplicateResult>('/api/materials/deduplicate', { method: 'POST' }),
  triggerTranscribe: (materialId: number) =>
    request<ProcessingJob>(`/api/materials/${materialId}/transcribe`, { method: 'POST' }),
  recognizeTimetable: async (file: File): Promise<TimetableRecognitionResult> => {
    const formData = new FormData()
    formData.append('file', file)
    const response = await fetch(`${apiBase}/api/timetable/recognize`, {
      method: 'POST',
      body: formData,
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: '识别课表截图失败' }))
      throw new Error(error.detail ?? '识别课表截图失败')
    }
    return response.json() as Promise<TimetableRecognitionResult>
  },
  applyTimetable: (items: TimetableCandidateItem[]) =>
    request<TimetableApplyResult>('/api/timetable/apply', {
      method: 'POST',
      body: JSON.stringify({ items }),
    }),
  materialFileUrl: (materialId: number, download = false) =>
    `${apiBase}/api/materials/${materialId}/file${download ? '?download=true' : ''}`,
  batchAssignMaterials: async (materialIds: number[], courseId: number) => {
    return Promise.all(
      materialIds.map((id) =>
        request<Material>(`/api/materials/${id}/assign`, {
          method: 'POST',
          body: JSON.stringify({ course_id: courseId }),
        })
      )
    )
  },
  deleteMaterial: (materialId: number, deleteFile = true) =>
    request<{ message: string; material_id: number; file_deleted: boolean }>(
      `/api/materials/${materialId}?delete_file=${deleteFile}`,
      { method: 'DELETE' }
    ),
  batchDeleteMaterials: (payload: BatchDeleteRequest) =>
    request<BatchDeleteResponse>('/api/materials/batch-delete', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  resolveDuplicateGroup: (payload: ResolveDuplicateGroupRequest) =>
    request<ResolveDuplicateGroupResponse>('/api/materials/duplicates/resolve-group', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  storageAudit: () => request<StorageAudit>('/api/system/storage/audit'),
  cleanOrphans: () => request<CleanOrphansResponse>('/api/system/storage/clean-orphans', { method: 'POST' }),

  // --- 系统设置中心 ---
  getSystemSettings: () => request<SystemSettings>('/api/system/settings'),
  saveSystemSettings: (payload: Partial<SystemSettings>) =>
    request<SystemSettings>('/api/system/settings', { method: 'PUT', body: JSON.stringify(payload) }),
  testAsrConnection: (asrConfig?: AsrSettingsConfig) =>
    request<AsrTestResponse>('/api/system/settings/asr/test', {
      method: 'POST',
      body: JSON.stringify({ asr: asrConfig }),
    }),

  // --- 日历日程与博弈论 (Tokii) ---
  calendarWorkspaces: () => request<CalendarWorkspace[]>('/api/calendar/workspaces'),
  createCalendarWorkspace: (payload: { name: string; color?: string; is_active?: boolean; data?: CalendarWorkspaceData }) =>
    request<CalendarWorkspace>('/api/calendar/workspaces', { method: 'POST', body: JSON.stringify(payload) }),
  updateCalendarWorkspace: (workspaceId: string, payload: Partial<CalendarWorkspace>) =>
    request<CalendarWorkspace>(`/api/calendar/workspaces/${workspaceId}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteCalendarWorkspace: (workspaceId: string) =>
    request<{ success: boolean }>(`/api/calendar/workspaces/${workspaceId}`, { method: 'DELETE' }),

  getStrategyBoard: () => request<StrategyBoard>('/api/calendar/strategy'),
  saveStrategyBoard: (items: StrategyItem[]) =>
    request<StrategyBoard>('/api/calendar/strategy', { method: 'PUT', body: JSON.stringify({ items }) }),
  syncCoursesToCalendar: (payload: SyncCoursesPayload) =>
    request<SyncCoursesResult>('/api/calendar/sync-courses', { method: 'POST', body: JSON.stringify(payload) }),


  // --- 任务规划工作流 (有绪) ---
  workflows: () => request<WorkflowProject[]>('/api/workflows'),
  createWorkflow: (payload: Partial<WorkflowProject>) =>
    request<WorkflowProject>('/api/workflows', { method: 'POST', body: JSON.stringify(payload) }),
  updateWorkflow: (flowId: string, payload: Partial<WorkflowProject>) =>
    request<WorkflowProject>(`/api/workflows/${flowId}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteWorkflow: (flowId: string) =>
    request<{ success: boolean }>(`/api/workflows/${flowId}`, { method: 'DELETE' }),
}

