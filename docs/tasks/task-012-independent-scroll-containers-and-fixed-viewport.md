# 任务登记：前端视口高度锁定与独立局部滚动容器重构

- 任务ID: TASK-012
- 状态: DONE
- 创建时间: 2026-10-13
- 责任Agent: Antigravity

## 任务目标
1. **取消整个页面的整体下滑滚动**：
   - 将应用主体（`html, body, #app, .app-shell`）锁定在 100vh 屏幕高度内，`overflow: hidden`，防止全局纵向滚动条；
2. **构建独立滚动的局部容器（尤其资料库条目与课程列表）**：
   - **侧边栏课程列表独立滚动**：品牌区与新建课程按钮固定，课程列表区设为 `flex: 1; overflow-y: auto`，底部设置链接常驻；
   - **工作台核心内容区自适应**：
     - 工作台顶部信息栏、统计指标卡片、排布搜索控制栏保持紧凑呈现；
     - 主体工作区（`content-layout`）垂直自适应填充剩余空间（`flex: 1; min-height: 0`）；
     - **资料库条目容器（materials-panel）**：面板表头和批量操作浮条吸顶，内部资料列表/卡片区（`groups-container`）作为专属独立滚动容器（`overflow-y: auto; flex: 1; min-height: 0`）；
     - **后台处理任务队列（jobs-panel）**：队列标题常驻，内部任务列表（`job-list`）独立滚动；
3. **响应式与滚动条精致化**：
   - 优化专属细条滚动条样式（Custom Scrollbar），悬浮时显示柔和滑块；
   - 保持在不同屏幕尺寸下的视觉自适应与无溢出。
4. **自动化测试与全量自检**：
   - 运行前端 `npm run build` 确保零错误；
   - 运行后端单元测试确保服务稳健。

## 锁定修改文件清单
- `frontend/src/styles.css`
- `frontend/src/App.vue`
- `docs/tasks/task-012-independent-scroll-containers-and-fixed-viewport.md`
