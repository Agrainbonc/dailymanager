from __future__ import annotations

import json
import logging
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WorkflowProject
from app.schemas import (
    WorkflowProjectCreate,
    WorkflowProjectRead,
    WorkflowProjectUpdate,
)

logger = logging.getLogger(__name__)


def _date_offset_str(days: int) -> str:
    target = date.today() + timedelta(days=days)
    return target.isoformat()


def _ensure_default_seed_flows(db: Session) -> None:
    count = db.scalar(select(WorkflowProject))
    if count is not None:
        return

    # 1. 明确研究问题、文献阅读等节点（种子）
    n0 = {
        "id": "node-1",
        "title": "明确研究问题",
        "description": "梳理研究背景与核心假设，确定这次研究真正想回答的问题。",
        "x": 30,
        "y": 180,
        "color": 1,
        "owner": "self",
        "assignee": "",
        "urgency": "medium",
        "importance": "high",
        "status": "done",
        "start": _date_offset_str(-7),
        "end": _date_offset_str(-5),
    }
    n1 = {
        "id": "node-2",
        "title": "文献阅读与整理",
        "description": "精读关键文献，整理研究方法、已有结论与值得继续探索的空白。",
        "x": 340,
        "y": 20,
        "color": 0,
        "owner": "self",
        "assignee": "",
        "urgency": "medium",
        "importance": "high",
        "status": "doing",
        "start": _date_offset_str(-4),
        "end": _date_offset_str(2),
    }
    n2 = {
        "id": "node-3",
        "title": "实验方案设计",
        "description": "把研究假设转化为可执行方案，明确变量、分组与评价指标。",
        "x": 340,
        "y": 260,
        "color": 3,
        "owner": "self",
        "assignee": "",
        "urgency": "high",
        "importance": "high",
        "status": "doing",
        "start": _date_offset_str(-1),
        "end": _date_offset_str(4),
    }
    n3 = {
        "id": "node-4",
        "title": "整理文献矩阵",
        "description": "按研究对象、方法和主要发现汇总文献，方便后续比较与引用。",
        "x": 650,
        "y": 0,
        "color": 0,
        "owner": "delegate",
        "assignee": "课题组同学",
        "urgency": "medium",
        "importance": "medium",
        "status": "todo",
        "start": _date_offset_str(2),
        "end": _date_offset_str(6),
    }
    n4 = {
        "id": "node-5",
        "title": "提炼研究创新点",
        "description": "从现有证据中找到切入点，写下这项研究的独特价值。",
        "x": 650,
        "y": 200,
        "color": 5,
        "owner": "self",
        "assignee": "",
        "urgency": "medium",
        "importance": "high",
        "status": "todo",
        "start": _date_offset_str(4),
        "end": _date_offset_str(8),
    }
    n5 = {
        "id": "node-6",
        "title": "准备实验材料",
        "description": "核对试剂、设备与样本清单，提前确认需要协作的事项。",
        "x": 650,
        "y": 400,
        "color": 2,
        "owner": "delegate",
        "assignee": "实验室同学",
        "urgency": "medium",
        "importance": "medium",
        "status": "todo",
        "start": "",
        "end": _date_offset_str(6),
    }
    n6 = {
        "id": "node-7",
        "title": "完成开题汇报",
        "description": "汇总研究背景、技术路线和预期结果，形成清晰的汇报故事。",
        "x": 960,
        "y": 200,
        "color": 4,
        "owner": "self",
        "assignee": "",
        "urgency": "medium",
        "importance": "high",
        "status": "todo",
        "start": "",
        "end": _date_offset_str(12),
    }

    edges = [
        {"id": "e-1", "from": "node-1", "to": "node-2", "label": ""},
        {"id": "e-2", "from": "node-1", "to": "node-3", "label": ""},
        {"id": "e-3", "from": "node-2", "to": "node-4", "label": "资料整理"},
        {"id": "e-4", "from": "node-2", "to": "node-5", "label": "形成思路"},
        {"id": "e-5", "from": "node-3", "to": "node-5", "label": ""},
        {"id": "e-6", "from": "node-3", "to": "node-6", "label": "并行准备"},
        {"id": "e-7", "from": "node-4", "to": "node-7", "label": ""},
        {"id": "e-8", "from": "node-5", "to": "node-7", "label": ""},
        {"id": "e-9", "from": "node-6", "to": "node-7", "label": ""},
    ]

    f1 = WorkflowProject(
        id="flow-research",
        name="研究课题推进",
        description="从一个研究问题出发，把文献、实验与汇报，整理成清晰的下一步。",
        color=0,
        is_active=True,
        viewport_json=json.dumps({"x": 40, "y": 40, "z": 0.9}),
        nodes_json=json.dumps([n0, n1, n2, n3, n4, n5, n6], ensure_ascii=False),
        edges_json=json.dumps(edges, ensure_ascii=False),
    )
    f2 = WorkflowProject(
        id="flow-paper",
        name="论文写作计划",
        description="把写作拆成小步，给每一个想法留出成形的时间。",
        color=1,
        is_active=False,
        viewport_json="{}",
        nodes_json="[]",
        edges_json="[]",
    )
    f3 = WorkflowProject(
        id="flow-ideas",
        name="灵感与待探索",
        description="先记下来。此刻还不清晰的想法，也可以慢慢长大。",
        color=2,
        is_active=False,
        viewport_json="{}",
        nodes_json="[]",
        edges_json="[]",
    )
    db.add_all([f1, f2, f3])
    db.commit()


def list_workflows(db: Session) -> list[WorkflowProjectRead]:
    _ensure_default_seed_flows(db)
    rows = db.scalars(select(WorkflowProject).order_by(WorkflowProject.created_at.asc())).all()
    results = []
    for r in rows:
        results.append(_to_read_model(r))
    return results


def _to_read_model(r: WorkflowProject) -> WorkflowProjectRead:
    try:
        vp = json.loads(r.viewport_json) if r.viewport_json else None
    except Exception:
        vp = None
    try:
        nodes = json.loads(r.nodes_json) if r.nodes_json else []
    except Exception:
        nodes = []
    try:
        edges = json.loads(r.edges_json) if r.edges_json else []
    except Exception:
        edges = []

    return WorkflowProjectRead(
        id=r.id,
        name=r.name,
        description=r.description,
        color=r.color,
        is_active=r.is_active,
        viewport=vp,
        nodes=nodes,
        edges=edges,
        updated_at=r.updated_at,
    )


def create_workflow(payload: WorkflowProjectCreate, db: Session) -> WorkflowProjectRead:
    fid = payload.id or f"flow-{uuid.uuid4().hex[:8]}"
    if payload.is_active:
        for other in db.scalars(select(WorkflowProject)).all():
            other.is_active = False

    flow = WorkflowProject(
        id=fid,
        name=payload.name.strip() or "新建任务流",
        description=payload.description.strip(),
        color=payload.color,
        is_active=payload.is_active,
        viewport_json=json.dumps(payload.viewport or {}, ensure_ascii=False),
        nodes_json=json.dumps(payload.nodes or [], ensure_ascii=False),
        edges_json=json.dumps(payload.edges or [], ensure_ascii=False),
    )
    db.add(flow)
    db.commit()
    db.refresh(flow)
    return _to_read_model(flow)


def update_workflow(fid: str, payload: WorkflowProjectUpdate, db: Session) -> WorkflowProjectRead:
    flow = db.scalar(select(WorkflowProject).where(WorkflowProject.id == fid))
    if not flow:
        raise ValueError(f"任务流不存在: {fid}")

    if payload.name is not None:
        flow.name = payload.name.strip()
    if payload.description is not None:
        flow.description = payload.description.strip()
    if payload.color is not None:
        flow.color = payload.color
    if payload.is_active is not None:
        if payload.is_active:
            for other in db.scalars(select(WorkflowProject).where(WorkflowProject.id != fid)).all():
                other.is_active = False
        flow.is_active = payload.is_active
    if payload.viewport is not None:
        flow.viewport_json = json.dumps(payload.viewport, ensure_ascii=False)
    if payload.nodes is not None:
        flow.nodes_json = json.dumps(payload.nodes, ensure_ascii=False)
    if payload.edges is not None:
        flow.edges_json = json.dumps(payload.edges, ensure_ascii=False)

    db.commit()
    db.refresh(flow)
    return _to_read_model(flow)


def delete_workflow(fid: str, db: Session) -> bool:
    flow = db.scalar(select(WorkflowProject).where(WorkflowProject.id == fid))
    if not flow:
        return False
    count = db.query(WorkflowProject).count()
    if count <= 1:
        raise ValueError("系统至少保留一个任务流")

    db.delete(flow)
    db.commit()

    remaining = db.scalars(select(WorkflowProject).order_by(WorkflowProject.created_at.asc())).first()
    if remaining and not any(r.is_active for r in db.scalars(select(WorkflowProject)).all()):
        remaining.is_active = True
        db.commit()

    return True
