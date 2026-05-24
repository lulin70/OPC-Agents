"""Tests for P0 product improvements: start.sh, demo mode, success toasts, and bug fixes."""

import os
import sys
import stat
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")


class TestStartScript:
    """P0-1: One-Click Start Script tests."""

    def test_start_sh_exists(self):
        """start.sh must exist at project root."""
        path = os.path.join(PROJECT_ROOT, "start.sh")
        assert os.path.isfile(path), "start.sh not found at project root"

    def test_start_sh_is_executable(self):
        """start.sh must have executable permission."""
        path = os.path.join(PROJECT_ROOT, "start.sh")
        assert os.path.isfile(path), "start.sh not found"
        mode = os.stat(path).st_mode
        assert (
            mode & stat.S_IXUSR
        ), "start.sh is not executable (user execute bit missing)"

    def test_start_sh_contains_version(self):
        """start.sh must contain v0.2.2 version marker."""
        path = os.path.join(PROJECT_ROOT, "start.sh")
        with open(path, "r") as f:
            content = f.read()
        assert "v0.2.2" in content, "start.sh missing v0.2.2 version string"

    def test_start_sh_auto_creates_venv(self):
        """start.sh should auto-create virtual environment."""
        path = os.path.join(PROJECT_ROOT, "start.sh")
        with open(path, "r") as f:
            content = f.read()
        assert "venv" in content, "start.sh missing venv handling"

    def test_start_sh_auto_installs_deps(self):
        """start.sh should auto-install dependencies."""
        path = os.path.join(PROJECT_ROOT, "start.sh")
        with open(path, "r") as f:
            content = f.read()
        assert (
            "requirements.txt" in content
        ), "start.sh missing requirements.txt install step"

    def test_start_sh_auto_opens_browser(self):
        """start.sh should auto-open browser on macOS/Linux."""
        path = os.path.join(PROJECT_ROOT, "start.sh")
        with open(path, "r") as f:
            content = f.read()
        has_macos = "open " in content or 'open "' in content
        has_linux = "xdg-open" in content
        assert has_macos or has_linux, "start.sh missing browser auto-open logic"

    def test_start_sh_checks_python(self):
        """start.sh should check Python availability."""
        path = os.path.join(PROJECT_ROOT, "start.sh")
        with open(path, "r") as f:
            content = f.read()
        assert "python3" in content, "start.sh missing Python version check"

    def test_start_sh_handles_env(self):
        """start.sh should handle .env file creation."""
        path = os.path.join(PROJECT_ROOT, "start.sh")
        with open(path, "r") as f:
            content = f.read()
        assert ".env" in content, "start.sh missing .env handling"


class TestRequirementsTxt:
    """P0-1B: Layered requirements.txt tests."""

    def test_requirements_exists(self):
        """requirements.txt must exist."""
        path = os.path.join(PROJECT_ROOT, "requirements.txt")
        assert os.path.isfile(path), "requirements.txt not found"

    def test_requirements_has_layered_comments(self):
        """requirements.txt must have layer/group comments."""
        path = os.path.join(PROJECT_ROOT, "requirements.txt")
        with open(path, "r") as f:
            content = f.read()
        assert (
            "Core" in content or "REQUIRED" in content
        ), "requirements.txt missing Core/REQUIRED section"
        assert "#" in content, "requirements.txt missing comments (should be layered)"

    def test_requirements_contains_streamlit(self):
        """requirements.txt must include streamlit."""
        path = os.path.join(PROJECT_ROOT, "requirements.txt")
        with open(path, "r") as f:
            content = f.read()
        assert "streamlit" in content, "requirements.txt missing streamlit dependency"

    def test_requirements_contains_openai(self):
        """requirements.txt must include openai."""
        path = os.path.join(PROJECT_ROOT, "requirements.txt")
        with open(path, "r") as f:
            content = f.read()
        assert "openai" in content, "requirements.txt missing openai dependency"

    def test_requirements_contains_cryptography(self):
        """requirements.txt must include cryptography."""
        path = os.path.join(PROJECT_ROOT, "requirements.txt")
        with open(path, "r") as f:
            content = f.read()
        assert (
            "cryptography" in content
        ), "requirements.txt missing cryptography dependency"


class TestDemoMode:
    """P0-2: No-LLM Demo Mode tests."""

    def test_demo_data_function_exists(self):
        """_get_demo_dashboard_data() must be importable from frontend.routers.base_router."""
        from frontend.routers.base_router import _get_demo_dashboard_data

        assert callable(_get_demo_dashboard_data)

    def test_demo_data_returns_expected_structure(self):
        """Demo data must return all required keys."""
        from frontend.routers.base_router import _get_demo_dashboard_data

        data = _get_demo_dashboard_data()
        expected_keys = {
            "income_trend",
            "client_health",
            "task_completion",
            "financial_summary",
            "timeline",
            "skill_usage",
        }
        assert expected_keys.issubset(
            data.keys()
        ), f"Demo data missing keys: {expected_keys - set(data.keys())}"

    def test_demo_data_income_trend_structure(self):
        """income_trend must have labels, values, total, growth."""
        from frontend.routers.base_router import _get_demo_dashboard_data

        data = _get_demo_dashboard_data()
        trend = data["income_trend"]
        assert "labels" in trend and isinstance(trend["labels"], list)
        assert "values" in trend and isinstance(trend["values"], list)
        assert "total" in trend and isinstance(trend["total"], int)
        assert "growth" in trend

    def test_demo_data_client_health_structure(self):
        """client_health must be a list of client dicts with name/score/trend/projects."""
        from frontend.routers.base_router import _get_demo_dashboard_data

        data = _get_demo_dashboard_data()
        clients = data["client_health"]
        assert isinstance(clients, list) and len(clients) > 0
        for c in clients:
            assert "name" in c
            assert "score" in c
            assert "trend" in c
            assert "projects" in c

    def test_demo_data_task_completion_structure(self):
        """task_completion must have total, done, rate."""
        from frontend.routers.base_router import _get_demo_dashboard_data

        data = _get_demo_dashboard_data()
        tc = data["task_completion"]
        assert "total" in tc and "done" in tc and "rate" in tc

    def test_demo_data_financial_summary_structure(self):
        """financial_summary must have income, expenses, profit."""
        from frontend.routers.base_router import _get_demo_dashboard_data

        data = _get_demo_dashboard_data()
        fs = data["financial_summary"]
        assert "income" in fs and "expenses" in fs and "profit" in fs

    def test_demo_data_timeline_structure(self):
        """timeline must be a list of event dicts with time/event/type."""
        from frontend.routers.base_router import _get_demo_dashboard_data

        data = _get_demo_dashboard_data()
        timeline = data["timeline"]
        assert isinstance(timeline, list) and len(timeline) > 0
        for e in timeline:
            assert "time" in e and "event" in e and "type" in e

    def test_demo_data_skill_usage_structure(self):
        """skill_usage must be a list of skill dicts with name/count."""
        from frontend.routers.base_router import _get_demo_dashboard_data

        data = _get_demo_dashboard_data()
        skills = data["skill_usage"]
        assert isinstance(skills, list) and len(skills) > 0
        for s in skills:
            assert "name" in s and "count" in s

    def test_is_demo_mode_callable(self):
        """_is_demo_mode() must be callable."""
        from frontend.routers.base_router import _is_demo_mode

        assert callable(_is_demo_mode)

    def test_is_demo_mode_returns_bool(self):
        """_is_demo_mode() must return a boolean."""
        from frontend.routers.base_router import _is_demo_mode

        result = _is_demo_mode()
        assert isinstance(
            result, bool
        ), f"_is_demo_mode returned {type(result)}, expected bool"

    def test_show_success_toast_callable(self):
        """_show_success_toast() must be callable."""
        from frontend.routers.base_router import _show_success_toast

        assert callable(_show_success_toast)


class TestDashboardDemoMode:
    """P0-2: Dashboard demo mode rendering tests."""

    def test_render_demo_dashboard_importable(self):
        """_render_demo_dashboard must be importable from dashboard_page."""
        from frontend.page_modules._dashboard_page import _render_demo_dashboard

        assert callable(_render_demo_dashboard)

    def test_render_dashboard_accepts_demo_param(self):
        """_render_dashboard_page must accept demo_mode parameter."""
        import inspect
        from frontend.page_modules._dashboard_page import _render_dashboard_page

        sig = inspect.signature(_render_dashboard_page)
        params = list(sig.parameters.keys())
        assert (
            "demo_mode" in params
        ), f"_render_dashboard_page missing demo_mode param, has: {params}"


class TestFinanceSkillBugFix:
    """P0-3: Finance skill silent failure bug fix verification."""

    def test_no_wrong_table_name_finances(self):
        """finance_skill.py must NOT reference table 'finances' (wrong name)."""
        path = os.path.join(PROJECT_ROOT, "opc_manager", "finance_skill.py")
        with open(path, "r") as f:
            content = f.read()
        wrong_refs = [
            line
            for line in content.split("\n")
            if "finances" in line.lower()
            and "finance_records" not in line
            and ("FROM " in line or "INTO " in line or "UPDATE " in line)
        ]
        assert (
            len(wrong_refs) == 0
        ), f"Found wrong table name 'finances' in:\n" + "\n".join(wrong_refs)

    def test_uses_correct_table_finance_records(self):
        """finance_skill.py undo functions must use finance_records table."""
        path = os.path.join(PROJECT_ROOT, "opc_manager", "finance_skill.py")
        with open(path, "r") as f:
            content = f.read()
        assert (
            "DELETE FROM finance_records" in content
        ), "finance_skill.py missing DELETE FROM finance_records (undo fix)"

    def test_undo_functions_check_return_value(self):
        """Undo functions must capture and check execute_write return value."""
        path = os.path.join(PROJECT_ROOT, "opc_manager", "finance_skill.py")
        with open(path, "r") as f:
            content = f.read()
        assert (
            "rows = execute_write" in content
        ), "Undo functions don't capture execute_write return value"
        assert (
            "rows > 0" in content or "rows == 0" in content
        ), "Undo functions don't check rows return value"


class TestDataManagerWriteConfirmation:
    """P0-3: Verify data_manager.execute_write returns row count."""

    def test_execute_write_returns_int(self):
        """execute_write() signature must return int."""
        import inspect
        from opc_manager.data_manager import execute_write

        hints = inspect.signature(execute_write).return_annotation
        assert hints == int, f"execute_write returns {hints}, expected int"

    def test_execute_write_uses_total_changes(self):
        """execute_write implementation must use conn.total_changes."""
        path = os.path.join(PROJECT_ROOT, "opc_manager", "data_manager.py")
        with open(path, "r") as f:
            content = f.read()
        assert (
            "total_changes" in content
        ), "execute_write doesn't use conn.total_changes for return value"
