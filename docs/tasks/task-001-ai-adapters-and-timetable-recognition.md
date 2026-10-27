# 任务登记：AI 适配器集成与课表截图识别导入

- 任务ID: TASK-001
- 状态: DONE
- 创建时间: 2026-10-12
- 完成时间: 2026-10-12
- 责任Agent: Antigravity

## 任务目标
1. 参考 `D:\codes\project\Zhixin-AI-Companion\ai` 实现可插拔的 ASR 适配器（含 Qwen3/DashScope/Mock），满足 `AsrProvider` 协议契约；
2. 参考 `D:\codes\project\BME_notebook\backend` 实现基于多模态视觉大模型（OpenAI/Gemini/DashScope 兼容接口及 Mock）的 `VisionProvider` 适配器；
3. 实现课表截图识别与导入服务（多模态识别结构化候选、时间与冲突校验、前端预览编辑与批量确认应用）；
4. 完善音频转写与资料多模态处理任务流转；
5. 前端增加课表截图上传识别对话框与资料详情/提取文本预览；
6. 自检并补充自动化单元测试。

## 锁定修改文件清单
- `backend/app/adapters/contracts.py`
- `backend/app/adapters/asr.py`
- `backend/app/adapters/vision.py`
- `backend/app/adapters/__init__.py`
- `backend/app/config.py`
- `backend/app/schemas.py`
- `backend/app/api.py`
- `backend/app/services/processors.py`
- `backend/app/services/job_runner.py`
- `backend/app/services/timetable_recognition.py`
- `backend/tests/test_ai_adapters.py`
- `frontend/src/api.ts`
- `frontend/src/types.ts`
- `frontend/src/App.vue`
- `frontend/src/styles.css`

## 验收结果
- 后端：全部 12 个单元测试用例执行通过（`python -m unittest discover tests`）。
- 前端：`vue-tsc -b && vite build` 0 报错构建成功。
- 新增功能均已在 API 与前端工作台贯通支持。
