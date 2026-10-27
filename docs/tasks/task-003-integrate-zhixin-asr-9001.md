# 任务登记：集成 Zhixin ASR 9001 端口直连服务

- 任务ID: TASK-003
- 状态: DONE
- 创建时间: 2026-10-12
- 完成时间: 2026-10-12
- 责任Agent: Antigravity

## 任务目标
1. 参考 `D:\codes\project\Zhixin-AI-Companion\ai` 中的 ASR WebSocket 协议（ZHIXIN-MSG-1 信封、`audio.start`/`audio.frame`/`audio.end`、16kHz/16bit/单声道 PCM 流传输）；
2. 实现 `ZhixinWsAsrProvider`，支持将音频转换为标准 16kHz PCM 并通过 WebSocket 发送至 `ws://127.0.0.1:9001/v1/stream` 获取转写结果；
3. 将 Zhixin 9001 端口 ASR 作为优先/默认 ASR 提供方（支持免密或 Token 鉴权），并在 `.env` 和 `.env.example` 中完善默认配置；
4. 编写针对 `ZhixinWsAsrProvider` 协议封装与转录行为的单元测试；
5. 跑通全量自检。

## 锁定修改文件清单
- `backend/app/adapters/asr.py`
- `backend/app/adapters/__init__.py`
- `backend/app/config.py`
- `backend/.env`
- `backend/.env.example`
- `backend/tests/test_ai_adapters.py`

## 验收结果
- 协议对接完成：严格遵循 ZHIXIN-MSG-1 信封，流式分包发送 16kHz/16bit 单声道 PCM 并接收 `ai.response`；
- 单元测试验证：13 个测试全部通过（含 WebSocket 协议封包测试与转写任务流测试）；
- 配置生效：`backend/.env` 默认配置 `DAILY_MANAGER_ASR_PROVIDER=zhixin` 和 `ZHIXIN_ASR_URL=ws://127.0.0.1:9001/v1/stream`，无需在本工程配置任何外部 ASR 权重或 Key。
