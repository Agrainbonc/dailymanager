<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import {
  Calendar,
  Check,
  ChevronRight,
  ExternalLink,
  GitBranch,
  Layers,
  Maximize2,
  Minimize2,
  Minus,
  MoreVertical,
  Plus,
  Redo2,
  RotateCcw,
  Search,
  Sparkles,
  Trash2,
  Undo2,
  User,
  X,
} from '@lucide/vue'
import { api } from '../api'
import type {
  NodeOwner,
  NodeStatus,
  PriorityLevel,
  WorkflowEdge,
  WorkflowNode,
  WorkflowProject,
  WorkflowViewport,
} from '../types'

const emit = defineEmits<{
  (e: 'notify', msg: string, isError?: boolean): void
}>()

const palette = [
  { name: '雾紫', accent: '#a38abd', tint: '#f2edf8' },
  { name: '鼠尾草', accent: '#8ba492', tint: '#edf4ef' },
  { name: '杏桃', accent: '#c49d82', tint: '#faf1e9' },
  { name: '雾蓝', accent: '#899fb9', tint: '#edf2f8' },
  { name: '玫瑰', accent: '#bd8e9e', tint: '#f9eef2' },
  { name: '麦穗', accent: '#b5a16d', tint: '#f7f3e8' },
]

const NODE_W = 244
const NODE_H = 175

const flows = ref<WorkflowProject[]>([])
const activeFlowId = ref<string>('')
const loading = ref(true)

// 当前视图：'canvas' (任务画布) | 'timeline' (时间轴)
const activeView = ref<'canvas' | 'timeline'>('canvas')
const isFullscreen = ref(false)

// 视口与画布缩放平移
const viewport = ref<WorkflowViewport>({ x: 40, y: 40, z: 1.0 })
const canvasRef = ref<HTMLElement | null>(null)
const isPanning = ref(false)
const panStart = ref({ x: 0, y: 0 })

// 选中状态
const selectedNodeId = ref<string | null>(null)
const selectedEdgeId = ref<string | null>(null)
const connectionStartNodeId = ref<string | null>(null)

// 节点拖拽
const draggingNodeId = ref<string | null>(null)
const dragOffset = ref({ x: 0, y: 0 })

// 筛选与搜索
const searchQuery = ref('')
const filterStatus = ref<string>('all')

const activeFlow = computed(() => {
  return flows.value.find((f) => f.id === activeFlowId.value) || flows.value[0] || null
})

const selectedNode = computed(() => {
  if (!activeFlow.value || !selectedNodeId.value) return null
  return activeFlow.value.nodes.find((n) => n.id === selectedNodeId.value) || null
})

function generateUid() {
  return 'n' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
}

// --- 数据同步后端逻辑 ---

async function loadFlows() {
  loading.value = true
  try {
    const list = await api.workflows()
    flows.value = list
    if (list.length > 0) {
      const active = list.find((f) => f.is_active) || list[0]
      activeFlowId.value = active.id
      if (active.viewport && active.viewport.z) {
        viewport.value = { ...active.viewport }
      }
    }
  } catch (err) {
    emit('notify', err instanceof Error ? err.message : '加载任务流失败', true)
  } finally {
    loading.value = false
  }
}

let saveTimer: any = null
function queueSaveActiveFlow() {
  clearTimeout(saveTimer)
  saveTimer = setTimeout(async () => {
    const f = activeFlow.value
    if (!f) return
    try {
      await api.updateWorkflow(f.id, {
        name: f.name,
        description: f.description,
        color: f.color,
        viewport: viewport.value,
        nodes: f.nodes,
        edges: f.edges,
      })
    } catch (err) {
      emit('notify', '任务流保存失败', true)
    }
  }, 400)
}

// --- 节点与连线操作 ---

function addNode(title = '新任务节点', x?: number, y?: number) {
  const f = activeFlow.value
  if (!f) return
  const posX = x !== undefined ? x : 100 - viewport.value.x / viewport.value.z
  const posY = y !== undefined ? y : 100 - viewport.value.y / viewport.value.z

  const newNode: WorkflowNode = {
    id: generateUid(),
    title,
    description: '',
    x: Math.round(posX),
    y: Math.round(posY),
    color: 0,
    owner: 'self',
    assignee: '',
    urgency: 'medium',
    importance: 'medium',
    status: 'todo',
    start: '',
    end: '',
  }
  f.nodes.push(newNode)
  selectedNodeId.value = newNode.id
  queueSaveActiveFlow()
}

function removeSelectedNode() {
  const f = activeFlow.value
  if (!f || !selectedNodeId.value) return
  const nid = selectedNodeId.value
  f.nodes = f.nodes.filter((n) => n.id !== nid)
  f.edges = f.edges.filter((e) => e.from !== nid && e.to !== nid)
  selectedNodeId.value = null
  queueSaveActiveFlow()
}

function toggleNodeStatus(node: WorkflowNode) {
  node.status = node.status === 'done' ? 'todo' : 'done'
  queueSaveActiveFlow()
}

function createBranchFrom(node: WorkflowNode) {
  const f = activeFlow.value
  if (!f) return
  const newNodeId = generateUid()
  const newNode: WorkflowNode = {
    id: newNodeId,
    title: '后续分支任务',
    description: '',
    x: node.x + 310,
    y: node.y,
    color: (node.color + 1) % palette.length,
    owner: 'self',
    assignee: '',
    urgency: 'medium',
    importance: 'medium',
    status: 'todo',
    start: '',
    end: '',
  }
  f.nodes.push(newNode)
  f.edges.push({
    id: 'e-' + Date.now().toString(36),
    from: node.id,
    to: newNodeId,
    label: '',
  })
  selectedNodeId.value = newNodeId
  queueSaveActiveFlow()
}

function startConnection(nodeId: string) {
  connectionStartNodeId.value = nodeId
  emit('notify', '请点击目标任务左侧端口完成连线，点击画布空白取消')
}

function endConnection(targetNodeId: string) {
  const f = activeFlow.value
  if (!f || !connectionStartNodeId.value || connectionStartNodeId.value === targetNodeId) {
    connectionStartNodeId.value = null
    return
  }
  const from = connectionStartNodeId.value
  const to = targetNodeId
  // 避免重复连线
  if (!f.edges.some((e) => e.from === from && e.to === to)) {
    f.edges.push({
      id: 'e-' + Date.now().toString(36),
      from,
      to,
      label: '',
    })
    queueSaveActiveFlow()
  }
  connectionStartNodeId.value = null
}

function removeSelectedEdge() {
  const f = activeFlow.value
  if (!f || !selectedEdgeId.value) return
  f.edges = f.edges.filter((e) => e.id !== selectedEdgeId.value)
  selectedEdgeId.value = null
  queueSaveActiveFlow()
}

// 连线贝塞尔路径计算
function calcEdgeGeometry(edge: WorkflowEdge) {
  const f = activeFlow.value
  if (!f) return null
  const a = f.nodes.find((n) => n.id === edge.from)
  const b = f.nodes.find((n) => n.id === edge.to)
  if (!a || !b) return null

  const x1 = a.x + NODE_W
  const y1 = a.y + NODE_H / 2
  const x2 = b.x
  const y2 = b.y + NODE_H / 2
  const bend = Math.max(70, Math.abs(x2 - x1) * 0.45)

  return {
    d: `M${x1},${y1} C${x1 + bend},${y1} ${x2 - bend},${y2} ${x2},${y2}`,
    labelX: (x1 + x2) / 2,
    labelY: (y1 + y2) / 2 - 8,
  }
}

// --- 画布缩放平移交互 ---

function onCanvasMouseDown(e: MouseEvent) {
  // 检查是否点击在节点或按钮上
  const target = e.target as HTMLElement
  if (target.closest('.node-card') || target.closest('.inspector-drawer') || target.closest('.controls-bar')) {
    return
  }
  selectedNodeId.value = null
  selectedEdgeId.value = null
  connectionStartNodeId.value = null

  isPanning.value = true
  panStart.value = { x: e.clientX - viewport.value.x, y: e.clientY - viewport.value.y }
}

function onCanvasMouseMove(e: MouseEvent) {
  if (draggingNodeId.value) {
    const f = activeFlow.value
    if (!f) return
    const n = f.nodes.find((x) => x.id === draggingNodeId.value)
    if (n) {
      n.x = Math.round((e.clientX - dragOffset.value.x) / viewport.value.z)
      n.y = Math.round((e.clientY - dragOffset.value.y) / viewport.value.z)
    }
    return
  }

  if (isPanning.value) {
    viewport.value.x = e.clientX - panStart.value.x
    viewport.value.y = e.clientY - panStart.value.y
  }
}

function onCanvasMouseUp() {
  if (draggingNodeId.value) {
    draggingNodeId.value = null
    queueSaveActiveFlow()
  }
  if (isPanning.value) {
    isPanning.value = false
    queueSaveActiveFlow()
  }
}

function onCanvasWheel(e: WheelEvent) {
  e.preventDefault()
  const zoomFactor = e.deltaY < 0 ? 1.08 : 0.92
  const newZ = Math.max(0.3, Math.min(2.0, viewport.value.z * zoomFactor))

  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) return
  const mouseX = e.clientX - rect.left
  const mouseY = e.clientY - rect.top

  viewport.value.x = mouseX - ((mouseX - viewport.value.x) * newZ) / viewport.value.z
  viewport.value.y = mouseY - ((mouseY - viewport.value.y) * newZ) / viewport.value.z
  viewport.value.z = newZ
  queueSaveActiveFlow()
}

function startNodeDrag(node: WorkflowNode, e: MouseEvent) {
  selectedNodeId.value = node.id
  draggingNodeId.value = node.id
  dragOffset.value = {
    x: e.clientX - node.x * viewport.value.z,
    y: e.clientY - node.y * viewport.value.z,
  }
}

function fitBoard() {
  const f = activeFlow.value
  if (!f || !f.nodes.length) {
    viewport.value = { x: 40, y: 40, z: 1.0 }
    return
  }
  const xs = f.nodes.map((n) => n.x)
  const ys = f.nodes.map((n) => n.y)
  const minX = Math.min(...xs) - 60
  const minY = Math.min(...ys) - 60
  const maxX = Math.max(...xs) + NODE_W + 60
  const maxY = Math.max(...ys) + NODE_H + 60
  const w = maxX - minX
  const h = maxY - minY

  const clientW = canvasRef.value?.clientWidth || 900
  const clientH = canvasRef.value?.clientHeight || 600

  const z = Math.max(0.4, Math.min(1.2, Math.min(clientW / w, clientH / h)))
  viewport.value = {
    x: (clientW - w * z) / 2 - minX * z,
    y: (clientH - h * z) / 2 - minY * z,
    z,
  }
  queueSaveActiveFlow()
}

async function createNewFlow() {
  const name = prompt('请输入新任务流名称：', '新研究课题规划')
  if (!name || !name.trim()) return
  try {
    const created = await api.createWorkflow({
      name: name.trim(),
      description: '把想法连接起来，让下一步变得清晰。',
      color: flows.value.length % palette.length,
      is_active: true,
      nodes: [],
      edges: [],
    })
    flows.value.push(created)
    activeFlowId.value = created.id
    viewport.value = { x: 40, y: 40, z: 1.0 }
    emit('notify', `任务流“${created.name}”已创建`)
  } catch (err) {
    emit('notify', '创建任务流失败', true)
  }
}

onMounted(() => {
  loadFlows()
})
</script>

<template>
  <div class="workflow-layout" :class="{ fullscreen: isFullscreen }">
    <!-- 侧边任务流列表 -->
    <aside v-if="!isFullscreen" class="flow-sidebar">
      <div class="sidebar-head">
        <div class="symbol-box">有</div>
        <div>
          <h3>有绪 · 任务流</h3>
          <small>让思路，有迹可循</small>
        </div>
      </div>

      <div class="flow-list-section">
        <div class="flow-section-label">
          <span>我的任务流</span>
          <button class="icon-add-btn" title="新建任务流" @click="createNewFlow">＋</button>
        </div>

        <div class="flow-items">
          <button
            v-for="f in flows"
            :key="f.id"
            class="flow-nav-item"
            :class="{ active: f.id === activeFlowId }"
            @click="activeFlowId = f.id"
          >
            <span class="flow-dot" :style="{ background: palette[f.color]?.accent || '#a38abd' }"></span>
            <div class="flow-meta-box">
              <span class="flow-title">{{ f.name }}</span>
              <small>{{ f.nodes.length }} 个节点 · {{ f.nodes.filter((n) => n.status === 'done').length }} 完成</small>
            </div>
          </button>
        </div>
      </div>

      <div class="sidebar-quote">
        <strong>一次，向前一小步</strong>
        <p>不必一次理清所有事。把复杂目标拆解成可以出发的下一步。</p>
      </div>
    </aside>

    <!-- 工作流主画布区 -->
    <main class="workflow-main">
      <header class="wf-topbar">
        <div class="topbar-info">
          <h2>{{ activeFlow?.name || '任务工作流' }}</h2>
          <div class="stats-row">
            <span>总任务 <b>{{ activeFlow?.nodes.length || 0 }}</b></span>
            <span>进行中 <b>{{ activeFlow?.nodes.filter((n) => n.status === 'doing').length || 0 }}</b></span>
            <span>已完成 <b>{{ activeFlow?.nodes.filter((n) => n.status === 'done').length || 0 }}</b></span>
          </div>
        </div>

        <div class="topbar-controls">
          <div class="view-switch-pills">
            <button :class="{ active: activeView === 'canvas' }" @click="activeView = 'canvas'">任务画布</button>
            <button :class="{ active: activeView === 'timeline' }" @click="activeView = 'timeline'">时间安排</button>
          </div>

          <button class="secondary-btn" @click="isFullscreen = !isFullscreen">
            <component :is="isFullscreen ? Minimize2 : Maximize2" :size="15" />
            {{ isFullscreen ? '退出全屏' : '全屏画布' }}
          </button>

          <button class="primary-btn" @click="addNode()">
            <Plus :size="16" /> 添加任务
          </button>
        </div>
      </header>

      <!-- 画布舞台 -->
      <div v-show="activeView === 'canvas'" class="stage-container">
        <div
          ref="canvasRef"
          class="canvas-viewport"
          :class="{ grabbing: isPanning || draggingNodeId }"
          @mousedown="onCanvasMouseDown"
          @mousemove="onCanvasMouseMove"
          @mouseup="onCanvasMouseUp"
          @wheel="onCanvasWheel"
        >
          <!-- 世界坐标容器 -->
          <div
            class="canvas-world"
            :style="{
              transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.z})`,
            }"
          >
            <!-- SVG 贝塞尔连线层 -->
            <svg class="svg-connections">
              <defs>
                <marker
                  id="wf-arrow"
                  viewBox="0 0 10 10"
                  refX="9"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto"
                >
                  <path d="M 0 1 L 9 5 L 0 9 z" fill="#c3bacf" />
                </marker>
              </defs>

              <g
                v-for="edge in activeFlow?.edges"
                :key="edge.id"
                class="edge-group"
                @click.stop="selectedEdgeId = edge.id"
              >
                <path
                  v-if="calcEdgeGeometry(edge)"
                  :d="calcEdgeGeometry(edge)!.d"
                  class="edge-path"
                  :class="{ selected: selectedEdgeId === edge.id }"
                  marker-end="url(#wf-arrow)"
                />
                <!-- 粗热区便于点击 -->
                <path
                  v-if="calcEdgeGeometry(edge)"
                  :d="calcEdgeGeometry(edge)!.d"
                  class="edge-hit-area"
                />
              </g>
            </svg>

            <!-- 节点卡片列表 -->
            <div
              v-for="(node, idx) in activeFlow?.nodes"
              :key="node.id"
              class="node-card"
              :class="[
                node.status,
                {
                  selected: selectedNodeId === node.id,
                  connecting: connectionStartNodeId === node.id,
                },
              ]"
              :style="{
                left: `${node.x}px`,
                top: `${node.y}px`,
                '--accent': palette[node.color]?.accent || '#a38abd',
                '--tint': palette[node.color]?.tint || '#f2edf8',
              }"
              @mousedown.stop="startNodeDrag(node, $event)"
              @click.stop="selectedNodeId = node.id"
            >
              <!-- 左侧输入连接桩 -->
              <button
                class="port-dot in"
                title="连接到此节点"
                @click.stop="endConnection(node.id)"
              ></button>

              <div class="node-header">
                <span class="node-badge">
                  <i class="badge-square"></i>
                  {{ node.importance === 'high' ? '关键任务' : '工作节点' }}
                </span>
                <span class="node-idx">{{ String(idx + 1).padStart(2, '0') }}</span>
              </div>

              <div class="node-body">
                <div class="node-title-row">
                  <button
                    class="status-circle-btn"
                    :class="{ done: node.status === 'done' }"
                    @click.stop="toggleNodeStatus(node)"
                  >
                    <Check v-if="node.status === 'done'" :size="12" />
                  </button>
                  <strong class="node-title-text">{{ node.title }}</strong>
                </div>

                <p class="node-desc">{{ node.description || '点击补充此任务的具体内容…' }}</p>

                <div class="tags-row">
                  <span v-if="node.owner === 'delegate'" class="tag delegate">
                    <User :size="10" /> {{ node.assignee || '他人协作' }}
                  </span>
                  <span v-if="node.urgency === 'high'" class="tag urgent">紧急</span>
                  <span v-if="node.importance === 'high'" class="tag important">重要</span>
                </div>
              </div>

              <div class="node-footer">
                <span class="date-meta">
                  <Calendar :size="11" />
                  {{ node.start || node.end ? `${node.start} ~ ${node.end}` : '待排期' }}
                </span>
                <span class="status-name">{{ node.status === 'done' ? '已完成' : node.status === 'doing' ? '进行中' : '待开始' }}</span>
              </div>

              <!-- 右侧输出连接桩 -->
              <button
                class="port-dot out"
                title="连线出发点"
                @click.stop="startConnection(node.id)"
              ></button>

              <!-- 右侧快捷新建后续分支按钮 -->
              <button
                class="branch-add-btn"
                title="快速新增后续分支"
                @click.stop="createBranchFrom(node)"
              >
                <Plus :size="13" />
              </button>
            </div>
          </div>
        </div>

        <!-- 连线选中删除浮条 -->
        <div v-if="selectedEdgeId" class="edge-tip-bar">
          <span>已选中任务连线</span>
          <button class="del-edge-btn" @click="removeSelectedEdge">删除此连线</button>
        </div>

        <!-- 底栏缩放平移控制器 -->
        <div class="controls-bar">
          <button class="ctrl-btn" title="缩小" @click="viewport.z = Math.max(0.3, viewport.z - 0.1); queueSaveActiveFlow()">
            <Minus :size="14" />
          </button>
          <span class="zoom-text">{{ Math.round(viewport.z * 100) }}%</span>
          <button class="ctrl-btn" title="放大" @click="viewport.z = Math.min(2.0, viewport.z + 0.1); queueSaveActiveFlow()">
            <Plus :size="14" />
          </button>
          <button class="ctrl-btn fit-btn" title="自适应视野" @click="fitBoard">适应画布</button>
        </div>

        <!-- 节点属性抽屉 (Inspector) -->
        <aside v-if="selectedNode" class="inspector-drawer">
          <div class="drawer-head">
            <h4>任务节点详情</h4>
            <button class="close-btn" @click="selectedNodeId = null"><X :size="16" /></button>
          </div>

          <div class="drawer-body">
            <label class="drawer-field">
              任务标题
              <input v-model="selectedNode.title" @input="queueSaveActiveFlow" />
            </label>

            <label class="drawer-field">
              详细描述 / 备注
              <textarea
                v-model="selectedNode.description"
                rows="3"
                placeholder="研究背景、预期产出、关键难点…"
                @input="queueSaveActiveFlow"
              ></textarea>
            </label>

            <div class="drawer-field">
              节点色调
              <div class="palette-swatches">
                <button
                  v-for="(p, i) in palette"
                  :key="i"
                  class="color-chip"
                  :class="{ active: selectedNode.color === i }"
                  :style="{ background: p.accent }"
                  @click="selectedNode.color = i; queueSaveActiveFlow()"
                ></button>
              </div>
            </div>

            <div class="drawer-field">
              执行状态
              <select v-model="selectedNode.status" @change="queueSaveActiveFlow">
                <option value="todo">待开始</option>
                <option value="doing">进行中</option>
                <option value="done">已完成</option>
              </select>
            </div>

            <div class="row-fields">
              <label class="drawer-field">
                紧急程度
                <select v-model="selectedNode.urgency" @change="queueSaveActiveFlow">
                  <option value="low">常规</option>
                  <option value="medium">一般</option>
                  <option value="high">高急</option>
                </select>
              </label>

              <label class="drawer-field">
                重要程度
                <select v-model="selectedNode.importance" @change="queueSaveActiveFlow">
                  <option value="low">一般</option>
                  <option value="medium">重要</option>
                  <option value="high">核心里程碑</option>
                </select>
              </label>
            </div>

            <div class="row-fields">
              <label class="drawer-field">
                计划开始
                <input v-model="selectedNode.start" type="date" @change="queueSaveActiveFlow" />
              </label>
              <label class="drawer-field">
                计划结束
                <input v-model="selectedNode.end" type="date" @change="queueSaveActiveFlow" />
              </label>
            </div>
          </div>

          <div class="drawer-foot">
            <button class="delete-node-btn" @click="removeSelectedNode">
              <Trash2 :size="14" /> 删除此任务
            </button>
          </div>
        </aside>
      </div>

      <!-- 时间安排视图 (Timeline) -->
      <div v-show="activeView === 'timeline'" class="timeline-container">
        <div class="timeline-intro">
          <h3>项目排期进度与里程碑</h3>
          <p>按起止时间线展现各项关键研究与论文推进节点</p>
        </div>

        <div class="timeline-list">
          <div
            v-for="node in activeFlow?.nodes"
            :key="node.id"
            class="timeline-card"
            :style="{ '--accent': palette[node.color]?.accent || '#a38abd' }"
          >
            <div class="tl-date-col">
              <strong>{{ node.start || node.end || '未排期' }}</strong>
            </div>
            <div class="tl-content-col">
              <h4>{{ node.title }}</h4>
              <p>{{ node.description || '无详细描述' }}</p>
            </div>
            <div class="tl-status-col">
              <span class="status-badge" :class="node.status">{{ node.status === 'done' ? '已完成' : node.status === 'doing' ? '进行中' : '待处理' }}</span>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.workflow-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  height: 100%;
  overflow: hidden;
  background: #faf9f6;
}

.workflow-layout.fullscreen {
  grid-template-columns: 1fr;
}

.flow-sidebar {
  background: #f7f6f3;
  border-right: 1px solid #e7e6e5;
  display: flex;
  flex-direction: column;
  padding: 22px 14px;
  gap: 16px;
}

.sidebar-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 4px;
}

.symbol-box {
  width: 32px;
  height: 32px;
  border-radius: 9px;
  background: #7460b9;
  color: white;
  display: grid;
  place-items: center;
  font-weight: 750;
  font-size: 16px;
}

.sidebar-head h3 {
  font-size: 15px;
  margin: 0;
  color: #292c37;
}

.sidebar-head small {
  font-size: 10px;
  color: #92939e;
}

.flow-list-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.flow-section-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: #9c99a4;
  margin-bottom: 8px;
  padding: 0 4px;
}

.icon-add-btn {
  border: 0;
  background: transparent;
  font-size: 14px;
  color: #7460b9;
  cursor: pointer;
}

.flow-items {
  display: grid;
  gap: 4px;
  overflow-y: auto;
}

.flow-nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  background: transparent;
  border: 0;
  border-radius: 8px;
  padding: 8px 10px;
  text-align: left;
  cursor: pointer;
}

.flow-nav-item:hover {
  background: #eae8e3;
}

.flow-nav-item.active {
  background: #ebe6f5;
  color: #66529f;
}

.flow-dot {
  width: 8px;
  height: 8px;
  border-radius: 3px;
  flex-shrink: 0;
}

.flow-meta-box {
  flex: 1;
  overflow: hidden;
}

.flow-title {
  display: block;
  font-size: 12px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.flow-meta-box small {
  display: block;
  font-size: 10px;
  color: #a09aa9;
  margin-top: 2px;
}

.sidebar-quote {
  margin-top: auto;
  background: #fffdf9;
  border: 1px solid #e9e5de;
  border-radius: 10px;
  padding: 12px;
  font-size: 11px;
  color: #817561;
}

.sidebar-quote p {
  margin: 4px 0 0;
  color: #9b9286;
  line-height: 1.5;
}

.workflow-main {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  position: relative;
}

.wf-topbar {
  height: 60px;
  background: #ffffffb5;
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--line);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  flex-shrink: 0;
}

.topbar-info h2 {
  font-size: 17px;
  margin: 0;
}

.stats-row {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #92939e;
  margin-top: 2px;
}

.stats-row b {
  color: #292c37;
}

.topbar-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.view-switch-pills {
  display: flex;
  gap: 2px;
  background: #f1edf6;
  border-radius: 8px;
  padding: 3px;
}

.view-switch-pills button {
  border: 0;
  background: transparent;
  padding: 5px 10px;
  border-radius: 6px;
  font-size: 11px;
  color: #796c87;
  cursor: pointer;
}

.view-switch-pills button.active {
  background: white;
  color: #66529f;
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.stage-container {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.canvas-viewport {
  position: absolute;
  inset: 0;
  background-color: #faf9f6;
  background-image: radial-gradient(#d9d5df 1px, transparent 1px);
  background-size: 20px 20px;
  overflow: hidden;
  cursor: grab;
}

.canvas-viewport.grabbing {
  cursor: grabbing;
}

.canvas-world {
  position: absolute;
  transform-origin: 0 0;
  width: 1px;
  height: 1px;
}

.svg-connections {
  position: absolute;
  left: 0;
  top: 0;
  overflow: visible;
  width: 1px;
  height: 1px;
  pointer-events: none;
}

.edge-path {
  fill: none;
  stroke: #c3bacf;
  stroke-width: 2;
  transition: stroke 0.15s;
}

.edge-path.selected {
  stroke: #7460b9;
  stroke-width: 3.5;
}

.edge-hit-area {
  fill: none;
  stroke: transparent;
  stroke-width: 16;
  cursor: pointer;
  pointer-events: stroke;
}

.node-card {
  position: absolute;
  width: 244px;
  min-height: 175px;
  border: 1px solid #e4e0e8;
  border-radius: 12px;
  background: #ffffff;
  box-shadow: 0 4px 12px rgba(59, 44, 75, 0.04);
  cursor: default;
  user-select: none;
  display: flex;
  flex-direction: column;
}

.node-card:hover {
  box-shadow: 0 8px 24px rgba(59, 44, 75, 0.08);
  border-color: #d5c8e4;
}

.node-card.selected {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(116, 96, 185, 0.15), 0 8px 24px rgba(59, 44, 75, 0.08);
}

.node-header {
  padding: 12px 14px 6px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.node-badge {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 9px;
  color: var(--accent);
  font-weight: 600;
}

.badge-square {
  width: 6px;
  height: 6px;
  background: var(--accent);
  border-radius: 2px;
}

.node-idx {
  font-size: 9px;
  color: #c0b9c8;
}

.node-body {
  padding: 0 14px 10px;
  flex: 1;
}

.node-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.status-circle-btn {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 1px solid #cbd5e1;
  background: white;
  display: grid;
  place-items: center;
  cursor: pointer;
  padding: 0;
  flex-shrink: 0;
}

.status-circle-btn.done {
  background: #8ba492;
  border-color: #8ba492;
  color: white;
}

.node-title-text {
  font-size: 13px;
  color: #292c37;
  font-weight: 650;
}

.node-desc {
  font-size: 11px;
  color: #918799;
  line-height: 1.5;
  margin: 0 0 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.tags-row {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.tag {
  font-size: 9px;
  padding: 2px 6px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.tag.delegate {
  background: var(--tint);
  color: var(--accent);
}

.tag.urgent {
  background: #fee2e2;
  color: #b91c1c;
}

.tag.important {
  background: #fef3c7;
  color: #b45309;
}

.node-footer {
  padding: 8px 14px;
  border-top: 1px solid #f0edf3;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 10px;
  color: #a095ac;
}

.date-meta {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* 连接桩 Port */
.port-dot {
  position: absolute;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid #d7cedf;
  background: white;
  top: 50%;
  transform: translateY(-50%);
  cursor: pointer;
  padding: 0;
  z-index: 5;
}

.port-dot:hover {
  background: #7460b9;
  border-color: #7460b9;
  transform: translateY(-50%) scale(1.3);
}

.port-dot.in {
  left: -6px;
}

.port-dot.out {
  right: -6px;
}

.branch-add-btn {
  position: absolute;
  right: -28px;
  top: calc(50% - 11px);
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 1px solid #ded5e6;
  background: white;
  color: #7460b9;
  display: grid;
  place-items: center;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s;
  padding: 0;
}

.node-card:hover .branch-add-btn {
  opacity: 1;
}

/* 控制栏 */
.controls-bar {
  position: absolute;
  left: 24px;
  bottom: 24px;
  background: white;
  border: 1px solid #e7e1ec;
  border-radius: 8px;
  padding: 4px 6px;
  display: flex;
  align-items: center;
  gap: 4px;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.05);
}

.ctrl-btn {
  border: 0;
  background: transparent;
  padding: 6px;
  border-radius: 6px;
  cursor: pointer;
  display: grid;
  place-items: center;
  color: #796c87;
}

.ctrl-btn:hover {
  background: #f1edf6;
}

.zoom-text {
  font-size: 11px;
  min-width: 40px;
  text-align: center;
  color: #64748b;
}

.fit-btn {
  font-size: 11px;
  padding: 4px 8px;
  color: #7460b9;
}

.edge-tip-bar {
  position: absolute;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  background: white;
  border: 1px solid #cbd5e1;
  border-radius: 20px;
  padding: 6px 14px;
  font-size: 11px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.del-edge-btn {
  border: 0;
  background: transparent;
  color: #ef4444;
  font-weight: 600;
  cursor: pointer;
}

/* 属性检视侧抽屉 */
.inspector-drawer {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 320px;
  background: #fffefa;
  border-left: 1px solid #e6e1ec;
  box-shadow: -8px 0 24px rgba(0, 0, 0, 0.04);
  display: flex;
  flex-direction: column;
  z-index: 10;
}

.drawer-head {
  padding: 16px;
  border-bottom: 1px solid var(--line);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.drawer-head h4 {
  margin: 0;
  font-size: 14px;
}

.close-btn {
  border: 0;
  background: transparent;
  cursor: pointer;
}

.drawer-body {
  padding: 16px;
  overflow-y: auto;
  flex: 1;
  display: grid;
  gap: 14px;
}

.drawer-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
}

.drawer-field input,
.drawer-field textarea,
.drawer-field select {
  border: 1px solid #d8d4df;
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 12px;
  background: white;
}

.row-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.palette-swatches {
  display: flex;
  gap: 8px;
}

.color-chip {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid white;
  outline: 1px solid #cbd5e1;
  cursor: pointer;
}

.color-chip.active {
  outline: 2px solid #7460b9;
}

.drawer-foot {
  padding: 14px 16px;
  border-top: 1px solid var(--line);
}

.delete-node-btn {
  width: 100%;
  border: 0;
  background: #fee2e2;
  color: #b91c1c;
  padding: 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
}

/* 时间线视图 */
.timeline-container {
  padding: 24px 36px;
  overflow-y: auto;
  height: 100%;
}

.timeline-intro {
  margin-bottom: 20px;
}

.timeline-intro h3 {
  margin: 0 0 4px;
  font-size: 16px;
}

.timeline-intro p {
  margin: 0;
  font-size: 12px;
  color: var(--sub);
}

.timeline-list {
  display: grid;
  gap: 12px;
}

.timeline-card {
  background: white;
  border: 1px solid #e7e1ec;
  border-left: 4px solid var(--accent);
  border-radius: 8px;
  padding: 14px 18px;
  display: grid;
  grid-template-columns: 140px 1fr 100px;
  align-items: center;
  gap: 16px;
}

.tl-date-col strong {
  font-size: 12px;
  color: #64748b;
}

.tl-content-col h4 {
  margin: 0 0 4px;
  font-size: 13px;
}

.tl-content-col p {
  margin: 0;
  font-size: 11px;
  color: #94a3b8;
}

.status-badge {
  font-size: 10px;
  padding: 3px 8px;
  border-radius: 4px;
  font-weight: 600;
}

.status-badge.todo {
  background: #f1f5f9;
  color: #64748b;
}

.status-badge.doing {
  background: #ede9fe;
  color: #6d28d9;
}

.status-badge.done {
  background: #ecfdf5;
  color: #047857;
}

.primary-btn {
  background: #7460b9;
  color: white;
  border: 0;
  border-radius: 8px;
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}

.secondary-btn {
  background: white;
  border: 1px solid #e7e1ec;
  color: #796c87;
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}
</style>
