# 任务登记：前后端架构重构与多模块整合（系统设置中心、日历/博弈论系统、任务流规划画布）

- 任务ID: TASK-016
- 状态: DONE
- 创建时间: 2026-10-25
- 完成时间: 2026-10-25
- 责任Agent: Antigravity

## 任务背景与目标
用户提出项目后续三大核心优化方向：
1. **ASR 灵活配置与部署解耦**：从原先代码硬编码本地 9001 端口改为系统设置面板，支持可视化切换配置阿里云 DashScope API、本地/远程自定义端口（OpenAI 兼容端点、WebSocket 等）或 Mock，并提供连通性测试。
2. **整合两套独立系统前端并后端化存储**：
   - `tokii_空白分享版.html`（日历日程与博弈论四象限看板）：从浏览器 `localStorage` 迁移至后端数据库，实现全功能日历、连续日期标注、当天排期、以及博弈论拖拽看板。
   - `index(1).html`（“有绪”科研任务工作流拓扑画布）：从浏览器 `localStorage` 迁移至后端数据库，实现多任务流无限画布（节点、连线、小地图、时间轴视图、全屏模式等）。
3. **统一系统设置中心**：
   - 聚合 ASR 语音配置、投递箱路径配置、多模态视觉模型配置、课表自动识别向导、系统数据全量备份/导出导入。

## 架构重构设计

### 1. 后端新增模型与服务逻辑
- **系统设置模型与服务 (`SystemSetting`, `settings_service.py`)**：
  - 动态持久化 ASR、投递箱、Vision 相关配置项；
  - 重构 `get_asr_provider()` 支持读取运行时持久化配置并按需实例化对应 Provider；
  - 增加 ASR 连接测试接口 `POST /api/system/settings/asr/test`。
- **日历与博弈论服务 (`CalendarWorkspace`, `StrategyBoard`, `calendar_service.py`)**：
  - 统一存储多套日历（事件、标记、待安排事项、长期/月度任务）及博弈论看板数据；
  - 提供 CRUD API：`GET/POST/PUT/DELETE /api/calendar/*`。
- **工作流规划系统服务 (`WorkflowProject`, `workflow_service.py`)**：
  - 统一存储多任务流画布（节点、连线、视口配置、属性）；
  - 提供 CRUD 与导入导出 API：`GET/POST/PUT/DELETE /api/workflows/*`。

### 2. 前端架构重构与组件化
- 原 2700+ 行单文件 `App.vue` 拆分为多功能标签页架构：
  - `src/views/MaterialsView.vue`：资料工作台（原有课程管理、归档扫描、资料检索、转写队列）；
  - `src/views/CalendarView.vue`：Tokii 日历日程与博弈论决策看板；
  - `src/views/WorkflowView.vue`：有绪科研任务流拓扑画布与时间轴；
  - `src/views/SettingsView.vue`：系统综合设置中心（ASR 配置、投递箱、课表识别向导、数据备份）；
  - `src/App.vue`：主框架导航栏（Sidebar Navigation）、全局提示与模块调度。

## 锁定修改文件清单
- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/adapters/asr.py`
- `backend/app/services/settings_service.py`
- `backend/app/services/calendar_service.py`
- `backend/app/services/workflow_service.py`
- `backend/app/api.py`
- `backend/tests/test_new_modules.py`
- `frontend/src/types.ts`
- `frontend/src/api.ts`
- `frontend/src/views/MaterialsView.vue`
- `frontend/src/views/CalendarView.vue`
- `frontend/src/views/WorkflowView.vue`
- `frontend/src/views/SettingsView.vue`
- `frontend/src/App.vue`
- `frontend/src/styles.css`
- `docs/tasks/task-016-architecture-redesign-and-multi-module-integration.md`
