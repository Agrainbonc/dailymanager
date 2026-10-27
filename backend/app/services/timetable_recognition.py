from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import time
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.vision import get_vision_provider
from app.models import Course
from app.services.watch_service import directory_watch_service

logger = logging.getLogger(__name__)


class TimetableCandidateItem(BaseModel):
    course_name: str
    weekday: int = Field(ge=1, le=7, description="1代表周一，7代表周日")
    start_time: str = Field(pattern=r"^([01]?\d|2[0-3]):[0-5]\d$")
    end_time: str = Field(pattern=r"^([01]?\d|2[0-3]):[0-5]\d$")
    location: str | None = None
    confidence: int = Field(default=85, ge=0, le=100)
    warnings: list[str] = Field(default_factory=list)


class TimetableRecognitionResult(BaseModel):
    image_hash: str
    filename: str
    candidates: list[TimetableCandidateItem]
    warnings: list[str] = Field(default_factory=list)


class TimetableApplyPayload(BaseModel):
    items: list[TimetableCandidateItem]


class TimetableApplyResult(BaseModel):
    created_courses_count: int
    updated_courses_count: int
    total_slots_count: int
    course_names: list[str]


def _strip_markdown_fence(content: str) -> str:
    text = content.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else text


def _validate_time_order(start_str: str, end_str: str) -> bool:
    try:
        start = time.fromisoformat(start_str.padStart(5, "0") if hasattr(start_str, "padStart") else start_str.zfill(5))
        end = time.fromisoformat(end_str.padStart(5, "0") if hasattr(end_str, "padStart") else end_str.zfill(5))
        return start < end
    except ValueError:
        return False


def _check_conflicts(candidates: list[TimetableCandidateItem]) -> None:
    """检查候选课表中相互重叠冲突的课程时段。"""
    for i, a in enumerate(candidates):
        try:
            a_start = time.fromisoformat(a.start_time.zfill(5))
            a_end = time.fromisoformat(a.end_time.zfill(5))
        except ValueError:
            a.warnings.append("时间格式非法")
            continue

        if a_start >= a_end:
            a.warnings.append("结束时间不得早于或等于开始时间")

        for j in range(i + 1, len(candidates)):
            b = candidates[j]
            if a.weekday != b.weekday:
                continue
            try:
                b_start = time.fromisoformat(b.start_time.zfill(5))
                b_end = time.fromisoformat(b.end_time.zfill(5))
            except ValueError:
                continue

            # 判断是否有重叠
            if max(a_start, b_start) < min(a_end, b_end):
                msg = f"与“{b.course_name}”({b.start_time}-{b.end_time}) 存在时段冲突"
                if msg not in a.warnings:
                    a.warnings.append(msg)
                msg_b = f"与“{a.course_name}”({a.start_time}-{a.end_time}) 存在时段冲突"
                if msg_b not in b.warnings:
                    b.warnings.append(msg_b)


def recognize_timetable_image(
    image_bytes: bytes,
    filename: str,
    provider: Any = None,
) -> TimetableRecognitionResult:
    """使用多模态大模型从课表截图中提取结构化课表安排。"""
    active_provider = provider or get_vision_provider()
    image_hash = hashlib.sha256(image_bytes).hexdigest()

    prompt = (
        "这是一张完整的学校课表排课截图（包含周一至周日各节次排课单元）。\n"
        "请完整、地毯式扫描课表网格，提取整张课表中【所有】课程的上课安排，切勿只识别前几行，切勿遗漏！\n\n"
        "【至关重要的规则 - 一周多节课】：\n"
        "1. 同一门课程在一周内常常有 2 节或多节（例如同一门课周二有一节、周五又有一节；或者同一天上午有一节、下午又有一节）。\n"
        "2. 请务必将【每一个具体的上课时段】都作为独立的一个元素输出到 courses 列表中！\n"
        "3. 允许且必须输出多个 course_name 完全相同、但 weekday 或 start_time 不同的记录，严禁进行名称去重或合并丢弃！\n\n"
        "针对识别到的每个排课时段单元，请提取：\n"
        "- course_name: 课程完整名称（字符串，去除杂乱符号）\n"
        "- weekday: 星期几（数字 1-7，1 代表周一，...，7 代表周日）\n"
        "- start_time: 开始时间（格式 HH:MM，如 08:00、14:20）\n"
        "- end_time: 结束时间（格式 HH:MM，如 09:40、16:00）\n"
        "- location: 上课地点/教室（字符串或 null）\n"
        "- confidence: 识别置信度（0-100的整数）\n\n"
        "请务必只返回 JSON 对象，格式示范：\n"
        "{\n"
        '  "courses": [\n'
        "    {\n"
        '      "course_name": "工程力学基础",\n'
        '      "weekday": 2,\n'
        '      "start_time": "14:20",\n'
        '      "end_time": "16:00",\n'
        '      "location": "西4-504",\n'
        '      "confidence": 95\n'
        "    },\n"
        "    {\n"
        '      "course_name": "工程力学基础",\n'
        '      "weekday": 5,\n'
        '      "start_time": "16:30",\n'
        '      "end_time": "18:10",\n'
        '      "location": "西4-504",\n'
        '      "confidence": 95\n'
        "    }\n"
        "  ]\n"
        "}"
    )

    system_prompt = (
        "你是一个极其严谨的教务课表多模态结构化提取助手。你能够完整扫描整张课表网格，"
        "准确提取出所有周一至周日的排课时段。对于一周内多次上课的同一课程，你会为每个时段分别保留一条完整记录。"
        "严格只返回合法的 JSON，不要输出任何额外的 markdown 解释。"
    )

    warnings: list[str] = []
    candidates: list[TimetableCandidateItem] = []

    try:
        raw_output = active_provider.analyze_image(
            image_bytes,
            prompt,
            system_prompt=system_prompt,
        )
        cleaned = _strip_markdown_fence(raw_output)
        data = json.loads(cleaned)
        raw_courses = data.get("courses") or []

        for item in raw_courses:
            name = str(item.get("course_name", "")).strip()
            if not name:
                continue
            weekday = int(item.get("weekday", 1))
            start_str = str(item.get("start_time", "08:00")).zfill(5)
            end_str = str(item.get("end_time", "09:40")).zfill(5)
            location = str(item.get("location")).strip() if item.get("location") else None
            confidence = int(item.get("confidence", 85))

            candidate = TimetableCandidateItem(
                course_name=name,
                weekday=max(1, min(7, weekday)),
                start_time=start_str,
                end_time=end_str,
                location=location,
                confidence=max(0, min(100, confidence)),
            )
            candidates.append(candidate)

        # 按星期和开始时间自然排序，方便用户核对
        candidates.sort(key=lambda c: (c.weekday, c.start_time, c.course_name))

    except Exception as exc:
        logger.warning("课表截图大模型识别失败或解析错误: %s", exc)
        warnings.append(f"模型识别遇到异常: {str(exc)[:200]}")

    # 规则冲突校验
    _check_conflicts(candidates)

    return TimetableRecognitionResult(
        image_hash=image_hash,
        filename=filename,
        candidates=candidates,
        warnings=warnings,
    )


def apply_timetable_candidates(
    session: Session,
    items: list[TimetableCandidateItem],
) -> TimetableApplyResult:
    """将用户确认的课表候选批量应用至本地数据库中。"""
    # 按课程名归类合并 schedule slots
    course_slots: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        name = item.course_name.strip()
        if not name:
            continue
        slot = {
            "weekday": item.weekday,
            "start_time": item.start_time.zfill(5),
            "end_time": item.end_time.zfill(5),
        }
        course_slots.setdefault(name, []).append(slot)

    created_count = 0
    updated_count = 0
    total_slots = sum(len(slots) for slots in course_slots.values())
    affected_courses: list[str] = []

    for name, new_slots in course_slots.items():
        # 查找课程是否存在
        course = session.scalar(select(Course).where(Course.name == name))
        if course:
            try:
                existing_slots = json.loads(course.schedule_json or "[]")
            except Exception:
                existing_slots = []
            # 合并去重 slots
            combined = existing_slots + [
                s for s in new_slots if s not in existing_slots
            ]
            course.schedule_json = json.dumps(combined, ensure_ascii=False)
            updated_count += 1
        else:
            course = Course(
                name=name,
                aliases_json="[]",
                keywords_json="[]",
                schedule_json=json.dumps(new_slots, ensure_ascii=False),
            )
            session.add(course)
            created_count += 1
        affected_courses.append(name)

    session.flush()
    directory_watch_service.refresh()

    return TimetableApplyResult(
        created_courses_count=created_count,
        updated_courses_count=updated_count,
        total_slots_count=total_slots,
        course_names=affected_courses,
    )
