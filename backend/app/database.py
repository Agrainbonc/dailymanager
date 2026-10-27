from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

import os
import sys

from app.config import DATABASE_PATH, ensure_data_directories


def _resolve_database_path() -> Path:
    # 单元测试与 pytest 运行时强制使用独立测试数据库，杜绝误清空用户生产数据
    is_testing = (
        os.getenv("TESTING") == "1"
        or "unittest" in sys.modules
        or any("unittest" in arg or "pytest" in arg for arg in sys.argv)
    )
    if is_testing:
        return DATABASE_PATH.parent / "dailymanager_test.db"
    return DATABASE_PATH


ACTIVE_DATABASE_PATH = _resolve_database_path()
ensure_data_directories()
engine = create_engine(
    f"sqlite:///{ACTIVE_DATABASE_PATH.as_posix()}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """事务级 Session 上下文管理器，供后台线程或适配器独立调用。"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()



def initialize_database() -> None:
    """Create fresh tables and apply the small additive migrations used by the local MVP."""
    Base.metadata.create_all(bind=engine)
    required_columns = {
        "courses": {
            "keywords_json": "TEXT NOT NULL DEFAULT '[]'",
            "schedule_json": "TEXT NOT NULL DEFAULT '[]'",
        },
        "materials": {
            "classification_status": "VARCHAR(32) NOT NULL DEFAULT 'needs_review'",
            "classification_confidence": "INTEGER NOT NULL DEFAULT 0",
            "classification_reason": "VARCHAR(500) NOT NULL DEFAULT '等待分类'",
        },
    }
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table_name, columns in required_columns.items():
            present = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, column_definition in columns.items():
                if column_name not in present:
                    connection.exec_driver_sql(
                        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
                    )
