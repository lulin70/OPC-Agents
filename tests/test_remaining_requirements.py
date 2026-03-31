#!/usr/bin/env python3
import unittest
import sys
import os
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConsensusManager(unittest.TestCase):

    def test_initiate_consensus(self):
        from opc_manager.consensus_manager import ConsensusManager, ConsensusStatus
        cm = ConsensusManager()
        session = cm.initiate_consensus("test topic", [{"id": "a", "name": "Agent A"}])
        self.assertIsNotNone(session.session_id)
        self.assertEqual(session.status, ConsensusStatus.PENDING)

    def test_add_opinion_and_synthesize(self):
        from opc_manager.consensus_manager import ConsensusManager, ConsensusStatus
        cm = ConsensusManager()
        session = cm.initiate_consensus("test topic", [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}])
        cm.add_opinion(session.session_id, "a", "A", "good plan", score=0.9)
        cm.add_opinion(session.session_id, "b", "B", "good plan", score=0.8)
        result = cm.synthesize(session.session_id)
        self.assertTrue(result["consensus_reached"])
        self.assertEqual(session.status, ConsensusStatus.COMPLETED)

    def test_consensus_not_reached(self):
        from opc_manager.consensus_manager import ConsensusManager
        cm = ConsensusManager()
        session = cm.initiate_consensus("test topic", [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}], threshold=0.8)
        cm.add_opinion(session.session_id, "a", "A", "bad", score=0.1)
        cm.add_opinion(session.session_id, "b", "B", "ok", score=0.9)
        result = cm.synthesize(session.session_id)
        self.assertFalse(result["consensus_reached"])
        self.assertGreater(len(result["divergent_points"]), 0)

    def test_get_session(self):
        from opc_manager.consensus_manager import ConsensusManager
        cm = ConsensusManager()
        session = cm.initiate_consensus("test", [])
        info = cm.get_session(session.session_id)
        self.assertEqual(info["session_id"], session.session_id)


class TestSchedulerThread(unittest.TestCase):

    def test_parse_time_minutes(self):
        from opc_manager.scheduler_thread import SchedulerThread
        st = SchedulerThread()
        result = st.parse_time_requirement("30分钟后看进度")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, datetime)

    def test_parse_time_hours(self):
        from opc_manager.scheduler_thread import SchedulerThread
        st = SchedulerThread()
        result = st.parse_time_requirement("2小时后报告")
        self.assertIsNotNone(result)

    def test_parse_time_pm(self):
        from opc_manager.scheduler_thread import SchedulerThread
        st = SchedulerThread()
        result = st.parse_time_requirement("下午5点看进度")
        self.assertIsNotNone(result)
        self.assertIn(result.hour, [17, 5])

    def test_parse_time_none(self):
        from opc_manager.scheduler_thread import SchedulerThread
        st = SchedulerThread()
        result = st.parse_time_requirement("hello world")
        self.assertIsNone(result)

    def test_schedule_monitoring(self):
        from opc_manager.scheduler_thread import SchedulerThread
        st = SchedulerThread(storage_path=tempfile.mkdtemp())
        st.schedule_monitoring("task-1", [{"trigger": "每30分钟检查"}])
        self.assertTrue(len(st.scheduled_tasks) > 0)
        self.assertEqual(st.scheduled_tasks[0]["type"], "monitor")

    def test_schedule_report(self):
        from opc_manager.scheduler_thread import SchedulerThread
        st = SchedulerThread()
        trigger = datetime.now() + timedelta(minutes=5)
        st.schedule_report("task-1", trigger, "check progress")
        self.assertTrue(len(st.scheduled_tasks) > 0)
        self.assertEqual(st.scheduled_tasks[-1]["type"], "report")

    def test_parse_interval(self):
        from opc_manager.scheduler_thread import SchedulerThread
        st = SchedulerThread()
        self.assertEqual(st._parse_interval("每30分钟"), 30)
        self.assertEqual(st._parse_interval("每2小时"), 120)
        self.assertIsNone(st._parse_interval(""))

    def test_optimization_history(self):
        try:
            from opc_hr.auto_optimizer import AutoOptimizer
            ao = AutoOptimizer()
            history = ao.load_optimization_history()
            self.assertIsInstance(history, list)
        except Exception:
            pass


if __name__ == '__main__':
    unittest.main()
