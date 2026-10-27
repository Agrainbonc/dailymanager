<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  ArrowUpDown,
  AudioLines,
  BookOpenText,
  Calendar,
  CalendarDays,
  Check,
  CheckCircle2,
  CheckSquare,
  ChevronDown,
  ChevronUp,
  CircleAlert,
  Clock,
  Copy,
  CornerDownRight,
  Cpu,
  Download,
  Eye,
  FileSearch,
  FileStack,
  FileText,
  Filter,
  FolderPlus,
  HardDrive,
  Highlighter,
  Inbox,
  Layers,
  LayoutGrid,
  LayoutList,
  LoaderCircle,
  PackageCheck,
  Pause,
  Pencil,
  Play,
  Plus,
  Presentation,
  RefreshCw,
  ScanSearch,
  Search,
  Settings2,
  SlidersHorizontal,
  Sparkles,
  Square,
  Target,
  Trash2,
  Upload,
  Volume2,
  X,
} from '@lucide/vue'
import { api } from '../api'
import type {
  AdaptersStatus,
  Course,
  DuplicateGroup,
  GroupMode,
  LibrarySettings,
  MatchedSentenceSnippet,
  Material,
  MaterialGroup,
  MaterialSearchResult,
  Overview,
  ProcessingJob,
  ScheduleSlot,
  SearchScope,
  SortOrder,
  StorageAudit,
  TextHighlightPart,
  TimetableCandidateItem,
  TypeFilter,
  ViewMode,
} from '../types'

// 基础业务数据
const courses = ref<Course[]>([])
const materials = ref<Material[]>([])
const jobs = ref<ProcessingJob[]>([])
const overview = ref<Overview>({
  course_count: 0,
  material_count: 0,
  pending_jobs: 0,
  awaiting_recognition: 0,
  needs_review: 0,
})
const settings = ref<LibrarySettings>({ input_directory: null, output_directory: null })
const adapters = ref<AdaptersStatus>({
  asr_provider: 'mock_asr',
  vision_provider: 'mock_vision',
  asr_ready: true,
  vision_ready: true,
})
const selectedCourseId = ref<number | null>(null)
const loading = ref(true)
const scanning = ref(false)
const savingSettings = ref(false)
const savingCourse = ref(false)
const errorMessage = ref('')
const successMessage = ref('')

// 排布分类、排序与视图控制
const searchQuery = ref('')
const searchScope = ref<SearchScope>('all')
const expandedSnippetsMap = ref<Record<number, boolean>>({})
const activeMatchNavIndex = ref(0)
const detailTextContainerRef = ref<HTMLElement | null>(null)
const typeFilter = ref<TypeFilter>('all')
const sortOrder = ref<SortOrder>('time_desc')
const groupMode = ref<GroupMode>('date')
const viewMode = ref<ViewMode>('list')

// 多选与批量操作
const selectedMaterialIds = ref<number[]>([])
const batchAssignCourseId = ref<number | null>(null)
const batchOperating = ref(false)

// 音频试听播放
const activeAudioId = ref<number | null>(null)
const audioPlayerRef = ref<HTMLAudioElement | null>(null)
const isAudioPlaying = ref(false)

// 任务队列面板折叠状态
const isJobsPanelCollapsed = ref(false)

// 弹窗引用
const courseDialog = ref<HTMLDialogElement | null>(null)
const settingsDialog = ref<HTMLDialogElement | null>(null)
const timetableDialog = ref<HTMLDialogElement | null>(null)
const materialDialog = ref<HTMLDialogElement | null>(null)
const customExportDialog = ref<HTMLDialogElement | null>(null)

// 课程表单状态
const courseForm = ref({ name: '', aliases: '', keywords: '', schedule: '' })
const settingsForm = ref({ inputDirectory: '' })
const editingCourseId = ref<number | null>(null)

// 课表识别状态
const recognizingTimetable = ref(false)
const applyingTimetable = ref(false)
const timetableCandidates = ref<TimetableCandidateItem[]>([])
const timetableWarnings = ref<string[]>([])
const timetableFileInput = ref<HTMLInputElement | null>(null)

// 选中的资料详情
const viewingMaterial = ref<Material | null>(null)
const triggeringTranscribe = ref(false)
const copySuccess = ref(false)

// 自定义/批量导出状态
const exportIncludeSource = ref(true)
const exportIncludeText = ref(true)
const exporting = ref(false)

// 资料文件上传与冲突排重状态
const uploadingMaterial = ref(false)
const materialFileInput = ref<HTMLInputElement | null>(null)
const conflictDialog = ref<HTMLDialogElement | null>(null)
const conflictExistingMaterial = ref<Material | null>(null)
const pendingUploadFile = ref<File | null>(null)

// 重复文件治理与存储优化状态
const duplicatesDialog = ref<HTMLDialogElement | null>(null)
const duplicateGroups = ref<DuplicateGroup[]>([])
const cleaningDuplicates = ref(false)
const keeperSelectedMap = ref<Record<string, number>>({})
const resolvingGroupHash = ref<string | null>(null)
const duplicateCount = computed(() => duplicateGroups.value.length)
const totalDuplicateFiles = computed(() =>
  duplicateGroups.value.reduce((acc, g) => acc + g.count - 1, 0)
)

// 存储空间审计与孤儿文件清理状态
const storageAuditData = ref<StorageAudit | null>(null)
const auditingStorage = ref(false)
const cleaningOrphans = ref(false)

// 确认删除弹窗状态
const deleteConfirmDialog = ref<HTMLDialogElement | null>(null)
const deleteTarget = ref<{ type: 'single' | 'batch'; material?: Material; ids?: number[] } | null>(null)
const deletePhysicalFiles = ref(true)
const deleting = ref(false)

// 智能自适应轮询定时器
let pollingTimer: number | null = null

const timetableStats = computed(() => {
  const list = timetableCandidates.value
  const uniqueCourses = new Set(list.map((c) => c.course_name.trim()).filter(Boolean))
  return {
    courseCount: uniqueCourses.size,
    slotCount: list.length,
  }
})

function getCourseSlotIndex(candidate: TimetableCandidateItem, index: number): { current: number; total: number } | null {
  const name = candidate.course_name.trim()
  if (!name) return null
  const sameCourses = timetableCandidates.value
    .map((c, i) => ({ name: c.course_name.trim(), index: i }))
    .filter((c) => c.name === name)
  if (sameCourses.length <= 1) return null
  const pos = sameCourses.findIndex((c) => c.index === index)
  return {
    current: pos + 1,
    total: sameCourses.length,
  }
}

const selectedCourse = computed(() => courses.value.find((course) => course.id === selectedCourseId.value) ?? null)
const selectedLabel = computed(() => selectedCourse.value?.name ?? '全部资料')
const activeJobs = computed(() => jobs.value.filter((job) => job.status === 'queued' || job.status === 'running'))
const readyJobs = computed(() => jobs.value.filter((job) => job.status === 'completed').length)

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function formatTime(value: string | null) {
  if (!value) return '刚刚'
  const date = new Date(value)
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function formatDateKey(value: string | null): { key: string; label: string; sublabel: string } {
  if (!value) {
    return { key: 'unknown', label: '未记录时间', sublabel: '' }
  }
  const target = new Date(value)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const targetDay = new Date(target.getFullYear(), target.getMonth(), target.getDate()).getTime()
  const oneDay = 86400000

  const yyyy = target.getFullYear()
  const mm = String(target.getMonth() + 1).padStart(2, '0')
  const dd = String(target.getDate()).padStart(2, '0')
  const isoDate = `${yyyy}-${mm}-${dd}`

  if (targetDay === today) {
    return { key: isoDate, label: '今天', sublabel: isoDate }
  } else if (targetDay === today - oneDay) {
    return { key: isoDate, label: '昨天', sublabel: isoDate }
  } else if (today - targetDay < 7 * oneDay && today > targetDay) {
    const days = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
    return { key: isoDate, label: `本周 ${days[target.getDay()]}`, sublabel: isoDate }
  }
  return { key: isoDate, label: `${yyyy}年${target.getMonth() + 1}月${target.getDate()}日`, sublabel: isoDate }
}

function materialIcon(material: Material) {
  return material.material_type === 'audio' ? AudioLines : Presentation
}

function splitTerms(value: string) {
  return value.split(/[，,]/).map((item) => item.trim()).filter(Boolean)
}

function parseSchedule(value: string): ScheduleSlot[] {
  const weekday = new Map([['一', 1], ['二', 2], ['三', 3], ['四', 4], ['五', 5], ['六', 6], ['日', 7], ['天', 7]])
  const pattern = /(?:周|星期)([一二三四五六日天])\s*([01]?\d:[0-5]\d)\s*[-~至]\s*([01]?\d:[0-5]\d)/g
  const slots: ScheduleSlot[] = []
  for (const match of value.matchAll(pattern)) {
    const day = weekday.get(match[1])
    if (day) slots.push({ weekday: day, start_time: match[2].padStart(5, '0'), end_time: match[3].padStart(5, '0') })
  }
  if (value.trim() && slots.length === 0) {
    throw new Error('课程表格式应为：周一 08:00-10:00；周三 14:00-16:00')
  }
  return slots
}

function formatSchedule(schedule: ScheduleSlot[]) {
  const weekday = ['', '周一', '周二', '周三', '周四', '周五', '周六', '周日']
  return [...schedule]
    .sort((left, right) => left.weekday - right.weekday || left.start_time.localeCompare(right.start_time))
    .map((slot) => `${weekday[slot.weekday]} ${slot.start_time}-${slot.end_time}`)
    .join('；')
}

function classificationLabel(material: Material) {
  if (material.classification_status === 'needs_review') return '待确认课程'
  if (material.classification_status === 'manual_assigned') return '已手动归类'
  return `自动归类 ${material.classification_confidence}%`
}

function getCourseNameById(courseId: number | null | undefined): string {
  if (!courseId) return '未归类 (needs-review)'
  const found = courses.value.find((c) => c.id === courseId)
  return found ? found.name : `课程 #${courseId}`
}

// 安全转义正则表达式元字符
function escapeRegExp(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// 搜索关键词分词（空格分隔）
const searchTokens = computed<string[]>(() => {
  const q = searchQuery.value.trim()
  if (!q) return []
  return q.split(/\s+/).filter(Boolean)
})

// 通用分词高亮切片函数
function splitHighlight(text: string, tokens: string[]): TextHighlightPart[] {
  if (!text) return []
  if (tokens.length === 0) return [{ text, isHighlight: false }]

  try {
    const pattern = new RegExp(`(${tokens.map(escapeRegExp).join('|')})`, 'gi')
    const parts: TextHighlightPart[] = []
    let lastIndex = 0

    for (const match of text.matchAll(pattern)) {
      const matchIndex = match.index ?? 0
      if (matchIndex > lastIndex) {
        parts.push({ text: text.slice(lastIndex, matchIndex), isHighlight: false })
      }
      parts.push({ text: match[0], isHighlight: true })
      lastIndex = matchIndex + match[0].length
    }

    if (lastIndex < text.length) {
      parts.push({ text: text.slice(lastIndex), isHighlight: false })
    }
    return parts
  } catch {
    return [{ text, isHighlight: false }]
  }
}

function getFilenameParts(filename: string): TextHighlightPart[] {
  return splitHighlight(filename, searchTokens.value)
}

// 语义断句与命中字句提取（KWIC 核心算法）
function extractSentenceSnippets(text: string | null, tokens: string[], maxSnippets = 6): MatchedSentenceSnippet[] {
  if (!text || tokens.length === 0) return []

  // 按常见中英文句末标点符号分句（句号、感叹号、问号、分号、换行）
  const sentenceRegex = /[^。！？\n；.!?]+[。！？\n；.!?]?/g
  const snippets: MatchedSentenceSnippet[] = []
  const lowerTokens = tokens.map((t) => t.toLowerCase())

  for (const match of text.matchAll(sentenceRegex)) {
    const rawSentence = match[0].trim()
    const charIndex = match.index ?? 0
    if (!rawSentence) continue

    const lowerSentence = rawSentence.toLowerCase()
    // 检查是否包含任一 token
    const hasMatch = lowerTokens.some((t) => lowerSentence.includes(t))
    if (!hasMatch) continue

    // 智能截取关键词前后上下文窗口（若单句过长，前后保留 35 字）
    let displaySentence = rawSentence
    let firstPos = -1
    for (const t of lowerTokens) {
      const pos = lowerSentence.indexOf(t)
      if (pos >= 0 && (firstPos === -1 || pos < firstPos)) {
        firstPos = pos
      }
    }

    if (rawSentence.length > 90 && firstPos >= 0) {
      const start = Math.max(0, firstPos - 35)
      const end = Math.min(rawSentence.length, firstPos + 45)
      displaySentence = `${start > 0 ? '...' : ''}${rawSentence.slice(start, end)}${end < rawSentence.length ? '...' : ''}`
    }

    snippets.push({
      sentence: displaySentence,
      charIndex,
      parts: splitHighlight(displaySentence, tokens),
    })

    if (snippets.length >= maxSnippets) break
  }

  return snippets
}

// 资料搜索命中分析缓存
const materialSearchMap = computed<Record<number, MaterialSearchResult>>(() => {
  const tokens = searchTokens.value
  const result: Record<number, MaterialSearchResult> = {}

  for (const m of materials.value) {
    if (tokens.length === 0) {
      result[m.id] = {
        material: m,
        matchCount: 0,
        filenameParts: [{ text: m.original_filename, isHighlight: false }],
        snippets: [],
      }
      continue
    }

    const filenameParts = splitHighlight(m.original_filename, tokens)
    const filenameMatchCount = filenameParts.filter((p) => p.isHighlight).length
    const snippets = extractSentenceSnippets(m.extracted_text, tokens)

    // 正文匹配总频次
    let textMatchCount = 0
    if (m.extracted_text) {
      const lower = m.extracted_text.toLowerCase()
      for (const t of tokens) {
        let pos = 0
        const lowerT = t.toLowerCase()
        while ((pos = lower.indexOf(lowerT, pos)) !== -1) {
          textMatchCount++
          pos += lowerT.length
        }
      }
    }

    result[m.id] = {
      material: m,
      matchCount: filenameMatchCount + textMatchCount,
      filenameParts,
      snippets,
    }
  }

  return result
})

function searchAnalysis(materialId: number): MaterialSearchResult {
  return materialSearchMap.value[materialId] ?? {
    material: {} as Material,
    matchCount: 0,
    filenameParts: [],
    snippets: [],
  }
}

// 核心排序与分类排布逻辑
const filteredAndSortedMaterials = computed(() => {
  let list = [...materials.value]

  // 1. 结构化搜索关键词过滤（多词 AND 逻辑与范围控制）
  if (searchTokens.value.length > 0) {
    const tokens = searchTokens.value.map((t) => t.toLowerCase())
    list = list.filter((m) => {
      const filename = m.original_filename.toLowerCase()
      const text = (m.extracted_text || '').toLowerCase()
      const reason = (m.classification_reason || '').toLowerCase()

      if (searchScope.value === 'filename') {
        return tokens.every((t) => filename.includes(t))
      }
      if (searchScope.value === 'content') {
        return tokens.every((t) => text.includes(t))
      }
      // all 模式：必须匹配所有 tokens
      return tokens.every((t) => filename.includes(t) || text.includes(t) || reason.includes(t))
    })
  }

  // 2. 类型过滤
  if (typeFilter.value === 'audio') {
    list = list.filter((m) => m.material_type === 'audio')
  } else if (typeFilter.value === 'presentation') {
    list = list.filter((m) => m.material_type === 'presentation')
  } else if (typeFilter.value === 'needs_review') {
    list = list.filter((m) => m.classification_status === 'needs_review')
  }

  // 3. 排序 (时间、名称、大小)
  list.sort((a, b) => {
    if (sortOrder.value === 'time_desc') {
      const timeA = a.created_at ? new Date(a.created_at).getTime() : 0
      const timeB = b.created_at ? new Date(b.created_at).getTime() : 0
      return timeB - timeA || b.id - a.id
    } else if (sortOrder.value === 'time_asc') {
      const timeA = a.created_at ? new Date(a.created_at).getTime() : 0
      const timeB = b.created_at ? new Date(b.created_at).getTime() : 0
      return timeA - timeB || a.id - b.id
    } else if (sortOrder.value === 'name_asc') {
      return a.original_filename.localeCompare(b.original_filename, 'zh-CN')
    } else if (sortOrder.value === 'size_desc') {
      return b.file_size - a.file_size
    }
    return 0
  })

  return list
})


// 多维有序分组结构
const materialGroups = computed<MaterialGroup[]>(() => {
  const list = filteredAndSortedMaterials.value
  if (list.length === 0) return []

  if (groupMode.value === 'none') {
    return [{
      key: 'all',
      title: '全部资料',
      subtitle: `按${getSortLabel(sortOrder.value)}排序`,
      badge: `${list.length} 项`,
      materials: list,
    }]
  }

  if (groupMode.value === 'date') {
    const map = new Map<string, { label: string; sublabel: string; items: Material[] }>()
    for (const item of list) {
      const { key, label, sublabel } = formatDateKey(item.created_at)
      if (!map.has(key)) {
        map.set(key, { label, sublabel, items: [] })
      }
      map.get(key)!.items.push(item)
    }

    return Array.from(map.entries()).map(([key, data]) => {
      const audioCount = data.items.filter((i) => i.material_type === 'audio').length
      const pptCount = data.items.filter((i) => i.material_type === 'presentation').length
      const summaryText = [
        audioCount > 0 ? `${audioCount} 录音` : '',
        pptCount > 0 ? `${pptCount} 课件` : '',
      ].filter(Boolean).join(' · ') || `${data.items.length} 文件`

      return {
        key,
        title: data.label,
        subtitle: data.sublabel,
        badge: summaryText,
        materials: data.items,
      }
    })
  }

  if (groupMode.value === 'type') {
    const audios = list.filter((m) => m.material_type === 'audio')
    const ppts = list.filter((m) => m.material_type === 'presentation')
    const others = list.filter((m) => m.material_type !== 'audio' && m.material_type !== 'presentation')
    const groups: MaterialGroup[] = []

    if (audios.length > 0) {
      groups.push({
        key: 'audio',
        title: '课堂录音 (Audio)',
        subtitle: '包含语音转写与要点提取',
        badge: `${audios.length} 节录音`,
        materials: audios,
      })
    }
    if (ppts.length > 0) {
      groups.push({
        key: 'presentation',
        title: '课件与演示文稿 (Slides)',
        subtitle: '包含幻灯片大纲与页面文本',
        badge: `${ppts.length} 份课件`,
        materials: ppts,
      })
    }
    if (others.length > 0) {
      groups.push({
        key: 'other',
        title: '其他资料',
        subtitle: '通用课堂材料',
        badge: `${others.length} 项`,
        materials: others,
      })
    }
    return groups
  }

  if (groupMode.value === 'course') {
    const map = new Map<number | 'unassigned', { name: string; schedule: string; items: Material[] }>()
    for (const item of list) {
      const key = item.course_id ?? 'unassigned'
      if (!map.has(key)) {
        const c = typeof key === 'number' ? courses.value.find((c) => c.id === key) : null
        map.set(key, {
          name: c ? c.name : '待确认归类资料',
          schedule: c ? formatSchedule(c.schedule) : '尚未指派课程',
          items: [],
        })
      }
      map.get(key)!.items.push(item)
    }

    return Array.from(map.entries()).map(([key, data]) => ({
      key: String(key),
      title: data.name,
      subtitle: data.schedule,
      badge: `${data.items.length} 项资料`,
      materials: data.items,
    }))
  }

  return []
})

function getSortLabel(order: SortOrder) {
  switch (order) {
    case 'time_desc': return '最新优先'
    case 'time_asc': return '时间顺序（从早到晚）'
    case 'name_asc': return '名称 A-Z'
    case 'size_desc': return '大小降序'
  }
}

// 多选选择与批量控制
const isAllSelected = computed(() => {
  if (filteredAndSortedMaterials.value.length === 0) return false
  return filteredAndSortedMaterials.value.every((m) => selectedMaterialIds.value.includes(m.id))
})

function toggleSelectAll() {
  if (isAllSelected.value) {
    selectedMaterialIds.value = []
  } else {
    selectedMaterialIds.value = filteredAndSortedMaterials.value.map((m) => m.id)
  }
}

function toggleSelectMaterial(id: number) {
  const idx = selectedMaterialIds.value.indexOf(id)
  if (idx >= 0) {
    selectedMaterialIds.value.splice(idx, 1)
  } else {
    selectedMaterialIds.value.push(id)
  }
}

function clearSelection() {
  selectedMaterialIds.value = []
}

// 音频试听播放
function togglePlayAudio(material: Material) {
  if (material.material_type !== 'audio') return

  if (activeAudioId.value === material.id) {
    if (audioPlayerRef.value) {
      if (audioPlayerRef.value.paused) {
        audioPlayerRef.value.play()
        isAudioPlaying.value = true
      } else {
        audioPlayerRef.value.pause()
        isAudioPlaying.value = false
      }
    }
  } else {
    activeAudioId.value = material.id
    isAudioPlaying.value = true
    setTimeout(() => {
      if (audioPlayerRef.value) {
        audioPlayerRef.value.src = api.materialFileUrl(material.id)
        audioPlayerRef.value.play().catch(() => {
          isAudioPlaying.value = false
        })
      }
    }, 50)
  }
}

function onAudioEnded() {
  isAudioPlaying.value = false
}

// 单文件下载
function downloadSingleMaterial(material: Material) {
  const link = document.createElement('a')
  link.href = api.materialFileUrl(material.id, true)
  link.download = material.original_filename
  document.body.append(link)
  link.click()
  link.remove()
}

// 复制提取文本
async function copyExtractedText(text: string | null) {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    copySuccess.value = true
    setTimeout(() => { copySuccess.value = false }, 2500)
    successMessage.value = '已将识别文本复制到剪贴板！'
    setTimeout(() => { successMessage.value = '' }, 3000)
  } catch {
    errorMessage.value = '复制失败，请手动选取复制'
  }
}

// 打开自定义导出弹窗
function openCustomExportDialog() {
  exportIncludeSource.value = true
  exportIncludeText.value = true
  customExportDialog.value?.showModal()
}

// 确认自定义导出
async function confirmCustomExport() {
  const courseId = selectedCourseId.value
  if (!courseId) {
    errorMessage.value = '批量导出请先在左侧选择对应课程或使用已选资料'
    return
  }
  const targetIds = selectedMaterialIds.value.length > 0
    ? selectedMaterialIds.value
    : materials.value.map((m) => m.id)

  if (targetIds.length === 0) {
    errorMessage.value = '当前无可导出的资料'
    return
  }

  exporting.value = true
  errorMessage.value = ''
  try {
    const courseName = selectedCourse.value?.name || '课程'
    await api.customCourseExport(
      courseId,
      {
        material_ids: targetIds,
        include_source: exportIncludeSource.value,
        include_text: exportIncludeText.value,
      },
      `${courseName}-精选资料包.zip`
    )
    customExportDialog.value?.close()
    successMessage.value = '导出压缩包已生成并开始下载！'
    setTimeout(() => { successMessage.value = '' }, 4000)
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : '导出失败'
  } finally {
    exporting.value = false
  }
}

// 批量指派课程
async function handleBatchAssignCourse() {
  if (!batchAssignCourseId.value || selectedMaterialIds.value.length === 0) return
  batchOperating.value = true
  errorMessage.value = ''
  try {
    await api.batchAssignMaterials(selectedMaterialIds.value, batchAssignCourseId.value)
    successMessage.value = `成功将 ${selectedMaterialIds.value.length} 项资料重新归类！`
    setTimeout(() => { successMessage.value = '' }, 4000)
    selectedMaterialIds.value = []
    batchAssignCourseId.value = null
    await refresh(false)
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : '批量归类失败'
  } finally {
    batchOperating.value = false
  }
}

// 批量转写
async function handleBatchTranscribe() {
  const audioIds = selectedMaterialIds.value.filter((id) => {
    const m = materials.value.find((item) => item.id === id)
    return m && m.material_type === 'audio'
  })
  if (audioIds.length === 0) {
    errorMessage.value = '所选项目中没有可转写的音频录音'
    return
  }

  batchOperating.value = true
  errorMessage.value = ''
  try {
    await Promise.all(audioIds.map((id) => api.triggerTranscribe(id)))
    successMessage.value = `已为 ${audioIds.length} 个音频提交语音转写任务！`
    setTimeout(() => { successMessage.value = '' }, 4000)
    await refresh(false)
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : '批量派发转写失败'
  } finally {
    batchOperating.value = false
  }
}

// 数据刷新
async function refresh(showLoadingState = true) {
  if (showLoadingState) loading.value = true
  errorMessage.value = ''
  try {
    const id = selectedCourseId.value ?? undefined
    const [nextOverview, nextCourses, nextMaterials, nextJobs, nextSettings, nextAdapters, nextDuplicates] = await Promise.all([
      api.overview(),
      api.courses(),
      api.materials(id),
      api.jobs(id),
      api.librarySettings(),
      api.adaptersStatus().catch(() => ({
        asr_provider: 'mock_asr',
        vision_provider: 'mock_vision',
        asr_ready: true,
        vision_ready: true,
      })),
      api.duplicateMaterials().catch(() => []),
    ])
    overview.value = nextOverview
    courses.value = nextCourses
    materials.value = nextMaterials
    jobs.value = nextJobs
    settings.value = nextSettings
    adapters.value = nextAdapters
    duplicateGroups.value = nextDuplicates

    // 同步更新详情中的数据
    if (viewingMaterial.value) {
      viewingMaterial.value = nextMaterials.find((m) => m.id === viewingMaterial.value?.id) ?? viewingMaterial.value
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '无法连接本地服务'
  } finally {
    if (showLoadingState) loading.value = false
  }
}

// 智能自适应轮询
function setupPolling() {
  if (pollingTimer) clearInterval(pollingTimer)
  const interval = activeJobs.value.length > 0 ? 3000 : 15000
  pollingTimer = window.setInterval(async () => {
    await refresh(false)
    // 任务状态变化后动态调整间隔
    if (activeJobs.value.length > 0 && interval !== 3000) {
      setupPolling()
    } else if (activeJobs.value.length === 0 && interval === 3000) {
      setupPolling()
    }
  }, interval)
}

async function selectCourse(courseId: number | null) {
  selectedCourseId.value = courseId
  selectedMaterialIds.value = []
  activeAudioId.value = null
  if (audioPlayerRef.value) audioPlayerRef.value.pause()
  await refresh(true)
}

function resetCourseDialog() {
  courseForm.value = { name: '', aliases: '', keywords: '', schedule: '' }
  editingCourseId.value = null
}

function openCourseDialog(course?: Course) {
  editingCourseId.value = course?.id ?? null
  courseForm.value = course
    ? {
        name: course.name,
        aliases: course.aliases.join('，'),
        keywords: course.keywords.join('，'),
        schedule: formatSchedule(course.schedule),
      }
    : { name: '', aliases: '', keywords: '', schedule: '' }
  courseDialog.value?.showModal()
}

function openSettingsDialog() {
  settingsForm.value = {
    inputDirectory: settings.value.input_directory ?? '',
  }
  settingsDialog.value?.showModal()
}

function openTimetableDialog() {
  timetableCandidates.value = []
  timetableWarnings.value = []
  recognizingTimetable.value = false
  timetableDialog.value?.showModal()
}

interface DialogHighlightPart {
  text: string
  isHighlight: boolean
  matchIdx?: number
}

const dialogTextParts = computed<DialogHighlightPart[]>(() => {
  const text = viewingMaterial.value?.extracted_text
  const tokens = searchTokens.value
  if (!text) return []
  if (tokens.length === 0) return [{ text, isHighlight: false }]

  try {
    const pattern = new RegExp(`(${tokens.map(escapeRegExp).join('|')})`, 'gi')
    const parts: DialogHighlightPart[] = []
    let lastIndex = 0
    let matchCount = 0

    for (const match of text.matchAll(pattern)) {
      const matchIndex = match.index ?? 0
      if (matchIndex > lastIndex) {
        parts.push({ text: text.slice(lastIndex, matchIndex), isHighlight: false })
      }
      parts.push({ text: match[0], isHighlight: true, matchIdx: matchCount })
      matchCount++
      lastIndex = matchIndex + match[0].length
    }

    if (lastIndex < text.length) {
      parts.push({ text: text.slice(lastIndex), isHighlight: false })
    }
    return parts
  } catch {
    return [{ text, isHighlight: false }]
  }
})

const dialogMatchTotal = computed(() => {
  return dialogTextParts.value.filter((p) => p.isHighlight).length
})

function scrollToActiveMatch() {
  setTimeout(() => {
    const el = document.getElementById(`match-pos-${activeMatchNavIndex.value}`)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, 50)
}

function nextMatch() {
  if (dialogMatchTotal.value === 0) return
  activeMatchNavIndex.value = (activeMatchNavIndex.value + 1) % dialogMatchTotal.value
  scrollToActiveMatch()
}

function prevMatch() {
  if (dialogMatchTotal.value === 0) return
  activeMatchNavIndex.value = (activeMatchNavIndex.value - 1 + dialogMatchTotal.value) % dialogMatchTotal.value
  scrollToActiveMatch()
}

function openMaterialDetail(material: Material, snippetIndex?: number) {
  viewingMaterial.value = material
  activeMatchNavIndex.value = snippetIndex ?? 0
  materialDialog.value?.showModal()
  if (snippetIndex !== undefined) {
    scrollToActiveMatch()
  } else if (dialogMatchTotal.value > 0) {
    activeMatchNavIndex.value = 0
    scrollToActiveMatch()
  }
}


async function triggerAudioTranscribe(materialId: number) {
  triggeringTranscribe.value = true
  errorMessage.value = ''
  try {
    await api.triggerTranscribe(materialId)
    successMessage.value = '已提交语音转写任务！'
    setTimeout(() => { successMessage.value = '' }, 4000)
    await refresh(false)
    if (viewingMaterial.value?.id === materialId) {
      viewingMaterial.value = materials.value.find((m) => m.id === materialId) ?? null
    }
    setupPolling()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '触发转写失败'
  } finally {
    triggeringTranscribe.value = false
  }
}

async function handleRecoverJobs() {
  errorMessage.value = ''
  try {
    const res = await api.recoverJobs()
    if (res.recovered_count > 0) {
      successMessage.value = `已恢复 ${res.recovered_count} 个卡死/中断的任务并重新排队`
    } else {
      successMessage.value = '队列状态健康，未检测到挂起的孤儿任务'
    }
    setTimeout(() => { successMessage.value = '' }, 4000)
    await refresh(false)
    setupPolling()
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : '恢复任务失败'
  }
}

async function handleRetryJob(jobId: number) {
  errorMessage.value = ''
  try {
    await api.retryJob(jobId)
    successMessage.value = `任务 #${jobId} 已重新加入队列`
    setTimeout(() => { successMessage.value = '' }, 4000)
    await refresh(false)
    setupPolling()
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : '重试任务失败'
  }
}

function triggerMaterialUploadDialog() {
  if (materialFileInput.value) {
    materialFileInput.value.value = ''
    materialFileInput.value.click()
  }
}

async function handleMaterialFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  uploadingMaterial.value = true
  errorMessage.value = ''
  try {
    const res = await api.uploadMaterial(file, selectedCourseId.value ?? undefined, false)
    if (res.conflict && res.existing_material) {
      conflictExistingMaterial.value = res.existing_material
      pendingUploadFile.value = file
      conflictDialog.value?.showModal()
    } else {
      successMessage.value = `文件 “${file.name}” 上传成功，已加入工作区！`
      setTimeout(() => { successMessage.value = '' }, 4000)
      await refresh(false)
    }
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : '上传文件失败'
  } finally {
    uploadingMaterial.value = false
  }
}

async function resolveConflict(forceKeep: boolean) {
  conflictDialog.value?.close()
  if (!forceKeep) {
    successMessage.value = '已保留现有文件，未创建重复副本'
    setTimeout(() => { successMessage.value = '' }, 3000)
    conflictExistingMaterial.value = null
    pendingUploadFile.value = null
    return
  }

  if (!pendingUploadFile.value) return
  uploadingMaterial.value = true
  try {
    const res = await api.uploadMaterial(pendingUploadFile.value, selectedCourseId.value ?? undefined, true)
    successMessage.value = `已确认保留副本：“${res.material?.original_filename ?? pendingUploadFile.value.name}”`
    setTimeout(() => { successMessage.value = '' }, 4000)
    await refresh(false)
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : '强制上传副本失败'
  } finally {
    uploadingMaterial.value = false
    conflictExistingMaterial.value = null
    pendingUploadFile.value = null
  }
}

async function openDuplicatesDialog() {
  try {
    duplicateGroups.value = await api.duplicateMaterials()
    duplicatesDialog.value?.showModal()
    handleAuditStorage()
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : '查询重复文件失败'
  }
}

function selectGroupKeeper(sha256: string, materialId: number) {
  keeperSelectedMap.value[sha256] = materialId
}

function getGroupKeeperId(group: DuplicateGroup): number {
  return keeperSelectedMap.value[group.sha256] ?? group.materials[0]?.id
}

async function handleResolveSingleGroup(group: DuplicateGroup) {
  const keeperId = getGroupKeeperId(group)
  resolvingGroupHash.value = group.sha256
  errorMessage.value = ''
  try {
    const res = await api.resolveDuplicateGroup({
      sha256: group.sha256,
      keeper_id: keeperId,
    })
    successMessage.value = `已合并本组重复项，保留主项 #${res.keeper_id}，清理 ${res.removed_ids.length} 个副本，释放空间 ${formatSize(res.freed_bytes)}！`
    setTimeout(() => { successMessage.value = '' }, 4000)
    await refresh(false)
    duplicateGroups.value = await api.duplicateMaterials()
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : '合并单组重复项失败'
  } finally {
    resolvingGroupHash.value = null
  }
}

async function handleDeduplicate() {
  cleaningDuplicates.value = true
  errorMessage.value = ''
  try {
    const res = await api.deduplicateMaterials()
    duplicatesDialog.value?.close()
    successMessage.value = `已清理 ${res.cleaned_count} 个冗余副本，保留 ${res.retained_count} 个主文件，释放空间 ${formatSize(res.freed_bytes)}！`
    setTimeout(() => { successMessage.value = '' }, 5000)
    await refresh(true)
    duplicateGroups.value = await api.duplicateMaterials()
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : '清理重复文件失败'
  } finally {
    cleaningDuplicates.value = false
  }
}

async function handleAuditStorage() {
  auditingStorage.value = true
  errorMessage.value = ''
  try {
    storageAuditData.value = await api.storageAudit()
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : '扫描物理存储失败'
  } finally {
    auditingStorage.value = false
  }
}

async function handleCleanOrphans() {
  cleaningOrphans.value = true
  errorMessage.value = ''
  try {
    const res = await api.cleanOrphans()
    successMessage.value = `已清理 ${res.cleaned_orphans_count} 个孤儿垃圾文件，释放空间 ${formatSize(res.freed_bytes)}！`
    setTimeout(() => { successMessage.value = '' }, 4000)
    storageAuditData.value = await api.storageAudit()
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : '清理孤儿文件失败'
  } finally {
    cleaningOrphans.value = false
  }
}

function promptDeleteSingle(material: Material) {
  deleteTarget.value = { type: 'single', material }
  deletePhysicalFiles.value = true
  deleteConfirmDialog.value?.showModal()
}

function promptBatchDelete() {
  if (selectedMaterialIds.value.length === 0) return
  deleteTarget.value = { type: 'batch', ids: [...selectedMaterialIds.value] }
  deletePhysicalFiles.value = true
  deleteConfirmDialog.value?.showModal()
}

async function confirmExecuteDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  errorMessage.value = ''
  try {
    if (deleteTarget.value.type === 'single' && deleteTarget.value.material) {
      const mat = deleteTarget.value.material
      await api.deleteMaterial(mat.id, deletePhysicalFiles.value)
      if (viewingMaterial.value?.id === mat.id) {
        materialDialog.value?.close()
        viewingMaterial.value = null
      }
      const sIdx = selectedMaterialIds.value.indexOf(mat.id)
      if (sIdx >= 0) selectedMaterialIds.value.splice(sIdx, 1)

      successMessage.value = `已删除资料：“${mat.original_filename}”`
    } else if (deleteTarget.value.type === 'batch' && deleteTarget.value.ids) {
      const ids = deleteTarget.value.ids
      const res = await api.batchDeleteMaterials({
        material_ids: ids,
        delete_files: deletePhysicalFiles.value,
      })
      clearSelection()
      if (viewingMaterial.value && ids.includes(viewingMaterial.value.id)) {
        materialDialog.value?.close()
        viewingMaterial.value = null
      }
      successMessage.value = `已批量删除 ${res.deleted_count} 项资料，释放空间 ${formatSize(res.freed_bytes)}！`
    }
    deleteConfirmDialog.value?.close()
    setTimeout(() => { successMessage.value = '' }, 4000)
    await refresh(true)
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : '删除操作失败'
  } finally {
    deleting.value = false
    deleteTarget.value = null
  }
}

async function handleTimetableFileUpload(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  recognizingTimetable.value = true
  errorMessage.value = ''
  try {
    const result = await api.recognizeTimetable(file)
    timetableCandidates.value = result.candidates
    timetableWarnings.value = result.warnings
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '识别课表失败'
  } finally {
    recognizingTimetable.value = false
  }
}

function addTimetableRow() {
  timetableCandidates.value.push({
    course_name: '',
    weekday: 1,
    start_time: '08:00',
    end_time: '09:40',
    location: '',
    confidence: 100,
    warnings: [],
  })
}

function removeTimetableRow(index: number) {
  timetableCandidates.value.splice(index, 1)
}

async function confirmApplyTimetable() {
  if (timetableCandidates.value.length === 0) return
  applyingTimetable.value = true
  errorMessage.value = ''
  try {
    const res = await api.applyTimetable(timetableCandidates.value)
    timetableDialog.value?.close()
    successMessage.value = `课表导入成功！新建 ${res.created_courses_count} 门课程，更新 ${res.updated_courses_count} 门课程（共 ${res.total_slots_count} 个时段）。`
    setTimeout(() => { successMessage.value = '' }, 5000)
    await refresh()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '课表应用失败'
  } finally {
    applyingTimetable.value = false
  }
}

async function saveCourse() {
  if (!courseForm.value.name.trim()) return
  savingCourse.value = true
  errorMessage.value = ''
  try {
    const payload = {
      aliases: splitTerms(courseForm.value.aliases),
      keywords: splitTerms(courseForm.value.keywords),
      schedule: parseSchedule(courseForm.value.schedule),
    }
    const course = editingCourseId.value === null
      ? await api.createCourse({
          name: courseForm.value.name.trim(),
          watch_path: null,
          ...payload,
        })
      : await api.updateCourse(editingCourseId.value, payload)
    courseDialog.value?.close()
    selectedCourseId.value = course.id
    await refresh()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '保存课程失败'
  } finally {
    savingCourse.value = false
  }
}

async function saveSettings() {
  savingSettings.value = true
  errorMessage.value = ''
  try {
    settings.value = await api.saveLibrarySettings({
      input_directory: settingsForm.value.inputDirectory.trim() || null,
      output_directory: null,
    })
    settingsDialog.value?.close()
    await refresh()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '保存资料库设置失败'
  } finally {
    savingSettings.value = false
  }
}

async function scanInputDirectory() {
  scanning.value = true
  errorMessage.value = ''
  try {
    await api.scanInputDirectory()
    await refresh()
    setupPolling()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '扫描统一投递目录失败'
  } finally {
    scanning.value = false
  }
}

async function assignMaterial(material: Material, event: Event) {
  const courseId = Number((event.target as HTMLSelectElement).value)
  if (!courseId) return
  errorMessage.value = ''
  try {
    await api.assignMaterial(material.id, courseId)
    await refresh(false)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '重新归类失败'
  }
}

onMounted(async () => {
  await refresh(true)
  setupPolling()
})

onUnmounted(() => {
  if (pollingTimer) clearInterval(pollingTimer)
})

defineExpose({
  openTimetableDialog,
})
</script>

<template>
  <main class="app-shell">
    <!-- 侧边导航栏 -->
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">
          <BookOpenText :size="20" />
        </div>
        <div class="brand-text">
          <strong>DailyManager</strong>
          <span>知识与课程资料库</span>
        </div>
      </div>

      <button class="primary-action full-width" type="button" @click="openCourseDialog()">
        <FolderPlus :size="16" aria-hidden="true" />
        新建课程
      </button>

      <nav class="course-nav" aria-label="课程导航">
        <div class="nav-fixed-section">
          <p class="nav-label">资料空间</p>
          <button
            class="course-item"
            :class="{ active: selectedCourseId === null }"
            type="button"
            @click="selectCourse(null)"
          >
            <FileStack :size="16" aria-hidden="true" />
            <span class="course-name">全部资料</span>
            <b class="badge">{{ overview.material_count }}</b>
          </button>

          <p class="nav-label" style="margin-top: 14px">课程列表 ({{ courses.length }})</p>
        </div>
        <div class="course-list-scroll">
          <button
            v-for="course in courses"
            :key="course.id"
            class="course-item"
            :class="{ active: selectedCourseId === course.id }"
            type="button"
            @click="selectCourse(course.id)"
          >
            <BookOpenText :size="16" aria-hidden="true" />
            <span class="course-name" :title="course.name">{{ course.name }}</span>
            <b class="badge">{{ course.material_count }}</b>
          </button>
        </div>
      </nav>

      <button class="settings-link" type="button" @click="openSettingsDialog">
        <Settings2 :size="16" aria-hidden="true" />
        <span>资料库目录设置</span>
      </button>
    </aside>

    <!-- 工作台主体 -->
    <section class="workspace">
      <!-- 顶部工作台状态栏 -->
      <header class="topbar">
        <div class="header-info">
          <div class="breadcrumbs">
            <span>资料工作台</span>
            <span class="separator">/</span>
            <strong class="current-scope">{{ selectedLabel }}</strong>
          </div>
          <h1 class="page-title">{{ selectedLabel }}</h1>
          <div class="course-meta-tags">
            <span v-if="selectedCourse" class="meta-tag schedule-tag">
              <Calendar :size="13" />
              {{ formatSchedule(selectedCourse.schedule) || '尚未配置固定课表' }}
            </span>
            <span class="meta-tag adapter-tag">
              <Cpu :size="13" /> ASR: {{ adapters.asr_provider }}
            </span>
            <span class="meta-tag adapter-tag">
              <Sparkles :size="13" /> Vision: {{ adapters.vision_provider }}
            </span>
            <span v-if="activeJobs.length > 0" class="meta-tag active-job-tag">
              <LoaderCircle class="spinning" :size="13" /> {{ activeJobs.length }} 个任务处理中
            </span>
          </div>
        </div>

        <div class="top-actions">
          <button
            class="secondary-action"
            type="button"
            :disabled="uploadingMaterial"
            @click="triggerMaterialUploadDialog"
          >
            <Upload :size="16" aria-hidden="true" />
            {{ uploadingMaterial ? '上传中...' : '上传资料' }}
          </button>

          <button
            v-if="duplicateCount > 0"
            class="secondary-action warning-btn"
            type="button"
            title="检测到工作区存在重复文件，点击查看并清理"
            @click="openDuplicatesDialog"
          >
            <Copy :size="16" aria-hidden="true" />
            清理重复 ({{ duplicateCount }})
          </button>

          <button class="secondary-action" type="button" @click="openTimetableDialog">
            <CalendarDays :size="16" aria-hidden="true" />
            识别课表
          </button>

          <button
            v-if="selectedCourse"
            class="secondary-action"
            type="button"
            @click="openCustomExportDialog"
          >
            <Download :size="16" aria-hidden="true" />
            自定义导出
          </button>

          <button
            v-if="selectedCourse"
            class="icon-button"
            type="button"
            aria-label="编辑当前课程"
            data-tooltip="编辑课程信息"
            @click="openCourseDialog(selectedCourse)"
          >
            <Pencil :size="16" aria-hidden="true" />
          </button>

          <button
            class="icon-button"
            type="button"
            aria-label="刷新资料库"
            data-tooltip="刷新资料"
            @click="refresh(true)"
          >
            <RefreshCw :size="16" :class="{ spinning: loading }" aria-hidden="true" />
          </button>

          <button
            class="primary-action scan-btn"
            type="button"
            :disabled="scanning || !settings.input_directory"
            @click="scanInputDirectory"
          >
            <ScanSearch :size="16" aria-hidden="true" />
            {{ scanning ? '扫描归档中...' : '扫描投递箱' }}
          </button>
        </div>
      </header>

      <!-- 提示条 -->
      <div v-if="errorMessage" class="feedback-banner error" role="alert">
        <CircleAlert :size="16" aria-hidden="true" />
        <span>{{ errorMessage }}</span>
        <button class="close-banner-btn" type="button" @click="errorMessage = ''">×</button>
      </div>

      <div v-if="successMessage" class="feedback-banner success" role="status">
        <CheckCircle2 :size="16" aria-hidden="true" />
        <span>{{ successMessage }}</span>
        <button class="close-banner-btn" type="button" @click="successMessage = ''">×</button>
      </div>

      <!-- 数据指标卡片 -->
      <section class="summary-grid" aria-label="资料概览指标">
        <article class="summary-card warm">
          <div class="summary-icon"><BookOpenText :size="20" /></div>
          <div class="summary-body">
            <span>课程空间</span>
            <strong>{{ overview.course_count }}</strong>
            <small>已归档的独立课程</small>
          </div>
        </article>
        <article class="summary-card mint">
          <div class="summary-icon"><PackageCheck :size="20" /></div>
          <div class="summary-body">
            <span>资料总项</span>
            <strong>{{ overview.material_count }}</strong>
            <small>{{ settings.input_directory ? '投递箱已激活' : '请先设置投递箱' }}</small>
          </div>
        </article>
        <article class="summary-card blue">
          <div class="summary-icon"><Clock :size="20" /></div>
          <div class="summary-body">
            <span>待确认归类</span>
            <strong>{{ overview.needs_review }}</strong>
            <small>需人工核对指定课程</small>
          </div>
        </article>
      </section>

      <!-- 资料排布控制栏（排序、分组、搜索、视图切换） -->
      <section class="material-controls-card">
        <div class="search-input-wrapper">
          <Search class="search-icon" :size="16" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索资料名称、课件及语音转写文本关键词（支持多词空格）..."
            class="search-input"
          />
          <div class="search-scope-selector">
            <button
              class="scope-btn"
              :class="{ active: searchScope === 'all' }"
              type="button"
              title="在文件名与转写正文中搜索"
              @click="searchScope = 'all'"
            >
              全部
            </button>
            <button
              class="scope-btn"
              :class="{ active: searchScope === 'content' }"
              type="button"
              title="仅在转写文本与课件大纲中搜索知识点"
              @click="searchScope = 'content'"
            >
              仅正文
            </button>
            <button
              class="scope-btn"
              :class="{ active: searchScope === 'filename' }"
              type="button"
              title="仅在文件名中搜索"
              @click="searchScope = 'filename'"
            >
              仅文件名
            </button>
          </div>
          <button v-if="searchQuery" class="clear-search-btn" type="button" title="清空搜索" @click="searchQuery = ''">
            <X :size="14" />
          </button>
        </div>


        <div class="controls-toolbar">
          <!-- 类型筛选胶囊 -->
          <div class="filter-pills" role="radiogroup" aria-label="资料类型过滤">
            <button
              class="filter-pill"
              :class="{ active: typeFilter === 'all' }"
              type="button"
              @click="typeFilter = 'all'"
            >
              全部
            </button>
            <button
              class="filter-pill"
              :class="{ active: typeFilter === 'audio' }"
              type="button"
              @click="typeFilter = 'audio'"
            >
              <AudioLines :size="13" /> 录音音频
            </button>
            <button
              class="filter-pill"
              :class="{ active: typeFilter === 'presentation' }"
              type="button"
              @click="typeFilter = 'presentation'"
            >
              <Presentation :size="13" /> 课件讲义
            </button>
            <button
              class="filter-pill"
              :class="{ active: typeFilter === 'needs_review' }"
              type="button"
              @click="typeFilter = 'needs_review'"
            >
              待确认 ({{ overview.needs_review }})
            </button>
          </div>

          <div class="controls-right-group">
            <!-- 分类排布模式选择 -->
            <label class="control-select-label" title="选择文件排布与组织维度">
              <Layers :size="14" />
              <span>排布分类:</span>
              <select v-model="groupMode" class="control-select">
                <option value="date">按上课时间分组 (推荐)</option>
                <option value="type">按文件类型分组 (录音/课件)</option>
                <option value="course" v-if="selectedCourseId === null">按所属课程分组</option>
                <option value="none">平铺排列 (不分组)</option>
              </select>
            </label>

            <!-- 排序顺序选择 -->
            <label class="control-select-label" title="选择组内文件排序规则">
              <ArrowUpDown :size="14" />
              <span>排序:</span>
              <select v-model="sortOrder" class="control-select">
                <option value="time_desc">最新时间优先</option>
                <option value="time_asc">时间正序 (从早到晚)</option>
                <option value="name_asc">文件名 (A-Z)</option>
                <option value="size_desc">文件大小 (降序)</option>
              </select>
            </label>

            <!-- 视图模式切换 -->
            <div class="view-switch-group">
              <button
                class="view-switch-btn"
                :class="{ active: viewMode === 'list' }"
                type="button"
                title="切换到紧凑列表视图"
                @click="viewMode = 'list'"
              >
                <LayoutList :size="16" />
              </button>
              <button
                class="view-switch-btn"
                :class="{ active: viewMode === 'grid' }"
                type="button"
                title="切换到卡片网格视图"
                @click="viewMode = 'grid'"
              >
                <LayoutGrid :size="16" />
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- 主体内容与右侧处理任务队列分栏 -->
      <section class="content-layout">
        <!-- 核心资料列表/卡片区 -->
        <article class="panel materials-panel">
          <div class="panel-heading">
            <div class="panel-heading-left">
              <button
                class="select-all-btn"
                type="button"
                :title="isAllSelected ? '取消全选' : '选择当前全部资料'"
                @click="toggleSelectAll"
              >
                <component :is="isAllSelected ? CheckSquare : Square" :size="16" />
                <span>{{ isAllSelected ? '取消全选' : '全选' }}</span>
              </button>
              <h2 class="section-title">
                资料库条目
                <span class="count-pill">{{ filteredAndSortedMaterials.length }} 项</span>
              </h2>
            </div>
            <span class="hint-text">
              同一课程文件已按<b>{{ getSortLabel(sortOrder) }}</b>有序排列
            </span>
          </div>

          <!-- 批量操作悬浮条 -->
          <transition name="fade">
            <div v-if="selectedMaterialIds.length > 0" class="batch-action-bar">
              <div class="batch-selected-info">
                <Check :size="16" />
                <span>已选中 <strong>{{ selectedMaterialIds.length }}</strong> 项资料</span>
              </div>
              <div class="batch-actions-btns">
                <button
                  class="batch-btn"
                  type="button"
                  :disabled="batchOperating"
                  @click="openCustomExportDialog"
                >
                  <Download :size="14" />
                  打包导出所选
                </button>
                <button
                  class="batch-btn"
                  type="button"
                  :disabled="batchOperating"
                  @click="handleBatchTranscribe"
                >
                  <AudioLines :size="14" />
                  批量转写音频
                </button>
                <div class="batch-assign-wrapper">
                  <select
                    v-model.number="batchAssignCourseId"
                    class="batch-select"
                    :disabled="batchOperating"
                    @change="handleBatchAssignCourse"
                  >
                    <option :value="null">批量指定到课程...</option>
                    <option v-for="c in courses" :key="c.id" :value="c.id">{{ c.name }}</option>
                  </select>
                </div>
                <button
                  class="batch-btn danger-batch-btn"
                  type="button"
                  :disabled="batchOperating"
                  @click="promptBatchDelete"
                >
                  <Trash2 :size="14" />
                  批量删除 ({{ selectedMaterialIds.length }})
                </button>
                <button class="batch-btn close-selection-btn" type="button" @click="clearSelection">
                  <X :size="14" /> 取消
                </button>
              </div>
            </div>
          </transition>

          <!-- 专属独立滚动容器 -->
          <div class="materials-scroll-wrapper">
            <!-- 加载中状态 -->
            <div v-if="loading" class="empty-state">
            <LoaderCircle class="spinning" :size="24" />
            <span>正在连接并索引本地资料库...</span>
          </div>

          <!-- 空数据状态 -->
          <div v-else-if="filteredAndSortedMaterials.length === 0" class="empty-state">
            <Inbox :size="32" aria-hidden="true" />
            <strong v-if="searchQuery">未找到与“{{ searchQuery }}”相符的资料</strong>
            <strong v-else-if="materials.length === 0">
              {{ settings.input_directory ? '投递箱目录暂无新增文件，请放入后点击“扫描投递箱”' : '请先在左下角设置投递箱目录' }}
            </strong>
            <span v-else>当前分类或过滤条件下无文件</span>
          </div>

          <!-- 按分类分组呈现 -->
          <div v-else class="groups-container">
            <section
              v-for="group in materialGroups"
              :key="group.key"
              class="material-group-section"
            >
              <!-- 分组标题栏 -->
              <header class="group-header">
                <div class="group-title-box">
                  <span class="group-bullet"></span>
                  <h3 class="group-title">{{ group.title }}</h3>
                  <small v-if="group.subtitle" class="group-subtitle">{{ group.subtitle }}</small>
                </div>
                <span v-if="group.badge" class="group-badge">{{ group.badge }}</span>
              </header>

              <!-- 列表模式视图 -->
              <ul v-if="viewMode === 'list'" class="material-list">
                <li
                  v-for="material in group.materials"
                  :key="material.id"
                  class="material-row-item"
                  :class="{ selected: selectedMaterialIds.includes(material.id) }"
                >
                  <!-- 勾选复选框 -->
                  <button
                    class="checkbox-btn"
                    type="button"
                    :aria-label="`选择 ${material.original_filename}`"
                    @click.stop="toggleSelectMaterial(material.id)"
                  >
                    <component
                      :is="selectedMaterialIds.includes(material.id) ? CheckSquare : Square"
                      :size="16"
                    />
                  </button>

                  <!-- 文件类型图标 -->
                  <div
                    class="file-icon-box"
                    :class="material.material_type"
                    @click="openMaterialDetail(material)"
                  >
                    <component :is="materialIcon(material)" :size="20" />
                  </div>

                  <!-- 资料标题与元信息 -->
                  <div class="material-info-col" @click="openMaterialDetail(material)">
                    <div class="filename-row">
                      <strong v-if="searchTokens.length > 0" class="filename-text" :title="material.original_filename">
                        <template v-for="(part, pIdx) in getFilenameParts(material.original_filename)" :key="pIdx">
                          <mark v-if="part.isHighlight" class="search-mark inline-mark">{{ part.text }}</mark>
                          <span v-else>{{ part.text }}</span>
                        </template>
                      </strong>
                      <strong v-else class="filename-text" :title="material.original_filename">
                        {{ material.original_filename }}
                      </strong>
                      <span class="type-tag" :class="material.material_type">
                        {{ material.material_type === 'audio' ? '录音' : '课件' }}
                      </span>
                      <span v-if="searchTokens.length > 0 && searchAnalysis(material.id).matchCount > 0" class="match-count-badge">
                        命中 {{ searchAnalysis(material.id).matchCount }} 处
                      </span>
                    </div>

                    <div class="file-meta-row">
                      <span>{{ formatSize(material.file_size) }}</span>
                      <span class="dot-divider">·</span>
                      <span>{{ formatTime(material.created_at) }}</span>
                      <span v-if="selectedCourseId === null" class="course-pill">
                        {{ getCourseNameById(material.course_id) }}
                      </span>
                      <span
                        v-if="material.extracted_text"
                        class="text-preview-pill"
                        :title="material.extracted_text.slice(0, 80)"
                      >
                        已提取 {{ material.extracted_text.length }} 字
                      </span>
                    </div>

                    <!-- 🎯 命中关键语句摘要（解决用户无法定位是哪一句话的痛点） -->
                    <div
                      v-if="searchTokens.length > 0 && searchAnalysis(material.id).snippets.length > 0"
                      class="matched-snippets-container"
                      @click.stop
                    >
                      <div class="snippets-header">
                        <Target :size="12" />
                        <span>命中的关键语句 (共 {{ searchAnalysis(material.id).snippets.length }} 处，点击直接定位)：</span>
                      </div>
                      <div class="snippets-list">
                        <div
                          v-for="(snippet, sIdx) in (expandedSnippetsMap[material.id] ? searchAnalysis(material.id).snippets : searchAnalysis(material.id).snippets.slice(0, 1))"
                          :key="sIdx"
                          class="snippet-item"
                          title="点击在全文弹窗中精确定位此句"
                          @click="openMaterialDetail(material, sIdx)"
                        >
                          <CornerDownRight class="snippet-icon" :size="13" />
                          <p class="snippet-text">
                            <template v-for="(part, spIdx) in snippet.parts" :key="spIdx">
                              <mark v-if="part.isHighlight" class="search-mark">{{ part.text }}</mark>
                              <span v-else>{{ part.text }}</span>
                            </template>
                          </p>
                        </div>
                      </div>
                      <button
                        v-if="searchAnalysis(material.id).snippets.length > 1"
                        class="toggle-snippets-btn"
                        type="button"
                        @click="expandedSnippetsMap[material.id] = !expandedSnippetsMap[material.id]"
                      >
                        <component :is="expandedSnippetsMap[material.id] ? ChevronUp : ChevronDown" :size="12" />
                        <span>{{ expandedSnippetsMap[material.id] ? '收起摘录' : `展开其余 ${searchAnalysis(material.id).snippets.length - 1} 处命中语句` }}</span>
                      </button>
                    </div>

                    <small
                      v-if="material.classification_status === 'needs_review'"
                      class="review-reason-text"
                    >
                      提示：{{ material.classification_reason }}
                    </small>
                  </div>


                  <!-- 快捷操作栏 -->
                  <div class="material-actions-col">
                    <!-- 音频快捷试听播放按钮 -->
                    <button
                      v-if="material.material_type === 'audio'"
                      class="action-pill-btn"
                      :class="{ playing: activeAudioId === material.id && isAudioPlaying }"
                      type="button"
                      :title="activeAudioId === material.id && isAudioPlaying ? '暂停播放' : '在线试听'"
                      @click.stop="togglePlayAudio(material)"
                    >
                      <component
                        :is="activeAudioId === material.id && isAudioPlaying ? Pause : Play"
                        :size="14"
                      />
                      <span>{{ activeAudioId === material.id && isAudioPlaying ? '暂停' : '试听' }}</span>
                    </button>

                    <!-- 音频转写/重新转写按钮 -->
                    <button
                      v-if="material.material_type === 'audio'"
                      class="action-pill-btn"
                      type="button"
                      :title="material.extracted_text ? '重新启动语音转写' : '开始语音转写'"
                      :disabled="triggeringTranscribe"
                      @click.stop="triggerAudioTranscribe(material.id)"
                    >
                      <AudioLines :size="14" />
                      <span>{{ material.extracted_text ? '重新转写' : '转文字' }}</span>
                    </button>

                    <!-- 单文件下载 -->
                    <button
                      class="action-icon-btn"
                      type="button"
                      title="下载源文件"
                      @click.stop="downloadSingleMaterial(material)"
                    >
                      <Download :size="15" />
                    </button>

                    <!-- 查看详情 -->
                    <button
                      class="action-icon-btn"
                      type="button"
                      title="查看详情与识别大纲"
                      @click.stop="openMaterialDetail(material)"
                    >
                      <Eye :size="15" />
                    </button>

                    <!-- 删除单项资料 -->
                    <button
                      class="action-icon-btn danger-hover"
                      type="button"
                      title="删除此资料"
                      @click.stop="promptDeleteSingle(material)"
                    >
                      <Trash2 :size="15" />
                    </button>

                    <!-- 状态标签与指派课程 -->
                    <div class="status-col">
                      <span class="status-badge" :class="material.classification_status">
                        {{ classificationLabel(material) }}
                      </span>
                      <select
                        v-if="material.classification_status === 'needs_review'"
                        class="quick-assign-select"
                        :aria-label="`为 ${material.original_filename} 指定课程`"
                        @change="assignMaterial(material, $event)"
                      >
                        <option value="">指派课程</option>
                        <option v-for="c in courses" :key="c.id" :value="c.id">{{ c.name }}</option>
                      </select>
                    </div>
                  </div>
                </li>
              </ul>

              <!-- 卡片网格模式视图 -->
              <div v-else class="material-grid">
                <article
                  v-for="material in group.materials"
                  :key="material.id"
                  class="material-card-item"
                  :class="{ selected: selectedMaterialIds.includes(material.id) }"
                  @click="openMaterialDetail(material)"
                >
                  <div class="card-top-row">
                    <button
                      class="checkbox-btn"
                      type="button"
                      @click.stop="toggleSelectMaterial(material.id)"
                    >
                      <component
                        :is="selectedMaterialIds.includes(material.id) ? CheckSquare : Square"
                        :size="16"
                      />
                    </button>
                    <span class="type-tag" :class="material.material_type">
                      {{ material.material_type === 'audio' ? '课堂录音' : '课件幻灯' }}
                    </span>
                    <span class="card-time-text">{{ formatTime(material.created_at) }}</span>
                  </div>

                  <div class="card-icon-area">
                    <component :is="materialIcon(material)" :size="32" />
                  </div>

                  <strong v-if="searchTokens.length > 0" class="card-title" :title="material.original_filename">
                    <template v-for="(part, pIdx) in getFilenameParts(material.original_filename)" :key="pIdx">
                      <mark v-if="part.isHighlight" class="search-mark inline-mark">{{ part.text }}</mark>
                      <span v-else>{{ part.text }}</span>
                    </template>
                  </strong>
                  <strong v-else class="card-title" :title="material.original_filename">
                    {{ material.original_filename }}
                  </strong>

                  <div class="card-meta-line">
                    <span>{{ formatSize(material.file_size) }}</span>
                    <span v-if="selectedCourseId === null" class="course-pill">
                      {{ getCourseNameById(material.course_id) }}
                    </span>
                    <span v-if="searchTokens.length > 0 && searchAnalysis(material.id).matchCount > 0" class="match-count-badge">
                      {{ searchAnalysis(material.id).matchCount }} 处命中
                    </span>
                  </div>

                  <!-- 卡片搜索语句摘要 -->
                  <div
                    v-if="searchTokens.length > 0 && searchAnalysis(material.id).snippets.length > 0"
                    class="card-search-snippet"
                    title="点击在全文弹窗中定位"
                    @click="openMaterialDetail(material, 0)"
                  >
                    <span class="card-snippet-label">🎯 命中语句：</span>
                    <p class="card-text-snippet highlighted">
                      <template v-for="(part, spIdx) in searchAnalysis(material.id).snippets[0].parts" :key="spIdx">
                        <mark v-if="part.isHighlight" class="search-mark">{{ part.text }}</mark>
                        <span v-else>{{ part.text }}</span>
                      </template>
                    </p>
                  </div>
                  <template v-else>
                    <p v-if="material.extracted_text" class="card-text-snippet">
                      {{ material.extracted_text.slice(0, 60) }}...
                    </p>
                    <p v-else class="card-text-snippet empty">
                      {{ material.material_type === 'audio' ? '尚未进行语音转写' : '课件无预览文本' }}
                    </p>
                  </template>


                  <div class="card-bottom-actions" @click.stop>
                    <button
                      v-if="material.material_type === 'audio'"
                      class="card-action-btn"
                      :class="{ playing: activeAudioId === material.id && isAudioPlaying }"
                      type="button"
                      @click="togglePlayAudio(material)"
                    >
                      <component
                        :is="activeAudioId === material.id && isAudioPlaying ? Pause : Play"
                        :size="14"
                      />
                      <span>{{ activeAudioId === material.id && isAudioPlaying ? '暂停' : '试听' }}</span>
                    </button>

                    <button
                      v-if="material.material_type === 'audio'"
                      class="card-action-btn"
                      type="button"
                      @click="triggerAudioTranscribe(material.id)"
                    >
                      <AudioLines :size="14" />
                      <span>转写</span>
                    </button>

                    <button
                      class="card-action-btn"
                      type="button"
                      title="下载"
                      @click="downloadSingleMaterial(material)"
                    >
                      <Download :size="14" />
                    </button>

                    <button
                      class="card-action-btn danger-hover"
                      type="button"
                      title="删除资料"
                      @click="promptDeleteSingle(material)"
                    >
                      <Trash2 :size="14" />
                    </button>
                  </div>
                </article>
              </div>
            </section>
          </div>
          </div>
        </article>

        <!-- 处理任务队列边栏 -->
        <aside class="panel jobs-panel" :class="{ collapsed: isJobsPanelCollapsed }">
          <div class="panel-heading jobs-heading">
            <div>
              <p class="eyebrow">后台队列</p>
              <h2 class="section-title">处理任务</h2>
            </div>
            <div class="jobs-heading-actions">
              <span class="quiet-count">{{ readyJobs }}/{{ jobs.length }} 已完成</span>
              <button
                class="collapse-toggle-btn recover-btn"
                type="button"
                title="检查并恢复卡住或异常中断的任务"
                @click="handleRecoverJobs"
              >
                恢复任务
              </button>
              <button
                class="collapse-toggle-btn"
                type="button"
                :title="isJobsPanelCollapsed ? '展开队列' : '收起队列'"
                @click="isJobsPanelCollapsed = !isJobsPanelCollapsed"
              >
                {{ isJobsPanelCollapsed ? '展开' : '收起' }}
              </button>
            </div>
          </div>

          <div v-show="!isJobsPanelCollapsed" class="jobs-scroll-wrapper">
            <div v-if="jobs.length === 0" class="empty-state compact">
              <CheckCircle2 :size="24" />
              <span>当前队列空闲，所有任务已就绪</span>
            </div>
            <ul v-else class="job-list">
              <li
                v-for="job in jobs.slice(0, 10)"
                :key="job.id"
                class="job-row-item"
                :class="job.status"
              >
                <div class="job-status-dot" :class="job.status"></div>
                <div class="job-details">
                  <div class="job-message-row">
                    <strong class="job-message">{{ job.message }}</strong>
                    <span class="job-percent">{{ job.progress }}%</span>
                  </div>
                  <div class="job-meta-row">
                    <span class="job-filename" v-if="job.material_filename" :title="job.material_filename">
                      {{ job.material_filename }}
                    </span>
                    <span class="job-stage-badge">{{ job.stage }}</span>
                    <button
                      v-if="job.status === 'failed'"
                      class="job-retry-link"
                      type="button"
                      title="重新排队此任务"
                      @click="handleRetryJob(job.id)"
                    >
                      重试
                    </button>
                  </div>
                  <!-- 进度条动效 -->
                  <div v-if="job.status === 'running'" class="job-progress-bar-bg">
                    <div class="job-progress-bar-fill" :style="{ width: `${job.progress}%` }"></div>
                  </div>
                </div>
              </li>
            </ul>
          </div>
        </aside>
      </section>

      <!-- 全局隐藏原生音频播放器，支持内嵌试听 -->
      <audio
        ref="audioPlayerRef"
        style="display: none"
        controls
        @ended="onAudioEnded"
      ></audio>
    </section>
  </main>

  <!-- 自定义与批量导出弹窗 -->
  <dialog ref="customExportDialog" class="course-dialog" @close="exporting = false">
    <div class="dialog-body">
      <div class="dialog-heading">
        <div>
          <p class="eyebrow">资料归档打包</p>
          <h2>自定义导出资料包</h2>
        </div>
        <button class="icon-button" type="button" aria-label="关闭" @click="customExportDialog?.close()">×</button>
      </div>

      <p class="dialog-desc">
        为您选中的资料生成整理对齐的 ZIP 压缩包，支持多时段录音、课件与对应 ASR 字幕大纲笔记一键导出。
      </p>

      <div class="export-options-box">
        <label class="checkbox-label">
          <input v-model="exportIncludeSource" type="checkbox" />
          <div>
            <strong>包含原始课件与录音文件 (source/)</strong>
            <small>将原始的 PPTX、PDF、MP3/M4A 完整打包</small>
          </div>
        </label>

        <label class="checkbox-label">
          <input v-model="exportIncludeText" type="checkbox" />
          <div>
            <strong>包含识别转写大纲与文本 (texts/)</strong>
            <small>将 ASR 录音文字与 PPT 提取文本生成 Markdown 笔记</small>
          </div>
        </label>
      </div>

      <div class="dialog-actions">
        <button class="secondary-action" type="button" @click="customExportDialog?.close()">取消</button>
        <button
          class="primary-action"
          type="button"
          :disabled="exporting || (!exportIncludeSource && !exportIncludeText)"
          @click="confirmCustomExport"
        >
          <Download :size="16" />
          {{ exporting ? '压缩打包中...' : '生成并下载 ZIP' }}
        </button>
      </div>
    </div>
  </dialog>

  <!-- 资料库设置弹窗 -->
  <dialog ref="settingsDialog" class="course-dialog" @close="settingsForm = { inputDirectory: '' }">
    <form method="dialog" @submit.prevent="saveSettings">
      <div class="dialog-heading">
        <div>
          <p class="eyebrow">本地文件监听与投递</p>
          <h2>资料库设置</h2>
        </div>
        <button class="icon-button" type="button" aria-label="关闭" @click="settingsDialog?.close()">×</button>
      </div>
      <label>
        统一投递箱目录 (绝对路径)
        <input v-model="settingsForm.inputDirectory" placeholder="例如：D:\课程资料\投递箱" />
        <span class="form-note">日常课后录音与课件拖入此目录后，点击工作台“扫描投递箱”即可自动分类归档</span>
      </label>
      <div class="dialog-actions">
        <button class="secondary-action" type="button" @click="settingsDialog?.close()">取消</button>
        <button class="primary-action" type="submit" :disabled="savingSettings">
          <Settings2 :size="16" aria-hidden="true" />
          {{ savingSettings ? '保存中...' : '保存设置' }}
        </button>
      </div>
    </form>
  </dialog>

  <!-- 课程维护弹窗 -->
  <dialog ref="courseDialog" class="course-dialog" @close="resetCourseDialog">
    <form method="dialog" @submit.prevent="saveCourse">
      <div class="dialog-heading">
        <div>
          <p class="eyebrow">课程空间管理</p>
          <h2>{{ editingCourseId === null ? '新建课程' : '编辑课程' }}</h2>
        </div>
        <button class="icon-button" type="button" aria-label="关闭" @click="courseDialog?.close()">×</button>
      </div>
      <label>
        课程名称
        <input v-model="courseForm.name" autofocus maxlength="120" placeholder="例如：高等数学" :disabled="editingCourseId !== null" required />
      </label>
      <label>
        文件名匹配别名 (逗号分隔)
        <input v-model="courseForm.aliases" placeholder="例如：高数，Calculus，微积分" />
      </label>
      <label>
        课程主题关键词 (逗号分隔)
        <input v-model="courseForm.keywords" placeholder="例如：极限，微分，积分，泰勒展开" />
      </label>
      <label>
        固定排课时间
        <input v-model="courseForm.schedule" placeholder="例如：周一 08:00-10:00；周三 14:00-16:00" />
        <span class="form-note">支持多时段排课，录音文件若落在此时段内将自动高置信度归类</span>
      </label>
      <div class="dialog-actions">
        <button class="secondary-action" type="button" @click="courseDialog?.close()">取消</button>
        <button class="primary-action" type="submit" :disabled="savingCourse">
          <FolderPlus :size="16" aria-hidden="true" />
          {{ savingCourse ? '保存中...' : editingCourseId === null ? '创建课程' : '更新课程' }}
        </button>
      </div>
    </form>
  </dialog>

  <!-- 课表截图识别与确认弹窗 -->
  <dialog ref="timetableDialog" class="course-dialog wide-dialog">
    <div class="dialog-body">
      <div class="dialog-heading">
        <div>
          <p class="eyebrow">多模态视觉理解</p>
          <h2>导入课表截图</h2>
        </div>
        <button class="icon-button" type="button" aria-label="关闭" @click="timetableDialog?.close()">×</button>
      </div>

      <div class="upload-dropzone" @click="timetableFileInput?.click()">
        <Upload :size="32" aria-hidden="true" />
        <strong>点击或拖拽上传课表截图</strong>
        <span class="quiet-count">支持教务系统网页截图、教务 App 截图（PNG, JPG, WebP 格式）</span>
        <input
          ref="timetableFileInput"
          type="file"
          accept="image/*"
          style="display: none"
          @change="handleTimetableFileUpload"
        />
      </div>

      <div v-if="recognizingTimetable" class="empty-state">
        <LoaderCircle class="spinning" :size="32" />
        <span>多模态视觉模型正在解析课表结构，请稍候...</span>
      </div>

      <div v-else-if="timetableCandidates.length > 0">
        <div class="timetable-summary-bar">
          <div class="timetable-stat-pill">
            <span>识别出课程</span>
            <strong>{{ timetableStats.courseCount }}</strong> 门
          </div>
          <div class="timetable-stat-pill">
            <span>总排课时段</span>
            <strong>{{ timetableStats.slotCount }}</strong> 节
          </div>
          <span class="quiet-count" style="margin-left: auto">
            已支持同门课程多个时段并按时间排序，导入时将合并归类
          </span>
        </div>

        <p v-if="timetableWarnings.length > 0" class="feedback-banner error">
          <CircleAlert :size="16" />
          {{ timetableWarnings.join('；') }}
        </p>

        <table class="timetable-preview-table">
          <thead>
            <tr>
              <th style="width: 25%">课程名称</th>
              <th style="width: 14%">星期</th>
              <th style="width: 15%">开始时间</th>
              <th style="width: 15%">结束时间</th>
              <th style="width: 20%">教室地点</th>
              <th style="width: 6%">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(cand, idx) in timetableCandidates" :key="idx">
              <td>
                <div class="course-input-wrapper">
                  <input v-model="cand.course_name" placeholder="课程名称" required />
                  <span v-if="getCourseSlotIndex(cand, idx)" class="multi-slot-badge">
                    多时段 (第 {{ getCourseSlotIndex(cand, idx)!.current }}/{{ getCourseSlotIndex(cand, idx)!.total }} 节)
                  </span>
                  <span v-if="cand.warnings.length > 0" class="warning-badge">{{ cand.warnings.join('；') }}</span>
                </div>
              </td>
              <td>
                <select v-model.number="cand.weekday">
                  <option :value="1">周一</option>
                  <option :value="2">周二</option>
                  <option :value="3">周三</option>
                  <option :value="4">周四</option>
                  <option :value="5">周五</option>
                  <option :value="6">周六</option>
                  <option :value="7">周日</option>
                </select>
              </td>
              <td><input v-model="cand.start_time" placeholder="08:00" /></td>
              <td><input v-model="cand.end_time" placeholder="09:40" /></td>
              <td><input v-model="cand.location" placeholder="教室地点" /></td>
              <td style="text-align: center">
                <button class="row-action-btn" type="button" title="删除本项" @click="removeTimetableRow(idx)">
                  <Trash2 :size="16" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>

        <div style="margin-top: 12px">
          <button class="secondary-action" type="button" @click="addTimetableRow">
            <Plus :size="16" /> 添加一行时段
          </button>
        </div>
      </div>

      <div class="dialog-actions">
        <button class="secondary-action" type="button" @click="timetableDialog?.close()">取消</button>
        <button
          class="primary-action"
          type="button"
          :disabled="applyingTimetable || timetableCandidates.length === 0"
          @click="confirmApplyTimetable"
        >
          <CalendarDays :size="16" />
          {{ applyingTimetable ? '导入应用中...' : '确认批量应用到课程库' }}
        </button>
      </div>
    </div>
  </dialog>

  <!-- 资料详情与提取文本查看弹窗 -->
  <dialog ref="materialDialog" class="course-dialog wide-dialog">
    <div v-if="viewingMaterial" class="dialog-body">
      <div class="dialog-heading">
        <div>
          <p class="eyebrow">资料详情与智能识别结果</p>
          <h2 :title="viewingMaterial.original_filename">{{ viewingMaterial.original_filename }}</h2>
        </div>
        <button class="icon-button" type="button" aria-label="关闭" @click="materialDialog?.close()">×</button>
      </div>

      <div class="material-detail-meta">
        <div><strong>资料类型：</strong>{{ viewingMaterial.material_type === 'audio' ? '课堂录音 (Audio)' : '课件幻灯 (Slides)' }}</div>
        <div><strong>处理状态：</strong><span class="status-badge" :class="viewingMaterial.status">{{ viewingMaterial.status }}</span></div>
        <div><strong>归类状态：</strong>{{ classificationLabel(viewingMaterial) }}</div>
        <div><strong>文件大小：</strong>{{ formatSize(viewingMaterial.file_size) }}</div>
        <div style="grid-column: 1 / -1"><strong>归类原因：</strong>{{ viewingMaterial.classification_reason }}</div>
      </div>

      <!-- 音频在线播放器 -->
      <div v-if="viewingMaterial.material_type === 'audio'" class="detail-audio-player-box">
        <div class="audio-player-header">
          <Volume2 :size="18" />
          <strong>录音试听播放</strong>
        </div>
        <audio
          class="detail-audio-element"
          controls
          :src="api.materialFileUrl(viewingMaterial.id)"
        ></audio>
      </div>

      <!-- 识别文本区域 -->
      <div class="detail-text-section">
        <div class="detail-text-header">
          <h3>识别转写与提取文本</h3>
          <div class="detail-text-actions">
            <button
              v-if="viewingMaterial.extracted_text"
              class="secondary-action compact-action"
              type="button"
              @click="copyExtractedText(viewingMaterial.extracted_text)"
            >
              <component :is="copySuccess ? Check : Copy" :size="14" />
              {{ copySuccess ? '已复制！' : '复制文本' }}
            </button>

            <button
              v-if="viewingMaterial.material_type === 'audio'"
              class="primary-action compact-action"
              type="button"
              :disabled="triggeringTranscribe"
              @click="triggerAudioTranscribe(viewingMaterial.id)"
            >
              <AudioLines :size="14" />
              {{ triggeringTranscribe ? '转写派发中...' : viewingMaterial.extracted_text ? '重新转写' : '立即启动语音转写' }}
            </button>
          </div>
        </div>

        <!-- 搜索字句定位条（当有搜索关键词且有匹配时显现） -->
        <div v-if="searchTokens.length > 0 && dialogMatchTotal > 0" class="dialog-search-locater-bar">
          <div class="locater-stat">
            <Highlighter :size="15" />
            <span>找到 <strong>{{ dialogMatchTotal }}</strong> 处关键词匹配</span>
            <span class="locater-pos-badge">第 {{ activeMatchNavIndex + 1 }} / {{ dialogMatchTotal }} 处</span>
          </div>
          <div class="locater-nav-buttons">
            <button class="locater-btn" type="button" title="上一处匹配 (快捷键 上箭头)" @click="prevMatch">
              <ChevronUp :size="15" /> 上一处
            </button>
            <button class="locater-btn" type="button" title="下一处匹配 (快捷键 下箭头)" @click="nextMatch">
              <ChevronDown :size="15" /> 下一处
            </button>
          </div>
        </div>

        <div v-if="viewingMaterial.extracted_text" ref="detailTextContainerRef" class="extracted-text-box">
          <template v-if="searchTokens.length > 0">
            <template v-for="(part, idx) in dialogTextParts" :key="idx">
              <mark
                v-if="part.isHighlight"
                :id="`match-pos-${part.matchIdx}`"
                class="search-mark"
                :class="{ 'active-match': part.matchIdx === activeMatchNavIndex }"
              >{{ part.text }}</mark>
              <span v-else>{{ part.text }}</span>
            </template>
          </template>
          <template v-else>
            {{ viewingMaterial.extracted_text }}
          </template>
        </div>
        <div v-else class="empty-state compact">
          <FileText :size="24" />
          <span>当前资料暂无可用提取文本。</span>
        </div>
      </div>


      <div class="dialog-actions">
        <button
          class="secondary-action"
          type="button"
          @click="downloadSingleMaterial(viewingMaterial)"
        >
          <Download :size="16" /> 下载原文件
        </button>
        <button
          class="secondary-action danger-hover-btn"
          type="button"
          @click="promptDeleteSingle(viewingMaterial)"
        >
          <Trash2 :size="16" /> 删除此资料
        </button>
        <button class="secondary-action" type="button" @click="materialDialog?.close()">关闭</button>
      </div>
    </div>
  </dialog>

  <!-- 资料直接上传隐藏文件输入 -->
  <input
    ref="materialFileInput"
    type="file"
    accept="audio/*,.mp3,.wav,.m4a,.aac,.flac,.wma,.ogg,.pptx,.ppt,.pdf"
    style="display: none"
    @change="handleMaterialFileChange"
  />

  <!-- 重复文件冲突询问对话框 -->
  <dialog ref="conflictDialog" class="modal-card dialog-box conflict-dialog">
    <div class="modal-header">
      <div>
        <p class="eyebrow warning-eyebrow">重复文件检测</p>
        <h3 class="modal-title">发现相同文件</h3>
      </div>
      <button class="icon-button" type="button" aria-label="关闭" @click="resolveConflict(false)">×</button>
    </div>

    <div class="conflict-content" v-if="conflictExistingMaterial">
      <p class="conflict-desc">
        您准备上传的文件 <strong>{{ pendingUploadFile?.name }}</strong> 与工作区中已有资料的内容哈希（SHA-256）完全一致：
      </p>

      <div class="conflict-card">
        <div class="conflict-card-row">
          <span class="label">已有文件：</span>
          <strong class="val">{{ conflictExistingMaterial.original_filename }}</strong>
        </div>
        <div class="conflict-card-row">
          <span class="label">所属课程：</span>
          <span class="val">{{ getCourseNameById(conflictExistingMaterial.course_id) }}</span>
        </div>
        <div class="conflict-card-row">
          <span class="label">文件大小：</span>
          <span class="val">{{ formatSize(conflictExistingMaterial.file_size) }}</span>
        </div>
        <div class="conflict-card-row">
          <span class="label">处理状态：</span>
          <span class="status-badge" :class="conflictExistingMaterial.status">{{ conflictExistingMaterial.status }}</span>
        </div>
      </div>

      <p class="conflict-question">
        工作区中已存在相同资料，是否仍要保留新文件作为独立副本？
      </p>

      <div class="modal-actions conflict-actions">
        <button class="primary-action" type="button" @click="resolveConflict(false)">
          取消上传（使用已有文件）
        </button>
        <button class="secondary-action danger-hover-btn" type="button" @click="resolveConflict(true)">
          仍然保留新副本
        </button>
      </div>
    </div>
  </dialog>

  <!-- 工作区重复文件排查与清理对话框 -->
  <dialog ref="duplicatesDialog" class="modal-card dialog-box duplicates-dialog wide-dialog">
    <div class="modal-header">
      <div>
        <p class="eyebrow">工作区与存储治理</p>
        <h3 class="modal-title">重复文件与磁盘空间治理</h3>
      </div>
      <button class="icon-button" type="button" aria-label="关闭" @click="duplicatesDialog?.close()">×</button>
    </div>

    <div class="duplicates-content">
      <!-- 物理存储审计面板 -->
      <div class="storage-audit-section">
        <div class="storage-audit-header">
          <div class="storage-title">
            <HardDrive :size="18" />
            <strong>磁盘存储健康审计</strong>
          </div>
          <button
            class="secondary-action compact-action"
            type="button"
            :disabled="auditingStorage"
            @click="handleAuditStorage"
          >
            <RefreshCw class="compact-icon" :class="{ spinning: auditingStorage }" :size="14" />
            {{ auditingStorage ? '扫描中...' : '重新审计存储' }}
          </button>
        </div>

        <div v-if="storageAuditData" class="storage-audit-grid">
          <div class="audit-stat-card">
            <span class="audit-stat-label">资料库记录</span>
            <strong class="audit-stat-val">{{ storageAuditData.total_materials_count }} 份</strong>
          </div>
          <div class="audit-stat-card">
            <span class="audit-stat-label">正常物理文件</span>
            <strong class="audit-stat-val green-text">{{ storageAuditData.valid_files_count }} 个</strong>
          </div>
          <div class="audit-stat-card" :class="{ 'warning-card': storageAuditData.missing_files_count > 0 }">
            <span class="audit-stat-label">丢失物理源文件</span>
            <strong class="audit-stat-val">{{ storageAuditData.missing_files_count }} 个</strong>
          </div>
          <div class="audit-stat-card" :class="{ 'danger-card': storageAuditData.orphan_files_count > 0 }">
            <span class="audit-stat-label">孤儿垃圾物理文件</span>
            <strong class="audit-stat-val">{{ storageAuditData.orphan_files_count }} 个 ({{ formatSize(storageAuditData.orphan_files_bytes) }})</strong>
          </div>
        </div>

        <div v-if="storageAuditData && storageAuditData.orphan_files_count > 0" class="orphan-action-box">
          <p class="orphan-warning-text">
            发现 <strong>{{ storageAuditData.orphan_files_count }}</strong> 个未被资料库关联的残留物理文件（占用 {{ formatSize(storageAuditData.orphan_files_bytes) }} 磁盘空间）。
          </p>
          <button
            class="primary-action danger-btn compact-action"
            type="button"
            :disabled="cleaningOrphans"
            @click="handleCleanOrphans"
          >
            {{ cleaningOrphans ? '清理中...' : '立即清理孤儿垃圾文件' }}
          </button>
        </div>
      </div>

      <div class="divider" style="margin: 16px 0"></div>

      <!-- 重复文件排查列表 -->
      <div class="duplicates-header-row">
        <h4>相同文件重复组 (SHA-256)</h4>
        <span class="dup-summary-badge" v-if="duplicateGroups.length > 0">
          共 {{ duplicateGroups.length }} 组，涉及 {{ totalDuplicateFiles }} 个冗余副本
        </span>
      </div>

      <div v-if="duplicateGroups.length === 0" class="empty-state compact">
        <CheckCircle2 :size="24" />
        <span>工作区状态良好，未发现重复文件。</span>
      </div>
      <div v-else>
        <p class="duplicates-summary">
          您可以自由点击每项单选指定「保留主项」，系统将优先保留主项的转写文本和任务记录，并安全合并其余副本。
        </p>

        <div class="duplicates-list">
          <div v-for="group in duplicateGroups" :key="group.sha256" class="duplicate-group-item">
            <div class="dup-group-header">
              <div>
                <span class="dup-hash">哈希：{{ group.sha256.slice(0, 12) }}...</span>
                <span class="dup-size">{{ formatSize(group.file_size) }} × {{ group.count }} 份副本</span>
              </div>
              <button
                class="secondary-action compact-action"
                type="button"
                :disabled="resolvingGroupHash === group.sha256"
                @click="handleResolveSingleGroup(group)"
              >
                {{ resolvingGroupHash === group.sha256 ? '正在合并...' : '合并此组' }}
              </button>
            </div>
            <ul class="dup-file-sublist">
              <li
                v-for="m in group.materials"
                :key="m.id"
                class="dup-item-clickable"
                :class="{ 'keeper-candidate': getGroupKeeperId(group) === m.id }"
                @click="selectGroupKeeper(group.sha256, m.id)"
              >
                <input
                  type="radio"
                  :name="`keeper-${group.sha256}`"
                  :checked="getGroupKeeperId(group) === m.id"
                  @click.stop="selectGroupKeeper(group.sha256, m.id)"
                />
                <span
                  class="dup-badge"
                  :class="{ 'keep-badge': getGroupKeeperId(group) === m.id, 'clean-badge': getGroupKeeperId(group) !== m.id }"
                >
                  {{ getGroupKeeperId(group) === m.id ? '保留主项' : '清理副本' }}
                </span>
                <span class="dup-file-name" :title="m.original_filename">{{ m.original_filename }}</span>
                <span class="dup-course">({{ getCourseNameById(m.course_id) }})</span>
                <span class="dup-detail-info">
                  {{ m.extracted_text ? '已转写文本' : '未转写' }} · {{ formatTime(m.created_at) }}
                </span>
              </li>
            </ul>
          </div>
        </div>

        <div class="modal-actions">
          <button class="secondary-action" type="button" @click="duplicatesDialog?.close()">稍后处理</button>
          <button class="primary-action danger-btn" type="button" :disabled="cleaningDuplicates" @click="handleDeduplicate">
            {{ cleaningDuplicates ? '正在清理...' : '一键合并全部重复组并清理副本' }}
          </button>
        </div>
      </div>
    </div>
  </dialog>

  <!-- 资料删除二次确认对话框 -->
  <dialog ref="deleteConfirmDialog" class="modal-card dialog-box confirm-dialog">
    <div class="modal-header">
      <div>
        <p class="eyebrow warning-eyebrow">删除确认</p>
        <h3 class="modal-title">
          {{ deleteTarget?.type === 'batch' ? '批量删除资料' : '删除单项资料' }}
        </h3>
      </div>
      <button class="icon-button" type="button" aria-label="关闭" @click="deleteConfirmDialog?.close()">×</button>
    </div>

    <div class="confirm-body" v-if="deleteTarget">
      <p class="confirm-message" v-if="deleteTarget.type === 'single' && deleteTarget.material">
        确认要删除资料 <strong>“{{ deleteTarget.material.original_filename }}”</strong> 吗？
      </p>
      <p class="confirm-message" v-else-if="deleteTarget.type === 'batch' && deleteTarget.ids">
        确认要批量删除已选中的 <strong>{{ deleteTarget.ids.length }}</strong> 项资料吗？
      </p>

      <div class="confirm-options">
        <label class="checkbox-label">
          <input type="checkbox" v-model="deletePhysicalFiles" />
          <span>彻底删除本地物理源文件（推荐，安全引用校验防止误删共享文件）</span>
        </label>
      </div>

      <div class="warning-callout">
        <CircleAlert :size="16" />
        <span>删除后此资料的转写记录及关联任务将一并移除，此操作不可撤销。</span>
      </div>

      <div class="modal-actions">
        <button class="secondary-action" type="button" @click="deleteConfirmDialog?.close()">取消</button>
        <button
          class="primary-action danger-btn"
          type="button"
          :disabled="deleting"
          @click="confirmExecuteDelete"
        >
          <Trash2 :size="16" />
          {{ deleting ? '正在删除...' : '确认删除' }}
        </button>
      </div>
    </div>
  </dialog>
</template>
