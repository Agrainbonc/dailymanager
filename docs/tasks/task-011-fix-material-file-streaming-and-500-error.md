# 任务登记：修复资料文件流式获取 500 报错与连接挂起问题

- 任务ID: TASK-011
- 状态: DONE
- 创建时间: 2026-10-13
- 完成时间: 2026-10-13
- 责任Agent: Antigravity

## 任务目标
1. **排查并解决 GET /api/materials/{material_id}/file 报 500 / 挂起超时问题**：
   - 路由函数声明改造为 `async def`，杜绝跨线程池 ASGI 协程调度与 SQLite Session 生命周期冲突；
   - 优化音频在线试听流式响应头（试听模式移除 Content-Disposition 标头，下载模式清洗非法字符并安全转码，支持标准 Range 请求）；
   - 添加客户端断开连接防护中间件，捕获音频拖拽或切歌时的 ConnectionResetError / BrokenPipeError；
2. **自动化测试与全量自检**：
   - 增加单元测试验证 `/api/materials/{material_id}/file` 在普通下载与浏览器试听模式下的响应与标头行为；
   - 运行全部测试自检（17项单元测试全绿，前端 build 通过），更新任务状态为 DONE。

## 锁定修改文件清单
- `backend/app/api.py`
- `backend/app/main.py`
- `backend/tests/test_ingestion_pipeline.py`
- `docs/tasks/task-011-fix-material-file-streaming-and-500-error.md`
