<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  ArrowRightLeft,
  BookOpenText,
  Calendar,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Download,
  FileSpreadsheet,
  GripVertical,
  Plus,
  RefreshCw,
  Settings2,
  Sparkles,
  Trash2,
  Upload,
  X,
} from '@lucide/vue'
import { api } from '../api'
import type {
  CalendarEventItem,
  CalendarMarkItem,
  CalendarTaskCard,
  CalendarWorkspace,
  Course,
  StrategyBoard,
  StrategyItem,
  StrategyZone,
} from '../types'

const emit = defineEmits<{
  (e: 'notify', msg: string, isError?: boolean): void
}>()

const COLORS = [
  '#627cf7',
  '#2fa69b',
  '#f4a624',
  '#e76491',
  '#a15cf3',
  '#458df2',
  '#399c74',
  '#fa7d2c',
  '#df45ea',
  '#687b97',
]

// 视图模式：'calendar' (游戏人生) | 'game' (博弈论)
const activeView = ref<'calendar' | 'game'>('calendar')

// 数据状态
const workspaces = ref<CalendarWorkspace[]>([])
const activeWorkspaceId = ref<string>('')
const strategyItems = ref<StrategyItem[]>([])
const loading = ref(true)

// 日历选区与时间状态
const today = new Date()
const currentYear = ref(today.getFullYear())
const selectedDay = ref<string | null>(null)
const selStart = ref<string | null>(null)
const selEnd = ref<string | null>(null)
const selectedMarkColor = ref(COLORS[0])

// 拖拽临时对象
interface DragPayload {
  kind: 'schedule' | 'game'
  source?: string
  id: string
  text: string
}
const dragData = ref<DragPayload | null>(null)

// 弹窗状态
const calendarModalOpen = ref(false)
const calendarEditing = ref(false)
const calendarNameInput = ref('')
const calendarColorInput = ref(COLORS[0])

const eventModalOpen = ref(false)
const editingEventId = ref<string | null>(null)
const eventDateInput = ref('')
const eventTitleInput = ref('')
const eventStartInput = ref('')
const eventEndInput = ref('')
const eventNoteInput = ref('')

// 课程表同步弹窗状态
const syncModalOpen = ref(false)
const syncingCourses = ref(false)
const availableCourses = ref<Course[]>([])
const syncForm = ref({
  workspaceId: '',
  startDate: '',
  endDate: '',
  courseIds: [] as number[],
  syncToEvents: true,
  syncToTray: false,
  syncToStrategy: false,
})

// 学习计划文件导入状态
interface ImportedStudyTask extends CalendarEventItem {
  rowNumber: number
}

const importModalOpen = ref(false)
const importFileInput = ref<HTMLInputElement | null>(null)
const importFileName = ref('')
const importedStudyTasks = ref<ImportedStudyTask[]>([])
const importWarnings = ref<string[]>([])
const importingPlan = ref(false)

function formatIsoDate(d: Date) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function addDays(base: Date, days: number) {
  const result = new Date(base)
  result.setDate(result.getDate() + days)
  return result
}

function normalizeHeader(value: string) {
  return value.trim().toLowerCase().replace(/[\s_（）()\-]/g, '')
}

function findRowValue(row: Record<string, unknown>, aliases: string[]) {
  const aliasSet = new Set(aliases.map(normalizeHeader))
  const matched = Object.entries(row).find(([key]) => aliasSet.has(normalizeHeader(key)))
  return matched?.[1]
}

function excelSerialToIsoDate(value: number): string | null {
  if (!Number.isFinite(value) || value <= 0) return null
  const utc = new Date(Date.UTC(1899, 11, 30) + Math.floor(value) * 24 * 60 * 60 * 1000)
  if (Number.isNaN(utc.getTime())) return null
  return `${utc.getUTCFullYear()}-${String(utc.getUTCMonth() + 1).padStart(2, '0')}-${String(utc.getUTCDate()).padStart(2, '0')}`
}

function normalizePlanDate(value: unknown): string | null {
  if (value instanceof Date && !Number.isNaN(value.getTime())) return formatIsoDate(value)

  if (typeof value === 'number' && Number.isFinite(value)) {
    return excelSerialToIsoDate(value)
  }

  const raw = String(value ?? '').trim()
  if (!raw) return null
  if (/^\d{5}(\.\d+)?$/.test(raw)) {
    return excelSerialToIsoDate(Number(raw))
  }

  const normalized = raw.replace(/[年/.]/g, '-').replace(/月/g, '-').replace(/日/g, '').replace(/-+/g, '-')
  const full = normalized.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/)
  const short = normalized.match(/^(\d{1,2})-(\d{1,2})$/)
  const year = full ? Number(full[1]) : currentYear.value
  const month = Number(full?.[2] ?? short?.[1])
  const day = Number(full?.[3] ?? short?.[2])
  if (!month || !day) return null
  const candidate = new Date(year, month - 1, day)
  if (candidate.getFullYear() !== year || candidate.getMonth() !== month - 1 || candidate.getDate() !== day) return null
  return formatIsoDate(candidate)
}

function normalizePlanTime(value: unknown, fallback = ''): string {
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    return `${String(value.getHours()).padStart(2, '0')}:${String(value.getMinutes()).padStart(2, '0')}`
  }
  if (typeof value === 'number' && value >= 0 && value < 1) {
    const totalMinutes = Math.round(value * 24 * 60)
    return `${String(Math.floor(totalMinutes / 60) % 24).padStart(2, '0')}:${String(totalMinutes % 60).padStart(2, '0')}`
  }
  const raw = String(value ?? '').trim().replace(/时|点/g, ':').replace(/分/g, '')
  const matched = raw.match(/^(\d{1,2})(?::(\d{1,2}))?$/)
  if (!matched) return fallback
  const hour = Math.min(23, Number(matched[1]))
  const minute = Math.min(59, Number(matched[2] || 0))
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
}

function normalizePriority(value: unknown): 'high' | 'medium' | 'low' {
  const raw = String(value ?? '').trim().toLowerCase()
  if (['高', '重要', '紧急', 'high', '1'].includes(raw)) return 'high'
  if (['低', '稍后', 'low', '3'].includes(raw)) return 'low'
  return 'medium'
}

function normalizeCompleted(value: unknown) {
  const raw = String(value ?? '').trim().toLowerCase()
  return ['是', '已完成', '完成', 'true', 'yes', '1'].includes(raw)
}

function parseCsvText(text: string): Record<string, unknown>[] {
  const matrix: string[][] = []
  let row: string[] = []
  let field = ''
  let quoted = false
  const source = text.replace(/^\uFEFF/, '')

  for (let index = 0; index < source.length; index += 1) {
    const char = source[index]
    if (char === '"') {
      if (quoted && source[index + 1] === '"') {
        field += '"'
        index += 1
      } else {
        quoted = !quoted
      }
    } else if (char === ',' && !quoted) {
      row.push(field.trim())
      field = ''
    } else if ((char === '\n' || char === '\r') && !quoted) {
      if (char === '\r' && source[index + 1] === '\n') index += 1
      row.push(field.trim())
      field = ''
      if (row.some((cell) => cell.length > 0)) matrix.push(row)
      row = []
    } else {
      field += char
    }
  }
  row.push(field.trim())
  if (row.some((cell) => cell.length > 0)) matrix.push(row)
  if (matrix.length < 2) return []

  const headers = matrix[0]
  return matrix.slice(1).map((cells) =>
    Object.fromEntries(headers.map((header, index) => [header, cells[index] ?? '']))
  )
}

function rowsToStudyTasks(rows: Record<string, unknown>[]) {
  const tasks: ImportedStudyTask[] = []
  const warnings: string[] = []

  rows.forEach((row, index) => {
    const rowNumber = index + 2
    const date = normalizePlanDate(findRowValue(row, ['日期', '学习日期', 'date', 'day']))
    const title = String(findRowValue(row, ['任务', '学习任务', '任务名称', '事项', 'title', 'task', 'content']) ?? '').trim()
    if (!date || !title) {
      warnings.push(`第 ${rowNumber} 行缺少有效日期或任务名称，已跳过`)
      return
    }

    const estimatedRaw = findRowValue(row, ['预计分钟', '预计时长', '时长分钟', 'minutes', 'duration'])
    const estimated = Number.parseInt(String(estimatedRaw ?? ''), 10)
    const start = normalizePlanTime(findRowValue(row, ['开始时间', '开始', 'start', 'time']), '09:00')
    let end = normalizePlanTime(findRowValue(row, ['结束时间', '结束', 'end']))
    if (!end && Number.isFinite(estimated) && estimated > 0) {
      const [hour, minute] = start.split(':').map(Number)
      const endMinutes = hour * 60 + minute + estimated
      end = `${String(Math.floor(endMinutes / 60) % 24).padStart(2, '0')}:${String(endMinutes % 60).padStart(2, '0')}`
    }

    tasks.push({
      id: generateId(),
      rowNumber,
      date,
      title,
      start,
      end,
      note: String(findRowValue(row, ['备注', '说明', 'note', 'description']) ?? '').trim(),
      category: String(findRowValue(row, ['分类', '科目', '课程', 'category', 'subject']) ?? '').trim(),
      priority: normalizePriority(findRowValue(row, ['优先级', '重要程度', 'priority'])),
      estimated_minutes: Number.isFinite(estimated) && estimated > 0 ? estimated : undefined,
      completed: normalizeCompleted(findRowValue(row, ['完成', '是否完成', '状态', 'completed', 'status'])),
      source: 'study-plan-import',
    })
  })

  importedStudyTasks.value = tasks
  importWarnings.value = warnings
}

function openStudyPlanImport() {
  importFileName.value = ''
  importedStudyTasks.value = []
  importWarnings.value = []
  if (importFileInput.value) importFileInput.value.value = ''
  importModalOpen.value = true
}

async function handleStudyPlanFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  importFileName.value = file.name
  importWarnings.value = []
  importedStudyTasks.value = []

  try {
    let rows: Record<string, unknown>[] = []
    const lowerName = file.name.toLowerCase()
    if (lowerName.endsWith('.json')) {
      const parsed = JSON.parse(await file.text())
      rows = Array.isArray(parsed) ? parsed : Array.isArray(parsed?.tasks) ? parsed.tasks : []
    } else if (lowerName.endsWith('.csv')) {
      rows = parseCsvText(await file.text())
    } else {
      const XLSX = await import('xlsx')
      const workbook = XLSX.read(await file.arrayBuffer(), { type: 'array', cellDates: true })
      const firstSheet = workbook.Sheets[workbook.SheetNames[0]]
      rows = XLSX.utils.sheet_to_json<Record<string, unknown>>(firstSheet, { defval: '', raw: true })
    }
    if (!rows.length) throw new Error('文件中没有可读取的任务行')
    rowsToStudyTasks(rows)
    if (!importedStudyTasks.value.length) throw new Error('没有识别到有效任务，请检查日期和任务名称列')
  } catch (err) {
    emit('notify', err instanceof Error ? err.message : '学习计划解析失败', true)
  }
}

async function downloadStudyPlanTemplate() {
  const XLSX = await import('xlsx')
  const rows = [
    {
      日期: formatIsoDate(today),
      学习任务: '复习高等数学极限章节',
      开始时间: '09:00',
      结束时间: '10:00',
      分类: '高等数学',
      优先级: '高',
      预计分钟: 60,
      备注: '完成例题 1-8',
      是否完成: '否',
    },
    {
      日期: formatIsoDate(addDays(today, 1)),
      学习任务: '背诵英语单词 50 个',
      开始时间: '20:00',
      结束时间: '20:30',
      分类: '英语',
      优先级: '中',
      预计分钟: 30,
      备注: '',
      是否完成: '否',
    },
  ]
  const sheet = XLSX.utils.json_to_sheet(rows)
  sheet['!cols'] = [{ wch: 12 }, { wch: 30 }, { wch: 12 }, { wch: 12 }, { wch: 16 }, { wch: 10 }, { wch: 12 }, { wch: 28 }, { wch: 12 }]
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, sheet, '学习计划')
  XLSX.writeFile(workbook, 'DailyManager学习计划导入模板.xlsx')
}

async function importStudyPlan() {
  const ws = activeWorkspace.value
  if (!ws || !importedStudyTasks.value.length) return
  importingPlan.value = true
  try {
    const existingKeys = new Set(ws.data.events.map((event) => `${event.date}|${event.title}|${event.start}`))
    const uniqueTasks = importedStudyTasks.value.filter((task) => {
      const key = `${task.date}|${task.title}|${task.start}`
      if (existingKeys.has(key)) return false
      existingKeys.add(key)
      return true
    })
    const duplicateCount = importedStudyTasks.value.length - uniqueTasks.length
    ws.data.events.push(...uniqueTasks.map(({ rowNumber: _rowNumber, ...task }) => task))
    await persistActiveWorkspace()
    if (uniqueTasks.length) {
      selectedDay.value = uniqueTasks[0].date
      currentYear.value = Number(uniqueTasks[0].date.slice(0, 4))
    }
    importModalOpen.value = false
    emit('notify', `已导入 ${uniqueTasks.length} 个每日学习任务${duplicateCount ? `，跳过 ${duplicateCount} 个重复任务` : ''}`)
  } finally {
    importingPlan.value = false
  }
}

function setSyncQuickWeeks(weeks: number) {
  const now = new Date()
  syncForm.value.startDate = formatIsoDate(now)
  const future = new Date(now.getTime() + weeks * 7 * 24 * 3600 * 1000)
  syncForm.value.endDate = formatIsoDate(future)
}

async function openSyncCoursesModal() {
  syncForm.value.workspaceId = activeWorkspaceId.value || ''
  setSyncQuickWeeks(8)
  try {
    availableCourses.value = await api.courses()
    // 默认全选课程
    syncForm.value.courseIds = availableCourses.value.map((c) => c.id)
  } catch (err) {
    emit('notify', '获取课程列表失败', true)
  }
  syncModalOpen.value = true
}

async function submitSyncCourses() {
  if (!syncForm.value.startDate || !syncForm.value.endDate) {
    emit('notify', '请选择同步起止日期', true)
    return
  }
  if (!syncForm.value.syncToEvents && !syncForm.value.syncToTray && !syncForm.value.syncToStrategy) {
    emit('notify', '请至少勾选一种同步目标（日历日程 / 待安排托盘 / 博弈论收集箱）', true)
    return
  }
  syncingCourses.value = true
  try {
    const res = await api.syncCoursesToCalendar({
      workspace_id: syncForm.value.workspaceId || null,
      start_date: syncForm.value.startDate,
      end_date: syncForm.value.endDate,
      course_ids: syncForm.value.courseIds,
      sync_to_events: syncForm.value.syncToEvents,
      sync_to_tray: syncForm.value.syncToTray,
      sync_to_strategy: syncForm.value.syncToStrategy,
    })
    emit(
      'notify',
      `同步成功！为“${res.target_workspace_name}”创建了 ${res.created_events_count} 节日程、${res.created_tray_count} 个托盘待办、${res.created_strategy_count} 个博弈论任务卡片。`
    )
    syncModalOpen.value = false
    await loadAllData()
  } catch (err) {
    emit('notify', err instanceof Error ? err.message : '课程同步失败', true)
  } finally {
    syncingCourses.value = false
  }
}

// 表单输入暂存
const gameInputText = ref('')
const trayInputText = ref('')
const markInputText = ref('')
const globalInputText = ref('')
const monthInputText = ref('')
const selectedMonthKey = ref(`${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`)

const activeWorkspace = computed(() => {
  return workspaces.value.find((w) => w.id === activeWorkspaceId.value) || workspaces.value[0] || null
})

function generateId() {
  return 'i' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
}

function dateKey(y: number, m: number, d: number) {
  return `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

function dateText(s: string) {
  const [y, m, d] = s.split('-').map(Number)
  return `${m}月${d}日`
}

function hexToRgba(hex: string, alpha: number) {
  const h = hex.replace('#', '')
  const n = parseInt(h, 16)
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`
}

// --- 数据同步后端逻辑 ---

async function loadAllData() {
  loading.value = true
  try {
    const [wsList, strat] = await Promise.all([api.calendarWorkspaces(), api.getStrategyBoard()])
    workspaces.value = wsList
    if (wsList.length > 0) {
      const active = wsList.find((w) => w.is_active) || wsList[0]
      activeWorkspaceId.value = active.id
    }
    strategyItems.value = strat.items || []
  } catch (err) {
    emit('notify', err instanceof Error ? err.message : '加载日历数据失败', true)
  } finally {
    loading.value = false
  }
}

async function persistActiveWorkspace() {
  const ws = activeWorkspace.value
  if (!ws) return
  try {
    await api.updateCalendarWorkspace(ws.id, {
      name: ws.name,
      color: ws.color,
      is_active: true,
      data: ws.data,
    })
  } catch (err) {
    emit('notify', '日历保存失败', true)
  }
}

async function persistStrategy() {
  try {
    await api.saveStrategyBoard(strategyItems.value)
  } catch (err) {
    emit('notify', '博弈论看板保存失败', true)
  }
}

// --- 日历工作区管理 ---

function openNewCalendarModal() {
  calendarEditing.value = false
  calendarNameInput.value = ''
  calendarColorInput.value = COLORS[workspaces.value.length % COLORS.length]
  calendarModalOpen.value = true
}

function openEditCalendarModal() {
  const ws = activeWorkspace.value
  if (!ws) return
  calendarEditing.value = true
  calendarNameInput.value = ws.name
  calendarColorInput.value = ws.color
  calendarModalOpen.value = true
}

async function saveCalendarModal() {
  const name = calendarNameInput.value.trim() || '未命名日历'
  if (calendarEditing.value) {
    const ws = activeWorkspace.value
    if (ws) {
      ws.name = name
      ws.color = calendarColorInput.value
      await persistActiveWorkspace()
    }
  } else {
    try {
      const created = await api.createCalendarWorkspace({
        name,
        color: calendarColorInput.value,
        is_active: true,
        data: { tray: [], events: [], marks: [], global: [], monthly: [] },
      })
      workspaces.value.push(created)
      activeWorkspaceId.value = created.id
    } catch (err) {
      emit('notify', '创建日历失败', true)
    }
  }
  calendarModalOpen.value = false
}

async function deleteCurrentCalendar() {
  const ws = activeWorkspace.value
  if (!ws || workspaces.value.length <= 1) return
  if (!confirm(`确定删除日历“${ws.name}”及所有日程事项吗？`)) return
  try {
    await api.deleteCalendarWorkspace(ws.id)
    workspaces.value = workspaces.value.filter((w) => w.id !== ws.id)
    activeWorkspaceId.value = workspaces.value[0].id
    emit('notify', '日历已删除')
  } catch (err) {
    emit('notify', err instanceof Error ? err.message : '删除失败', true)
  }
  calendarModalOpen.value = false
}

// --- 博弈论操作 ---

function addGameTask() {
  const t = gameInputText.value.trim()
  if (!t) return
  strategyItems.value.push({ id: generateId(), text: t, zone: 'inbox' })
  gameInputText.value = ''
  persistStrategy()
}

function removeGameTask(id: string) {
  strategyItems.value = strategyItems.value.filter((x) => x.id !== id)
  persistStrategy()
}

function onGameDragStart(item: StrategyItem, e: DragEvent) {
  dragData.value = { kind: 'game', id: item.id, text: item.text }
  e.dataTransfer?.setData('text/plain', item.id)
}

function onGameDrop(zone: StrategyZone, e: DragEvent) {
  e.preventDefault()
  if (dragData.value?.kind !== 'game') return
  const item = strategyItems.value.find((x) => x.id === dragData.value?.id)
  if (item) {
    item.zone = zone
    persistStrategy()
  }
  dragData.value = null
}

// --- 日历操作 ---

function marksOnDate(key: string): CalendarMarkItem[] {
  const ws = activeWorkspace.value
  if (!ws) return []
  return ws.data.marks.filter((m) => m.start <= key && m.end >= key)
}

function sortedEventsOnDate(key: string): CalendarEventItem[] {
  const ws = activeWorkspace.value
  if (!ws) return []
  return ws.data.events.filter((e) => e.date === key).sort((a, b) => a.start.localeCompare(b.start))
}

function completedEventsOnDate(key: string) {
  return sortedEventsOnDate(key).filter((event) => event.completed).length
}

function completionPercentOnDate(key: string) {
  const events = sortedEventsOnDate(key)
  return events.length ? Math.round((events.filter((event) => event.completed).length / events.length) * 100) : 0
}

function toggleEventCompleted(event: CalendarEventItem, mouseEvent?: MouseEvent) {
  mouseEvent?.stopPropagation()
  event.completed = !event.completed
  persistActiveWorkspace()
}

function marksBackground(ms: CalendarMarkItem[]): string {
  if (!ms.length) return ''
  if (ms.length === 1) return hexToRgba(ms[0].color, 0.22)
  const piece = 100 / ms.length
  const stops: string[] = []
  ms.forEach((m, i) => {
    const col = hexToRgba(m.color, 0.22)
    stops.push(`${col} ${(piece * i).toFixed(1)}%`, `${col} ${(piece * (i + 1)).toFixed(1)}%`)
  })
  return `linear-gradient(135deg, ${stops.join(',')})`
}

function onDateClick(key: string) {
  selectedDay.value = key
  if (!selStart.value || (selEnd.value && selStart.value !== selEnd.value)) {
    selStart.value = selEnd.value = key
  } else if (selStart.value === selEnd.value) {
    selEnd.value = key
  } else {
    selStart.value = selEnd.value = key
  }
}

function clearDateSelection() {
  selectedDay.value = null
  selStart.value = null
  selEnd.value = null
}

function addTrayItem() {
  const ws = activeWorkspace.value
  const t = trayInputText.value.trim()
  if (!ws || !t) return
  ws.data.tray.push({ id: generateId(), text: t })
  trayInputText.value = ''
  persistActiveWorkspace()
}

function removeTrayItem(id: string) {
  const ws = activeWorkspace.value
  if (!ws) return
  ws.data.tray = ws.data.tray.filter((x) => x.id !== id)
  persistActiveWorkspace()
}

function saveDateMark() {
  const ws = activeWorkspace.value
  const text = markInputText.value.trim()
  if (!ws || !selStart.value) {
    emit('notify', '请先在日历中选择日期', true)
    return
  }
  if (!text) {
    emit('notify', '请输入标注内容', true)
    return
  }
  const range = [selStart.value, selEnd.value || selStart.value].sort()
  ws.data.marks.push({
    id: generateId(),
    text,
    color: selectedMarkColor.value,
    start: range[0],
    end: range[1],
  })
  markInputText.value = ''
  selStart.value = selEnd.value = null
  persistActiveWorkspace()
}

function addGlobalTask() {
  const ws = activeWorkspace.value
  const t = globalInputText.value.trim()
  if (!ws || !t) return
  ws.data.global.push({ id: generateId(), text: t })
  globalInputText.value = ''
  persistActiveWorkspace()
}

function addMonthTask() {
  const ws = activeWorkspace.value
  const t = monthInputText.value.trim()
  if (!ws || !t) return
  ws.data.monthly.push({ id: generateId(), text: t, month: selectedMonthKey.value })
  monthInputText.value = ''
  persistActiveWorkspace()
}

function removeTaskCard(kind: 'global' | 'monthly' | 'marks', id: string) {
  const ws = activeWorkspace.value
  if (!ws) return
  if (kind === 'global') ws.data.global = ws.data.global.filter((x) => x.id !== id)
  if (kind === 'monthly') ws.data.monthly = ws.data.monthly.filter((x) => x.id !== id)
  if (kind === 'marks') ws.data.marks = ws.data.marks.filter((x) => x.id !== id)
  persistActiveWorkspace()
}

// 日程弹窗
function openEventModal(day: string, editEvent?: CalendarEventItem) {
  eventDateInput.value = day
  editingEventId.value = editEvent ? editEvent.id : null
  eventTitleInput.value = editEvent ? editEvent.title : dragData.value?.text || ''
  eventStartInput.value = editEvent ? editEvent.start : '09:00'
  eventEndInput.value = editEvent?.end || '10:00'
  eventNoteInput.value = editEvent?.note || ''
  eventModalOpen.value = true
}

function saveEventModal() {
  const ws = activeWorkspace.value
  const title = eventTitleInput.value.trim()
  if (!ws || !title) {
    emit('notify', '请输入日程标题', true)
    return
  }

  if (editingEventId.value) {
    const ev = ws.data.events.find((x) => x.id === editingEventId.value)
    if (ev) {
      ev.title = title
      ev.start = eventStartInput.value
      ev.end = eventEndInput.value
      ev.note = eventNoteInput.value
    }
  } else {
    ws.data.events.push({
      id: generateId(),
      date: eventDateInput.value,
      title,
      start: eventStartInput.value || '09:00',
      end: eventEndInput.value,
      note: eventNoteInput.value,
    })
    // 如果是从托盘拖入的，清理托盘对应项
    if (dragData.value?.source === 'tray') {
      ws.data.tray = ws.data.tray.filter((x) => x.id !== dragData.value?.id)
    }
  }

  eventModalOpen.value = false
  dragData.value = null
  persistActiveWorkspace()
}

function deleteEventModal() {
  const ws = activeWorkspace.value
  if (!ws || !editingEventId.value) return
  ws.data.events = ws.data.events.filter((x) => x.id !== editingEventId.value)
  eventModalOpen.value = false
  persistActiveWorkspace()
}

function onDateDrop(dateStr: string, e: DragEvent) {
  e.preventDefault()
  if (dragData.value?.kind === 'schedule') {
    openEventModal(dateStr)
  }
}

onMounted(() => {
  selectedDay.value = formatIsoDate(today)
  loadAllData()
})
</script>

<template>
  <div class="calendar-layout" :style="{ '--accent': activeWorkspace?.color || '#627cf7' }">
    <!-- 侧边栏：多日历切换 -->
    <aside class="cal-sidebar">
      <div class="cal-brand">
        <div class="brand-avatar" :style="{ background: activeWorkspace?.color || '#627cf7' }">t</div>
        <span class="brand-title">tokii · 日历日程</span>
      </div>

      <nav class="cal-nav">
        <button
          class="nav-tab"
          :class="{ active: activeView === 'game' }"
          @click="activeView = 'game'"
        >
          <span>◈</span> 博弈论看板
        </button>
        <button
          class="nav-tab"
          :class="{ active: activeView === 'calendar' }"
          @click="activeView = 'calendar'"
        >
          <span>▦</span> 游戏人生日历
        </button>
      </nav>

      <div v-if="activeView === 'calendar'" class="workspace-list-section">
        <div class="section-title">
          <span>我的日历</span>
          <button class="add-btn" title="新建日历" @click="openNewCalendarModal">＋ 新建</button>
        </div>
        <div class="workspaces-scroll">
          <button
            v-for="ws in workspaces"
            :key="ws.id"
            class="workspace-item"
            :class="{ active: ws.id === activeWorkspaceId }"
            @click="activeWorkspaceId = ws.id"
          >
            <span class="ws-dot" :style="{ background: ws.color }"></span>
            <span class="ws-name">{{ ws.name }}</span>
          </button>
        </div>
      </div>

      <div class="sidebar-tip">
        <p>数据自动持久化至本地后端数据库，无需担心浏览器缓存清理。</p>
      </div>
    </aside>

    <!-- 主展示区 -->
    <main class="cal-main">
      <header class="cal-topbar">
        <div>
          <h2 class="top-title">{{ activeView === 'game' ? '博弈论 · 事情决策看板' : activeWorkspace?.name || '游戏人生' }}</h2>
          <p class="top-desc">
            {{ activeView === 'game' ? '先收集，再决定现在是否值得承担（必须完成 / 可延期 / 别担心）' : '把待办事项拖进日期，排定具体时间' }}
          </p>
        </div>

        <div class="top-tools">
          <button class="tool-btn sync-btn" title="将课程表批量同步到日程或博弈论" @click="openSyncCoursesModal">
            <ArrowRightLeft :size="14" />
            <span>同步课程表</span>
          </button>
          <template v-if="activeView === 'calendar'">
            <button class="tool-btn import-plan-btn" title="从 Excel、CSV 或 JSON 导入每日学习任务" @click="openStudyPlanImport">
              <Upload :size="14" />
              <span>导入学习计划</span>
            </button>
            <button class="tool-btn" @click="currentYear = today.getFullYear()">回到今年</button>
            <button class="tool-btn icon-btn" @click="currentYear--"><ChevronLeft :size="16" /></button>
            <span class="year-label">{{ currentYear }} 年</span>
            <button class="tool-btn icon-btn" @click="currentYear++"><ChevronRight :size="16" /></button>
            <button class="tool-btn edit-btn" @click="openEditCalendarModal">
              <Settings2 :size="14" /> 日历设置
            </button>
          </template>
        </div>
      </header>

      <!-- 1. 博弈论视图 -->
      <section v-if="activeView === 'game'" class="game-view">
        <div class="game-container">
          <div class="inbox-panel">
            <div class="panel-head">
              <h3>事情收集托盘</h3>
              <span class="count-badge">{{ strategyItems.filter((x) => x.zone === 'inbox').length }}</span>
            </div>
            <div class="add-row">
              <input
                v-model="gameInputText"
                placeholder="写下脑海中占位置的事情……"
                @keydown.enter="addGameTask"
              />
              <button class="primary-btn" @click="addGameTask">加入</button>
            </div>
            <div
              class="drop-zone inbox-drop"
              @dragover.prevent
              @drop="onGameDrop('inbox', $event)"
            >
              <div
                v-for="item in strategyItems.filter((x) => x.zone === 'inbox')"
                :key="item.id"
                class="todo-card"
                draggable="true"
                @dragstart="onGameDragStart(item, $event)"
              >
                <GripVertical :size="14" class="handle" />
                <span class="todo-text">{{ item.text }}</span>
                <button class="del-btn" @click="removeGameTask(item.id)">×</button>
              </div>
            </div>
          </div>

          <!-- 3 个决策分类列 -->
          <div class="decision-columns">
            <div class="decision-col must" @dragover.prevent @drop="onGameDrop('must', $event)">
              <div class="col-head">
                <h3>必须完成</h3>
                <span class="count-badge">{{ strategyItems.filter((x) => x.zone === 'must').length }}</span>
              </div>
              <small>不处理会造成明确后果，近期必须推进。</small>
              <div class="col-items">
                <div
                  v-for="item in strategyItems.filter((x) => x.zone === 'must')"
                  :key="item.id"
                  class="todo-card"
                  draggable="true"
                  @dragstart="onGameDragStart(item, $event)"
                >
                  <GripVertical :size="14" class="handle" />
                  <span class="todo-text">{{ item.text }}</span>
                  <button class="del-btn" @click="removeGameTask(item.id)">×</button>
                </div>
              </div>
            </div>

            <div class="decision-col later" @dragover.prevent @drop="onGameDrop('later', $event)">
              <div class="col-head">
                <h3>可延期</h3>
                <span class="count-badge">{{ strategyItems.filter((x) => x.zone === 'later').length }}</span>
              </div>
              <small>重要，但目前可以等一等。</small>
              <div class="col-items">
                <div
                  v-for="item in strategyItems.filter((x) => x.zone === 'later')"
                  :key="item.id"
                  class="todo-card"
                  draggable="true"
                  @dragstart="onGameDragStart(item, $event)"
                >
                  <GripVertical :size="14" class="handle" />
                  <span class="todo-text">{{ item.text }}</span>
                  <button class="del-btn" @click="removeGameTask(item.id)">×</button>
                </div>
              </div>
            </div>

            <div class="decision-col calm" @dragover.prevent @drop="onGameDrop('calm', $event)">
              <div class="col-head">
                <h3>别担心</h3>
                <span class="count-badge">{{ strategyItems.filter((x) => x.zone === 'calm').length }}</span>
              </div>
              <small>记录已经足够，暂时不必再消耗精力。</small>
              <div class="col-items">
                <div
                  v-for="item in strategyItems.filter((x) => x.zone === 'calm')"
                  :key="item.id"
                  class="todo-card"
                  draggable="true"
                  @dragstart="onGameDragStart(item, $event)"
                >
                  <GripVertical :size="14" class="handle" />
                  <span class="todo-text">{{ item.text }}</span>
                  <button class="del-btn" @click="removeGameTask(item.id)">×</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 2. 游戏人生日历视图 -->
      <section v-else class="calendar-view">
        <div class="calendar-grid">
          <!-- 左侧：12个月年度日历滚动 -->
          <div class="months-scroll">
            <div class="selection-helper">
              <span>
                {{
                  selStart
                    ? `已选 ${dateText(selStart)}${selEnd && selEnd !== selStart ? ' — ' + dateText(selEnd) : ''}`
                    : '点击一天查看日程；再点一天可选择连续日期。将右侧事项拖到日期排时间。'
                }}
              </span>
              <button v-if="selStart" class="clear-btn" @click="clearDateSelection">清除选择</button>
            </div>

            <div class="months-wrapper">
              <div v-for="m in 12" :key="m" class="month-box">
                <div class="month-title">
                  <strong>{{ m }} 月</strong>
                  <button
                    class="month-action-link"
                    @click="
                      selectedMonthKey = `${currentYear}-${String(m).padStart(2, '0')}`
                    "
                  >
                    写本月任务 →
                  </button>
                </div>
                <div class="weekdays">
                  <span>日</span><span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span>六</span>
                </div>
                <div class="dates-grid">
                  <!-- 前置留白 -->
                  <div
                    v-for="n in new Date(currentYear, m - 1, 1).getDay()"
                    :key="'empty-' + n"
                    class="date-cell empty"
                  ></div>

                  <!-- 当月日期 -->
                  <div
                    v-for="d in new Date(currentYear, m, 0).getDate()"
                    :key="d"
                    class="date-cell"
                    :class="{
                      today: dateKey(currentYear, m - 1, d) === dateKey(today.getFullYear(), today.getMonth(), today.getDate()),
                      selected: dateKey(currentYear, m - 1, d) === selectedDay,
                      inrange:
                        selStart &&
                        selEnd &&
                        dateKey(currentYear, m - 1, d) >= (selStart < selEnd ? selStart : selEnd) &&
                        dateKey(currentYear, m - 1, d) <= (selStart < selEnd ? selEnd : selStart),
                    }"
                    @click="onDateClick(dateKey(currentYear, m - 1, d))"
                    @dragover.prevent
                    @drop="onDateDrop(dateKey(currentYear, m - 1, d), $event)"
                  >
                    <span class="date-num">{{ d }}</span>

                    <!-- 连续日期标记背景与圆点 -->
                    <div
                      v-if="marksOnDate(dateKey(currentYear, m - 1, d)).length"
                      class="mark-bg"
                      :style="{ background: marksBackground(marksOnDate(dateKey(currentYear, m - 1, d))) }"
                    ></div>
                    <div v-if="marksOnDate(dateKey(currentYear, m - 1, d)).length" class="mark-dots">
                      <i
                        v-for="mark in marksOnDate(dateKey(currentYear, m - 1, d))"
                        :key="mark.id"
                        :style="{ background: mark.color }"
                      ></i>
                    </div>

                    <!-- 当天日程摘要 -->
                    <div class="day-events-preview">
                      <span
                        v-for="ev in sortedEventsOnDate(dateKey(currentYear, m - 1, d)).slice(0, 2)"
                        :key="ev.id"
                        class="event-chip"
                        :class="{ completed: ev.completed }"
                        @click.stop="openEventModal(ev.date, ev)"
                      >
                        {{ ev.completed ? '✓' : '' }} {{ ev.start }} {{ ev.title }}
                      </span>
                      <small
                        v-if="sortedEventsOnDate(dateKey(currentYear, m - 1, d)).length > 2"
                        class="more-events"
                      >
                        +{{ sortedEventsOnDate(dateKey(currentYear, m - 1, d)).length - 2 }}
                      </small>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 右侧：待安排托盘、当天日程、连续标注、总/月任务 -->
          <aside class="cal-right-pane">
            <!-- 待安排事项托盘 -->
            <div class="side-card">
              <div class="card-head-sm">
                <h4>待安排事项</h4>
                <span class="count-badge">{{ activeWorkspace?.data.tray.length || 0 }}</span>
              </div>
              <p class="panel-hint">先记在这里。拖拽到左侧日期即可安排几点开始、几点结束。</p>
              <div class="add-row">
                <input
                  v-model="trayInputText"
                  placeholder="例如：整理课程笔记"
                  @keydown.enter="addTrayItem"
                />
                <button class="primary-btn" @click="addTrayItem">加入</button>
              </div>
              <div class="tray-list">
                <div
                  v-for="item in activeWorkspace?.data.tray"
                  :key="item.id"
                  class="todo-card"
                  draggable="true"
                  @dragstart="
                    dragData = { kind: 'schedule', source: 'tray', id: item.id, text: item.text }
                  "
                >
                  <GripVertical :size="14" class="handle" />
                  <span class="todo-text">{{ item.text }}</span>
                  <button class="del-btn" @click="removeTrayItem(item.id)">×</button>
                </div>
              </div>
            </div>

            <!-- 当天日程详情 -->
            <div class="side-card">
              <div class="card-head-sm">
                <div>
                  <h4>当天学习任务</h4>
                  <small v-if="selectedDay && sortedEventsOnDate(selectedDay).length" class="day-progress-text">
                    已完成 {{ completedEventsOnDate(selectedDay) }}/{{ sortedEventsOnDate(selectedDay).length }}
                  </small>
                </div>
                <span class="tag-badge">{{ selectedDay ? dateText(selectedDay) : '未选择' }}</span>
              </div>
              <div v-if="selectedDay" class="day-schedule">
                <div v-if="sortedEventsOnDate(selectedDay).length" class="day-progress-track">
                  <span :style="{ width: completionPercentOnDate(selectedDay) + '%' }"></span>
                </div>
                <div
                  v-for="ev in sortedEventsOnDate(selectedDay)"
                  :key="ev.id"
                  class="event-row"
                  :class="[`priority-${ev.priority || 'medium'}`, { completed: ev.completed }]"
                  @click="openEventModal(selectedDay, ev)"
                >
                  <button
                    class="event-check"
                    :class="{ checked: ev.completed }"
                    :title="ev.completed ? '标记为未完成' : '标记为已完成'"
                    @click="toggleEventCompleted(ev, $event)"
                  >
                    <CheckCircle2 v-if="ev.completed" :size="16" />
                    <span v-else></span>
                  </button>
                  <div class="event-content">
                    <div class="event-time">
                      {{ ev.start }}{{ ev.end ? '–' + ev.end : '' }}
                      <span v-if="ev.estimated_minutes">· {{ ev.estimated_minutes }} 分钟</span>
                    </div>
                    <div class="event-title">{{ ev.title }}</div>
                    <div v-if="ev.category || ev.note" class="event-meta">
                      <span v-if="ev.category" class="category-pill">{{ ev.category }}</span>
                      <span v-if="ev.note" class="event-note">{{ ev.note }}</span>
                    </div>
                  </div>
                </div>
                <p v-if="!sortedEventsOnDate(selectedDay).length" class="panel-hint empty-day-hint">
                  这一天还没有学习任务，可以单独添加或批量导入计划。
                </p>
                <button
                  class="outline-action"
                  style="width: 100%; margin-top: 8px"
                  @click="openEventModal(selectedDay)"
                >
                  ＋ 安排这一天
                </button>
              </div>
              <p v-else class="panel-hint">点击日历中的某一天查看或添加日程</p>
            </div>

            <!-- 连续日期标注 -->
            <div class="side-card">
              <div class="card-head-sm">
                <h4>连续日期标注</h4>
                <span class="tag-badge">{{ selStart ? '已选时段' : '未选择' }}</span>
              </div>
              <p class="panel-hint">适合考试周、项目突击、旅行；多重标注颜色会层叠显示。</p>
              <div class="colors-row">
                <button
                  v-for="c in COLORS"
                  :key="c"
                  class="color-dot"
                  :class="{ active: selectedMarkColor === c }"
                  :style="{ background: c }"
                  @click="selectedMarkColor = c"
                ></button>
              </div>
              <textarea v-model="markInputText" placeholder="写下连续几天的标注事件……"></textarea>
              <button
                class="primary-btn"
                style="width: 100%; margin-top: 8px"
                @click="saveDateMark"
              >
                标记日期
              </button>
            </div>

            <!-- 总任务与月份任务 -->
            <div class="side-card">
              <div class="card-head-sm">
                <h4>总任务清单</h4>
                <span class="count-badge">{{ activeWorkspace?.data.global.length || 0 }}</span>
              </div>
              <div class="add-row">
                <input
                  v-model="globalInputText"
                  placeholder="长期目标与任务……"
                  @keydown.enter="addGlobalTask"
                />
                <button class="primary-btn" @click="addGlobalTask">＋</button>
              </div>
              <div class="tasks-mini-list">
                <div
                  v-for="t in activeWorkspace?.data.global"
                  :key="t.id"
                  class="task-mini-card"
                  draggable="true"
                  @dragstart="
                    dragData = { kind: 'schedule', source: 'global', id: t.id, text: t.text }
                  "
                >
                  <span>{{ t.text }}</span>
                  <button class="del-btn" @click="removeTaskCard('global', t.id)">×</button>
                </div>
              </div>
            </div>

            <!-- 月份任务 -->
            <div class="side-card">
              <div class="card-head-sm">
                <h4>月份任务</h4>
                <select v-model="selectedMonthKey" class="month-select">
                  <option v-for="m in 12" :key="m" :value="`${currentYear}-${String(m).padStart(2, '0')}`">
                    {{ currentYear }} 年 {{ m }} 月
                  </option>
                </select>
              </div>
              <div class="add-row">
                <input
                  v-model="monthInputText"
                  placeholder="当月计划……"
                  @keydown.enter="addMonthTask"
                />
                <button class="primary-btn" @click="addMonthTask">＋</button>
              </div>
              <div class="tasks-mini-list">
                <div
                  v-for="t in activeWorkspace?.data.monthly.filter((x) => x.month === selectedMonthKey)"
                  :key="t.id"
                  class="task-mini-card"
                  draggable="true"
                  @dragstart="
                    dragData = { kind: 'schedule', source: 'monthly', id: t.id, text: t.text }
                  "
                >
                  <span>{{ t.text }}</span>
                  <button class="del-btn" @click="removeTaskCard('monthly', t.id)">×</button>
                </div>
              </div>
            </div>
          </aside>
        </div>
      </section>
    </main>

    <!-- 新建/编辑日历弹窗 -->
    <div v-if="calendarModalOpen" class="modal-backdrop">
      <div class="cal-modal">
        <h3>{{ calendarEditing ? '日历设置' : '新建日历' }}</h3>
        <label class="modal-label">
          日历名称
          <input v-model="calendarNameInput" placeholder="例如：考研复习、生活日常" />
        </label>
        <div class="modal-label">
          主题颜色
          <div class="colors-row" style="margin-top: 8px">
            <button
              v-for="c in COLORS"
              :key="c"
              class="color-dot"
              :class="{ active: calendarColorInput === c }"
              :style="{ background: c }"
              @click="calendarColorInput = c"
            ></button>
          </div>
        </div>
        <div class="modal-actions">
          <button
            v-if="calendarEditing && workspaces.length > 1"
            class="danger-btn"
            @click="deleteCurrentCalendar"
          >
            删除此日历
          </button>
          <button class="secondary-btn" @click="calendarModalOpen = false">取消</button>
          <button class="primary-btn" @click="saveCalendarModal">保存</button>
        </div>
      </div>
    </div>

    <!-- 排期日程弹窗 -->
    <div v-if="eventModalOpen" class="modal-backdrop">
      <div class="cal-modal">
        <h3>{{ editingEventId ? '编辑日程' : '安排到这一天' }}</h3>
        <p class="modal-sub">{{ eventDateInput }}</p>
        <label class="modal-label">
          事项标题
          <input v-model="eventTitleInput" placeholder="写下要完成的事项…" />
        </label>
        <div class="time-inputs-row">
          <label class="modal-label">
            开始时间
            <input v-model="eventStartInput" type="time" />
          </label>
          <label class="modal-label">
            结束时间 (可选)
            <input v-model="eventEndInput" type="time" />
          </label>
        </div>
        <label class="modal-label">
          备注 (可选)
          <textarea v-model="eventNoteInput" rows="2" placeholder="地点、要求等…"></textarea>
        </label>
        <div class="modal-actions">
          <button v-if="editingEventId" class="danger-btn" @click="deleteEventModal">删除日程</button>
          <button class="secondary-btn" @click="eventModalOpen = false">取消</button>
          <button class="primary-btn" @click="saveEventModal">保存</button>
        </div>
      </div>
    </div>

    <!-- 学习计划批量导入弹窗 -->
    <div v-if="importModalOpen" class="modal-backdrop">
      <div class="cal-modal study-import-modal">
        <div class="modal-head-row">
          <div class="modal-title-box">
            <FileSpreadsheet :size="21" class="text-accent" />
            <div>
              <h3>一键导入学习计划</h3>
              <p class="modal-sub">把计划按日期拆成每天的小任务，完成状态会保存在当前日历。</p>
            </div>
          </div>
          <button class="close-btn" @click="importModalOpen = false"><X :size="16" /></button>
        </div>

        <div class="import-guide">
          <strong>支持 Excel、CSV、JSON</strong>
          <span>至少需要“日期”和“学习任务”两列；时间、分类、优先级、时长和备注可选。</span>
          <button class="template-btn" type="button" @click="downloadStudyPlanTemplate">
            <Download :size="14" /> 下载填写模板
          </button>
        </div>

        <label class="file-drop-zone">
          <Upload :size="24" />
          <strong>{{ importFileName || '选择学习计划文件' }}</strong>
          <span>{{ importFileName ? '可以重新选择其他文件' : '点击选择 .xlsx / .xls / .csv / .json' }}</span>
          <input
            ref="importFileInput"
            type="file"
            accept=".xlsx,.xls,.csv,.json"
            @change="handleStudyPlanFile"
          />
        </label>

        <div v-if="importedStudyTasks.length" class="import-summary">
          <div class="summary-stat">
            <strong>{{ importedStudyTasks.length }}</strong>
            <span>个有效任务</span>
          </div>
          <div class="summary-stat">
            <strong>{{ new Set(importedStudyTasks.map((task) => task.date)).size }}</strong>
            <span>个学习日</span>
          </div>
          <div class="summary-stat">
            <strong>{{ importedStudyTasks.filter((task) => task.priority === 'high').length }}</strong>
            <span>个高优先级</span>
          </div>
        </div>

        <div v-if="importedStudyTasks.length" class="import-preview">
          <div
            v-for="task in importedStudyTasks.slice(0, 8)"
            :key="task.id"
            class="preview-task"
          >
            <span class="preview-date">{{ task.date }}</span>
            <div>
              <strong>{{ task.title }}</strong>
              <small>{{ task.start }}{{ task.end ? `–${task.end}` : '' }}{{ task.category ? ` · ${task.category}` : '' }}</small>
            </div>
            <span class="priority-pill" :class="`priority-${task.priority}`">
              {{ task.priority === 'high' ? '高' : task.priority === 'low' ? '低' : '中' }}
            </span>
          </div>
          <p v-if="importedStudyTasks.length > 8" class="preview-more">
            还有 {{ importedStudyTasks.length - 8 }} 个任务将在确认后导入
          </p>
        </div>

        <div v-if="importWarnings.length" class="import-warnings">
          <strong>{{ importWarnings.length }} 条提示</strong>
          <span>{{ importWarnings.slice(0, 3).join('；') }}</span>
        </div>

        <div class="modal-actions">
          <button class="secondary-btn" @click="importModalOpen = false">取消</button>
          <button
            class="primary-btn import-confirm-btn"
            :disabled="!importedStudyTasks.length || importingPlan"
            @click="importStudyPlan"
          >
            <RefreshCw v-if="importingPlan" class="spin-icon" :size="14" />
            <Upload v-else :size="14" />
            {{ importingPlan ? '正在导入…' : `导入 ${importedStudyTasks.length || ''} 个任务` }}
          </button>
        </div>
      </div>
    </div>

    <!-- 同步课程表弹窗 -->
    <div v-if="syncModalOpen" class="modal-backdrop">
      <div class="cal-modal sync-courses-modal">
        <div class="modal-head-row">
          <div class="modal-title-box">
            <BookOpenText :size="20" class="text-accent" />
            <div>
              <h3>课程表同步导入</h3>
              <p class="modal-sub">将课程库排课安排（星期/时间）自动批量导入到日程或博弈论看板</p>
            </div>
          </div>
          <button class="close-btn" @click="syncModalOpen = false"><X :size="16" /></button>
        </div>

        <!-- 目标日历 -->
        <label class="modal-label">
          目标日历工作区
          <select v-model="syncForm.workspaceId">
            <option v-for="ws in workspaces" :key="ws.id" :value="ws.id">
              {{ ws.name }}
            </option>
          </select>
        </label>

        <!-- 同步起止日期范围与快捷标签 -->
        <div class="modal-label">
          <div class="range-head">
            <span>同步日期范围</span>
            <div class="quick-ranges">
              <button type="button" @click="setSyncQuickWeeks(4)">未来4周</button>
              <button type="button" @click="setSyncQuickWeeks(8)">未来8周</button>
              <button type="button" @click="setSyncQuickWeeks(16)">本学期(16周)</button>
            </div>
          </div>
          <div class="time-inputs-row">
            <input v-model="syncForm.startDate" type="date" />
            <input v-model="syncForm.endDate" type="date" />
          </div>
        </div>

        <!-- 同步目标 -->
        <div class="modal-label">
          同步目标选择
          <div class="sync-targets-box">
            <label class="checkbox-item">
              <input v-model="syncForm.syncToEvents" type="checkbox" />
              <div>
                <strong>生成具体日历日程（Events）</strong>
                <small>在所选时间跨度内，按每门课的周几和起止时间自动批量填入日历（自动防重）</small>
              </div>
            </label>
            <label class="checkbox-item">
              <input v-model="syncForm.syncToTray" type="checkbox" />
              <div>
                <strong>同步到日历待安排托盘（Tray）</strong>
                <small>作为待办事项卡片放入待安排列表，方便随时拖拽排期</small>
              </div>
            </label>
            <label class="checkbox-item">
              <input v-model="syncForm.syncToStrategy" type="checkbox" />
              <div>
                <strong>同步到博弈论看板收集箱（Inbox）</strong>
                <small>作为课程复习任务放入博弈论事情托盘，进行必须完成/可延期决策</small>
              </div>
            </label>
          </div>
        </div>

        <!-- 课程选择 -->
        <div class="modal-label">
          选择参与同步的课程 ({{ syncForm.courseIds.length }}/{{ availableCourses.length }})
          <div class="course-pick-box">
            <label v-for="c in availableCourses" :key="c.id" class="course-pick-item">
              <input v-model="syncForm.courseIds" type="checkbox" :value="c.id" />
              <span>{{ c.name }}</span>
              <small v-if="c.schedule.length">({{ c.schedule.length }}节课/周)</small>
              <small v-else class="text-muted">(暂未配置时段)</small>
            </label>
          </div>
        </div>

        <div class="modal-actions">
          <button class="secondary-btn" @click="syncModalOpen = false">取消</button>
          <button class="primary-btn" :disabled="syncingCourses" @click="submitSyncCourses">
            <RefreshCw v-if="syncingCourses" class="spin-icon" :size="14" />
            <ArrowRightLeft v-else :size="14" />
            {{ syncingCourses ? '正在同步...' : '开始导入' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.calendar-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  height: 100%;
  overflow: hidden;
  background: #f7f9fc;
}

.cal-sidebar {
  background: #141c2d;
  color: #f8fafc;
  display: flex;
  flex-direction: column;
  padding: 20px 14px;
  gap: 14px;
}

.cal-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 4px 10px;
}

.brand-avatar {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  display: grid;
  place-items: center;
  font-weight: 800;
  color: white;
  font-size: 16px;
}

.brand-title {
  font-size: 16px;
  font-weight: 750;
  letter-spacing: -0.02em;
}

.cal-nav {
  display: grid;
  gap: 6px;
}

.nav-tab {
  width: 100%;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: #b7c4d7;
  text-align: left;
  padding: 10px 12px;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  gap: 9px;
  align-items: center;
  cursor: pointer;
}

.nav-tab:hover {
  background: #25334c;
}

.nav-tab.active {
  background: #2b374e;
  color: #ffffff;
}

.workspace-list-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
  min-height: 0;
}

.section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: #8c9cb3;
  padding: 0 4px;
}

.add-btn {
  background: #ffffff;
  border: 0;
  border-radius: 6px;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 700;
  color: #24324b;
  cursor: pointer;
}

.workspaces-scroll {
  display: grid;
  gap: 4px;
  overflow-y: auto;
}

.workspace-item {
  display: flex;
  align-items: center;
  gap: 8px;
  background: transparent;
  color: #c0cce0;
  border: 0;
  padding: 9px 8px;
  border-radius: 8px;
  text-align: left;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.workspace-item:hover {
  background: #253148;
}

.workspace-item.active {
  background: #2b374e;
  color: #ffffff;
}

.ws-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.ws-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-tip {
  margin-top: auto;
  font-size: 10px;
  color: #72849e;
  line-height: 1.5;
  padding: 8px 4px 0;
}

.cal-main {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  overflow: hidden;
}

.cal-topbar {
  height: 60px;
  background: #ffffff;
  border-bottom: 1px solid var(--line);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  flex-shrink: 0;
}

.top-title {
  font-size: 17px;
  font-weight: 750;
  margin: 0;
}

.top-desc {
  font-size: 11px;
  color: var(--sub);
  margin: 2px 0 0;
}

.top-tools {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tool-btn {
  background: #ffffff;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.icon-btn {
  display: grid;
  place-items: center;
  padding: 6px;
}

.year-label {
  font-size: 13px;
  font-weight: 750;
  padding: 0 4px;
}

.edit-btn {
  display: flex;
  align-items: center;
  gap: 5px;
}

/* 博弈论看板 */
.game-view {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.game-container {
  max-width: 1200px;
  margin: 0 auto;
  display: grid;
  gap: 20px;
}

.inbox-panel {
  background: #ffffff;
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 16px;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.panel-head h3 {
  font-size: 14px;
  margin: 0;
}

.count-badge {
  background: #f1f4f8;
  color: #64748b;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
}

.add-row {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.add-row input {
  flex: 1;
  height: 36px;
  border: 1px solid #dce2ec;
  border-radius: 8px;
  padding: 0 10px;
  font-size: 12px;
}

.primary-btn {
  background: var(--accent);
  color: white;
  border: 0;
  border-radius: 8px;
  padding: 0 14px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.drop-zone {
  min-height: 60px;
  border: 1px dashed #d8e0eb;
  border-radius: 10px;
  padding: 8px;
  background: #fafbfe;
  display: grid;
  gap: 6px;
}

.decision-columns {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.decision-col {
  background: #ffffff;
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 14px;
  min-height: 360px;
  display: flex;
  flex-direction: column;
}

.decision-col.must {
  border-top: 3px solid #ef4444;
}

.decision-col.later {
  border-top: 3px solid #f59e0b;
}

.decision-col.calm {
  border-top: 3px solid #10b981;
}

.col-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.col-head h3 {
  font-size: 14px;
  margin: 0;
}

.decision-col small {
  font-size: 11px;
  color: var(--sub);
  margin-bottom: 12px;
}

.col-items {
  flex: 1;
  display: grid;
  gap: 6px;
  align-content: flex-start;
  min-height: 120px;
}

.todo-card {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 12px;
  cursor: grab;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
}

.handle {
  color: #94a3b8;
}

.todo-text {
  flex: 1;
  word-break: break-all;
}

.del-btn {
  border: 0;
  background: transparent;
  color: #94a3b8;
  font-size: 15px;
  cursor: pointer;
  padding: 0 4px;
}

.del-btn:hover {
  color: #ef4444;
}

/* 游戏人生日历 */
.calendar-view {
  flex: 1;
  overflow: hidden;
}

.calendar-grid {
  display: grid;
  grid-template-columns: 1fr 340px;
  height: 100%;
}

.months-scroll {
  overflow-y: auto;
  padding: 18px 24px 60px;
}

.selection-helper {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #64748b;
  margin-bottom: 16px;
  background: #ffffff;
  padding: 10px 14px;
  border-radius: 8px;
  border: 1px solid var(--line);
}

.clear-btn {
  border: 0;
  background: #edf2f7;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  cursor: pointer;
}

.months-wrapper {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.month-box {
  background: #ffffff;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02);
}

.month-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.month-title strong {
  font-size: 14px;
}

.month-action-link {
  border: 0;
  background: transparent;
  font-size: 11px;
  color: var(--accent);
  cursor: pointer;
}

.weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  text-align: center;
  font-size: 10px;
  color: #94a3b8;
  margin-bottom: 4px;
}

.dates-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
}

.date-cell {
  position: relative;
  min-height: 48px;
  border: 1px solid transparent;
  border-radius: 6px;
  padding: 3px;
  cursor: pointer;
  overflow: hidden;
}

.date-cell:hover {
  background: #f1f5f9;
}

.date-cell.today {
  outline: 2px solid #10b981;
  outline-offset: -2px;
}

.date-cell.selected {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}

.date-cell.inrange {
  background: rgba(98, 124, 247, 0.12);
}

.date-num {
  font-size: 10px;
  font-weight: 700;
  position: relative;
  z-index: 2;
}

.mark-bg {
  position: absolute;
  inset: 0;
  z-index: 1;
}

.mark-dots {
  position: absolute;
  top: 3px;
  right: 3px;
  display: flex;
  gap: 2px;
  z-index: 2;
}

.mark-dots i {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  display: block;
}

.day-events-preview {
  margin-top: 2px;
  display: grid;
  gap: 2px;
  position: relative;
  z-index: 2;
}

.event-chip {
  display: block;
  font-size: 8px;
  background: #ffffffd6;
  border-radius: 3px;
  padding: 1px 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #334155;
}

.event-chip.completed {
  color: #64748b;
  text-decoration: line-through;
  opacity: 0.72;
}

.more-events {
  font-size: 8px;
  color: var(--accent);
  font-weight: 700;
  padding-left: 2px;
}

/* 右侧栏 */
.cal-right-pane {
  background: #ffffff;
  border-left: 1px solid var(--line);
  overflow-y: auto;
  padding: 16px;
  display: grid;
  gap: 16px;
  align-content: flex-start;
}

.side-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px;
  background: #fafbfe;
}

.card-head-sm {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.card-head-sm h4 {
  font-size: 13px;
  margin: 0;
}

.panel-hint {
  font-size: 11px;
  color: #64748b;
  margin: 0 0 8px;
  line-height: 1.4;
}

.tag-badge {
  font-size: 10px;
  background: #e2e8f0;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 600;
}

.colors-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.color-dot {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid white;
  outline: 1px solid #cbd5e1;
  cursor: pointer;
}

.color-dot.active {
  outline: 2px solid #0f172a;
}

textarea {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 11px;
  resize: vertical;
}

.outline-action {
  border: 1px dashed #cbd5e1;
  background: white;
  border-radius: 6px;
  padding: 6px;
  font-size: 11px;
  cursor: pointer;
}

.day-schedule {
  display: grid;
  gap: 6px;
}

.day-progress-text {
  display: block;
  color: #64748b;
  font-size: 9px;
  margin-top: 2px;
}

.day-progress-track {
  height: 5px;
  overflow: hidden;
  border-radius: 999px;
  background: #e2e8f0;
  margin-bottom: 2px;
}

.day-progress-track span {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, var(--accent), #34d399);
  border-radius: inherit;
  transition: width 0.2s ease;
}

.event-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  background: white;
  border: 1px solid #e2e8f0;
  border-left: 3px solid var(--accent);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 11px;
  cursor: pointer;
}

.event-row.priority-high {
  border-left-color: #ef4444;
}

.event-row.priority-low {
  border-left-color: #94a3b8;
}

.event-row.completed {
  background: #f8fafc;
  opacity: 0.75;
}

.event-row.completed .event-title {
  color: #64748b;
  text-decoration: line-through;
}

.event-check {
  width: 20px;
  height: 20px;
  flex: 0 0 20px;
  display: grid;
  place-items: center;
  border: 0;
  background: transparent;
  color: #10b981;
  padding: 1px;
  cursor: pointer;
}

.event-check > span {
  width: 14px;
  height: 14px;
  border: 1.5px solid #cbd5e1;
  border-radius: 50%;
}

.event-content {
  min-width: 0;
  flex: 1;
}

.event-time {
  font-size: 10px;
  color: #64748b;
  font-weight: 600;
}

.event-title {
  margin-top: 2px;
  font-weight: 650;
  color: #1e293b;
  line-height: 1.35;
}

.event-meta {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 4px;
  min-width: 0;
}

.category-pill {
  flex: 0 0 auto;
  padding: 1px 5px;
  border-radius: 999px;
  background: #eef2ff;
  color: #4f46e5;
  font-size: 9px;
}

.event-note {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #64748b;
  font-size: 9px;
}

.empty-day-hint {
  padding: 10px 4px 2px;
  text-align: center;
}

.tasks-mini-list {
  display: grid;
  gap: 4px;
  margin-top: 6px;
}

.task-mini-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 5px 8px;
  font-size: 11px;
  cursor: grab;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.4);
  backdrop-filter: blur(2px);
  display: grid;
  place-items: center;
  z-index: 100;
  padding: 20px;
}

.cal-modal {
  background: #ffffff;
  border-radius: 12px;
  padding: 20px;
  width: 100%;
  max-width: 420px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.15);
}

.cal-modal h3 {
  margin: 0 0 6px;
  font-size: 16px;
}

.modal-sub {
  font-size: 12px;
  color: #64748b;
  margin: 0 0 14px;
}

.modal-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 12px;
}

.modal-label input,
.modal-label textarea {
  width: 100%;
  margin-top: 6px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 12px;
}

.time-inputs-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}

.danger-btn {
  margin-right: auto;
  border: 0;
  background: #fee2e2;
  color: #b91c1c;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
}

.secondary-btn {
  border: 1px solid #cbd5e1;
  background: white;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
}

/* 课程表同步相关样式 */
.sync-btn {
  background: var(--accentSoft, #eef2ff);
  color: var(--accent, #627cf7);
  border-color: rgba(98, 124, 247, 0.3);
  display: flex;
  align-items: center;
  gap: 5px;
}

.import-plan-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #0f766e;
  border-color: #99f6e4;
  background: #f0fdfa;
}

.import-plan-btn:hover {
  background: #ccfbf1;
}

.sync-btn:hover {
  background: var(--accent, #627cf7);
  color: white;
}

.sync-courses-modal {
  max-width: 520px;
}

.study-import-modal {
  max-width: 620px;
  max-height: calc(100vh - 40px);
  overflow-y: auto;
}

.import-guide {
  position: relative;
  display: grid;
  gap: 3px;
  padding: 11px 150px 11px 12px;
  border-radius: 8px;
  background: #f0fdfa;
  border: 1px solid #ccfbf1;
  color: #134e4a;
  margin-bottom: 12px;
}

.import-guide strong {
  font-size: 12px;
}

.import-guide span {
  font-size: 10px;
  line-height: 1.45;
}

.template-btn {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  gap: 5px;
  border: 1px solid #5eead4;
  background: white;
  color: #0f766e;
  border-radius: 6px;
  padding: 6px 9px;
  font-size: 10px;
  font-weight: 700;
  cursor: pointer;
}

.file-drop-zone {
  display: grid;
  place-items: center;
  gap: 5px;
  min-height: 120px;
  border: 1.5px dashed #94a3b8;
  border-radius: 10px;
  background: #f8fafc;
  color: #475569;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.file-drop-zone:hover {
  border-color: var(--accent);
  background: #f5f7ff;
}

.file-drop-zone strong {
  color: #1e293b;
  font-size: 12px;
}

.file-drop-zone span {
  font-size: 10px;
}

.file-drop-zone input {
  display: none;
}

.import-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-top: 12px;
}

.summary-stat {
  display: flex;
  align-items: baseline;
  gap: 5px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px 10px;
}

.summary-stat strong {
  font-size: 18px;
  color: var(--accent);
}

.summary-stat span {
  font-size: 10px;
  color: #64748b;
}

.import-preview {
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-top: 10px;
}

.preview-task {
  display: grid;
  grid-template-columns: 82px 1fr auto;
  gap: 9px;
  align-items: center;
  padding: 8px 10px;
  border-bottom: 1px solid #eef2f7;
}

.preview-task:last-child {
  border-bottom: 0;
}

.preview-date {
  color: #475569;
  font-size: 10px;
  font-variant-numeric: tabular-nums;
}

.preview-task div {
  min-width: 0;
}

.preview-task strong,
.preview-task small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-task strong {
  font-size: 11px;
  color: #1e293b;
}

.preview-task small {
  font-size: 9px;
  color: #64748b;
  margin-top: 2px;
}

.priority-pill {
  padding: 2px 6px;
  border-radius: 999px;
  background: #fef3c7;
  color: #92400e;
  font-size: 9px;
  font-weight: 700;
}

.priority-pill.priority-high {
  background: #fee2e2;
  color: #b91c1c;
}

.priority-pill.priority-low {
  background: #e2e8f0;
  color: #475569;
}

.preview-more {
  margin: 0;
  padding: 7px 10px;
  text-align: center;
  color: #64748b;
  background: #f8fafc;
  font-size: 10px;
}

.import-warnings {
  display: grid;
  gap: 2px;
  padding: 8px 10px;
  margin-top: 10px;
  border-radius: 7px;
  background: #fff7ed;
  color: #9a3412;
  font-size: 10px;
}

.import-confirm-btn {
  display: flex;
  align-items: center;
  gap: 5px;
}

.import-confirm-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.modal-head-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 14px;
}

.modal-title-box {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.modal-title-box h3 {
  margin: 0;
  font-size: 16px;
}

.close-btn {
  border: 0;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  padding: 4px;
}

.range-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.quick-ranges {
  display: flex;
  gap: 4px;
}

.quick-ranges button {
  border: 1px solid #cbd5e1;
  background: white;
  border-radius: 4px;
  font-size: 10px;
  padding: 2px 6px;
  color: #64748b;
  cursor: pointer;
}

.quick-ranges button:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.sync-targets-box {
  display: grid;
  gap: 8px;
  margin-top: 6px;
}

.checkbox-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #f8fafc;
  cursor: pointer;
}

.checkbox-item input {
  margin-top: 2px;
}

.checkbox-item strong {
  display: block;
  font-size: 12px;
  color: #1e293b;
}

.checkbox-item small {
  display: block;
  font-size: 10px;
  color: #64748b;
  line-height: 1.4;
}

.course-pick-box {
  max-height: 140px;
  overflow-y: auto;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 6px;
  display: grid;
  gap: 4px;
  background: #ffffff;
  margin-top: 6px;
}

.course-pick-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
}

.course-pick-item:hover {
  background: #f1f5f9;
}

.text-accent {
  color: var(--accent);
}

.text-muted {
  color: #94a3b8;
}

.spin-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
