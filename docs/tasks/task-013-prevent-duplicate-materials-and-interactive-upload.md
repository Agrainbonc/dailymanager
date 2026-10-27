# 任务登记：防范重复文件逻辑优化、重复治理与前端上传排重确认交互

- 任务ID: TASK-013
- 状态: DONE
- 创建时间: 2026-10-13
- 完成时间: 2026-10-13
- 责任Agent: Antigravity

## 任务背景与目标
工作区中由于文件多次复制、导入产生了相同文件（多组相同 SHA256 记录），导致存储浪费和转写任务重复调度。
本任务已完善全链路防重逻辑：
1. **工作区现有重复文件检测与合并清理**：提供检测与安全去重机制（`GET /api/materials/duplicates` 与 `POST /api/materials/deduplicate`），合并保留最优记录，清理冗余副本并释放磁盘存储；
2. **后台自动扫描/导入严格防重**：同一 SHA256 严禁重复创建 Material 和 ProcessingJob；
3. **新增资料上传接口及冲突预检机制**：
   - 增加文件上传与哈希预检接口（`POST /api/materials/upload`）；
   - 遇到相同文件时，不直接覆盖或静默新增，而是向前端返回冲突信息与已有文件元数据；
4. **前端交互弹窗确认**：
   - 提供资料直接上传入口；
   - 当检测到相同文件时，弹出确认对话框让用户自主选择「取消上传（使用已有文件）」或「仍然保留新副本」；
   - 顶部提供「清理重复 (N组)」排查与清理操作入口；
5. **自动化测试与全量自检**：
   - 编写针对上传排重、冲突询问、重复检测与合并的单元测试，22项后端测试全量通过，前端构建 0 错误。

## 锁定修改文件清单
- `backend/app/schemas.py`
- `backend/app/services/inference.py`
- `backend/app/services/library.py`
- `backend/app/api.py`
- `frontend/src/types.ts`
- `frontend/src/api.ts`
- `frontend/src/App.vue`
- `frontend/src/styles.css`
- `backend/tests/test_ingestion_pipeline.py`
- `docs/tasks/task-013-prevent-duplicate-materials-and-interactive-upload.md`
