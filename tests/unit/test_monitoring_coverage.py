"""Tests for opc_manager.monitoring module — coverage improvement (P2-11)."""

import os
import sys
from unittest.mock import patch, MagicMock


class TestInitMonitoring:
    """Test init_monitoring function."""

    def test_init_creates_log_dir(self, tmp_path):
        """init_monitoring should create log directory if not exists."""
        log_dir = str(tmp_path / "logs")
        with patch.dict(os.environ, {"LOG_DIR": log_dir}):
            from opc_manager.monitoring import init_monitoring

            init_monitoring()
            assert os.path.isdir(log_dir)

    def test_init_without_sentry_dsn(self):
        """init_monitoring should work without SENTRY_DSN."""
        with patch.dict(os.environ, {"SENTRY_DSN": ""}, clear=False):
            os.environ.pop("SENTRY_DSN", None)
            from opc_manager.monitoring import init_monitoring

            init_monitoring()

    def test_init_with_sentry_dsn(self):
        """init_monitoring should init Sentry when SENTRY_DSN is set."""
        mock_sentry = MagicMock()
        with patch.dict(sys.modules, {"sentry_sdk": mock_sentry}):
            with patch.dict(os.environ, {"SENTRY_DSN": "test-dsn"}):
                from opc_manager.monitoring import init_monitoring

                init_monitoring()
                mock_sentry.init.assert_called_once()


class TestTrackEvent:
    """Test track_event function."""

    def test_track_event_no_properties(self):
        """track_event should work without properties."""
        from opc_manager.monitoring import track_event

        track_event("test_event")

    def test_track_event_with_properties(self):
        """track_event should work with properties dict."""
        from opc_manager.monitoring import track_event

        track_event("test_event", {"key": "value", "count": 42})

    def test_track_event_with_sentry(self):
        """track_event should send to Sentry when SENTRY_DSN is set."""
        mock_sentry = MagicMock()
        mock_scope = MagicMock()
        mock_sentry.push_scope.return_value.__enter__ = MagicMock(
            return_value=mock_scope
        )
        mock_sentry.push_scope.return_value.__exit__ = MagicMock(return_value=None)

        with patch.dict(sys.modules, {"sentry_sdk": mock_sentry}):
            with patch.dict(os.environ, {"SENTRY_DSN": "test-dsn"}):
                from opc_manager.monitoring import track_event

                track_event("test_event", {"key": "value"})
                mock_scope.set_tag.assert_called_with("key", "value")
                mock_sentry.capture_message.assert_called_with(
                    "test_event", level="info"
                )

    def test_track_event_sentry_no_properties(self):
        """track_event should not call set_tag when no properties."""
        mock_sentry = MagicMock()
        mock_scope = MagicMock()
        mock_sentry.push_scope.return_value.__enter__ = MagicMock(
            return_value=mock_scope
        )
        mock_sentry.push_scope.return_value.__exit__ = MagicMock(return_value=None)

        with patch.dict(sys.modules, {"sentry_sdk": mock_sentry}):
            with patch.dict(os.environ, {"SENTRY_DSN": "test-dsn"}):
                from opc_manager.monitoring import track_event

                track_event("test_event")
                mock_scope.set_tag.assert_not_called()
                mock_sentry.capture_message.assert_called_once()


class TestTrackError:
    """Test track_error function."""

    def test_track_error_no_context(self):
        """track_error should work without context."""
        from opc_manager.monitoring import track_error

        track_error(ValueError("test error"))

    def test_track_error_with_context(self):
        """track_error should work with context dict."""
        from opc_manager.monitoring import track_error

        track_error(RuntimeError("test error"), {"module": "test", "phase": "exec"})

    def test_track_error_with_sentry(self):
        """track_error should send to Sentry when SENTRY_DSN is set."""
        mock_sentry = MagicMock()
        mock_scope = MagicMock()
        mock_sentry.push_scope.return_value.__enter__ = MagicMock(
            return_value=mock_scope
        )
        mock_sentry.push_scope.return_value.__exit__ = MagicMock(return_value=None)

        error = ValueError("test error")
        with patch.dict(sys.modules, {"sentry_sdk": mock_sentry}):
            with patch.dict(os.environ, {"SENTRY_DSN": "test-dsn"}):
                from opc_manager.monitoring import track_error

                track_error(error, {"module": "test"})
                mock_scope.set_context.assert_called_with("module", "test")
                mock_sentry.capture_exception.assert_called_with(error)

    def test_track_error_sentry_no_context(self):
        """track_error should not call set_context when no context."""
        mock_sentry = MagicMock()
        mock_scope = MagicMock()
        mock_sentry.push_scope.return_value.__enter__ = MagicMock(
            return_value=mock_scope
        )
        mock_sentry.push_scope.return_value.__exit__ = MagicMock(return_value=None)

        with patch.dict(sys.modules, {"sentry_sdk": mock_sentry}):
            with patch.dict(os.environ, {"SENTRY_DSN": "test-dsn"}):
                from opc_manager.monitoring import track_error

                track_error(ValueError("test error"))
                mock_scope.set_context.assert_not_called()
                mock_sentry.capture_exception.assert_called_once()
