# 任务登记：修复 ASR 音频解码与支持云端切换

- 任务ID: TASK-008
- 状态: IN_PROGRESS
- 创建时间: 2026-10-12
- 责任Agent: Antigravity

## 任务目标
1. 彻底解决“全部识别为‘嗯’”的根本问题：此前缺失 ffmpeg 导致将未解码的 MP3/M4A 压缩位流当作 PCM 传给 ASR 模型。在虚拟环境中安装 `imageio-ffmpeg` 并为 `backend/app/adapters/asr.py` 补充自适应 ffmpeg 探测，确保音频被正确解码为 16000Hz 16-bit 单声道 PCM；
2. 严禁未解码兜底：若系统无法解析音频，显式报错而非向模型投喂不可读压缩数据；
3. 为用户提供清晰的云端 ASR 切换配置说明（如 DashScope SenseVoice / Whisper）；
4. 跑通单元测试自检，并重新对刚才识别为“嗯”的录音执行真正的课堂转写。

## 锁定修改文件清单
- `backend/app/adapters/asr.py`
- `backend/tests/test_ai_adapters.py`
