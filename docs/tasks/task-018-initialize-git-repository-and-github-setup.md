# 任务登记：初始化本地 Git 仓库与关联 GitHub 远程仓库 (Agrainbonc)

- 任务ID: TASK-018
- 状态: IN_PROGRESS
- 创建时间: 2026-10-27
- 完成时间: 未完成
- 责任Agent: Antigravity

## 任务背景与目标
用户要求为当前项目初始化 GitHub 仓库，所有者为 `Agrainbonc`。
1. 优化并完善 `.gitignore`，严防敏感数据（`.env`、`data/` 运行时数据与 SQLite 数据库、`.venv/` 虚拟环境、`node_modules/`、构建产物等）泄露；
2. 初始化本地 Git 仓库 (`git init -b main`)；
3. 将项目初始代码暂存并创建初始提交；
4. 配置关联远程 GitHub 仓库 `https://github.com/Agrainbonc/dailymanager.git`（或 `git@github.com:Agrainbonc/dailymanager.git`），并指导用户完成远端创建与推送。

## 锁定修改文件清单
- `.gitignore`
- `docs/tasks/task-018-initialize-git-repository-and-github-setup.md`
