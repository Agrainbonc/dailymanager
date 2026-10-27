from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import session_scope
from app.models import AppSetting
from app.schemas import AsrSettingsConfig, SystemSettingsRead, SystemSettingsUpdate, VisionSettingsConfig

logger = logging.getLogger(__name__)

SYSTEM_SETTINGS_KEY = "system_settings_v1"


def get_default_asr_config() -> AsrSettingsConfig:
    env_provider = os.getenv("DAILY_MANAGER_ASR_PROVIDER", "").strip().lower()
    provider = "zhixin_ws"
    if env_provider in {"dashscope", "openai", "mock", "zhixin_ws"}:
        provider = env_provider
    elif os.getenv("DASHSCOPE_API_KEY"):
        provider = "dashscope"

    return AsrSettingsConfig(
        provider=provider,
        dashscope_api_key=os.getenv("DASHSCOPE_API_KEY"),
        dashscope_model=os.getenv("DASHSCOPE_ASR_MODEL", "qwen-audio-turbo"),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1"),
        openai_api_key=os.getenv("OPENAI_API_KEY", "local"),
        openai_model=os.getenv("OPENAI_ASR_MODEL", "whisper-1"),
        zhixin_ws_url=os.getenv("ZHIXIN_ASR_URL", "ws://127.0.0.1:9001/v1/stream"),
        zhixin_token=os.getenv("ZHIXIN_MODEL_CORE_TOKEN") or os.getenv("ZHIXIN_ASR_TOKEN") or "change-me",
    )


def get_default_vision_config() -> VisionSettingsConfig:
    return VisionSettingsConfig(
        provider="dashscope" if os.getenv("DASHSCOPE_API_KEY") else "mock",
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        model=os.getenv("VISION_MODEL", "qwen-vl-max"),
    )


def load_system_settings(db: Session) -> SystemSettingsRead:
    # 投递目录优先从已有 key 兼容读取
    input_dir_setting = db.scalar(select(AppSetting).where(AppSetting.key == "input_directory"))
    output_dir_setting = db.scalar(select(AppSetting).where(AppSetting.key == "output_directory"))
    input_dir = input_dir_setting.value.strip() if input_dir_setting and input_dir_setting.value.strip() else None
    output_dir = output_dir_setting.value.strip() if output_dir_setting and output_dir_setting.value.strip() else None

    setting_row = db.scalar(select(AppSetting).where(AppSetting.key == SYSTEM_SETTINGS_KEY))
    if not setting_row or not setting_row.value.strip():
        # 初始化默认
        default_asr = get_default_asr_config()
        default_vision = get_default_vision_config()
        return SystemSettingsRead(
            input_directory=input_dir,
            output_directory=output_dir,
            asr=default_asr,
            vision=default_vision,
        )

    try:
        data = json.loads(setting_row.value)
        asr_data = data.get("asr") or {}
        vision_data = data.get("vision") or {}
        return SystemSettingsRead(
            input_directory=input_dir or data.get("input_directory"),
            output_directory=output_dir or data.get("output_directory"),
            asr=AsrSettingsConfig(**asr_data) if asr_data else get_default_asr_config(),
            vision=VisionSettingsConfig(**vision_data) if vision_data else get_default_vision_config(),
        )
    except Exception as exc:
        logger.warning("解析系统设置 JSON 失败，回退为默认: %s", exc)
        return SystemSettingsRead(
            input_directory=input_dir,
            output_directory=output_dir,
            asr=get_default_asr_config(),
            vision=get_default_vision_config(),
        )


def save_system_settings(payload: SystemSettingsUpdate, db: Session) -> SystemSettingsRead:
    curr = load_system_settings(db)

    # 1. 保存目录
    if payload.input_directory is not None:
        curr.input_directory = payload.input_directory.strip() or None
        in_setting = db.scalar(select(AppSetting).where(AppSetting.key == "input_directory"))
        if not in_setting:
            in_setting = AppSetting(key="input_directory", value=curr.input_directory or "")
            db.add(in_setting)
        else:
            in_setting.value = curr.input_directory or ""

    if payload.output_directory is not None:
        curr.output_directory = payload.output_directory.strip() or None
        out_setting = db.scalar(select(AppSetting).where(AppSetting.key == "output_directory"))
        if not out_setting:
            out_setting = AppSetting(key="output_directory", value=curr.output_directory or "")
            db.add(out_setting)
        else:
            out_setting.value = curr.output_directory or ""

    # 2. 保存 ASR & Vision
    if payload.asr is not None:
        curr.asr = payload.asr
    if payload.vision is not None:
        curr.vision = payload.vision

    # 3. 序列化持久化
    data = {
        "input_directory": curr.input_directory,
        "output_directory": curr.output_directory,
        "asr": curr.asr.model_dump(),
        "vision": curr.vision.model_dump(),
    }
    system_row = db.scalar(select(AppSetting).where(AppSetting.key == SYSTEM_SETTINGS_KEY))
    if not system_row:
        system_row = AppSetting(key=SYSTEM_SETTINGS_KEY, value=json.dumps(data, ensure_ascii=False))
        db.add(system_row)
    else:
        system_row.value = json.dumps(data, ensure_ascii=False)

    db.commit()
    return curr


def test_asr_connection(config: AsrSettingsConfig) -> tuple[bool, str, int]:
    """测试指定 ASR 配置的连通性。"""
    provider = config.provider.lower().strip()
    start_time = time.time()

    if provider == "mock":
        return True, "Mock ASR 服务已就绪（离线测试模式）", int((time.time() - start_time) * 1000)

    if provider == "dashscope":
        api_key = (config.dashscope_api_key or os.getenv("DASHSCOPE_API_KEY", "")).strip()
        if not api_key:
            return False, "未填写阿里云 DashScope API Key", 0
        try:
            req = urllib.request.Request(
                "https://dashscope.aliyuncs.com/api/v1/services/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                status = resp.status
                latency = int((time.time() - start_time) * 1000)
                if status in (200, 204):
                    return True, f"阿里云 DashScope API 鉴权连通成功 (延迟 {latency}ms)", latency
                return False, f"阿里云 DashScope API 返回状态码 {status}", latency
        except urllib.error.HTTPError as exc:
            latency = int((time.time() - start_time) * 1000)
            if exc.code == 401 or exc.code == 403:
                return False, f"DashScope API Key 无效或未授权 (HTTP {exc.code})", latency
            # 某些子接口即使 404 也证明网关鉴权通过
            return True, f"DashScope 服务节点连通成功 (HTTP {exc.code})", latency
        except Exception as exc:
            return False, f"连接阿里云 DashScope 失败: {exc}", int((time.time() - start_time) * 1000)

    if provider == "openai":
        base_url = (config.openai_base_url or "http://127.0.0.1:8000/v1").rstrip("/")
        api_key = (config.openai_api_key or "local").strip()
        try:
            req = urllib.request.Request(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                latency = int((time.time() - start_time) * 1000)
                return True, f"OpenAI/Whisper 兼容接口已成功响应 (延迟 {latency}ms)", latency
        except urllib.error.HTTPError as exc:
            latency = int((time.time() - start_time) * 1000)
            if exc.code in (401, 403):
                return False, f"API Key 鉴权失败 (HTTP {exc.code})", latency
            # 若 endpoint 存在但 models 路由不存在，也说明端口通畅
            return True, f"服务端口连通 (HTTP {exc.code})", latency
        except Exception as exc:
            return False, f"连接接口 {base_url} 失败: {exc}", int((time.time() - start_time) * 1000)

    if provider == "zhixin_ws":
        ws_url = (config.zhixin_ws_url or "ws://127.0.0.1:9001/v1/stream").strip()
        try:
            from websockets.sync.client import connect

            headers = {}
            if config.zhixin_token:
                headers["Authorization"] = f"Bearer {config.zhixin_token}"
            with connect(ws_url, additional_headers=headers, open_timeout=5, close_timeout=2) as ws:
                latency = int((time.time() - start_time) * 1000)
                return True, f"Zhixin ASR WebSocket 握手成功 (延迟 {latency}ms)", latency
        except Exception as exc:
            return False, f"连接本地 Zhixin WebSocket ({ws_url}) 失败: {exc}", int((time.time() - start_time) * 1000)

    return False, f"未知 ASR 提供方: {provider}", 0
