from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock


class AiAdaptersAndTimetableTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temp_dir = tempfile.TemporaryDirectory()
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
        cls._temp_dir.cleanup()

    def setUp(self) -> None:
        from app.models import Course, LessonSession, Material, ProcessingJob

        with self.SessionLocal() as session:
            session.query(ProcessingJob).delete()
            session.query(Material).delete()
            session.query(LessonSession).delete()
            session.query(Course).delete()
            session.commit()

    def test_mock_asr_provider_contract(self) -> None:
        from app.adapters.asr import MockAsrProvider

        provider = MockAsrProvider()
        test_file = Path(self._temp_dir.name) / "高等数学_极限_08点30分.m4a"
        test_file.write_bytes(b"mock audio bytes")

        result = provider.transcribe(test_file)
        self.assertGreater(len(result.segments), 0)
        self.assertIn("极限", result.full_text)
        self.assertEqual(result.segments[0].start_ms, 0)
        self.assertGreater(result.segments[0].end_ms, result.segments[0].start_ms)

    def test_zhixin_ws_asr_provider_mocked_socket(self) -> None:
        import json
        from unittest.mock import MagicMock, patch
        from app.adapters.asr import ZhixinWsAsrProvider

        test_file = Path(self._temp_dir.name) / "test_zhixin.wav"
        # 写入最小合法 16kHz 16-bit 单声道 WAV 头部及数据
        test_file.write_bytes(
            b"RIFF\x28\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x04\x00\x00\x00\x00\x00\x00\x00"
        )

        provider = ZhixinWsAsrProvider(ws_url="ws://127.0.0.1:9001/v1/stream")
        self.assertIn("9001", provider.name)

        mock_ws = MagicMock()
        mock_ws.recv.return_value = json.dumps({
            "type": "ai.response",
            "source": "model:asr",
            "destination": "core",
            "data": {
                "request_id": "req-1",
                "kind": "asr",
                "output": {"text": "9001 端口识别成功：今天讲解数字信号处理"},
            },
        })

        with patch("websockets.sync.client.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_ws
            result = provider.transcribe(test_file)
            self.assertIn("数字信号处理", result.full_text)
            self.assertEqual(len(result.segments), 1)

            # 验证完整 ZHIXIN-MSG-1 交互
            sent_messages = [json.loads(call[0][0]) for call in mock_ws.send.call_args_list]
            self.assertEqual(sent_messages[0]["type"], "audio.start")
            self.assertEqual(sent_messages[0]["destination"], "model:asr")
            self.assertEqual(sent_messages[0]["data"]["pcm"]["sample_rate"], 16000)
            self.assertEqual(sent_messages[-1]["type"], "audio.end")

    def test_mock_vision_provider_contract(self) -> None:
        from app.adapters.vision import MockVisionProvider

        provider = MockVisionProvider()
        test_file = Path(self._temp_dir.name) / "slide.png"
        test_file.write_bytes(b"fake image bytes")

        analysis = provider.analyze_slide(test_file, page_number=1, native_text="函数连续性与介值定理")
        self.assertIn("函数连续性", analysis.summary)
        self.assertGreaterEqual(analysis.confidence, 0.9)

    def test_timetable_recognition_and_conflict_check(self) -> None:
        from app.services.timetable_recognition import (
            TimetableCandidateItem,
            _check_conflicts,
            recognize_timetable_image,
        )

        # 1. 冲突检查算法验证
        candidates = [
            TimetableCandidateItem(
                course_name="课程A",
                weekday=1,
                start_time="08:00",
                end_time="10:00",
            ),
            TimetableCandidateItem(
                course_name="课程B",
                weekday=1,
                start_time="09:00",
                end_time="11:00",
            ),
        ]
        _check_conflicts(candidates)
        self.assertTrue(any("时段冲突" in w for w in candidates[0].warnings))
        self.assertTrue(any("时段冲突" in w for w in candidates[1].warnings))

        # 2. 图像识别调用验证
        result = recognize_timetable_image(b"fake_image_bytes", "timetable.png")
        self.assertGreater(len(result.candidates), 0)
        self.assertEqual(result.filename, "timetable.png")

    def test_apply_timetable_creates_and_updates_courses(self) -> None:
        from app.models import Course
        from app.services.timetable_recognition import (
            TimetableCandidateItem,
            apply_timetable_candidates,
        )

        with self.SessionLocal() as session:
            # 预先存在一个课程
            existing = Course(name="人工智能导论（理工）", schedule_json="[]")
            session.add(existing)
            session.commit()

            items = [
                TimetableCandidateItem(
                    course_name="人工智能导论（理工）",
                    weekday=1,
                    start_time="08:00",
                    end_time="09:40",
                    location="西4-402",
                ),
                TimetableCandidateItem(
                    course_name="全新课程X",
                    weekday=3,
                    start_time="14:00",
                    end_time="16:00",
                ),
            ]
            apply_result = apply_timetable_candidates(session, items)
            session.commit()

            self.assertEqual(apply_result.created_courses_count, 1)
            self.assertEqual(apply_result.updated_courses_count, 1)

            updated_course = session.query(Course).filter_by(name="人工智能导论（理工）").one()
            self.assertIn("08:00", updated_course.schedule_json)

            new_course = session.query(Course).filter_by(name="全新课程X").one()
            self.assertIn("14:00", new_course.schedule_json)

    def test_audio_transcription_job_execution(self) -> None:
        from app.models import Course, Material, ProcessingJob
        from app.services.processors import process_transcribe_job

        audio_file = Path(self._temp_dir.name) / "test_lecture.m4a"
        audio_file.write_bytes(b"audio content")

        with self.SessionLocal() as session:
            course = Course(name="医学图像处理")
            session.add(course)
            session.flush()

            material = Material(
                course_id=course.id,
                material_type="audio",
                status="queued",
                classification_status="classified",
                classification_confidence=90,
                classification_reason="课程名匹配",
                original_filename="医学图像处理_第一讲.m4a",
                source_path=str(audio_file),
                stored_path=str(audio_file),
                sha256="c" * 64,
                file_size=audio_file.stat().st_size,
                inferred_by="test",
            )
            session.add(material)
            session.flush()

            job = ProcessingJob(
                material_id=material.id,
                job_type="audio.transcribe",
                message="等待语音转写",
            )
            session.add(job)
            session.commit()

            from unittest.mock import patch
            from app.adapters.asr import MockAsrProvider

            with patch("app.services.processors.get_asr_provider", return_value=MockAsrProvider()):
                process_transcribe_job(session, job)

            refreshed_material = session.get(Material, material.id)
            refreshed_job = session.get(ProcessingJob, job.id)

            self.assertEqual(refreshed_material.status, "ready")
            self.assertIn("# 语音转录文本", refreshed_material.extracted_text or "")
            self.assertEqual(refreshed_job.status, "completed")
            self.assertEqual(refreshed_job.progress, 100)

    def test_api_functions_adapters_status_and_timetable(self) -> None:
        from app.api import apply_timetable, get_adapters_status, recognize_timetable, trigger_material_transcribe
        from app.models import Course, Material
        from app.services.timetable_recognition import TimetableApplyPayload

        # 1. 适配器状态函数
        status = get_adapters_status()
        self.assertTrue(status.asr_ready)
        self.assertTrue(status.vision_ready)

        # 2. 课表截图识别函数：应能提取全量多时段课表（如 12 节排课）
        mock_file = MagicMock()
        mock_file.filename = "timetable.png"
        mock_file.read = MagicMock(return_value=asyncio.run(asyncio.sleep(0, result=b"fake image bytes")))
        rec_data = asyncio.run(recognize_timetable(file=mock_file))
        self.assertEqual(len(rec_data.candidates), 12)
        # 验证同一课程包含多个排课时段（如工程力学基础有周二和周五各一节）
        mechanics_slots = [c for c in rec_data.candidates if c.course_name == "工程力学基础"]
        self.assertEqual(len(mechanics_slots), 2)

        # 3. 课表应用函数：将全量识别结果应用，验证同一课程多个 slot 被合并归档
        with self.SessionLocal() as session:
            payload = TimetableApplyPayload(items=rec_data.candidates)
            apply_res = apply_timetable(payload=payload, session=session)
            self.assertEqual(apply_res.total_slots_count, 12)
            self.assertEqual(apply_res.created_courses_count, 9)
            # 验证工程力学基础课程下存储了 2 个 schedule_json 时段
            mechanics_course = session.query(Course).filter(Course.name == "工程力学基础").first()
            self.assertIsNotNone(mechanics_course)
            self.assertEqual(len(json.loads(mechanics_course.schedule_json)), 2)

        # 4. 手动触发语音转录接口函数
        with self.SessionLocal() as session:
            course = Course(name="生物力学")
            session.add(course)
            session.flush()
            audio_m = Material(
                course_id=course.id,
                material_type="audio",
                status="awaiting_recognition",
                classification_status="classified",
                classification_confidence=95,
                classification_reason="课程名",
                original_filename="生物力学.m4a",
                source_path="dummy",
                stored_path="dummy",
                sha256="d" * 64,
                file_size=100,
                inferred_by="test",
            )
            session.add(audio_m)
            session.commit()

            job_read_result = trigger_material_transcribe(audio_m.id, session=session)
            self.assertEqual(job_read_result.job_type, "audio.transcribe")
            self.assertEqual(audio_m.status, "queued")

    def test_zhixin_asr_provider_configuration_and_chunking(self) -> None:
        from unittest.mock import MagicMock, patch
        from app.adapters.asr import ZhixinWsAsrProvider

        # 1. 验证默认 token 与分片参数配置
        provider = ZhixinWsAsrProvider()
        self.assertEqual(provider.core_token, "change-me")
        self.assertEqual(provider.slice_duration_sec, 20)
        self.assertEqual(provider.chunk_size_bytes, 16000)

        # 2. 模拟长音频分片（例如生成 40 秒数据 = 2 个切片），验证切片循环调用与拼接
        mock_pcm = b"\x00\x00" * 16000 * 40  # 40 秒 16kHz 16-bit PCM (1,280,000 字节)
        test_audio = Path(self._temp_dir.name) / "test_long.wav"
        test_audio.write_bytes(mock_pcm)

        mock_ws = MagicMock()
        mock_ws.recv.side_effect = [
            json.dumps({"type": "ai.response", "data": {"output": {"text": "第一切片文本"}}}),
            json.dumps({"type": "ai.response", "data": {"output": {"text": "第二切片文本"}}}),
        ]

        with patch("app.adapters.asr._convert_audio_to_pcm16le", return_value=mock_pcm):
            with patch("websockets.sync.client.connect", return_value=MagicMock(__enter__=MagicMock(return_value=mock_ws))):
                res = provider.transcribe(test_audio)
                self.assertEqual(len(res.segments), 2)
                self.assertIn("第一切片文本", res.full_text)
                self.assertIn("第二切片文本", res.full_text)
                self.assertEqual(res.segments[0].start_ms, 0)
                self.assertEqual(res.segments[0].end_ms, 20000)
                self.assertEqual(res.segments[1].start_ms, 20000)
                self.assertEqual(res.segments[1].end_ms, 40000)


if __name__ == "__main__":
    unittest.main()
