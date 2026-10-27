from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Material, ProcessingJob
from app.services.processors import (
    process_prepare_job,
    process_transcribe_job,
    process_vision_job,
)

logger = logging.getLogger(__name__)


class LocalJobRunner:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._current_job_id: int | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        # 启动前自动执行一次僵尸任务恢复，将历史由于意外重启残留的 running 任务恢复为重新入队或标错
        recovered_count = self.recover_stale_jobs(requeue=True)
        if recovered_count > 0:
            logger.info("已自动恢复 %d 个历史中断的任务", recovered_count)

        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="daily-manager-jobs", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def recover_stale_jobs(self, requeue: bool = True) -> int:
        """扫描并恢复因服务崩溃、重启或热重载导致的孤儿 running 状态任务。"""
        with SessionLocal() as session:
            stale_jobs = list(
                session.scalars(
                    select(ProcessingJob).where(ProcessingJob.status == "running")
                ).all()
            )
            if not stale_jobs:
                return 0

            count = len(stale_jobs)
            for job in stale_jobs:
                material = session.get(Material, job.material_id)
                # 若任务重试次数小于 3 且允许重新入队，则重置为 queued
                if requeue and job.attempts < 3:
                    job.status = "queued"
                    job.stage = "queued"
                    job.progress = 0
                    job.message = f"服务重启恢复排队 (已尝试 {job.attempts} 次)"
                    if material:
                        material.status = "queued"
                else:
                    job.status = "failed"
                    job.stage = "interrupted"
                    job.progress = 0
                    job.message = f"任务中断或超出最大尝试次数 (已尝试 {job.attempts} 次)"
                    job.completed_at = datetime.now()
                    if material:
                        material.status = "awaiting_recognition"
            session.commit()
            return count

    def retry_job(self, job_id: int) -> bool:
        """重置指定任务，使其重新进入排队状态。"""
        with SessionLocal() as session:
            job = session.get(ProcessingJob, job_id)
            if not job:
                return False
            material = session.get(Material, job.material_id)
            job.status = "queued"
            job.stage = "queued"
            job.progress = 0
            job.message = "用户手动触发重试"
            job.completed_at = None
            job.started_at = None
            if material:
                material.status = "queued"
            session.commit()
            return True

    def _run(self) -> None:
        while not self._stop.is_set():
            if not self._process_next_job():
                self._stop.wait(0.5)

    def _process_next_job(self) -> bool:
        with SessionLocal() as session:
            job = session.scalar(
                select(ProcessingJob)
                .where(ProcessingJob.status == "queued")
                .order_by(ProcessingJob.created_at, ProcessingJob.id)
                .limit(1)
            )
            if not job:
                self._current_job_id = None
                return False

            self._current_job_id = job.id
            job.status = "running"
            job.attempts += 1
            job.started_at = datetime.now()
            session.commit()

            try:
                if job.job_type == "material.prepare":
                    process_prepare_job(session, job)
                elif job.job_type == "audio.transcribe":
                    process_transcribe_job(session, job)
                elif job.job_type == "ppt.analyze":
                    process_vision_job(session, job)
                else:
                    job.status = "failed"
                    job.message = f"不支持的任务类型：{job.job_type}"
                    job.completed_at = datetime.now()
                    session.commit()
            except Exception as exc:
                logger.exception("任务 #%d 执行异常", job.id)
                session.rollback()
                failed = session.get(ProcessingJob, job.id)
                if failed:
                    failed.status = "failed"
                    failed.message = f"处理失败：{str(exc)[:420]}"
                    failed.completed_at = datetime.now()
                    # 联动更新资料状态，解除死锁
                    failed_material = session.get(Material, failed.material_id)
                    if failed_material:
                        failed_material.status = "awaiting_recognition"
                    session.commit()
            finally:
                self._current_job_id = None

            return True


job_runner = LocalJobRunner()
