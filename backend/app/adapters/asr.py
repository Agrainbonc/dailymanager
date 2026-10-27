from __future__ import annotations

import base64
import json
import logging
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.adapters.contracts import AsrProvider, TranscriptionResult, TranscriptSegment

logger = logging.getLogger(__name__)


def _find_ffmpeg_executable() -> str | None:
    """自适应探测可用的 ffmpeg 可执行文件路径。"""
    # 1. 优先使用 Python 虚拟环境内置的 imageio-ffmpeg
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).is_file():
            return exe
    except (ImportError, Exception):
        pass

    # 2. 检查环境变量自定义指定
    env_bin = os.getenv("FFMPEG_BINARY") or os.getenv("FFMPEG_PATH")
    if env_bin and Path(env_bin).is_file():
        return env_bin

    # 3. 检查系统全局 PATH 或常用已知路径
    for candidate in [
        "ffmpeg",
        r"D:\codes\items\deskpet\Sakura\tts\gpt\runtime\ffmpeg.exe",
        r"D:\oopz\oopz\ffmpeg.exe",
    ]:
        try:
            res = subprocess.run([candidate, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                return candidate
        except (FileNotFoundError, OSError):
            continue
    return None


def _convert_audio_to_pcm16le(audio_path: Path) -> bytes:
    """提取或转换音频为 16000Hz、16位小端、单声道原始 PCM 数据。"""
    # 1. 优先使用 ffmpeg 转换（支持 MP3/M4A/AAC/FLAC/WAV/OGG 等全部格式）
    ffmpeg_exe = _find_ffmpeg_executable()
    if ffmpeg_exe:
        try:
            cmd = [
                ffmpeg_exe,
                "-y",
                "-i",
                str(audio_path),
                "-f",
                "s16le",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-",
            ]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
            if proc.stdout:
                return proc.stdout
        except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
            logger.warning("ffmpeg 解码音频失败：%s", exc)

    # 2. 如果是标准单声道 16kHz WAV 文件，尝试使用标准库 wave 解析
    if audio_path.suffix.lower() == ".wav":
        try:
            with wave.open(str(audio_path), "rb") as wf:
                n_channels, sampwidth, framerate, n_frames, _, _ = wf.getparams()
                frames = wf.readframes(n_frames)
                if framerate == 16000 and sampwidth == 2 and n_channels == 1:
                    return frames
                if framerate == 16000 and sampwidth == 2 and n_channels == 2:
                    # 双声道取左声道 (每4字节取前2字节)
                    out = bytearray()
                    for idx in range(0, len(frames), 4):
                        out.extend(frames[idx : idx + 2])
                    return bytes(out)
        except Exception:
            pass

    # 3. 若无可用解码器，显式抛出明确异常，严禁将未解码的 MP3/M4A 压缩数据当成 PCM 喂给模型
    raise RuntimeError(
        f"无法解码音频文件 {audio_path.name} 为 16kHz PCM 数据。请确保已安装 imageio-ffmpeg 或系统已配置 ffmpeg。"
    )


class ZhixinWsAsrProvider:
    """直连本地 Zhixin-AI-Companion 9001 端口的 WebSocket ASR 服务。

    遵循 ZHIXIN-MSG-1 六字段信封规范：
    - 连接 ws://127.0.0.1:9001/v1/stream
    - 鉴权：Bearer token (默认 change-me)
    - 针对长课堂录音自适应切片（每片 20 秒），逐片流式交互，避免单流超过 30 秒上限
    - 接收服务端返回的 ai.response，生成带精准时间戳的 TranscriptSegment 列表
    """

    def __init__(
        self,
        *,
        ws_url: str | None = None,
        core_token: str | None = None,
        chunk_size_bytes: int = 16000,
        slice_duration_sec: int = 20,
        timeout: float = 25.0,
        max_consecutive_errors: int = 3,
    ) -> None:
        self.ws_url = (ws_url or os.getenv("ZHIXIN_ASR_URL", "ws://127.0.0.1:9001/v1/stream")).strip()
        self.core_token = (
            core_token or os.getenv("ZHIXIN_MODEL_CORE_TOKEN") or os.getenv("ZHIXIN_ASR_TOKEN") or "change-me"
        ).strip()
        self.chunk_size_bytes = chunk_size_bytes
        self.slice_duration_sec = slice_duration_sec
        self.timeout = timeout
        self.max_consecutive_errors = max_consecutive_errors
        self.name = f"zhixin_asr({self.ws_url})"

    def _transcribe_slice(
        self,
        connect_fn,
        slice_data: bytes,
        slice_duration_ms: int,
        headers: dict,
        max_attempts: int = 3,
    ) -> str:
        stream_id = f"dm-{uuid.uuid4().hex[:12]}"
        session_id = f"session-{uuid.uuid4().hex[:8]}"

        last_error: Exception | None = None
        for attempt in range(max_attempts):
            try:
                with connect_fn(self.ws_url, additional_headers=headers, close_timeout=3) as ws:
                    # 1. 发送 audio.start
                    start_msg = {
                        "type": "audio.start",
                        "source": "core",
                        "destination": "model:asr",
                        "session": session_id,
                        "timestamp": int(time.time() * 1000),
                        "data": {
                            "stream_id": stream_id,
                            "pcm": {
                                "sample_rate": 16000,
                                "bit_depth": 16,
                                "channels": 1,
                            },
                        },
                    }
                    ws.send(json.dumps(start_msg))

                    # 2. 分帧发送当前切片的 PCM 数据
                    seq = 0
                    for frame_off in range(0, len(slice_data), self.chunk_size_bytes):
                        chunk = slice_data[frame_off : frame_off + self.chunk_size_bytes]
                        frame_msg = {
                            "type": "audio.frame",
                            "source": "core",
                            "destination": "model:asr",
                            "session": session_id,
                            "timestamp": int(time.time() * 1000),
                            "data": {
                                "stream_id": stream_id,
                                "seq": seq,
                                "pcm": base64.b64encode(chunk).decode("ascii"),
                            },
                        }
                        ws.send(json.dumps(frame_msg))
                        seq += 1

                    # 3. 发送 audio.end
                    end_msg = {
                        "type": "audio.end",
                        "source": "core",
                        "destination": "model:asr",
                        "session": session_id,
                        "timestamp": int(time.time() * 1000),
                        "data": {
                            "stream_id": stream_id,
                            "total_frames": seq,
                            "duration_ms": slice_duration_ms,
                        },
                    }
                    ws.send(json.dumps(end_msg))

                    # 4. 等待该切片的识别结果
                    while True:
                        raw_msg = ws.recv(timeout=self.timeout)
                        reply = json.loads(raw_msg)
                        reply_type = reply.get("type")
                        reply_data = reply.get("data", {})
                        if reply_type == "ai.response":
                            output = reply_data.get("output", {})
                            return str(output.get("text", "")).strip()
                        elif reply_type == "ai.error":
                            error_info = reply_data.get("error", {})
                            err_msg = error_info.get("message") or reply_data.get("message", "Zhixin ASR 服务返回错误")
                            # 若为并发繁忙则退避重试
                            if "并发" in err_msg or error_info.get("code") == "E5008":
                                time.sleep(0.8)
                                break
                            logger.warning("切片转写业务异常：%s", err_msg)
                            return ""
            except (ConnectionRefusedError, OSError, TimeoutError) as exc:
                last_error = exc
                if attempt < max_attempts - 1:
                    time.sleep(0.6)
                else:
                    logger.warning("切片网络通信失败 (尝试 %d/%d)：%s", attempt + 1, max_attempts, exc)
                    raise
            except Exception as exc:
                last_error = exc
                if attempt < max_attempts - 1:
                    time.sleep(0.6)
                else:
                    logger.warning("切片转写未知异常：%s", exc)
                    return ""
        if last_error:
            raise last_error
        return ""

    def transcribe(
        self,
        audio_path: Path,
        *,
        language_hint: str | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> TranscriptionResult:
        pcm_bytes = _convert_audio_to_pcm16le(audio_path)
        if not pcm_bytes:
            raise ValueError(f"无法读取音频数据：{audio_path.name}")

        total_duration_ms = max(1000, int(len(pcm_bytes) / 32))

        headers = {}
        if self.core_token:
            headers["Authorization"] = f"Bearer {self.core_token}"

        try:
            from websockets.sync.client import connect
        except ImportError as exc:
            raise RuntimeError("请确保已安装 websockets 库以支持 Zhixin ASR 客户端通信") from exc

        # 16000Hz, 16bit, 单声道 => 32,000 字节/秒
        slice_bytes = self.slice_duration_sec * 32000
        total_slices = max(1, (len(pcm_bytes) + slice_bytes - 1) // slice_bytes)
        segments: list[TranscriptSegment] = []
        collected_texts: list[str] = []

        offset = 0
        slice_idx = 0
        consecutive_errors = 0

        while offset < len(pcm_bytes):
            slice_data = pcm_bytes[offset : offset + slice_bytes]
            slice_start_ms = int(offset / 32)
            slice_end_ms = int((offset + len(slice_data)) / 32)
            slice_duration_ms = slice_end_ms - slice_start_ms

            slice_text = ""
            try:
                # 执行切片转写（带并发忙自动退避）
                slice_text = self._transcribe_slice(
                    connect,
                    slice_data,
                    slice_duration_ms,
                    headers,
                )
                consecutive_errors = 0
            except (ConnectionRefusedError, OSError, TimeoutError) as exc:
                consecutive_errors += 1
                logger.warning("切片 %d/%d 网络连接异常 (%d/%d): %s", slice_idx + 1, total_slices, consecutive_errors, self.max_consecutive_errors, exc)
                if consecutive_errors >= self.max_consecutive_errors:
                    raise RuntimeError(
                        f"连接 Zhixin ASR 服务 ({self.ws_url}) 连续 {consecutive_errors} 次失败，可能服务已挂起或离线，已触发安全熔断保护: {exc}"
                    ) from exc
            except Exception as exc:
                consecutive_errors += 1
                logger.warning("切片 %d/%d 转写异常: %s", slice_idx + 1, total_slices, exc)
                if consecutive_errors >= self.max_consecutive_errors:
                    raise RuntimeError(f"切片转写连续失败达到上限: {exc}") from exc

            if slice_text:
                collected_texts.append(slice_text)
                segments.append(
                    TranscriptSegment(
                        start_ms=slice_start_ms,
                        end_ms=slice_end_ms,
                        text=slice_text,
                    )
                )

            # 触发进度回调
            if progress_callback:
                try:
                    progress_callback(slice_idx + 1, total_slices, slice_text or "")
                except Exception as cb_exc:
                    logger.debug("进度回调异常：%s", cb_exc)

            offset += slice_bytes
            slice_idx += 1
            # 每个切片间隔 0.25 秒，让 GPU 显存与会话平稳释放
            time.sleep(0.25)

        full_text = "\n".join(collected_texts) if collected_texts else ""
        return TranscriptionResult(
            full_text=full_text,
            duration_ms=total_duration_ms,
            language=language_hint or "zh",
            segments=segments,
        )


class MockAsrProvider:
    """开箱即用的离线/测试 ASR 适配器。无需外部依赖或 API Key。"""

    name = "mock_asr"

    def transcribe(
        self,
        audio_path: Path,
        *,
        language_hint: str | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> TranscriptionResult:
        stem = audio_path.stem
        # 根据文件名生成更逼真的仿真分段
        time_hint = "课堂录音"
        match = re.search(r"(\d{1,2}点\d{1,2}分|\d{1,2}[:：]\d{1,2})", stem)
        if match:
            time_hint = f"{match.group(1)} 课堂记录"

        segments = [
            TranscriptSegment(
                start_ms=0,
                end_ms=4500,
                text=f"同学们上课了，今天开始讲解 {stem} 相关内容。",
                confidence=0.95,
                speaker="教师",
            ),
            TranscriptSegment(
                start_ms=5000,
                end_ms=12000,
                text="请大家翻开教材对应章节，注意本次课程的核心概念与公式推导。",
                confidence=0.92,
                speaker="教师",
            ),
            TranscriptSegment(
                start_ms=12500,
                end_ms=21000,
                text=f"接下来我们来看具体的例题分析与应用背景（{time_hint}）。",
                confidence=0.94,
                speaker="教师",
            ),
        ]
        full_text = "".join(seg.text for seg in segments)
        if progress_callback:
            try:
                progress_callback(1, 1, full_text)
            except Exception:
                pass
        return TranscriptionResult(
            full_text=full_text,
            duration_ms=21000,
            language=language_hint or "zh",
            segments=segments,
        )


class OpenAiCompatibleAsrProvider:
    """兼容 OpenAI 音频转录接口 (v1/audio/transcriptions) 的适配器。"""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "whisper-1",
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.model = os.getenv("OPENAI_ASR_MODEL", model)
        self.name = f"openai_asr({self.model})"

    def transcribe(
        self,
        audio_path: Path,
        *,
        language_hint: str | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> TranscriptionResult:
        if not self.api_key:
            raise ValueError("未配置 OPENAI_API_KEY，无法调用 OpenAI 兼容 ASR 接口")

        boundary = "----DailyManagerBoundary" + os.urandom(8).hex()
        url = f"{self.base_url}/audio/transcriptions"

        with audio_path.open("rb") as f:
            audio_bytes = f.read()

        body = bytearray()
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n{self.model}\r\n".encode())
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"response_format\"\r\n\r\nverbose_json\r\n".encode())
        if language_hint:
            body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"language\"\r\n\r\n{language_hint}\r\n".encode())

        content_type = "audio/mpeg" if audio_path.suffix.lower() == ".mp3" else "audio/wav"
        body.extend(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{audio_path.name}\"\r\nContent-Type: {content_type}\r\n\r\n".encode()
        )
        body.extend(audio_bytes)
        body.extend(f"\r\n--{boundary}--\r\n".encode())

        req = urllib.request.Request(
            url,
            data=bytes(body),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                result_json = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"OpenAI ASR 请求失败 (HTTP {exc.code}): {err_body}") from exc

        full_text = result_json.get("text", "")
        raw_segments = result_json.get("segments") or []
        segments: list[TranscriptSegment] = []
        for item in raw_segments:
            start_ms = int(float(item.get("start", 0)) * 1000)
            end_ms = int(float(item.get("end", 0)) * 1000)
            text = str(item.get("text", "")).strip()
            confidence = float(item.get("avg_logprob", 0.0)) if "avg_logprob" in item else None
            segments.append(TranscriptSegment(start_ms=start_ms, end_ms=end_ms, text=text, confidence=confidence))

        duration_ms = int(float(result_json.get("duration", 0)) * 1000) if "duration" in result_json else 0
        if progress_callback:
            try:
                progress_callback(1, 1, full_text)
            except Exception:
                pass
        return TranscriptionResult(
            full_text=full_text,
            duration_ms=duration_ms,
            language=result_json.get("language", language_hint or "zh"),
            segments=segments,
        )


class DashScopeAsrProvider:
    """阿里云 DashScope (Paraformer / SenseVoice / Qwen-Audio) ASR 适配器。"""

    def __init__(self, *, api_key: str | None = None, model: str = "qwen-audio-turbo") -> None:
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY", "")
        self.model = os.getenv("DASHSCOPE_ASR_MODEL", model)
        self.name = f"dashscope_asr({self.model})"

    def transcribe(
        self,
        audio_path: Path,
        *,
        language_hint: str | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> TranscriptionResult:
        if not self.api_key:
            raise ValueError("未配置 DASHSCOPE_API_KEY，无法调用 DashScope ASR")

        if os.name == "nt":
            drive, rest = os.path.splitdrive(str(audio_path.resolve()))
            audio_url = f"file://{drive[0].lower()}:{rest}".replace("\\", "/") if drive else f"file://{audio_path.resolve()}".replace("\\", "/")
        else:
            audio_url = f"file://{audio_path.resolve()}"

        try:
            import dashscope
            from dashscope import MultiModalConversation

            dashscope.api_key = self.api_key
            dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

            prompt = (
                "请转写这段课堂音频的所有对话内容。按以下格式输出：\n"
                "## 转写内容\n"
                "### 00:00 - 01:30\n"
                "分段文字...\n"
            )
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"audio": audio_url},
                        {"text": prompt},
                    ],
                }
            ]
            response = MultiModalConversation.call(model=self.model, messages=messages)
            if response.status_code != 200:
                raise RuntimeError(f"DashScope ASR 返回错误: {response.code} {response.message}")

            text = response.output.choices[0].message.content[0].get("text", "")
            segments: list[TranscriptSegment] = []
            curr_start = 0
            curr_end = 0
            for part in text.split("### "):
                if not part.strip():
                    continue
                lines = part.strip().split("\n")
                time_line = lines[0].strip()
                seg_text = "\n".join(lines[1:]).strip()
                time_match = re.search(r"(\d{1,2}):(\d{2})\s*[-~至]\s*(\d{1,2}):(\d{2})", time_line)
                if time_match:
                    start_sec = int(time_match.group(1)) * 60 + int(time_match.group(2))
                    end_sec = int(time_match.group(3)) * 60 + int(time_match.group(4))
                    curr_start = start_sec * 1000
                    curr_end = end_sec * 1000
                if seg_text:
                    segments.append(TranscriptSegment(start_ms=curr_start, end_ms=curr_end, text=seg_text))

            if progress_callback:
                try:
                    progress_callback(1, 1, text)
                except Exception:
                    pass
            return TranscriptionResult(
                full_text=text,
                duration_ms=curr_end,
                language=language_hint or "zh",
                segments=segments,
            )
        except ImportError:
            logger.warning("未安装 dashscope 依赖，回退为 MockAsrProvider 结果")
            return MockAsrProvider().transcribe(audio_path, language_hint=language_hint, progress_callback=progress_callback)


class QwenAsrLocalProvider:
    """本地 Qwen3-ASR 适配器。"""

    def __init__(self, model_path: str = "ai/models/Qwen3-ASR-1.7B", device: str = "auto") -> None:
        self.model_path = model_path
        self.device = device
        self.name = "qwen_local_asr"
        self._model = None

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from qwen_asr import Qwen3ASRModel

            device_map = "cuda:0" if torch.cuda.is_available() and self.device != "cpu" else "cpu"
            self._model = Qwen3ASRModel.from_pretrained(
                self.model_path,
                device_map=device_map,
                max_inference_batch_size=1,
            )
        except ImportError as exc:
            raise RuntimeError("请安装 qwen-asr 与 PyTorch 依赖以启用本地 Qwen3-ASR") from exc

    def transcribe(
        self,
        audio_path: Path,
        *,
        language_hint: str | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> TranscriptionResult:
        try:
            self._ensure_model()
            result = self._model.transcribe(audio_path=str(audio_path), language="Chinese")
            full_text = getattr(result[0], "text", str(result))
            if progress_callback:
                try:
                    progress_callback(1, 1, full_text)
                except Exception:
                    pass
            return TranscriptionResult(
                full_text=full_text,
                duration_ms=0,
                language=language_hint or "zh",
                segments=[TranscriptSegment(start_ms=0, end_ms=0, text=full_text)],
            )
        except Exception as exc:
            logger.warning("本地 Qwen3-ASR 执行失败，使用 Mock 兜底: %s", exc)
            return MockAsrProvider().transcribe(audio_path, language_hint=language_hint, progress_callback=progress_callback)


def get_asr_provider(custom_config: Any = None) -> AsrProvider:
    """获取当前激活的 ASR Provider。

    支持运行时从数据库配置读取，并优先使用前端用户设置的值；若未配置或异常则按环境变量策略兜底。
    """
    config = custom_config
    if config is None:
        try:
            from app.database import session_scope
            from app.services.settings_service import load_system_settings

            with session_scope() as db:
                system_settings = load_system_settings(db)
                config = system_settings.asr
        except Exception:
            config = None

    if config is not None:
        p = getattr(config, "provider", "").strip().lower()
        if p == "dashscope":
            return DashScopeAsrProvider(
                api_key=getattr(config, "dashscope_api_key", None),
                model=getattr(config, "dashscope_model", "qwen-audio-turbo") or "qwen-audio-turbo",
            )
        if p == "openai":
            return OpenAiCompatibleAsrProvider(
                api_key=getattr(config, "openai_api_key", None),
                base_url=getattr(config, "openai_base_url", None),
                model=getattr(config, "openai_model", "whisper-1") or "whisper-1",
            )
        if p == "mock":
            return MockAsrProvider()
        if p == "zhixin_ws":
            return ZhixinWsAsrProvider(
                ws_url=getattr(config, "zhixin_ws_url", None),
                core_token=getattr(config, "zhixin_token", None),
            )

    # 兜底：环境变量策略
    provider_name = os.getenv("DAILY_MANAGER_ASR_PROVIDER", "").strip().lower()
    if provider_name == "mock":
        return MockAsrProvider()
    if provider_name == "dashscope":
        return DashScopeAsrProvider()
    if provider_name == "openai":
        return OpenAiCompatibleAsrProvider()
    if provider_name == "qwen_local":
        return QwenAsrLocalProvider()
    return ZhixinWsAsrProvider()
