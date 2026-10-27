# 任务登记：设计与实现课程表同步导入到日程与博弈论系统

- 任务ID: TASK-019
- 状态: DONE
- 创建时间: 2026-10-27
- 完成时间: 2026-10-27
- 责任Agent: Antigravity

## 任务背景与目标
用户希望将系统中的课程表（Course 及排课时段 ScheduleSlot，如星期几、开始/结束时间、教室）同步导入到“日程与博弈论”（Tokii 日历）中。
由于课程表属于按周循环规律，而日程是基于具体日期的事件（Calendar Events）与博弈论待办托盘（Tray / Strategy Items），本任务旨在打通“课程库”与“日程/博弈论”：

1. **后端同步服务与 API**：
   - 新增 API `POST /api/calendar/sync-courses`；
   - 支持参数：
     - `workspace_id`: 目标日历 ID（若为空则同步到当前激活日历）；
     - `start_date` 与 `end_date`: 同步的时间跨度范围（例如未来 4 周、整个学期 16 周等）；
     - `course_ids`: 可选指定的课程 ID 列表（留空则同步全部有排课时段的课程）；
     - `sync_to_events`: 是否生成具体日期的日历排期事件（自动计算指定日期范围内的星期匹配，避免重复生成）；
     - `sync_to_tray`: 是否同步到日历的待安排托盘（Tray）；
     - `sync_to_strategy`: 是否同步到博弈论四列看板的事情托盘（Inbox）。
   - 返回统计结果（新增日历事件数、新增托盘数、新增博弈论卡片数）。

2. **前端交互设计与接入**：
   - 在 [`CalendarView.vue`](file:///d:/codes/items/dailymanager/frontend/src/views/CalendarView.vue) 顶部操作栏增加【同步课程表】按钮；
   - 弹窗提供直观的配置选项：
     - 选择目标日历；
     - 快捷时间范围选择（“未来 4 周”、“未来 8 周”、“整学期 16 周”或自定义日期）；
     - 勾选同步目标：具体日历排期 / 待安排托盘 / 博弈论事情收集箱；
   - 导入后自动刷新日历与博弈论看板并触发全局通知。

## 锁定修改文件清单
- `backend/app/schemas.py`
- `backend/app/services/calendar_service.py`
- `backend/app/api.py`
- `backend/tests/test_new_modules.py`
- `frontend/src/types.ts`
- `frontend/src/api.ts`
- `frontend/src/views/CalendarView.vue`
- `docs/tasks/task-019-sync-courses-to-calendar-and-strategy.md`
