# 任务登记：修复资料库存储根路径并重分类投递箱录音文件

- 任务ID: TASK-005
- 状态: DONE
- 创建时间: 2026-10-12
- 责任Agent: Antigravity

## 任务目标
1. 修复 `backend/app/services/library.py` 中的 `_library_root` 逻辑：当未设置自定义输出目录时，默认使用系统资料库目录 `LIBRARY_DIR`，杜绝将投递箱（inbox）误作资料库归档根目录；
2. 修复 `import_from_inbox` 与投递箱扫描对 `needs-review` 遗留子目录的误判跳过问题；
3. 将用户投递箱（`D:\我的文件\学习资料\投递箱`）中遗留/嵌套在 `needs-review` 目录下的 24 个真实课堂录音文件解救出来，依据当前最新课表与时间推断，自动归类入库到各课程并建立处理任务；
4. 清理投递箱内误创建的空 `needs-review` 目录，使投递箱恢复整洁；
5. 运行全部后端单元测试与自检。

## 锁定修改文件清单
- `backend/app/services/library.py`
- `backend/tests/test_ingestion_pipeline.py`
- `backend/tests/__init__.py`

## 自检记录
- `backend`: `.\.venv\Scripts\python -m unittest discover tests` 14 个测试全数通过（包含针对 output_directory 为空时的资料库根目录隔离与投递箱空目录清理的新测试）。
- `frontend`: `npm run build` 构建成功，无类型或打包错误。
- 数据验证：24 门课堂录音 100% 完成自动归类入库（状态均为 `classified`，`needs_review` 为 0）；投递箱目录 `D:\我的文件\学习资料\投递箱` 已完全清空并恢复整洁。
