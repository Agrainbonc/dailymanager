from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.config import ensure_data_directories
from app.database import initialize_database
from app.services.job_runner import job_runner
from app.services.watch_service import directory_watch_service


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_data_directories()
    initialize_database()
    job_runner.start()
    directory_watch_service.start()
    yield
    directory_watch_service.stop()
    job_runner.stop()


app = FastAPI(title="Daily Manager Local API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["*"],
)


@app.middleware("http")
async def handle_client_disconnect_middleware(request, call_next):
    try:
        return await call_next(request)
    except (ConnectionResetError, BrokenPipeError):
        # 客户端（如浏览器试听音频拖动进度条、关闭弹窗）主动断开网络连接属于正常交互，静默响应
        from starlette.responses import Response
        return Response(status_code=499)


app.include_router(router)
