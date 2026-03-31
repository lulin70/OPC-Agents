#!/usr/bin/env python3
import unittest
import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opc_manager.workflow_engine import WorkflowEngine, WorkflowStep, WorkflowStatus, StepStatus
from opc_manager.loop_controller import LoopController


class TestWorkflowEngine(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.engine = WorkflowEngine(self.tmpdir)

    def test_create_workflow(self):
        steps = [WorkflowStep(step_id="s1", name="step1", description="d",
                              role_id="eng", action="test_action")]
        wf = self.engine.create_workflow("test", "desc", steps)
        self.assertEqual(wf.name, "test")
        self.assertEqual(len(wf.steps), 1)
        self.assertIn(wf.workflow_id, self.engine.definitions)

    def test_register_executor(self):
        self.engine.register_executor("test_action", lambda s, i, inst: {"result": "ok"})
        self.assertIn("test_action", self.engine.executors)

    def test_start_and_complete(self):
        self.engine.register_executor("test_action", lambda s, i, inst: {"result": "ok"})
        steps = [
            WorkflowStep(step_id="s1", name="step1", description="d",
                          role_id="eng", action="test_action"),
            WorkflowStep(step_id="s2", name="step2", description="d",
                          role_id="eng", action="test_action", depends_on=["s1"])
        ]
        wf = self.engine.create_workflow("test", "desc", steps)
        instance = self.engine.start_workflow(wf.workflow_id)
        self.assertIsNotNone(instance)
        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)
        self.assertEqual(len(instance.completed_steps), 2)

    def test_pause_resume(self):
        call_count = [0]
        def slow_executor(step, inputs, instance):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("simulate failure")
            return {"result": "ok"}
        self.engine.register_executor("slow_action", slow_executor)
        steps = [
            WorkflowStep(step_id="s1", name="step1", description="d",
                          role_id="eng", action="slow_action", retry_count=0)
        ]
        wf = self.engine.create_workflow("test", "desc", steps)
        instance = self.engine.start_workflow(wf.workflow_id)
        self.assertEqual(instance.status, WorkflowStatus.FAILED)

    def test_condition_skip(self):
        self.engine.register_executor("test_action", lambda s, i, inst: {"result": "ok"})
        steps = [
            WorkflowStep(step_id="s1", name="step1", description="d",
                          role_id="eng", action="test_action",
                          conditions={"skip_me": True}),
            WorkflowStep(step_id="s2", name="step2", description="d",
                          role_id="eng", action="test_action")
        ]
        wf = self.engine.create_workflow("test", "desc", steps)
        instance = self.engine.start_workflow(wf.workflow_id, variables={"skip_me": True})
        self.assertEqual(len(instance.completed_steps), 2)

    def test_variable_template(self):
        def check_executor(step, inputs, instance):
            return {"result": "ok", "msg": inputs.get("msg", "")}
        self.engine.register_executor("test_action", check_executor)
        steps = [
            WorkflowStep(step_id="s1", name="step1", description="${greeting}",
                          role_id="eng", action="test_action",
                          inputs={"msg": "${greeting}"})
        ]
        wf = self.engine.create_workflow("test", "desc", steps)
        instance = self.engine.start_workflow(wf.workflow_id, variables={"greeting": "hello"})
        self.assertEqual(instance.variables.get("result"), "ok")
        self.assertEqual(instance.variables.get("msg"), "hello")

    def test_get_progress(self):
        self.engine.register_executor("test_action", lambda s, i, inst: {"result": "ok"})
        steps = [
            WorkflowStep(step_id="s1", name="step1", description="d",
                          role_id="eng", action="test_action")
        ]
        wf = self.engine.create_workflow("test", "desc", steps)
        instance = self.engine.start_workflow(wf.workflow_id)
        progress = self.engine.get_progress(instance.instance_id)
        self.assertEqual(progress["status"], "completed")
        self.assertEqual(progress["progress_pct"], 100.0)

    def test_handoff_history(self):
        self.engine.register_executor("test_action", lambda s, i, inst: {"result": "ok"})
        steps = [
            WorkflowStep(step_id="s1", name="step1", description="d",
                          role_id="eng", action="test_action")
        ]
        wf = self.engine.create_workflow("test", "desc", steps)
        instance = self.engine.start_workflow(wf.workflow_id)
        instance.handoff_history.append({"from": "a", "to": "b", "handoff_id": "h1"})
        self.assertEqual(len(instance.handoff_history), 1)

    def test_persistence(self):
        self.engine.register_executor("test_action", lambda s, i, inst: {"result": "ok"})
        steps = [
            WorkflowStep(step_id="s1", name="step1", description="d",
                          role_id="eng", action="test_action")
        ]
        wf = self.engine.create_workflow("test", "desc", steps)
        engine2 = WorkflowEngine(self.tmpdir)
        self.assertIn(wf.workflow_id, engine2.definitions)


class TestLoopController(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.ctrl = LoopController(max_iterations=5, storage_path=self.tmpdir)

    def test_start_and_complete(self):
        self.ctrl.start_task("t1", "task1")
        self.ctrl.complete_task("t1", success=True)
        self.assertTrue(self.ctrl.check_all_completed())
        self.assertIn("t1", self.ctrl.loop_progress["tasks_completed"])

    def test_max_iterations(self):
        self.ctrl.iteration_count = 5
        should_exit, reason = self.ctrl.should_exit()
        self.assertTrue(should_exit)
        self.assertEqual(reason, "max_iterations_reached")

    def test_manual_stop(self):
        self.ctrl.stop()
        should_exit, reason = self.ctrl.should_exit()
        self.assertTrue(should_exit)
        self.assertEqual(reason, "manual_stop")

    def test_progress_persistence(self):
        self.ctrl.start_task("t1", "task1")
        self.ctrl.complete_task("t1", success=True)
        ctrl2 = LoopController(max_iterations=5, storage_path=self.tmpdir)
        self.assertIn("t1", ctrl2.loop_progress["tasks_completed"])

    def test_statistics(self):
        self.ctrl.start_task("t1", "task1")
        self.ctrl.start_task("t2", "task2")
        self.ctrl.complete_task("t1", success=True)
        self.ctrl.complete_task("t2", success=False)
        stats = self.ctrl.get_statistics()
        self.assertEqual(stats["tasks_completed"], 1)
        self.assertEqual(stats["tasks_failed"], 1)
        self.assertEqual(stats["tasks_pending"], 0)

    def test_reset(self):
        self.ctrl.iteration_count = 10
        self.ctrl._stopped = True
        self.ctrl.reset()
        self.assertEqual(self.ctrl.iteration_count, 0)
        self.assertFalse(self.ctrl._stopped)


if __name__ == '__main__':
    unittest.main()
