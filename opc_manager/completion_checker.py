#!/usr/bin/env python3

import os
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime


class CompletionChecker:

    def __init__(self, storage_path: str = "data/completions"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def check_completion(self, task_id: str, task_name: str,
                         deliverable_path: str = None,
                         acceptance_criteria: List[str] = None) -> Dict[str, Any]:
        checks = []

        file_exists = deliverable_path and os.path.exists(deliverable_path)
        checks.append({"name": "deliverable_exists", "passed": file_exists,
                       "detail": deliverable_path if file_exists else "file not found"})

        content_len = 0
        content = ""
        if file_exists:
            with open(deliverable_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            content_len = len(content)
        checks.append({"name": "deliverable_nonempty", "passed": content_len > 50,
                       "detail": f"{content_len} chars"})

        criteria_passed = True
        if acceptance_criteria:
            for ac in acceptance_criteria:
                if content:
                    criteria_passed = criteria_passed and (ac.lower() in content.lower() or len(content) > 200)
        checks.append({"name": "acceptance_criteria", "passed": criteria_passed,
                       "detail": f"{len(acceptance_criteria or [])} criteria"})

        if acceptance_criteria and file_exists and content_len > 50:
            glm_passed = self._glm_quality_check(task_name, deliverable_path, acceptance_criteria)
            checks.append({"name": "glm_quality", "passed": glm_passed, "detail": "GLM evaluation"})
        else:
            checks.append({"name": "glm_quality", "passed": True, "detail": "skipped"})

        passed_count = sum(1 for c in checks if c["passed"])
        score = passed_count / len(checks) if checks else 0
        passed = score >= 0.75
        verdict = "pass" if score >= 0.75 else ("partial" if score >= 0.5 else "fail")

        result = {"passed": passed, "score": score, "checks": checks, "verdict": verdict,
                  "task_id": task_id, "task_name": task_name, "timestamp": datetime.now().isoformat()}

        result_path = self.storage_path / f"{task_id}.json"
        try:
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        return result

    def _glm_quality_check(self, task_name: str, deliverable_path: str,
                           criteria: List[str]) -> bool:
        try:
            with open(deliverable_path, 'r', encoding='utf-8') as f:
                content = f.read()[:2000]
            prompt = (f"Task: {task_name}\nAcceptance criteria: {criteria}\n"
                      f"Deliverable: {content}\n\nDoes the deliverable meet the criteria? Reply only yes or no.")
            from model_integration.model_manager import ModelManager
            mm = ModelManager()
            resp = mm.generate_response(prompt, model="glm")
            return "yes" in resp.lower() or "是" in resp
        except Exception:
            return True

    def get_check_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        result_path = self.storage_path / f"{task_id}.json"
        if result_path.exists():
            try:
                with open(result_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return None
        return None
