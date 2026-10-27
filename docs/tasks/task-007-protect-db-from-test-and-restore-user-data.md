# 任务登记：彻底隔离测试数据库并完全恢复用户资料库数据

- 任务ID: TASK-007
- 状态: DONE
- 创建时间: 2026-10-12
- 责任Agent: Antigravity

## 任务目标
1. 彻底根除测试对生产数据库的污染：在 `backend/app/database.py` 中增加环境感知，检测到 `unittest`/`pytest` 或 `TESTING=1` 时，强制绑定到独立的 `dailymanager_test.db`，物理阻绝测试对生产数据库 `dailymanager.db` 的清空操作；
2. 完全恢复生产数据库数据：将 9 门学期课程课表与已归档在 `data/library/` 下的全部课堂录音资料（24 项）重新建档入库；
3. 重启后端服务，确保前端 API 正常返回全部课程与资料；
4. 跑通单元测试自检，验证单元测试跑完后生产数据库数据 0 丢失。

## 锁定修改文件清单
- `backend/app/database.py`
- `backend/tests/__init__.py`

## 自检记录
- `backend`: `.\.venv\Scripts\python -m unittest discover tests` 15 项单元测试通过。
- 数据库物理强隔离验证：测试跑完后，生产库中 10 门课程与 64 项资料数据无任何变动（0 丢失）。
- 前端 API 响应：`http://127.0.0.1:8000/api/overview` 与 `/api/courses` 已完整返回所有课程与资料项。
