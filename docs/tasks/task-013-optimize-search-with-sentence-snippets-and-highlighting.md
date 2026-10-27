# 任务登记：优化搜索算法、命中字句精确定位与高亮交互重构

- 任务ID: TASK-013
- 状态: DONE
- 创建时间: 2026-10-13
- 责任Agent: Antigravity

## 任务目标
1. **解决搜索定位不明确与特殊字符崩溃 Bug**：
   - 安全转义搜索词中的正则元字符（如 `()[]*?+` 等），修复特殊字符搜索报错；
   - 支持多关键词空格分词搜索与中英文忽略大小写匹配；
2. **实现成熟项目级的上下文命中字句精准提取（KWIC Context Snippet Extraction）**：
   - 算法解析：将长达数万字的 ASR 转录及课件大纲文本按语义断句，精确定位每一个命中词所在句子与字符偏移；
   - 上下文摘录：智能截取关键词前后上下文窗口（30-40字），生成安全的结构化高亮片段数组；
3. **列表与卡片行内命中字句展示**：
   - 处于搜索状态时，资料行与卡片直接展示【🎯 命中语句摘要】，高亮标出关键词；
   - 显示命中频次（如“命中 3 处”），支持快速展开/收起多处上下文句子；
4. **详情弹窗内全文字句精准导航与自动滚动定位**：
   - 打开详情弹窗后，文本框内所有关键词高亮标记；
   - 浮动展示【匹配定位条】（“第 M / N 处”，提供“上一处 / 下一处”导航按钮）；
   - 点击或切换时自动平滑滚动（`scrollIntoView`）至对应句子并聚焦放大；
5. **后端 API 全文检索支撑**：
   - `/api/materials` 端点增加可选参数 `q: str | None`，支持 SQL 级文本与文件名检索；
   - 补充后端单元测试；
6. **自动化测试与全量自检**：
   - 运行前端 `npm run build` 确保零错误；
   - 运行后端单元测试确保全绿，更新状态为 DONE。

## 锁定修改文件清单
- `backend/app/api.py`
- `backend/tests/test_ingestion_pipeline.py`
- `frontend/src/types.ts`
- `frontend/src/api.ts`
- `frontend/src/App.vue`
- `frontend/src/styles.css`
- `docs/tasks/task-013-optimize-search-with-sentence-snippets-and-highlighting.md`
