"""Tests for opc_manager.cli module.

Coverage target: 0% → 50%+
Dimensions: Happy Path (--version/--help/normal startup), Error (app not found/
streamlit missing/keyboard interrupt), Boundary (empty args/extra args),
Configuration (env file present/absent/example only)
"""

import sys
import os
from unittest.mock import patch

import pytest

from opc_manager.cli import main


class TestVersionFlag:
    """Test --version flag handling."""

    def test_version_exits_zero(self):
        """Verify: --version exits with code 0.

        Scenario: User runs `opc-agents --version`
        Expected: SystemExit with code 0
        """
        with patch.object(sys, "argv", ["opc-agents", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 0

    def test_version_output_contains_version_string(self, capsys):
        """Verify: --version output contains 'OPC-Agents v'."""
        with patch.object(sys, "argv", ["opc-agents", "--version"]):
            with pytest.raises(SystemExit):
                main()
        captured = capsys.readouterr()
        assert "OPC-Agents v" in captured.out


class TestHelpFlag:
    """Test --help flag handling."""

    def test_help_exits_zero(self, capsys):
        """Verify: --help exits with code 0 and prints usage."""
        with patch.object(sys, "argv", ["opc-agents", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 0

    def test_help_prints_usage_and_options(self, capsys):
        """Verify: --help prints usage, options, and env vars.

        Scenario: User runs `opc-agents --help`
        Expected: Output contains Usage, --version, --help, and env var names
        """
        with patch.object(sys, "argv", ["opc-agents", "--help"]):
            with pytest.raises(SystemExit):
                main()
        captured = capsys.readouterr()
        assert "Usage: opc-agents" in captured.out
        assert "--version" in captured.out
        assert "--help" in captured.out
        assert "OPC_WORKSPACE" in captured.out
        assert "MOKA_API_KEY" in captured.out
        assert "GLM_API_KEY" in captured.out
        assert "OPENAI_API_KEY" in captured.out
        assert "OLLAMA_BASE_URL" in captured.out

    def test_help_prints_app_url(self, capsys):
        """Verify: --help mentions localhost:8501."""
        with patch.object(sys, "argv", ["opc-agents", "--help"]):
            with pytest.raises(SystemExit):
                main()
        captured = capsys.readouterr()
        assert "localhost:8501" in captured.out


class TestNormalStartup:
    """Test normal application startup (no --version/--help)."""

    @patch("subprocess.run")
    @patch("dotenv.load_dotenv")
    def test_startup_calls_streamlit_with_app_path(self, mock_load, mock_run, tmp_path):
        """Verify: normal startup launches streamlit with frontend/app.py path.

        Scenario: User runs `opc-agents` without flags
        Expected: subprocess.run called with [python, -m, streamlit, run, <app_path>]
        """
        env_file = tmp_path / ".env"
        env_file.write_text("# test")
        with patch.object(sys, "argv", ["opc-agents"]):
            with patch.dict(os.environ, {"OPC_WORKSPACE": str(tmp_path)}):
                main()
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert cmd[0] == sys.executable
        assert "-m" in cmd
        assert "streamlit" in cmd
        assert "run" in cmd
        assert any(str(p).endswith("app.py") for p in cmd)
        assert call_args[1].get("check") is True

    @patch("subprocess.run")
    @patch("dotenv.load_dotenv")
    def test_startup_loads_env_file_when_exists(self, mock_load, mock_run, tmp_path):
        """Verify: .env file is loaded via load_dotenv(env_file) when it exists.

        Scenario: OPC_WORKSPACE dir contains .env file
        Expected: load_dotenv called with full path to .env
        """
        env_file = tmp_path / ".env"
        env_file.write_text("# test")
        with patch.object(sys, "argv", ["opc-agents"]):
            with patch.dict(os.environ, {"OPC_WORKSPACE": str(tmp_path)}):
                main()
        mock_load.assert_called_once_with(str(env_file))

    @patch("subprocess.run")
    @patch("dotenv.load_dotenv")
    def test_startup_calls_load_dotenv_no_args_when_env_absent(
        self, mock_load, mock_run, tmp_path
    ):
        """Verify: load_dotenv() called with no args when .env not found.

        Scenario: OPC_WORKSPACE dir has no .env file
        Expected: load_dotenv() called with no arguments
        """
        with patch.object(sys, "argv", ["opc-agents"]):
            with patch.dict(os.environ, {"OPC_WORKSPACE": str(tmp_path)}):
                main()
        mock_load.assert_called_once_with()

    @patch("subprocess.run")
    @patch("dotenv.load_dotenv")
    def test_startup_prints_hint_when_only_env_example_exists(
        self, mock_load, mock_run, tmp_path, capsys
    ):
        """Verify: prints .env.example hint when .env absent but .env.example exists.

        Scenario: .env absent, .env.example present
        Expected: stdout contains hint about copying .env.example to .env
        """
        example_file = tmp_path / ".env.example"
        example_file.write_text("# example config")
        with patch.object(sys, "argv", ["opc-agents"]):
            with patch.dict(os.environ, {"OPC_WORKSPACE": str(tmp_path)}):
                main()
        captured = capsys.readouterr()
        assert ".env.example" in captured.out
        assert "cp .env.example .env" in captured.out

    @patch("subprocess.run")
    @patch("dotenv.load_dotenv")
    def test_startup_prints_workspace_hint_when_no_env_files(
        self, mock_load, mock_run, tmp_path, capsys
    ):
        """Verify: prints workspace hint when no .env or .env.example found."""
        with patch.object(sys, "argv", ["opc-agents"]):
            with patch.dict(os.environ, {"OPC_WORKSPACE": str(tmp_path)}):
                main()
        captured = capsys.readouterr()
        assert str(tmp_path) in captured.out
        assert "OPC_WORKSPACE" in captured.out

    @patch("subprocess.run")
    @patch("dotenv.load_dotenv")
    def test_startup_passes_extra_args_to_streamlit(
        self, mock_load, mock_run, tmp_path
    ):
        """Verify: extra args (not --version/--help) are passed to streamlit.

        Scenario: User runs `opc-agents --server.port=8502`
        Expected: --server.port=8502 appears in subprocess.run command
        """
        env_file = tmp_path / ".env"
        env_file.write_text("# test")
        with patch.object(sys, "argv", ["opc-agents", "--server.port=8502"]):
            with patch.dict(os.environ, {"OPC_WORKSPACE": str(tmp_path)}):
                main()
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "--server.port=8502" in cmd

    @patch("subprocess.run")
    @patch("dotenv.load_dotenv")
    def test_startup_uses_cwd_when_opc_workspace_unset(
        self, mock_load, mock_run, tmp_path
    ):
        """Verify: defaults to cwd when OPC_WORKSPACE not set.

        Scenario: OPC_WORKSPACE not in environment
        Expected: workspace = os.getcwd()
        """
        env_file = tmp_path / ".env"
        env_file.write_text("# test")
        with patch.object(sys, "argv", ["opc-agents"]):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("OPC_WORKSPACE", None)
                with patch("os.getcwd", return_value=str(tmp_path)):
                    main()
        mock_load.assert_called_once_with(str(env_file))


class TestErrorHandling:
    """Test error handling paths."""

    @patch("subprocess.run")
    @patch("dotenv.load_dotenv")
    def test_app_path_not_found_exits_one(self, mock_load, mock_run, tmp_path):
        """Verify: exits with code 1 when app.py not found.

        Scenario: frontend/app.py doesn't exist on disk
        Expected: SystemExit(1), error message to stderr
        """
        env_file = tmp_path / ".env"
        env_file.write_text("# test")
        with patch.object(sys, "argv", ["opc-agents"]):
            with patch.dict(os.environ, {"OPC_WORKSPACE": str(tmp_path)}):
                with patch("frontend.__file__", "/nonexistent/frontend/__init__.py"):
                    with pytest.raises(SystemExit) as exc_info:
                        main()
        assert exc_info.value.code == 1

    @patch("subprocess.run", side_effect=KeyboardInterrupt)
    @patch("dotenv.load_dotenv")
    def test_keyboard_interrupt_prints_stopped_message(
        self, mock_load, mock_run, tmp_path, capsys
    ):
        """Verify: KeyboardInterrupt prints 'OPC-Agents stopped.' and exits cleanly.

        Scenario: User presses Ctrl+C during streamlit execution
        Expected: 'stopped' in stdout, no SystemExit raised
        """
        env_file = tmp_path / ".env"
        env_file.write_text("# test")
        with patch.object(sys, "argv", ["opc-agents"]):
            with patch.dict(os.environ, {"OPC_WORKSPACE": str(tmp_path)}):
                main()
        captured = capsys.readouterr()
        assert "stopped" in captured.out.lower()

    @patch("subprocess.run", side_effect=FileNotFoundError)
    @patch("dotenv.load_dotenv")
    def test_streamlit_not_found_exits_one(self, mock_load, mock_run, tmp_path, capsys):
        """Verify: FileNotFoundError (streamlit not installed) exits with code 1.

        Scenario: streamlit not installed, subprocess.run raises FileNotFoundError
        Expected: SystemExit(1), error message to stderr
        """
        env_file = tmp_path / ".env"
        env_file.write_text("# test")
        with patch.object(sys, "argv", ["opc-agents"]):
            with patch.dict(os.environ, {"OPC_WORKSPACE": str(tmp_path)}):
                with pytest.raises(SystemExit) as exc_info:
                    main()
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Streamlit not found" in captured.err

    @patch("subprocess.run", side_effect=KeyboardInterrupt)
    @patch("dotenv.load_dotenv")
    def test_keyboard_interrupt_does_not_call_sys_exit(
        self, mock_load, mock_run, tmp_path
    ):
        """Verify: KeyboardInterrupt path does not raise SystemExit.

        Scenario: subprocess.run raises KeyboardInterrupt
        Expected: main() returns normally (no SystemExit)
        """
        env_file = tmp_path / ".env"
        env_file.write_text("# test")
        with patch.object(sys, "argv", ["opc-agents"]):
            with patch.dict(os.environ, {"OPC_WORKSPACE": str(tmp_path)}):
                main()


class TestSecureStorageInit:
    """Test secure_storage initialization path."""

    @patch("subprocess.run")
    @patch("dotenv.load_dotenv")
    def test_secure_storage_init_called_during_startup(
        self, mock_load, mock_run, tmp_path
    ):
        """Verify: init_secure_storage is called during normal startup.

        Scenario: secure_storage module available
        Expected: init_secure_storage() called before subprocess.run
        """
        env_file = tmp_path / ".env"
        env_file.write_text("# test")
        with patch.object(sys, "argv", ["opc-agents"]):
            with patch.dict(os.environ, {"OPC_WORKSPACE": str(tmp_path)}):
                with patch(
                    "opc_manager.secure_storage.init_secure_storage"
                ) as mock_init:
                    main()
        mock_init.assert_called_once()
