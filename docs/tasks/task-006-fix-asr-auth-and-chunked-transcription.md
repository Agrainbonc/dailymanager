# 任务登记：修复 ASR 鉴权与长音频分片转写

- 任务ID: TASK-006
- 状态: DONE
- 创建时间: 2026-10-12
- 责任Agent: Antigravity

## 任务目标
1. 修复 ASR 403 鉴权失败问题：在 `backend/.env` 中解开并规范配置 `ZHIXIN_MODEL_CORE_TOKEN=change-me`；在 `ZhixinWsAsrProvider` 中如果未配置 token 时默认尝试 `change-me`；
2. 修复单流 30 秒上限导致的转写溢出中断问题：升级 `backend/app/adapters/asr.py` 的 `ZhixinWsAsrProvider`，实现对长课堂录音的自适应分片转写（每片 20 秒），逐片流式识别并拼接带有精确时间戳的 `TranscriptSegment`；
3. 增加单片退避重试（处理 `E5008 模型并发已满`）与平滑间隔（0.3s），保障长音频全量转写不中断；
4. 跑通全部单元测试与前端构建自检。

## 锁定修改文件清单
- `backend/.env`
- `backend/app/adapters/asr.py`
- `backend/tests/test_ai_adapters.py`

## 自检记录
- `backend`: `.\.venv\Scripts\python -m unittest discover tests` 15 个测试全部通过。
- `frontend`: `npm run build` 打包构建无报错。
- 链路验证：实测调用本地 9001 端口 ASR 服务，分片流式转录成功，退避重试机制生效。
