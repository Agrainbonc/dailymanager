from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from app.schemas import (
    AsrSettingsConfig,
    CalendarWorkspaceCreate,
    CalendarWorkspaceUpdate,
    StrategyBoardUpdate,
    SystemSettingsUpdate,
    WorkflowProjectCreate,
    WorkflowProjectUpdate,
)


class NewModulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temp_dir = tempfile.TemporaryDirectory()
        os.environ["DAILY_MANAGER_DATA_DIR"] = str(Path(cls._temp_dir.name) / "app-data")

        from app.config import ensure_data_directories
        from app.database import Base, SessionLocal, engine
        import app.models  # noqa: F401

        ensure_data_directories()
        cls.Base = Base
        cls.SessionLocal = SessionLocal
        cls.engine = engine
        Base.metadata.create_all(bind=engine)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.engine.dispose()
        try:
            cls._temp_dir.cleanup()
        except Exception:
            pass

    def test_settings_service_and_asr_switch(self):
        from app.services.settings_service import (
            load_system_settings,
            save_system_settings,
            test_asr_connection,
        )
        from app.adapters.asr import get_asr_provider

        with self.SessionLocal() as db:
            # 1. 默认设置加载
            settings = load_system_settings(db)
            self.assertIsNotNone(settings.asr)

            # 2. 更新 ASR 为 mock
            update_payload = SystemSettingsUpdate(
                input_directory="D:\\test_inbox",
                asr=AsrSettingsConfig(provider="mock"),
            )
            saved = save_system_settings(update_payload, db)
            self.assertEqual(saved.input_directory, "D:\\test_inbox")
            self.assertEqual(saved.asr.provider, "mock")

            # 3. 验证连通性测试
            success, msg, latency = test_asr_connection(saved.asr)
            self.assertTrue(success)
            self.assertIn("Mock", msg)

            # 4. 验证 get_asr_provider 工厂正确动态实例化 MockAsrProvider
            provider = get_asr_provider()
            self.assertEqual(provider.name, "mock_asr")

    def test_calendar_and_strategy_service(self):
        from app.services.calendar_service import (
            create_calendar_workspace,
            delete_calendar_workspace,
            get_strategy_board,
            list_calendar_workspaces,
            update_calendar_workspace,
            update_strategy_board,
        )

        with self.SessionLocal() as db:
            # 1. 默认自举一套日历
            workspaces = list_calendar_workspaces(db)
            self.assertGreaterEqual(len(workspaces), 1)

            # 2. 新增一套日历
            created = create_calendar_workspace(
                CalendarWorkspaceCreate(
                    name="考试冲刺日历",
                    color="#e76491",
                    is_active=True,
                    data={"tray": [{"id": "t1", "text": "刷题"}], "events": []},
                ),
                db,
            )
            self.assertEqual(created.name, "考试冲刺日历")
            self.assertTrue(created.is_active)

            # 3. 更新日历
            updated = update_calendar_workspace(
                created.id,
                CalendarWorkspaceUpdate(name="2026冲刺计划"),
                db,
            )
            self.assertEqual(updated.name, "2026冲刺计划")

            # 4. 博弈论看板更新与读取
            strat = get_strategy_board(db)
            self.assertIsNotNone(strat)
            new_board = update_strategy_board(
                StrategyBoardUpdate(
                    items=[
                        {"id": "g1", "text": "精读核心论文", "zone": "must"},
                        {"id": "g2", "text": "重构项目代码", "zone": "later"},
                    ]
                ),
                db,
            )
            self.assertEqual(len(new_board.items), 2)
            self.assertEqual(new_board.items[0]["zone"], "must")

            # 5. 删除日历
            ok = delete_calendar_workspace(created.id, db)
            self.assertTrue(ok)

    def test_workflow_service(self):
        from app.services.workflow_service import (
            create_workflow,
            delete_workflow,
            list_workflows,
            update_workflow,
        )

        with self.SessionLocal() as db:
            # 1. 默认种子工作流
            flows = list_workflows(db)
            self.assertGreaterEqual(len(flows), 1)
            research = next(f for f in flows if "研究" in f.name)
            self.assertGreaterEqual(len(research.nodes), 3)

            # 2. 创建新任务流
            created = create_workflow(
                WorkflowProjectCreate(
                    name="开题答辩攻坚",
                    description="从实验到PPT准备",
                    color=2,
                    nodes=[{"id": "n1", "title": "准备PPT", "x": 0, "y": 0, "status": "todo"}],
                    edges=[],
                ),
                db,
            )
            self.assertEqual(created.name, "开题答辩攻坚")

            # 3. 更新任务流
            updated = update_workflow(
                created.id,
                WorkflowProjectUpdate(
                    nodes=[
                        {"id": "n1", "title": "准备PPT", "x": 10, "y": 10, "status": "doing"},
                        {"id": "n2", "title": "预答辩演练", "x": 300, "y": 10, "status": "todo"},
                    ],
                    edges=[{"id": "e1", "from": "n1", "to": "n2", "label": "推进"}],
                ),
                db,
            )
            self.assertEqual(len(updated.nodes), 2)
            self.assertEqual(len(updated.edges), 1)

            # 4. 删除任务流
            ok = delete_workflow(created.id, db)
            self.assertTrue(ok)

    def test_storage_audit_and_clean_orphans_schema(self):
        from app.services.library import audit_storage, clean_orphan_files
        from app.schemas import StorageAuditRead, CleanOrphansResponse

        with self.SessionLocal() as db:
            # 1. 验证 audit_storage 能成功转为 StorageAuditRead
            audit_dict = audit_storage(db)
            audit_read = StorageAuditRead(**audit_dict)
            self.assertGreaterEqual(audit_read.total_materials_count, 0)
            self.assertIsInstance(audit_read.orphan_sample_paths, list)

            # 2. 验证 clean_orphan_files 能成功转为 CleanOrphansResponse
            clean_dict = clean_orphan_files(db)
            clean_res = CleanOrphansResponse(**clean_dict)
            self.assertGreaterEqual(clean_res.cleaned_orphans_count, 0)
            self.assertEqual(clean_res.deleted_files_count, clean_res.cleaned_orphans_count)


if __name__ == "__main__":
    unittest.main()
