from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
IS_FROZEN = bool(getattr(sys, "frozen", False))
RUNTIME_DIR = Path(sys.executable).resolve().parent if IS_FROZEN else PROJECT_DIR
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", PROJECT_DIR))

# 自动加载 .env 配置文件（优先 backend/.env，其次项目根目录 .env）
try:
    from dotenv import load_dotenv

    backend_env = BACKEND_DIR / ".env"
    project_env = PROJECT_DIR / ".env"
    if backend_env.is_file():
        load_dotenv(backend_env)
    elif project_env.is_file():
        load_dotenv(project_env)
    else:
        load_dotenv()
except ImportError:
    pass

# 兼容常见环境变量别名（如与 BME_notebook / Zhixin 配置兼容）
if os.getenv("KEY") and not os.getenv("DASHSCOPE_API_KEY"):
    os.environ["DASHSCOPE_API_KEY"] = os.environ["KEY"]
if os.getenv("AI_BASE_URL") and not os.getenv("OPENAI_BASE_URL"):
    os.environ["OPENAI_BASE_URL"] = os.environ["AI_BASE_URL"]
if os.getenv("AI_MODEL") and not os.getenv("VISION_MODEL"):
    os.environ["VISION_MODEL"] = os.environ["AI_MODEL"]

def get_data_dir() -> Path:
    return Path(os.getenv("DAILY_MANAGER_DATA_DIR", RUNTIME_DIR / "data")).resolve()


def get_frontend_dist_dir() -> Path:
    """Return the Vite build directory in development or a PyInstaller bundle."""
    return (BUNDLE_DIR / "frontend" / "dist").resolve()


def get_library_dir() -> Path:
    return get_data_dir() / "library"


def get_artifacts_dir() -> Path:
    return get_data_dir() / "artifacts"


DATA_DIR = get_data_dir()
LIBRARY_DIR = get_library_dir()
ARTIFACTS_DIR = get_artifacts_dir()
DATABASE_PATH = DATA_DIR / "dailymanager.db"

SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".wma"}
SUPPORTED_PRESENTATION_EXTENSIONS = {".pptx", ".ppt", ".pdf"}
SUPPORTED_EXTENSIONS = SUPPORTED_AUDIO_EXTENSIONS | SUPPORTED_PRESENTATION_EXTENSIONS


def ensure_data_directories() -> None:
    global DATA_DIR, LIBRARY_DIR, ARTIFACTS_DIR, DATABASE_PATH
    DATA_DIR = get_data_dir()
    LIBRARY_DIR = get_library_dir()
    ARTIFACTS_DIR = get_artifacts_dir()
    DATABASE_PATH = DATA_DIR / "dailymanager.db"
    for path in (DATA_DIR, LIBRARY_DIR, ARTIFACTS_DIR):
        path.mkdir(parents=True, exist_ok=True)
