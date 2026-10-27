# 任务登记：修复存储审计与孤儿文件清理 Pydantic Schema 字段不匹配问题

- 任务ID: TASK-017
- 状态: DONE
- 创建时间: 2026-10-27
- 完成时间: 2026-10-27
- 责任Agent: Antigravity

## 任务背景与问题分析
后端运行时接口 `GET /api/system/storage/audit` 报 500 错误：
`pydantic_core._pydantic_core.ValidationError: 3 validation errors for StorageAuditRead`，缺少 `total_materials_bytes`、`orphan_files`、`temp_export_files_bytes` 字段。
经排查：
1. `backend/app/services/library.py` 的 `audit_storage()` 返回字段为：
   - `total_materials_count`
   - `valid_files_count`
   - `missing_files_count`
   - `orphan_files_count`
   - `orphan_files_bytes`
   - `orphan_sample_paths`
   而 `backend/app/schemas.py` 中的 `StorageAuditRead` 字段定义不匹配。
2. `clean_orphan_files()` 返回：
   - `cleaned_orphans_count`
   - `freed_bytes`
   - `removed_paths`
   而 `backend/app/schemas.py` 中的 `CleanOrphansResponse` 字段名误写为 `deleted_files_count`。
3. 前端 `types.ts` 和视图组件使用的正是 `valid_files_count`、`missing_files_count`、`orphan_sample_paths`、`cleaned_orphans_count`。

## 修复方案
1. 修正 `backend/app/schemas.py` 中的 `StorageAuditRead` 与 `CleanOrphansResponse` 定义，与 Service 层返回及前端接口定义保持完全一致，并提供向后兼容字段别名。
2. 在 `backend/tests/test_new_modules.py` 中补充针对 `audit_storage` 与 `clean_orphan_files` 接口序列化的单元测试，确保回归测试通过。

## 锁定修改文件清单
- `backend/app/schemas.py`
- `backend/tests/test_new_modules.py`
- `docs/tasks/task-017-fix-storage-audit-and-clean-orphans-schemas.md`
