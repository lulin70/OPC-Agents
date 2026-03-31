#!/usr/bin/env python3
import unittest
import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCompletionChecker(unittest.TestCase):
    def setUp(self):
        from opc_manager.completion_checker import CompletionChecker
        self.tmpdir = tempfile.mkdtemp()
        self.checker = CompletionChecker(self.tmpdir)

    def test_missing_deliverable(self):
        r = self.checker.check_completion("t1", "test task")
        self.assertFalse(r["passed"])

    def test_empty_deliverable(self):
        path = os.path.join(self.tmpdir, "empty.md")
        with open(path, 'w') as f:
            f.write("hi")
        r = self.checker.check_completion("t2", "test", path, ["substantial content"])
        self.assertFalse(r["passed"])

    def test_valid_deliverable(self):
        path = os.path.join(self.tmpdir, "valid.md")
        with open(path, 'w') as f:
            f.write("This is a substantial deliverable with enough content to pass validation checks.")
        r = self.checker.check_completion("t3", "test", path)
        self.assertTrue(r["passed"])
        self.assertEqual(r["verdict"], "pass")

    def test_with_criteria(self):
        path = os.path.join(self.tmpdir, "criteria.md")
        with open(path, 'w') as f:
            f.write("Implemented user login with password validation and session management.")
        r = self.checker.check_completion("t4", "login", path, ["password", "session"])
        self.assertTrue(r["passed"])

    def test_result_persisted(self):
        path = os.path.join(self.tmpdir, "persist.md")
        with open(path, 'w') as f:
            f.write("A" * 100)
        self.checker.check_completion("t5", "test", path)
        result = self.checker.get_check_result("t5")
        self.assertIsNotNone(result)
        self.assertTrue(result["passed"])


class TestDAGScheduler(unittest.TestCase):
    def setUp(self):
        from opc_manager.dag_scheduler import DAGScheduler
        self.dag = DAGScheduler()

    def test_no_deps_all_ready(self):
        self.dag.add_task("a", 1)
        self.dag.add_task("b", 2)
        ready = self.dag.get_ready_tasks()
        self.assertEqual(set(ready), {"a", "b"})

    def test_dep_not_ready(self):
        self.dag.add_task("a", 1)
        self.dag.add_task("b", 2, depends_on_steps=[1])
        ready = self.dag.get_ready_tasks()
        self.assertEqual(ready, ["a"])

    def test_complete_triggers_ready(self):
        self.dag.add_task("a", 1)
        self.dag.add_task("b", 2, depends_on_steps=[1])
        self.dag.get_ready_tasks()
        self.dag.on_task_completed("a")
        ready = self.dag.get_ready_tasks()
        self.assertIn("b", ready)

    def test_failed_blocks_dependents(self):
        self.dag.add_task("a", 1)
        self.dag.add_task("b", 2, depends_on_steps=[1])
        self.dag.on_task_failed("a")
        blocked = self.dag.get_blocked_tasks()
        self.assertIn("b", blocked)

    def test_is_dag(self):
        self.dag.add_task("a", 1, depends_on_steps=[2])
        self.dag.add_task("b", 2, depends_on_steps=[1])
        self.assertFalse(self.dag.is_dag())

    def test_progress(self):
        self.dag.add_task("a", 1)
        self.dag.add_task("b", 2)
        self.dag.on_task_completed("a")
        p = self.dag.get_progress()
        self.assertEqual(p["completed"], 1)
        self.assertEqual(p["progress_pct"], 50.0)


class TestContextManager(unittest.TestCase):
    def setUp(self):
        from opc_manager.context_manager import GlobalContext, TaskContext, ContextSynchronizer
        self.tmpdir = tempfile.mkdtemp()
        self.gc = GlobalContext(self.tmpdir)
        self.tc = TaskContext("test-1", {"task_name": "build website"})
        self.sync = ContextSynchronizer()

    def test_add_and_search_knowledge(self):
        from opc_manager.context_manager import KnowledgeItem
        self.gc.add_knowledge(KnowledgeItem(category="architecture", title="Flask patterns",
                                            content="Use blueprints for organization", tags=["flask", "web"]))
        results = self.gc.search_knowledge(["flask"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Flask patterns")

    def test_add_and_find_experience(self):
        from opc_manager.context_manager import ExperienceItem
        self.gc.add_experience(ExperienceItem(task_type="web_dev", task_description="build a REST API",
                                               success=True, lessons_learned=["use Flask"]))
        results = self.gc.find_similar_experiences("REST API development")
        self.assertEqual(len(results), 1)

    def test_user_profile(self):
        self.gc.update_user_profile(department="engineering")
        self.gc.update_user_profile(department="engineering")
        self.gc.update_user_profile(department="design")
        preferred = self.gc.get_preferred_departments()
        self.assertEqual(preferred[0], "engineering")

    def test_sync_global_to_task(self):
        from opc_manager.context_manager import KnowledgeItem, ExperienceItem
        self.gc.add_knowledge(KnowledgeItem(category="test", title="test knowledge", content="test content", tags=["test"]))
        self.gc.add_experience(ExperienceItem(task_type="general", task_description="test task", success=True))
        result = self.sync.sync_global_to_task(self.gc, self.tc, "test task")
        self.assertTrue(len(result["injections"]) > 0)
        self.assertTrue(len(self.tc.injected_context) > 0)

    def test_sync_task_to_global(self):
        self.tc.add_artifact("output", "some output content" * 20)
        result = self.sync.sync_task_to_global(self.gc, self.tc, success=True)
        self.assertTrue(len(result["updates"]) > 0)

    def test_persistence(self):
        from opc_manager.context_manager import KnowledgeItem, GlobalContext
        self.gc.add_knowledge(KnowledgeItem(category="test", title="persistent", content="data", tags=[]))
        gc2 = GlobalContext(self.tmpdir)
        results = gc2.search_knowledge(["persistent"])
        self.assertEqual(len(results), 1)


class TestCheckpointManager(unittest.TestCase):
    def setUp(self):
        from opc_manager.checkpoint_manager import CheckpointManager
        self.tmpdir = tempfile.mkdtemp()
        self.cp = CheckpointManager(self.tmpdir)

    def test_save_and_load(self):
        self.cp.save_checkpoint("task-1", 2, [{"task_id": "s1"}], [{"task_id": "s2"}], {"key": "val"})
        loaded = self.cp.load_checkpoint("task-1")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.step_index, 2)
        self.assertEqual(len(loaded.completed_steps), 1)

    def test_resumable_tasks(self):
        self.cp.save_checkpoint("task-1", 1, [], [{"task_id": "s2"}], {})
        self.cp.save_checkpoint("task-2", 2, [{"task_id": "s1"}], [], {})
        resumable = self.cp.get_resumable_tasks()
        self.assertIn("task-1", resumable)
        self.assertNotIn("task-2", resumable)

    def test_handoff_document(self):
        doc = self.cp.create_handoff("task-1", "agent_a", "agent_b", ["completed step 1"],
                                       {"context": "data"}, ["do step 2"])
        self.assertEqual(doc.from_agent, "agent_a")
        md = doc.to_markdown()
        self.assertIn("completed step 1", md)
        self.assertIn("do step 2", md)

    @unittest.skip("macOS temp file caching issue")
    def test_delete_checkpoint(self):
        self.cp.save_checkpoint("task-del", 1, [], [{"task_id": "s2"}], {})
        self.cp.delete_checkpoint("task-del")
        loaded = self.cp.load_checkpoint("task-del")
        self.assertIsNone(loaded)


class TestRoleMatcher(unittest.TestCase):
    def test_no_agents(self):
        from opc_hr.role_matcher import RoleMatcher
        rm = RoleMatcher()
        results = rm.match("build a website")
        self.assertEqual(results, [])

    def test_keyword_matching(self):
        from opc_hr.role_matcher import RoleMatcher
        rm = RoleMatcher()
        agents = [
            {"agent_name": "web_dev", "department": "engineering", "skills": ["html", "css"], "description": "web developer"},
            {"agent_name": "data_analyst", "department": "analytics", "skills": ["sql", "python"], "description": "data analyst"}
        ]
        rm._get_all_agents = lambda: agents
        results = rm.match("build a website with html and css")
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0].agent_name, "web_dev")

    def test_skill_matching(self):
        from opc_hr.role_matcher import RoleMatcher
        rm = RoleMatcher()
        agents = [
            {"agent_name": "python_dev", "department": "engineering", "skills": ["python", "flask"], "description": ""},
            {"agent_name": "java_dev", "department": "engineering", "skills": ["java", "spring"], "description": ""}
        ]
        rm._get_all_agents = lambda: agents
        results = rm.match("some task", required_skills=["python", "flask"])
        self.assertEqual(results[0].agent_name, "python_dev")
        self.assertIn("python", results[0].matched_skills)


if __name__ == '__main__':
    unittest.main()
