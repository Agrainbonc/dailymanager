from __future__ import annotations

import threading
import time
from pathlib import Path

from sqlalchemy import select
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from app.config import SUPPORTED_EXTENSIONS
from app.database import SessionLocal
from app.models import Course
from app.services.library import get_input_directory, import_from_inbox, import_material


class _DirectoryWatchHandler(FileSystemEventHandler):
    def __init__(self, service: "DirectoryWatchService", course_id: int | None) -> None:
        self.service = service
        self.course_id = course_id

    def on_created(self, event: FileSystemEvent) -> None:
        self.service.schedule_import(self.course_id, Path(event.src_path), is_directory=event.is_directory)

    def on_moved(self, event: FileSystemEvent) -> None:
        self.service.schedule_import(self.course_id, Path(event.dest_path), is_directory=event.is_directory)


class DirectoryWatchService:
    """Watch configured course folders while the local application is running."""

    def __init__(self) -> None:
        self._observer: Observer | None = None
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.RLock()

    def start(self) -> None:
        with self._lock:
            if self._observer and self._observer.is_alive():
                return
            self._observer = Observer()
            self._schedule_configured_courses()
            self._observer.start()

    def stop(self) -> None:
        with self._lock:
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()
            observer = self._observer
            self._observer = None
        if observer:
            observer.stop()
            observer.join(timeout=2)

    def refresh(self) -> None:
        """Rebuild watched paths after a course or its watch folder changes."""
        was_running = bool(self._observer and self._observer.is_alive())
        if was_running:
            self.stop()
        self.start()

    def _schedule_configured_courses(self) -> None:
        if not self._observer:
            return
        with SessionLocal() as session:
            scheduled_paths: set[str] = set()
            input_directory = get_input_directory(session)
            if input_directory and input_directory.is_dir():
                input_path = str(input_directory.resolve())
                self._observer.schedule(_DirectoryWatchHandler(self, None), input_path, recursive=True)
                scheduled_paths.add(input_path.casefold())
            courses = session.scalars(select(Course).where(Course.watch_path.is_not(None))).all()
            for course in courses:
                path = Path(course.watch_path or "").expanduser()
                if path.is_dir() and str(path.resolve()).casefold() not in scheduled_paths:
                    self._observer.schedule(_DirectoryWatchHandler(self, course.id), str(path), recursive=True)

    def schedule_import(self, course_id: int | None, path: Path, *, is_directory: bool) -> None:
        if is_directory or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return
        resolved = str(path.resolve())
        with self._lock:
            prior = self._timers.pop(resolved, None)
            if prior:
                prior.cancel()
            timer = threading.Timer(1.5, self._import_after_write, args=(course_id, path, resolved))
            timer.daemon = True
            self._timers[resolved] = timer
            timer.start()

    def _import_after_write(self, course_id: int | None, path: Path, key: str) -> None:
        try:
            if not path.is_file():
                return
            initial_size = path.stat().st_size
            time.sleep(1)
            if not path.is_file() or path.stat().st_size != initial_size:
                self.schedule_import(course_id, path, is_directory=False)
                return
            with SessionLocal() as session:
                if course_id is None:
                    import_from_inbox(session, path, inferred_by="directory_watcher")
                else:
                    course = session.get(Course, course_id)
                    if course:
                        import_material(session, path, course, inferred_by="directory_watcher")
                session.commit()
        except OSError:
            # An application may still have the source file open; the next filesystem event retries it.
            return
        finally:
            with self._lock:
                self._timers.pop(key, None)


directory_watch_service = DirectoryWatchService()
