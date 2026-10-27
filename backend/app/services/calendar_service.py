from __future__ import annotations

import json
import logging
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CalendarWorkspace, Course, StrategyBoard
from app.schemas import (
    CalendarWorkspaceCreate,
    CalendarWorkspaceRead,
    CalendarWorkspaceUpdate,
    StrategyBoardRead,
    StrategyBoardUpdate,
    SyncCoursesToCalendarRequest,
    SyncCoursesToCalendarResponse,
)

logger = logging.getLogger(__name__)


def _ensure_default_calendar(db: Session) -> None:
    """初始化一套默认日历工作区。"""
    count = db.scalar(select(CalendarWorkspace))
    if count is None:
        default_id = f"cal_{uuid.uuid4().hex[:8]}"
        initial_data = {
            "tray": [],
            "events": [],
            "marks": [],
            "global": [],
            "monthly": [],
        }
        workspace = CalendarWorkspace(
            id=default_id,
            name="我的日历",
            color="#627cf7",
            is_active=True,
            data_json=json.dumps(initial_data, ensure_ascii=False),
        )
        db.add(workspace)
        db.commit()


def _ensure_default_strategy(db: Session) -> None:
    """初始化默认博弈论决策看板。"""
    board = db.scalar(select(StrategyBoard).where(StrategyBoard.id == "default"))
    if not board:
        board = StrategyBoard(
            id="default",
            data_json=json.dumps([], ensure_ascii=False),
        )
        db.add(board)
        db.commit()


def list_calendar_workspaces(db: Session) -> list[CalendarWorkspaceRead]:
    _ensure_default_calendar(db)
    rows = db.scalars(select(CalendarWorkspace).order_by(CalendarWorkspace.created_at.asc())).all()
    results = []
    for r in rows:
        try:
            parsed = json.loads(r.data_json) if r.data_json else {}
        except Exception:
            parsed = {}
        results.append(
            CalendarWorkspaceRead(
                id=r.id,
                name=r.name,
                color=r.color,
                is_active=r.is_active,
                data=parsed,
                updated_at=r.updated_at,
            )
        )
    return results


def create_calendar_workspace(payload: CalendarWorkspaceCreate, db: Session) -> CalendarWorkspaceRead:
    cid = payload.id or f"cal_{uuid.uuid4().hex[:8]}"
    clean_data = payload.data or {"tray": [], "events": [], "marks": [], "global": [], "monthly": []}

    # 如果设为激活，先把其他设为未激活
    if payload.is_active:
        for other in db.scalars(select(CalendarWorkspace)).all():
            other.is_active = False

    workspace = CalendarWorkspace(
        id=cid,
        name=payload.name.strip() or "未命名日历",
        color=payload.color or "#627cf7",
        is_active=payload.is_active,
        data_json=json.dumps(clean_data, ensure_ascii=False),
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return CalendarWorkspaceRead(
        id=workspace.id,
        name=workspace.name,
        color=workspace.color,
        is_active=workspace.is_active,
        data=clean_data,
        updated_at=workspace.updated_at,
    )


def update_calendar_workspace(cid: str, payload: CalendarWorkspaceUpdate, db: Session) -> CalendarWorkspaceRead:
    workspace = db.scalar(select(CalendarWorkspace).where(CalendarWorkspace.id == cid))
    if not workspace:
        raise ValueError(f"日历工作区不存在: {cid}")

    if payload.name is not None:
        workspace.name = payload.name.strip()
    if payload.color is not None:
        workspace.color = payload.color.strip()
    if payload.is_active is not None:
        if payload.is_active:
            for other in db.scalars(select(CalendarWorkspace).where(CalendarWorkspace.id != cid)).all():
                other.is_active = False
        workspace.is_active = payload.is_active
    if payload.data is not None:
        workspace.data_json = json.dumps(payload.data, ensure_ascii=False)

    db.commit()
    db.refresh(workspace)

    try:
        parsed = json.loads(workspace.data_json)
    except Exception:
        parsed = {}

    return CalendarWorkspaceRead(
        id=workspace.id,
        name=workspace.name,
        color=workspace.color,
        is_active=workspace.is_active,
        data=parsed,
        updated_at=workspace.updated_at,
    )


def delete_calendar_workspace(cid: str, db: Session) -> bool:
    workspace = db.scalar(select(CalendarWorkspace).where(CalendarWorkspace.id == cid))
    if not workspace:
        return False
    # 至少保留一套日历
    count = db.query(CalendarWorkspace).count()
    if count <= 1:
        raise ValueError("系统至少需要保留一套日历工作区")

    db.delete(workspace)
    db.commit()

    # 若被删的是 active，让第一套成为 active
    remaining = db.scalars(select(CalendarWorkspace).order_by(CalendarWorkspace.created_at.asc())).first()
    if remaining and not any(r.is_active for r in db.scalars(select(CalendarWorkspace)).all()):
        remaining.is_active = True
        db.commit()

    return True


def get_strategy_board(db: Session) -> StrategyBoardRead:
    _ensure_default_strategy(db)
    board = db.scalar(select(StrategyBoard).where(StrategyBoard.id == "default"))
    try:
        items = json.loads(board.data_json) if board and board.data_json else []
    except Exception:
        items = []
    return StrategyBoardRead(id="default", items=items, updated_at=board.updated_at if board else None)


def update_strategy_board(payload: StrategyBoardUpdate, db: Session) -> StrategyBoardRead:
    _ensure_default_strategy(db)
    board = db.scalar(select(StrategyBoard).where(StrategyBoard.id == "default"))
    board.data_json = json.dumps(payload.items, ensure_ascii=False)
    db.commit()
    db.refresh(board)
    return StrategyBoardRead(id="default", items=payload.items, updated_at=board.updated_at)


def sync_courses_to_calendar(
    payload: SyncCoursesToCalendarRequest, db: Session
) -> SyncCoursesToCalendarResponse:
    """将课程表自动同步导入到日历日程（events）、待安排托盘（tray）或博弈论看板（strategy）。"""
    _ensure_default_calendar(db)
    _ensure_default_strategy(db)

    # 1. 确定目标日历工作区
    if payload.workspace_id:
        workspace = db.scalar(select(CalendarWorkspace).where(CalendarWorkspace.id == payload.workspace_id))
    else:
        workspace = db.scalar(select(CalendarWorkspace).where(CalendarWorkspace.is_active.is_(True)))
        if not workspace:
            workspace = db.scalar(select(CalendarWorkspace).order_by(CalendarWorkspace.created_at.asc()))

    if not workspace:
        raise ValueError("未找到可用的日历工作区")

    try:
        cal_data = json.loads(workspace.data_json) if workspace.data_json else {}
    except Exception:
        cal_data = {}

    for key in ("tray", "events", "marks", "global", "monthly"):
        if key not in cal_data or not isinstance(cal_data[key], list):
            cal_data[key] = []

    # 2. 获取待同步课程
    query = select(Course)
    if payload.course_ids:
        query = query.where(Course.id.in_(payload.course_ids))
    courses = db.scalars(query.order_by(Course.name.asc())).all()

    # 3. 日期范围解析
    start_d = date.fromisoformat(payload.start_date)
    end_d = date.fromisoformat(payload.end_date)
    if start_d > end_d:
        raise ValueError("开始日期不能晚于结束日期")

    created_events_count = 0
    created_tray_count = 0
    created_strategy_count = 0
    affected_courses: list[str] = []

    # 4. 同步至日历具体排期日程 (Calendar Events)
    if payload.sync_to_events:
        existing_event_keys = {
            (ev.get("date"), ev.get("title"), ev.get("start"))
            for ev in cal_data["events"]
            if isinstance(ev, dict)
        }

        for course in courses:
            try:
                slots = json.loads(course.schedule_json or "[]")
            except Exception:
                slots = []
            if not slots:
                continue

            if course.name not in affected_courses:
                affected_courses.append(course.name)

            curr = start_d
            while curr <= end_d:
                weekday_num = curr.isoweekday()  # 1=周一, 7=周日
                for slot in slots:
                    if slot.get("weekday") == weekday_num:
                        start_t = slot.get("start_time", "08:00")
                        end_t = slot.get("end_time")
                        key = (curr.isoformat(), course.name, start_t)
                        if key not in existing_event_keys:
                            event_id = f"ev_{uuid.uuid4().hex[:8]}"
                            cal_data["events"].append({
                                "id": event_id,
                                "date": curr.isoformat(),
                                "title": course.name,
                                "start": start_t,
                                "end": end_t,
                                "note": "课程表自动同步",
                            })
                            existing_event_keys.add(key)
                            created_events_count += 1
                curr += timedelta(days=1)

    # 5. 同步至待安排托盘 (Tray)
    if payload.sync_to_tray:
        existing_tray_texts = {t.get("text") for t in cal_data["tray"] if isinstance(t, dict)}
        for course in courses:
            if course.name not in affected_courses:
                affected_courses.append(course.name)
            tray_text = f"【课程】{course.name}"
            if tray_text not in existing_tray_texts:
                cal_data["tray"].append({
                    "id": f"tray_{uuid.uuid4().hex[:8]}",
                    "text": tray_text,
                })
                existing_tray_texts.add(tray_text)
                created_tray_count += 1

    # 保存日历工作区
    workspace.data_json = json.dumps(cal_data, ensure_ascii=False)

    # 6. 同步至博弈论看板 (StrategyBoard)
    if payload.sync_to_strategy:
        board = db.scalar(select(StrategyBoard).where(StrategyBoard.id == "default"))
        try:
            strategy_items = json.loads(board.data_json) if board and board.data_json else []
        except Exception:
            strategy_items = []
        existing_strategy_texts = {s.get("text") for s in strategy_items if isinstance(s, dict)}

        for course in courses:
            if course.name not in affected_courses:
                affected_courses.append(course.name)
            strat_text = f"复习与巩固：{course.name}"
            if strat_text not in existing_strategy_texts:
                strategy_items.append({
                    "id": f"strat_{uuid.uuid4().hex[:8]}",
                    "text": strat_text,
                    "zone": "inbox",
                })
                existing_strategy_texts.add(strat_text)
                created_strategy_count += 1

        if board:
            board.data_json = json.dumps(strategy_items, ensure_ascii=False)

    db.commit()

    return SyncCoursesToCalendarResponse(
        created_events_count=created_events_count,
        created_tray_count=created_tray_count,
        created_strategy_count=created_strategy_count,
        target_workspace_name=workspace.name,
        affected_course_names=affected_courses,
    )

