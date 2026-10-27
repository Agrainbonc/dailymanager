# Daily Manager

本地优先的课堂资料库。把录音、PPT 或 PDF 拖到一个统一目录，程序会基于课程名、别名、关键词、文件名日期/时间和课程表自动将它们移动至：

`统一投递目录/<课程名>/<上课日期>/source/`

无法可靠判断课程的文件会移至 `统一投递目录/needs-review/<上课日期>/source/`，在界面中指定课程后即可重新归档。

一个本地优先的学习资料管理平台。首期提供课程管理、投递目录扫描、文件归档和可恢复的处理任务队列；ASR 与 PPT 视觉理解通过可替换适配器接入。

选择课程后可以导出源文件 ZIP，或导出可供其他 AI 使用的文本 ZIP。文本包包括每份资料的 Markdown、分类和处理状态；尚未完成 ASR/视觉识别的资料会明确说明缺少文本。

## 目录

- `backend/`：FastAPI 本地服务、SQLite 数据和文件处理任务。
- `frontend/`：Vue 3 桌面应用界面。
- `docs/`：架构和识别适配器设计。
- `data/`：运行时生成的本地数据库、资料库与任务产物，不提交到仓库。

## 本地开发

1. 创建 Python 虚拟环境并安装 `backend/requirements.txt`。
2. 在 `backend/` 运行 `python -m uvicorn app.main:app --reload --port 8000`。
3. 在 `frontend/` 安装依赖后运行 `npm run dev`。

前端开发服务器会将 `/api` 请求转发到本地 Python 服务。发布版将由 Tauri 启动 Python Sidecar，而不是暴露公网服务。
