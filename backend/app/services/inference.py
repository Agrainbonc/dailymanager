from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path

from app.config import SUPPORTED_AUDIO_EXTENSIONS, SUPPORTED_PRESENTATION_EXTENSIONS
from app.models import Course


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value.lower())


def infer_material_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in SUPPORTED_AUDIO_EXTENSIONS:
        return "audio"
    if suffix in SUPPORTED_PRESENTATION_EXTENSIONS:
        return "presentation"
    return "other"


def infer_lesson_date(path: Path) -> date:
    match = re.search(r"(20\d{2})\s*(?:[-_./]|年)?\s*(\d{1,2})\s*(?:[-_./]|月)?\s*(\d{1,2})(?:日)?", path.stem)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass
    short_match = re.search(r"(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*日?", path.stem)
    if short_match:
        try:
            mtime = path.stat().st_mtime if path.is_file() else datetime.now().timestamp()
            modified_date = datetime.fromtimestamp(mtime).date()
            return date(modified_date.year, int(short_match.group(1)), int(short_match.group(2)))
        except (ValueError, OSError):
            pass
    if path.is_file():
        try:
            return datetime.fromtimestamp(path.stat().st_mtime).date()
        except OSError:
            pass
    return datetime.now().date()


@dataclass(frozen=True)
class ClassificationDecision:
    course: Course | None
    lesson_date: date
    confidence: int
    status: str
    method: str
    reason: str
    candidates: list[dict[str, object]]

    def metadata(self) -> dict[str, object]:
        return {
            "status": self.status,
            "confidence": self.confidence,
            "method": self.method,
            "reason": self.reason,
            "lesson_date": self.lesson_date.isoformat(),
            "candidates": self.candidates,
        }


def _json_list(value: str) -> list:
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def _filename_time(path: Path) -> tuple[time, str]:
    # Remove the date first so names such as 2026-09-14_09-10 do not
    # accidentally interpret the month and day as a time.
    name = re.sub(
        r"20\d{2}\s*(?:[-_./]|年)?\s*\d{1,2}\s*(?:[-_./]|月)?\s*\d{1,2}(?:日)?",
        " ",
        path.stem,
    )
    colon_time = re.search(r"(?<!\d)([01]?\d|2[0-3])[:：]([0-5]\d)(?!\d)", name)
    chinese_time = re.search(r"(?<!\d)([01]?\d|2[0-3])\s*点\s*([0-5]?\d)?\s*(?:分)?", name)
    compact_time = re.search(r"(?:^|[_\s-])([01]\d|2[0-3])([0-5]\d)(?:$|[_\s-])", name)
    separated_time = re.search(r"(?<!\d)([01]?\d|2[0-3])[-_](?:([0-5]\d))(?!\d)", name)
    match = colon_time or chinese_time or compact_time or separated_time
    if match:
        return time(int(match.group(1)), int(match.group(2) or 0)), "filename_time"
    return datetime.fromtimestamp(path.stat().st_mtime).time().replace(second=0, microsecond=0), "modified_time"


def _course_terms(course: Course) -> list[tuple[str, str, int]]:
    terms = [("课程名", course.name, 90)]
    terms.extend(("别名", str(item), 82) for item in _json_list(course.aliases_json))
    terms.extend(("关键词", str(item), 66) for item in _json_list(course.keywords_json))
    deduped: dict[str, tuple[str, str, int]] = {}
    for kind, raw, score in terms:
        normalized = normalize_name(raw)
        if len(normalized) < 2:
            continue
        previous = deduped.get(normalized)
        if previous is None or previous[2] < score:
            deduped[normalized] = (kind, raw, score)
    return list(deduped.values())


def _schedule_score(course: Course, lesson_date: date, observed_time: time, time_source: str) -> tuple[int, list[str]]:
    best_score = 0
    signals: list[str] = []
    for slot in _json_list(course.schedule_json):
        if not isinstance(slot, dict) or slot.get("weekday") != lesson_date.isoweekday():
            continue
        try:
            start = time.fromisoformat(str(slot.get("start_time")))
            end = time.fromisoformat(str(slot.get("end_time")))
        except ValueError:
            continue
        observed_minutes = observed_time.hour * 60 + observed_time.minute
        start_minutes = start.hour * 60 + start.minute
        end_minutes = end.hour * 60 + end.minute
        source_weight = 1 if time_source == "filename_time" else 0.65
        if start_minutes <= observed_minutes <= end_minutes:
            score = round(68 * source_weight)
            label = f"课表匹配 周{slot['weekday']} {start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
        else:
            distance = min(abs(observed_minutes - start_minutes), abs(observed_minutes - end_minutes))
            if distance > 90:
                continue
            score = round((46 if distance <= 30 else 28) * source_weight)
            label = f"课表邻近 {distance} 分钟"
        if score > best_score:
            best_score = score
            signals = [label]
    return best_score, signals


def classify_material(path: Path, courses: list[Course]) -> ClassificationDecision:
    lesson_date = infer_lesson_date(path)
    observed_time, time_source = _filename_time(path)
    normalized_filename = normalize_name(path.stem)
    candidates: list[tuple[int, Course, list[str]]] = []

    for course in courses:
        score = 0
        signals: list[str] = []
        for kind, raw, weight in _course_terms(course):
            normalized_term = normalize_name(raw)
            if normalized_term and normalized_term in normalized_filename:
                score += weight
                signals.append(f"{kind}“{raw}”")
        schedule_score, schedule_signals = _schedule_score(course, lesson_date, observed_time, time_source)
        score += schedule_score
        signals.extend(schedule_signals)
        if score:
            candidates.append((min(score, 100), course, signals))

    candidates.sort(key=lambda item: (-item[0], item[1].name))
    candidate_payload = [
        {"course_id": course.id, "course_name": course.name, "score": score, "signals": signals}
        for score, course, signals in candidates[:3]
    ]
    if not candidates:
        return ClassificationDecision(
            course=None,
            lesson_date=lesson_date,
            confidence=0,
            status="needs_review",
            method="no_match",
            reason="未命中文件名关键词或课程表时间",
            candidates=candidate_payload,
        )

    top_score, top_course, top_signals = candidates[0]
    runner_up = candidates[1][0] if len(candidates) > 1 else 0
    margin = top_score - runner_up
    reliable = top_score >= 60 and (margin >= 14 or top_score >= 85)
    if reliable:
        return ClassificationDecision(
            course=top_course,
            lesson_date=lesson_date,
            confidence=top_score,
            status="classified",
            method="scored_classification",
            reason="；".join(top_signals),
            candidates=candidate_payload,
        )
    return ClassificationDecision(
        course=None,
        lesson_date=lesson_date,
        confidence=top_score,
        status="needs_review",
        method="ambiguous_classification",
        reason=f"候选课程“{top_course.name}”评分 {top_score}，与下一候选差值 {margin}，需要确认",
        candidates=candidate_payload,
    )


def infer_course(path: Path, courses: list[Course]) -> Course | None:
    decision = classify_material(path, courses)
    return decision.course
