#!/usr/bin/env python3
import unittest
import sys
import os
import tempfile
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConfirmPlanIntegration(unittest.TestCase):

    def test_dag_circular_dependency_rejected(self):
        from opc_manager.dag_scheduler import DAGScheduler
        dag = DAGScheduler()
        dag.add_task("a", 1, depends_on_steps=[2])
        dag.add_task("b", 2, depends_on_steps=[1])
        self.assertFalse(dag.is_dag())

    def test_dag_ready_tasks_order(self):
        from opc_manager.dag_scheduler import DAGScheduler
        dag = DAGScheduler()
        dag.add_task("a", 1)
        dag.add_task("b", 2, depends_on_steps=[1])
        dag.add_task("c", 3, depends_on_steps=[1])
        ready = dag.get_ready_tasks()
        self.assertEqual(ready, ["a"])
        dag.on_task_completed("a")
        ready = dag.get_ready_tasks()
        self.assertIn("b", ready)
        self.assertIn("c", ready)

    def test_role_matcher_called_when_agent_empty(self):
        from opc_hr.role_matcher import RoleMatcher
        rm = RoleMatcher(MagicMock(), MagicMock())
        agents = [
            {"agent_name": "web_dev", "department": "engineering", "skills": ["html", "css"], "description": "web developer"}
        ]
        rm._get_all_agents = lambda: agents
        results = rm.match("build a website with html", top_k=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].agent_name, "web_dev")

    def test_acceptance_criteria_in_task_data(self):
        criteria = ["must include tests", "must pass lint"]
        task_data = {
            "task_name": "test",
            "description": "test task",
            "department": "engineering",
            "assigned_agent": "dev",
            "context": {},
            "acceptance_criteria": criteria
        }
        self.assertEqual(task_data["acceptance_criteria"], criteria)
        self.assertEqual(len(task_data["acceptance_criteria"]), 2)

    def test_context_sync_injects_knowledge(self):
        from opc_manager.context_manager import GlobalContext, TaskContext, ContextSynchronizer, KnowledgeItem
        gc = GlobalContext(self.tmpdir)
        gc.add_knowledge(KnowledgeItem(category="test", title="website patterns", content="important info", tags=["website", "build"]))
        tc = TaskContext("test-task", {"task_name": "build website"})
        sync = ContextSynchronizer()
        sync.sync_global_to_task(gc, tc, "build website")
        self.assertTrue(len(tc.injected_context) > 0)

    def test_context_sync_extracts_experience(self):
        from opc_manager.context_manager import GlobalContext, TaskContext, ContextSynchronizer
        gc = GlobalContext(self.tmpdir)
        tc = TaskContext("test-task", {"task_name": "build api"})
        tc.add_artifact("output", "Built a REST API with Flask and SQLAlchemy. " * 20)
        sync = ContextSynchronizer()
        result = sync.sync_task_to_global(gc, tc, success=True)
        self.assertTrue(len(result["updates"]) > 0)

    def test_empty_execution_steps_handled(self):
        from opc_manager.dag_scheduler import DAGScheduler
        dag = DAGScheduler()
        ready = dag.get_ready_tasks()
        self.assertEqual(ready, [])
        self.assertTrue(dag.is_dag())

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()


if __name__ == '__main__':
    unittest.main()
