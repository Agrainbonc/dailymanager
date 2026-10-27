<script setup lang="ts">
import { ref } from 'vue'
import {
  AudioLines,
  BookOpenText,
  Calendar,
  CalendarDays,
  FolderGit2,
  Inbox,
  LayoutGrid,
  Layers,
  Settings,
  Sparkles,
} from '@lucide/vue'
import type { ActiveTab } from './types'
import MaterialsView from './views/MaterialsView.vue'
import CalendarView from './views/CalendarView.vue'
import WorkflowView from './views/WorkflowView.vue'
import SettingsView from './views/SettingsView.vue'

const activeTab = ref<ActiveTab>('materials')
const materialsViewRef = ref<InstanceType<typeof MaterialsView> | null>(null)

// 全局 Toast 消息
const toastMessage = ref('')
const toastIsError = ref(false)
let toastTimer: any = null

function showNotification(msg: string, isError = false) {
  toastMessage.value = msg
  toastIsError.value = isError
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toastMessage.value = ''
  }, 3500)
}

function handleOpenTimetable() {
  activeTab.value = 'materials'
  // 等待组件挂载渲染后调用其打开弹窗方法
  setTimeout(() => {
    materialsViewRef.value?.openTimetableDialog()
  }, 100)
}
</script>

<template>
  <div class="app-shell">
    <!-- 顶部全局系统导航栏 -->
    <header class="app-global-nav">
      <div class="brand-container">
        <div class="brand-icon">
          <BookOpenText :size="20" />
        </div>
        <div class="brand-text">
          <strong>DailyManager</strong>
          <span>智能学习工作台</span>
        </div>
      </div>

      <!-- 四大核心功能模块切换 Tabs -->
      <nav class="nav-tabs-wrapper" aria-label="核心功能导航">
        <button
          class="nav-tab-btn"
          :class="{ active: activeTab === 'materials' }"
          type="button"
          @click="activeTab = 'materials'"
        >
          <BookOpenText :size="16" />
          <span>课堂资料库</span>
        </button>

        <button
          class="nav-tab-btn"
          :class="{ active: activeTab === 'calendar' }"
          type="button"
          @click="activeTab = 'calendar'"
        >
          <Calendar :size="16" />
          <span>日程与博弈论</span>
        </button>

        <button
          class="nav-tab-btn"
          :class="{ active: activeTab === 'workflow' }"
          type="button"
          @click="activeTab = 'workflow'"
        >
          <Layers :size="16" />
          <span>科研任务流</span>
        </button>

        <button
          class="nav-tab-btn"
          :class="{ active: activeTab === 'settings' }"
          type="button"
          @click="activeTab = 'settings'"
        >
          <Settings :size="16" />
          <span>系统综合设置</span>
        </button>
      </nav>

      <!-- 右侧快捷动作 -->
      <div class="nav-right-actions">
        <button
          class="quick-action-btn"
          type="button"
          title="上传并自动识别教务课表截图"
          @click="handleOpenTimetable"
        >
          <Sparkles :size="15" />
          <span>课表智能识别</span>
        </button>
      </div>
    </header>

    <!-- 主视图容器 -->
    <main class="app-main-content">
      <KeepAlive>
        <MaterialsView
          v-if="activeTab === 'materials'"
          ref="materialsViewRef"
          @notify="showNotification"
        />
        <CalendarView
          v-else-if="activeTab === 'calendar'"
          @notify="showNotification"
        />
        <WorkflowView
          v-else-if="activeTab === 'workflow'"
          @notify="showNotification"
        />
        <SettingsView
          v-else-if="activeTab === 'settings'"
          @notify="showNotification"
          @open-timetable="handleOpenTimetable"
        />
      </KeepAlive>
    </main>

    <!-- 全局 Toast 提示浮条 -->
    <transition name="toast-fade">
      <div v-if="toastMessage" class="global-toast" :class="{ error: toastIsError }">
        <span>{{ toastMessage }}</span>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background: var(--bg);
  font-family: inherit;
}

.app-global-nav {
  height: 52px;
  background: #111827;
  color: #f9fafb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 18px;
  flex-shrink: 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  z-index: 50;
}

.brand-container {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-icon {
  width: 30px;
  height: 30px;
  background: #3b82f6;
  border-radius: 8px;
  display: grid;
  place-items: center;
  color: white;
}

.brand-text strong {
  display: block;
  font-size: 13px;
  letter-spacing: -0.02em;
  line-height: 1.2;
}

.brand-text span {
  display: block;
  font-size: 9px;
  color: #9ca3af;
  letter-spacing: 0.04em;
}

.nav-tabs-wrapper {
  display: flex;
  align-items: center;
  gap: 4px;
  background: rgba(255, 255, 255, 0.06);
  padding: 4px;
  border-radius: 9px;
}

.nav-tab-btn {
  border: 0;
  background: transparent;
  color: #9ca3af;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 14px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 7px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.nav-tab-btn:hover {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.08);
}

.nav-tab-btn.active {
  background: #2563eb;
  color: #ffffff;
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.35);
}

.nav-right-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.quick-action-btn {
  border: 1px solid rgba(255, 255, 255, 0.16);
  background: rgba(255, 255, 255, 0.06);
  color: #e5e7eb;
  font-size: 11px;
  font-weight: 600;
  padding: 6px 12px;
  border-radius: 7px;
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  transition: background 0.15s;
}

.quick-action-btn:hover {
  background: rgba(255, 255, 255, 0.14);
  color: #ffffff;
}

.app-main-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  position: relative;
}

.global-toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  background: #1f2937;
  color: #f9fafb;
  padding: 10px 20px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
  z-index: 9999;
  pointer-events: none;
}

.global-toast.error {
  background: #b91c1c;
  color: #ffffff;
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: all 0.25s ease;
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, 15px);
}
</style>
