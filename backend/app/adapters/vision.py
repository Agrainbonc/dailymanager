from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from app.adapters.contracts import SlideVisualAnalysis, VisionProvider

logger = logging.getLogger(__name__)


def _strip_markdown_fence(content: str) -> str:
    text = content.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else text


class MockVisionProvider:
    """开箱即用的离线/测试多模态视觉适配器。"""

    name = "mock_vision"

    def analyze_slide(
        self,
        image_path: Path,
        *,
        page_number: int,
        native_text: str,
    ) -> SlideVisualAnalysis:
        cleaned_text = [line.strip() for line in native_text.splitlines() if line.strip()]
        title = cleaned_text[0] if cleaned_text else f"第 {page_number} 页幻灯片"
        return SlideVisualAnalysis(
            page_number=page_number,
            summary=f"本页重点展示：{title}。包含关键公式、结构框图与教学概念示意。",
            key_elements=cleaned_text[:4] if cleaned_text else ["课程教学大纲", "核心概念解析", "例题计算演示"],
            confidence=0.96,
            uncertainty=None,
        )

    def analyze_image(
        self,
        image_bytes: bytes,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        # 如果是课表识别场景的 Mock 返回（基于真实学期课表，涵盖一周多节课情况）
        if "课表" in prompt or "课程表" in prompt:
            return json.dumps(
                {
                    "courses": [
                        {
                            "course_name": "人工智能导论（理工）",
                            "weekday": 1,
                            "start_time": "08:00",
                            "end_time": "09:40",
                            "location": "西教学楼-西4-402",
                            "confidence": 98,
                        },
                        {
                            "course_name": "基础日语 II",
                            "weekday": 1,
                            "start_time": "19:00",
                            "end_time": "20:40",
                            "location": "西教学楼-西3-108",
                            "confidence": 96,
                        },
                        {
                            "course_name": "工程力学基础",
                            "weekday": 2,
                            "start_time": "14:20",
                            "end_time": "16:00",
                            "location": "西教学楼-西4-504",
                            "confidence": 95,
                        },
                        {
                            "course_name": "生物医学电子学基础（I）",
                            "weekday": 2,
                            "start_time": "16:30",
                            "end_time": "18:10",
                            "location": "西教学楼-西2-201",
                            "confidence": 95,
                        },
                        {
                            "course_name": "英语学术交流",
                            "weekday": 3,
                            "start_time": "10:10",
                            "end_time": "11:50",
                            "location": "西教学楼-西3-109",
                            "confidence": 97,
                        },
                        {
                            "course_name": "人体结构学",
                            "weekday": 3,
                            "start_time": "14:20",
                            "end_time": "16:00",
                            "location": "西教学楼-西4-404",
                            "confidence": 94,
                        },
                        {
                            "course_name": "生物医学电子学基础（I）",
                            "weekday": 4,
                            "start_time": "08:00",
                            "end_time": "09:40",
                            "location": "西教学楼-西2-201",
                            "confidence": 95,
                        },
                        {
                            "course_name": "概率统计（理工类）",
                            "weekday": 4,
                            "start_time": "10:10",
                            "end_time": "11:50",
                            "location": "西教学楼-西4-305",
                            "confidence": 96,
                        },
                        {
                            "course_name": "马克思主义基本原理",
                            "weekday": 5,
                            "start_time": "08:55",
                            "end_time": "11:50",
                            "location": "西教学楼-西2-301",
                            "confidence": 98,
                        },
                        {
                            "course_name": "人体结构学",
                            "weekday": 5,
                            "start_time": "14:20",
                            "end_time": "16:00",
                            "location": "西教学楼-西4-404",
                            "confidence": 94,
                        },
                        {
                            "course_name": "工程力学基础",
                            "weekday": 5,
                            "start_time": "16:30",
                            "end_time": "18:10",
                            "location": "西教学楼-西4-504",
                            "confidence": 95,
                        },
                        {
                            "course_name": "形势与政策（二）",
                            "weekday": 6,
                            "start_time": "14:20",
                            "end_time": "18:10",
                            "location": "西教学楼-西2-203",
                            "confidence": 93,
                        },
                    ]
                },
                ensure_ascii=False,
            )
        return json.dumps({"summary": "图像识别分析完成", "elements": ["教学资料", "课件示意图"]}, ensure_ascii=False)


class OpenAIVisionProvider:
    """基于 OpenAI Chat Completions 多模态规范的通用视觉适配器。

    支持：
    - Gemini 1.5 / 2.0 (OpenAI 兼容端点或 Google API)
    - 阿里 DashScope (qwen-vl-max / qwen2.5-vl)
    - 本地 vLLM / Ollama
    参考 BME_notebook/backend/app/services/multimodal_parser.py 中使用 base64 封装。
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("VISION_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("DASHSCOPE_API_KEY", "")
        # 如果配置了 DASHSCOPE_API_KEY 且没有明确 base_url，优先适配 DashScope 兼容端点
        if not base_url and os.getenv("DASHSCOPE_API_KEY") and not os.getenv("OPENAI_BASE_URL"):
            self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            self.model = model or os.getenv("VISION_MODEL", "qwen-vl-max")
        else:
            self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
            self.model = model or os.getenv("VISION_MODEL", "gpt-4o")

        self.name = f"openai_vision({self.model})"

    def _call_vlm(self, image_bytes: bytes, prompt: str, *, mime_type: str = "image/png", system_prompt: str | None = None) -> str:
        if not self.api_key:
            raise ValueError("未配置 API Key，无法调用多模态视觉模型")

        b64_data = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64_data}"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        )

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 4096,
        }

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result_json = json.loads(resp.read().decode("utf-8"))
                choices = result_json.get("choices") or []
                if not choices:
                    return ""
                return choices[0]["message"]["content"]
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"视觉模型请求失败 (HTTP {exc.code}): {err_body}") from exc

    def analyze_image(self, image_bytes: bytes, prompt: str, *, system_prompt: str | None = None) -> str:
        return self._call_vlm(image_bytes, prompt, system_prompt=system_prompt)

    def analyze_slide(
        self,
        image_path: Path,
        *,
        page_number: int,
        native_text: str,
    ) -> SlideVisualAnalysis:
        with image_path.open("rb") as f:
            image_bytes = f.read()

        mime_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
        prompt = (
            f"以下是教学课件第 {page_number} 页的截图，该页原生提取文字为：\n"
            f"```text\n{native_text}\n```\n\n"
            "请基于图片图像与上下文，分析本页课件。请只返回 JSON 对象，格式如下：\n"
            "{\n"
            '  "summary": "简短中文总结本页核心内容（100字以内）",\n'
            '  "key_elements": ["关键概念或图表/公式/结论1", "重点2", ...],\n'
            '  "confidence": 0.95,\n'
            '  "uncertainty": null\n'
            "}"
        )

        try:
            raw_response = self._call_vlm(
                image_bytes,
                prompt,
                mime_type=mime_type,
                system_prompt="你是专业的课堂课件理解助手。请严格按照要求返回标准 JSON。",
            )
            cleaned = _strip_markdown_fence(raw_response)
            parsed = json.loads(cleaned)
            return SlideVisualAnalysis(
                page_number=page_number,
                summary=parsed.get("summary", "未能生成摘要"),
                key_elements=parsed.get("key_elements", []),
                confidence=float(parsed.get("confidence", 0.9)),
                uncertainty=parsed.get("uncertainty"),
            )
        except Exception as exc:
            logger.warning("多模态幻灯片分析失败，回退为基础文本解析: %s", exc)
            return MockVisionProvider().analyze_slide(image_path, page_number=page_number, native_text=native_text)


def get_vision_provider() -> VisionProvider:
    """根据环境变量配置工厂获取当前激活的 Vision Provider。"""
    provider_name = os.getenv("DAILY_MANAGER_VISION_PROVIDER", "").strip().lower()
    has_key = bool(os.getenv("VISION_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("DASHSCOPE_API_KEY"))

    if provider_name == "openai" or provider_name == "dashscope" or (not provider_name and has_key):
        return OpenAIVisionProvider()
    return MockVisionProvider()
