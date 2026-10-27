# 单机应用架构

首版采用 Tauri + Vue 3 前端和 FastAPI Python Sidecar。业务数据保存在 SQLite，原始文件和派生产物保存在用户选择的资料库目录中。

## 设计约束

- 不引入 Redis、Celery、Docker、Qdrant 等常驻基础设施。
- 统一投递目录中的文件先移动至课程归档目录，再创建处理任务；归档源文件永远不被模型处理流程覆盖。
- 任务状态和检查点写入 SQLite，应用重启后可恢复。
- ASR、视觉模型和向量检索只能通过适配器调用，避免平台绑定某一家服务。
- 发布版的 API 仅监听 `127.0.0.1`，由 Tauri 负责进程生命周期和访问令牌。

## 识别管线

1. `material.prepare`：识别类型、读取哈希、归档、提取基础元信息。
2. `audio.transcribe`：产出逐段文本、开始/结束时间、置信度、Markdown 和字幕文件。
3. `ppt.analyze`：提取原生文字、页面媒体、页面图像和视觉解释。
4. `course.index`：按照课程隔离写入全文检索与可选语义索引。

## 课程导出

课程页提供两种本地 ZIP 导出：

- `source`：归档后的 PPT、PDF、录音等源文件与 `manifest.json`；缺失文件会保留在清单中，但不会生成空白替代文件。
- `text`：`texts/` 中按资料拆分的 Markdown、`manifest.json` 和说明文件。没有识别结果的资料会导出处理状态，而不是生成推测内容。

ZIP 在 `artifacts/exports` 临时生成，通过 HTTP 下载完成后由后台任务清理。导出不改动课程资料、数据库或原始投递目录。

参考 BioNoteBooks 的文件阶段检查点和媒体证据定位模式，但不引入其 PPT 生成、图谱和多用户模块。
