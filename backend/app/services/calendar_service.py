from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CalendarWorkspace, StrategyBoard
from app.schemas import (
    CalendarWorkspaceCreate,
    CalendarWorkspaceRead,
    CalendarWorkspaceUpdate,
    StrategyBoardRead,
    StrategyBoardUpdate,
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
