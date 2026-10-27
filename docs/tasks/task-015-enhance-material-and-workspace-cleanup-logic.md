# 任务登记：完善资料清理体系（单项/批量删除、细粒度去重治理、孤儿文件垃圾清理）

- 任务ID: TASK-015
- 状态: DONE
- 创建时间: 2026-10-14
- 完成时间: 2026-10-14
- 责任Agent: Antigravity

## 任务背景与目标
现有的清理逻辑仅支持全局一键哈希去重，缺乏单项资料删除、多选批量删除、重复文件指定主项细粒度合并、以及磁盘孤儿文件扫描清理能力。
本任务旨在建立完整、严密的资料生命周期与工作区清理管理体系：

1. **单项与批量资料安全删除**：
   - 后端新增 `DELETE /api/materials/{material_id}` 与 `POST /api/materials/batch-delete`；
   - 物理文件引用计数保护（严禁误删共享物理文件），级联清理关联的 `ProcessingJob`；
   - 前端资料详情页支持单项删除，多选操作栏支持批量删除并带二次确认；
2. **重复文件细粒度治理与选择性合并**：
   - 后端新增 `POST /api/materials/duplicates/resolve-group`（允许指定 keeper 主文件合并单组）与 `POST /api/materials/duplicates/ignore`（忽略豁免指定重复组）；
   - 前端重复治理弹窗支持逐组审查、用户手动指定“保留此项”并合并多余项，或单组独立清理；
3. **工作区存储审计与孤儿文件清理**：
   - 后端新增 `GET /api/system/storage/audit` 与 `POST /api/system/storage/clean-orphans`；
   - 审计并清理磁盘上有物理文件但数据库无对应记录的孤儿垃圾；
4. **自动化测试与全量自检**：
   - 增加删除、批量删除、单组指定主项合并、孤儿文件清理的自动化单元测试；
   - 确保前后端构建与自检全部通过。

## 锁定修改文件清单
- `backend/app/schemas.py`
- `backend/app/services/library.py`
- `backend/app/api.py`
- `frontend/src/types.ts`
- `frontend/src/api.ts`
- `frontend/src/App.vue`
- `frontend/src/styles.css`
- `backend/tests/test_ingestion_pipeline.py`
- `docs/tasks/task-015-enhance-material-and-workspace-cleanup-logic.md`
