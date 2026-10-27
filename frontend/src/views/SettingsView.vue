<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  AudioLines,
  CalendarDays,
  CheckCircle2,
  HardDrive,
  Inbox,
  LoaderCircle,
  RefreshCw,
  Save,
  Server,
  Sparkles,
  Trash2,
  Wifi,
  XCircle,
} from '@lucide/vue'
import { api } from '../api'
import type {
  AsrSettingsConfig,
  CleanOrphansResponse,
  StorageAudit,
  SystemSettings,
  TimetableCandidateItem,
  TimetableRecognitionResult,
} from '../types'

const emit = defineEmits<{
  (e: 'notify', msg: string, isError?: boolean): void
  (e: 'open-timetable'): void
}>()

const loading = ref(true)
const saving = ref(false)
const testingAsr = ref(false)
const testResult = ref<{ success: boolean; message: string; latency_ms: number } | null>(null)

const settings = ref<SystemSettings>({
  input_directory: null,
  output_directory: null,
  asr: {
    provider: 'zhixin_ws',
    dashscope_api_key: '',
    dashscope_model: 'qwen-audio-turbo',
    openai_base_url: 'http://127.0.0.1:8000/v1',
    openai_api_key: 'local',
    openai_model: 'whisper-1',
    zhixin_ws_url: 'ws://127.0.0.1:9001/v1/stream',
    zhixin_token: 'change-me',
  },
  vision: {
    provider: 'dashscope',
    api_key: '',
    base_url: '',
    model: 'qwen-vl-max',
  },
})

// 存储审计状态
const storageAudit = ref<StorageAudit | null>(null)
const loadingAudit = ref(false)
const cleaningOrphans = ref(false)

async function loadSettings() {
  loading.value = true
  try {
    const res = await api.getSystemSettings()
    settings.value = res
  } catch (err) {
    emit('notify', err instanceof Error ? err.message : '加载系统设置失败', true)
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  saving.value = true
  try {
    const updated = await api.saveSystemSettings(settings.value)
    settings.value = updated
    emit('notify', '系统设置已成功保存！')
  } catch (err) {
    emit('notify', err instanceof Error ? err.message : '保存设置失败', true)
  } finally {
    saving.value = false
  }
}

async function runAsrTest() {
  testingAsr.value = true
  testResult.value = null
  try {
    const res = await api.testAsrConnection(settings.value.asr)
    testResult.value = res
    if (res.success) {
      emit('notify', `ASR 测试成功: ${res.message}`)
    } else {
      emit('notify', `ASR 测试未通过: ${res.message}`, true)
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : '连接测试异常'
    testResult.value = { success: false, message: msg, latency_ms: 0 }
    emit('notify', msg, true)
  } finally {
    testingAsr.value = false
  }
}

async function loadStorageAudit() {
  loadingAudit.value = true
  try {
    storageAudit.value = await api.storageAudit()
  } catch (err) {
    emit('notify', err instanceof Error ? err.message : '获取存储审计失败', true)
  } finally {
    loadingAudit.value = false
  }
}

async function cleanOrphanFiles() {
  if (!confirm('确定清理无数据库关联的磁盘孤儿文件吗？')) return
  cleaningOrphans.value = true
  try {
    const res: CleanOrphansResponse = await api.cleanOrphans()
    emit('notify', `清理完成：删除了 ${res.cleaned_orphans_count} 个孤儿文件，释放 ${(res.freed_bytes / 1024 / 1024).toFixed(2)} MB`)
    await loadStorageAudit()
  } catch (err) {
    emit('notify', err instanceof Error ? err.message : '清理孤儿文件失败', true)
  } finally {
    cleaningOrphans.value = false
  }
}

function formatBytes(bytes: number) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i]
}

onMounted(() => {
  loadSettings()
  loadStorageAudit()
})
</script>

<template>
  <div class="settings-page">
    <header class="settings-header">
      <div>
        <p class="eyebrow">SYSTEM & AI CONFIGURATION</p>
        <h2>系统综合设置中心</h2>
      </div>
      <button class="primary-action" :disabled="saving" @click="saveSettings">
        <Save :size="16" />
        {{ saving ? '正在保存...' : '保存全部设置' }}
      </button>
    </header>

    <div v-if="loading" class="loading-state">
      <LoaderCircle class="spinner" :size="32" />
      <p>正在读取系统配置…</p>
    </div>

    <div v-else class="settings-grid">
      <!-- 1. ASR 语音识别配置模块 -->
      <section class="settings-card asr-card">
        <div class="card-head">
          <div class="card-title">
            <AudioLines :size="20" class="icon-accent" />
            <div>
              <h3>ASR 语音转写服务设置</h3>
              <p class="subtext">支持灵活切换公有云大模型 API 或本地自建端口，告别固定端口强依赖</p>
            </div>
          </div>
          <button class="secondary-action" :disabled="testingAsr" @click="runAsrTest">
            <Wifi :size="15" />
            {{ testingAsr ? '测试中...' : '测试连通性' }}
          </button>
        </div>

        <div v-if="testResult" class="test-feedback" :class="testResult.success ? 'success' : 'failed'">
          <component :is="testResult.success ? CheckCircle2 : XCircle" :size="16" />
          <span>{{ testResult.message }} ({{ testResult.latency_ms }}ms)</span>
        </div>

        <div class="field-group">
          <label class="field-label">服务使用方式</label>
          <div class="provider-selector">
            <label class="provider-radio" :class="{ active: settings.asr.provider === 'dashscope' }">
              <input v-model="settings.asr.provider" type="radio" value="dashscope" />
              <div class="radio-content">
                <strong>阿里云 API (DashScope)</strong>
                <small>免本地显存部署，通义千问/SenseVoice 极速转写</small>
              </div>
            </label>

            <label class="provider-radio" :class="{ active: settings.asr.provider === 'openai' }">
              <input v-model="settings.asr.provider" type="radio" value="openai" />
              <div class="radio-content">
                <strong>自定义本地端口 / OpenAI 兼容接口</strong>
                <small>支持 Whisper.cpp / vLLM 或外部 OpenAI 协议接口</small>
              </div>
            </label>

            <label class="provider-radio" :class="{ active: settings.asr.provider === 'zhixin_ws' }">
              <input v-model="settings.asr.provider" type="radio" value="zhixin_ws" />
              <div class="radio-content">
                <strong>本地 Zhixin WebSocket 端口</strong>
                <small>直连本地 9001 端口 Companion 流式 ASR</small>
              </div>
            </label>

            <label class="provider-radio" :class="{ active: settings.asr.provider === 'mock' }">
              <input v-model="settings.asr.provider" type="radio" value="mock" />
              <div class="radio-content">
                <strong>Mock 离线仿真测试</strong>
                <small>无需任何网络和模型依赖，秒级生成仿真字幕测试</small>
              </div>
            </label>
          </div>
        </div>

        <!-- 针对 DashScope 的表单 -->
        <div v-if="settings.asr.provider === 'dashscope'" class="sub-form">
          <div class="input-row">
            <label>
              阿里云 DashScope API Key
              <input
                v-model="settings.asr.dashscope_api_key"
                type="password"
                placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxx"
              />
            </label>
            <label>
              模型名称
              <select v-model="settings.asr.dashscope_model">
                <option value="qwen-audio-turbo">qwen-audio-turbo (推荐，高准确度)</option>
                <option value="sensevoice-v1">sensevoice-v1 (超快极速)</option>
                <option value="paraformer-realtime-v1">paraformer-realtime-v1</option>
              </select>
            </label>
          </div>
        </div>

        <!-- 针对 OpenAI / 本地兼容端口的表单 -->
        <div v-if="settings.asr.provider === 'openai'" class="sub-form">
          <div class="input-row">
            <label>
              接口地址 (Base URL)
              <input
                v-model="settings.asr.openai_base_url"
                type="text"
                placeholder="例如：http://127.0.0.1:8000/v1"
              />
            </label>
            <label>
              API Key
              <input
                v-model="settings.asr.openai_api_key"
                type="password"
                placeholder="本地部署可填 local 或留空"
              />
            </label>
            <label>
              模型名称
              <input v-model="settings.asr.openai_model" type="text" placeholder="whisper-1" />
            </label>
          </div>
        </div>

        <!-- 针对 Zhixin WS 的表单 -->
        <div v-if="settings.asr.provider === 'zhixin_ws'" class="sub-form">
          <div class="input-row">
            <label>
              WebSocket 端点 URL
              <input
                v-model="settings.asr.zhixin_ws_url"
                type="text"
                placeholder="ws://127.0.0.1:9001/v1/stream"
              />
            </label>
            <label>
              鉴权 Token
              <input
                v-model="settings.asr.zhixin_token"
                type="password"
                placeholder="默认 change-me"
              />
            </label>
          </div>
        </div>
      </section>

      <!-- 2. 统一投递箱与资料库路径 -->
      <section class="settings-card">
        <div class="card-head">
          <div class="card-title">
            <Inbox :size="20" class="icon-accent" />
            <div>
              <h3>统一投递箱目录设置</h3>
              <p class="subtext">日常课后录音与课件拖入此目录后，点击“扫描投递箱”即可自动归档</p>
            </div>
          </div>
        </div>
        <div class="field-group">
          <label>
            投递箱绝对路径
            <input
              v-model="settings.input_directory"
              type="text"
              placeholder="例如：D:\课程资料\投递箱"
            />
          </label>
        </div>
      </section>

      <!-- 3. 课表智能识别与多模态模型入口 -->
      <section class="settings-card">
        <div class="card-head">
          <div class="card-title">
            <CalendarDays :size="20" class="icon-accent" />
            <div>
              <h3>课表上传自动识别</h3>
              <p class="subtext">基于多模态大模型视觉能力，扫描截图地毯式提取排课时间并排重入库</p>
            </div>
          </div>
          <button class="primary-action" @click="emit('open-timetable')">
            <Sparkles :size="16" />
            打开课表识别导入向导
          </button>
        </div>
        <p class="info-note">
          实现原理：系统接收课表图片后调用多模态模型对网格单元进行结构化解析，自动纠偏同一课程一周多次上课等复杂情况，经冲突校验后一键生成课程空间与课程表。
        </p>
      </section>

      <!-- 4. 存储审计与冗余孤儿文件清理 -->
      <section class="settings-card">
        <div class="card-head">
          <div class="card-title">
            <HardDrive :size="20" class="icon-accent" />
            <div>
              <h3>存储空间审计与垃圾清理</h3>
              <p class="subtext">检查物理磁盘与数据库引用一致性，防止孤儿文件占用空间</p>
            </div>
          </div>
          <button class="secondary-action" :disabled="loadingAudit" @click="loadStorageAudit">
            <RefreshCw :size="15" />
            重新审计
          </button>
        </div>

        <div v-if="storageAudit" class="audit-stats">
          <div class="stat-pill">
            <span>总资料文件数</span>
            <strong>{{ storageAudit.total_materials_count }}</strong>
          </div>
          <div class="stat-pill">
            <span>有效引用文件</span>
            <strong>{{ storageAudit.valid_files_count }}</strong>
          </div>
          <div class="stat-pill warning">
            <span>孤儿占用文件</span>
            <strong>{{ storageAudit.orphan_files_count }} 项 ({{ formatBytes(storageAudit.orphan_files_bytes) }})</strong>
          </div>
        </div>

        <div v-if="storageAudit && storageAudit.orphan_files_count > 0" class="orphan-action-bar">
          <p>检测到有物理文件存在但无数据库引用的冗余文件：</p>
          <button class="danger-action" :disabled="cleaningOrphans" @click="cleanOrphanFiles">
            <Trash2 :size="15" />
            {{ cleaningOrphans ? '清理中...' : '一键清理全部孤儿垃圾' }}
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  padding: 28px 36px 60px;
  max-width: 1200px;
  margin: 0 auto;
  overflow-y: auto;
  height: 100%;
}

.settings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--line);
}

.settings-header h2 {
  font-size: 22px;
  font-weight: 700;
  margin: 4px 0 0;
  color: var(--ink);
}

.settings-grid {
  display: grid;
  gap: 22px;
}

.settings-card {
  background: #ffffff;
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 22px;
  box-shadow: 0 4px 18px rgba(31, 43, 67, 0.03);
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  gap: 16px;
}

.card-title {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.card-title h3 {
  font-size: 16px;
  font-weight: 650;
  margin: 0 0 4px;
}

.card-title .subtext {
  font-size: 12px;
  color: var(--sub);
  margin: 0;
}

.icon-accent {
  color: var(--accent);
  flex-shrink: 0;
  margin-top: 2px;
}

.field-group {
  margin-top: 14px;
}

.field-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 10px;
  color: #435269;
}

.provider-selector {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}

.provider-radio {
  display: flex;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid #dce2ec;
  border-radius: 10px;
  cursor: pointer;
  background: #fbfcfd;
  transition: all 0.15s ease;
}

.provider-radio:hover {
  border-color: var(--accent);
  background: #f5f8ff;
}

.provider-radio.active {
  border-color: var(--accent);
  background: #eef2ff;
  box-shadow: 0 0 0 2px var(--accent);
}

.provider-radio input {
  margin-top: 3px;
}

.radio-content strong {
  display: block;
  font-size: 13px;
  color: var(--ink);
  margin-bottom: 2px;
}

.radio-content small {
  display: block;
  font-size: 11px;
  color: var(--sub);
  line-height: 1.4;
}

.sub-form {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 16px;
  margin-top: 12px;
}

.input-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 14px;
}

.input-row label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #4a5568;
}

.input-row input,
.input-row select {
  height: 38px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 0 12px;
  font-size: 13px;
  background: #ffffff;
}

.test-feedback {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 12px;
  margin-bottom: 14px;
}

.test-feedback.success {
  background: #ecfdf5;
  color: #065f46;
  border: 1px solid #a7f3d0;
}

.test-feedback.failed {
  background: #fef2f2;
  color: #991b1b;
  border: 1px solid #fecaca;
}

.info-note {
  font-size: 12px;
  color: #64748b;
  line-height: 1.6;
  margin: 6px 0 0;
  background: #f8fafc;
  padding: 10px 14px;
  border-radius: 8px;
}

.audit-stats {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  margin-top: 12px;
}

.stat-pill {
  flex: 1;
  min-width: 140px;
  padding: 12px 14px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.stat-pill span {
  display: block;
  font-size: 11px;
  color: var(--sub);
  margin-bottom: 4px;
}

.stat-pill strong {
  font-size: 16px;
  color: var(--ink);
}

.stat-pill.warning strong {
  color: #b91c1c;
}

.orphan-action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 14px;
  padding: 12px 14px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 10px;
  font-size: 12px;
  color: #991b1b;
}

.danger-action {
  background: #dc2626;
  color: white;
  border: none;
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}

.danger-action:hover {
  background: #b91c1c;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
  color: var(--sub);
  gap: 12px;
}

.spinner {
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
