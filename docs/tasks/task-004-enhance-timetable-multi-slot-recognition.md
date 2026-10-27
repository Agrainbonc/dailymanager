# 任务登记：课表识别多时段与全量识别增强

- 任务ID: TASK-004
- 状态: DONE
- 创建时间: 2026-10-12
- 责任Agent: Antigravity

## 任务目标
1. 增强课表识别 Prompt 与调用参数（设置高输出 token 上限、强调遍历所有网格单元，杜绝只识别部分行）；
2. 明确指示大模型支持并提取“同一课程在一周内多次上课”的所有独立时段条目（同名多课时）；
3. 升级 MockVisionProvider，基于 docs/timetable-2026-1.md 真实课表结构提供完整的包含同一课程多时段的对照数据；
4. 前端识别预览表增强：展示每个课程对应的星期与时段标签，支持同名课程时段直观识别与多时段汇总提示；
5. 补充针对多时段同名课程识别与合并的自动化测试；
6. 跑通全量自检。

## 锁定修改文件清单
- `backend/app/services/timetable_recognition.py`
- `backend/app/adapters/vision.py`
- `backend/tests/test_ai_adapters.py`
- `frontend/src/App.vue`
- `frontend/src/styles.css`

## 自检记录
- `backend`: `.\.venv\Scripts\python -m unittest discover tests` 全部 13 项单元测试通过（包含多时段课表识别提取、时段自然排序以及同一课程合并验证）。
- `frontend`: `npm run build` TypeScript 静态检查与 Vite 生产构建顺利通过，无报错。
