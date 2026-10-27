# 任务登记：提升语音转写鲁棒性与解决队列卡死悬挂问题

- 任务ID: TASK-012
- 状态: DONE
- 创建时间: 2026-10-13
- 完成时间: 2026-10-13
- 责任Agent: Antigravity

## 任务背景与根因
1. **大音频切片缺乏进度反馈**：长课堂录音（如50MB+、50多分钟）需切成100~160片，转写期间 `job.progress` 死死停留在 30%，用户从前端看似卡死；
2. **服务重启导致的僵尸任务挂死**：后端重启或重载时，处于 `running` 状态的任务未被恢复，`LocalJobRunner` 只消费 `queued` 任务，导致历史 `running` 任务永久卡在 30%，资料状态死锁在 `processing`；
3. **缺乏连接熔断与合理超时**：单片等待超时过长，连续失联未及时熔断；
4. **缺乏任务恢复与重试管理接口**：前端无法在任务异常或中断后一键恢复或重试。

## 任务目标
1. **ASR 模块增加切片进度回调与快速熔断** (`backend/app/adapters/asr.py`)：
   - 增加 `progress_callback`，支持向调用方报告 `(current_slice, total_slices, partial_text)`；
   - 优化单切片超时为 25 秒，连续 3 次切片连接失败立即触发熔断抛出异常，杜绝机械空转；
2. **后台任务执行器增加僵尸恢复与看门狗机制** (`backend/app/services/job_runner.py`)：
   - 启动时及定期自动运行 `recover_stale_jobs()`，将由于服务重启遗留的 `running` 孤儿任务恢复并重新入队或标错；
   - 增加任务心跳/看门狗，超长时间未更新状态的任务自动恢复；
3. **转写处理器支持实时进度写入** (`backend/app/services/processors.py`)：
   - 接入 ASR 进度回调，动态更新 `job.progress` (30% -> 95%) 及 `job.message`（如：`正在转写 (35/150 片)`）；
4. **API 提供恢复与重试能力** (`backend/app/api.py`)：
   - 增强 `POST /materials/{material_id}/transcribe` 的并发防抖与状态清理；
   - 提供 `POST /jobs/recover` 与 `POST /jobs/{job_id}/retry` 接口；
5. **前端界面呈现与交互优化** (`frontend/src/api.ts`, `frontend/src/App.vue`, `frontend/src/styles.css`)：
   - 展示细粒度切片进度；
   - 增加一键“检查并恢复挂起任务”快捷操作；
6. **自动化测试与全量自检** (`backend/tests/test_ingestion_pipeline.py`)：
   - 增加任务恢复、进度写入、异常重试的自动化测试并全部通过（19项全部通过，前端 build 0 错误）。

## 锁定修改文件清单
- `backend/app/adapters/contracts.py`
- `backend/app/adapters/asr.py`
- `backend/app/services/job_runner.py`
- `backend/app/services/processors.py`
- `backend/app/api.py`
- `frontend/src/api.ts`
- `frontend/src/App.vue`
- `frontend/src/styles.css`
- `backend/tests/test_ingestion_pipeline.py`
- `docs/tasks/task-012-robust-transcription-and-job-runner.md`
