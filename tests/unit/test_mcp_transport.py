"""Tests for opc_manager.mcp_transport module.

Coverage target: 23% → 50%+
Dimensions: Happy Path (create_server/stdio run/health endpoint), Error
(JSONDecodeError/Exception/auth failure), Boundary (empty line/EOF/whitespace),
Security (auth check/HTTPS enforcement/non-localhost refusal), Configuration
(SSE_AVAILABLE true/false)
"""

import sys
import os
import logging
from unittest.mock import patch, MagicMock

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from opc_manager.mcp_transport import (
    create_mcp_server,
    StdioTransport,
    main as transport_main,
    start_sse_server,
    SSE_AVAILABLE,
)

if SSE_AVAILABLE:
    from opc_manager.mcp_transport import create_sse_app


class TestCreateMcpServer:
    """Test create_mcp_server factory function."""

    def test_returns_mcp_server_instance(self):
        """Verify: create_mcp_server returns MCPServer instance.

        Scenario: Factory called with no arguments
        Expected: Returns MCPServer object with task_engine and skill_registry
        """
        from opc_manager.mcp_protocol import MCPServer

        server = create_mcp_server()
        assert isinstance(server, MCPServer)

    def test_server_has_task_engine(self):
        """Verify: created server has a non-null task_engine."""
        server = create_mcp_server()
        assert server.task_engine is not None

    def test_server_has_skill_registry(self):
        """Verify: created server has a non-null skill_registry."""
        server = create_mcp_server()
        assert server.skill_registry is not None


@pytest.mark.skipif(not SSE_AVAILABLE, reason="SSE not available")
class TestSseAppHealth:
    """Test SSE FastAPI application — health endpoint."""

    @patch.dict(os.environ, {"MCP_API_KEY": "test-key-123"})
    def test_health_returns_ok(self):
        """Verify: /health returns status ok with transport=sse.

        Scenario: GET /health
        Expected: 200, {"status": "ok", "transport": "sse", "version": ...}
        """
        app = create_sse_app()
        with TestClient(app) as client:
            resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["transport"] == "sse"
        assert "version" in data

    @patch.dict(os.environ, {"MCP_API_KEY": ""})
    def test_health_works_without_api_key(self):
        """Verify: /health does not require authentication.

        Scenario: MCP_API_KEY empty, GET /health
        Expected: 200 (health is public)
        """
        app = create_sse_app()
        with TestClient(app) as client:
            resp = client.get("/health")
        assert resp.status_code == 200


@pytest.mark.skipif(not SSE_AVAILABLE, reason="SSE not available")
class TestSseAppAuth:
    """Test SSE FastAPI application — authentication."""

    @patch.dict(os.environ, {"MCP_API_KEY": ""})
    def test_sse_rejected_when_api_key_not_configured(self):
        """Verify: /sse returns 401 when MCP_API_KEY not set.

        Scenario: MCP_API_KEY empty
        Expected: 401 with error message about configuration
        """
        app = create_sse_app()
        with TestClient(app) as client:
            resp = client.get("/sse")
        assert resp.status_code == 401
        assert "not configured" in resp.json()["error"].lower()

    @patch.dict(os.environ, {"MCP_API_KEY": "secret-key"})
    def test_sse_rejected_with_wrong_bearer_token(self):
        """Verify: /sse returns 401 with wrong bearer token.

        Scenario: MCP_API_KEY=secret-key, Authorization: Bearer wrong-key
        Expected: 401 Unauthorized
        """
        app = create_sse_app()
        with TestClient(app) as client:
            resp = client.get("/sse", headers={"Authorization": "Bearer wrong-key"})
        assert resp.status_code == 401
        assert "Unauthorized" in resp.json()["error"]

    @patch.dict(os.environ, {"MCP_API_KEY": "secret-key"})
    def test_messages_rejected_without_auth_header(self):
        """Verify: /messages returns 401 without Authorization header.

        Scenario: MCP_API_KEY set, no auth header
        Expected: 401
        """
        app = create_sse_app()
        with TestClient(app) as client:
            resp = client.post("/messages", json={"jsonrpc": "2.0", "id": 1})
        assert resp.status_code == 401

    @patch.dict(os.environ, {"MCP_API_KEY": "secret-key"})
    def test_messages_accepted_with_correct_bearer_token(self):
        """Verify: /messages accepts request with correct bearer token.

        Scenario: MCP_API_KEY=secret-key, correct Authorization header
        Expected: Not 401 (request reaches mcp_server.handle_request)
        """
        app = create_sse_app()
        with TestClient(app) as client:
            resp = client.post(
                "/messages",
                json={"jsonrpc": "2.0", "method": "ping", "id": 1},
                headers={"Authorization": "Bearer secret-key"},
            )
        assert resp.status_code != 401

    @patch.dict(os.environ, {"MCP_API_KEY": "secret-key"})
    def test_messages_with_unknown_method_returns_error_response(self):
        """Verify: /messages passes unknown method to server, gets error response.

        Scenario: Correct auth, unknown JSON-RPC method
        Expected: 200 with error code -32601 (method not found)
        """
        app = create_sse_app()
        with TestClient(app) as client:
            resp = client.post(
                "/messages",
                json={"jsonrpc": "2.0", "method": "nonexistent", "id": 99},
                headers={"Authorization": "Bearer secret-key"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("id") == 99
        assert "error" in data


@pytest.mark.skipif(not SSE_AVAILABLE, reason="SSE not available")
class TestSseAppHttps:
    """Test SSE FastAPI application — HTTPS enforcement."""

    @patch.dict(os.environ, {"MCP_ENFORCE_HTTPS": "true", "MCP_API_KEY": "key"})
    def test_https_middleware_rejects_http_request(self):
        """Verify: HTTPS enforcement returns 426 for non-HTTPS requests.

        Scenario: MCP_ENFORCE_HTTPS=true, HTTP request
        Expected: 426 status (Upgrade Required)
        """
        app = create_sse_app()
        with TestClient(app) as client:
            resp = client.get(
                "/health",
                headers={"x-forwarded-proto": "http"},
            )
        assert resp.status_code == 426

    @patch.dict(os.environ, {"MCP_ENFORCE_HTTPS": "true", "MCP_API_KEY": "key"})
    def test_https_middleware_accepts_https_request(self):
        """Verify: HTTPS enforcement allows HTTPS requests through.

        Scenario: MCP_ENFORCE_HTTPS=true, x-forwarded-proto=https
        Expected: Not 426 (request passes through)
        """
        app = create_sse_app()
        with TestClient(app) as client:
            resp = client.get(
                "/health",
                headers={"x-forwarded-proto": "https"},
            )
        assert resp.status_code != 426

    @patch.dict(os.environ, {"MCP_ENFORCE_HTTPS": "false", "MCP_API_KEY": "key"})
    def test_https_middleware_disabled_by_default(self):
        """Verify: HTTPS enforcement off by default, all requests pass.

        Scenario: MCP_ENFORCE_HTTPS=false (default)
        Expected: Request passes through regardless of protocol
        """
        app = create_sse_app()
        with TestClient(app) as client:
            resp = client.get("/health")
        assert resp.status_code == 200


class TestStdioTransportInit:
    """Test StdioTransport initialization."""

    def test_init_creates_default_server(self):
        """Verify: StdioTransport creates MCPServer when none provided.

        Scenario: No mcp_server argument
        Expected: self.mcp_server is a MCPServer instance, _shutdown=False
        """
        from opc_manager.mcp_protocol import MCPServer

        transport = StdioTransport()
        assert isinstance(transport.mcp_server, MCPServer)
        assert transport._shutdown is False

    def test_init_accepts_custom_server(self):
        """Verify: StdioTransport accepts custom mcp_server.

        Scenario: Pass mock mcp_server to constructor
        Expected: self.mcp_server is the passed mock
        """
        mock_server = MagicMock()
        transport = StdioTransport(mcp_server=mock_server)
        assert transport.mcp_server is mock_server

    def test_shutdown_sets_flag(self):
        """Verify: shutdown() sets _shutdown to True.

        Scenario: Call shutdown() on a transport
        Expected: _shutdown becomes True, breaking the run() loop
        """
        transport = StdioTransport(mcp_server=MagicMock())
        assert transport._shutdown is False
        transport.shutdown()
        assert transport._shutdown is True


class TestStdioTransportRun:
    """Test StdioTransport.run() loop."""

    def test_run_processes_valid_request_and_writes_response(self):
        """Verify: run() reads JSON from stdin, calls handle_request, writes response.

        Scenario: stdin has one valid JSON-RPC line then EOF
        Expected: handle_request called once, response written to stdout
        """
        mock_server = MagicMock()
        mock_server.handle_request.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": "ok",
        }
        transport = StdioTransport(mcp_server=mock_server)

        mock_stdin = MagicMock()
        mock_stdin.readline = MagicMock(
            side_effect=['{"jsonrpc": "2.0", "method": "ping", "id": 1}\n', ""]
        )
        mock_stdout = MagicMock()
        with patch("sys.stdin", mock_stdin), patch("sys.stdout", mock_stdout):
            transport.run()

        mock_server.handle_request.assert_called_once_with(
            {"jsonrpc": "2.0", "method": "ping", "id": 1}
        )
        written = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
        assert '"result": "ok"' in written
        assert "\n" in written

    def test_run_handles_json_decode_error(self):
        """Verify: run() handles malformed JSON, writes parse error response.

        Scenario: stdin has invalid JSON line then EOF
        Expected: JSON-RPC parse error (-32700) written to stdout
        """
        mock_server = MagicMock()
        transport = StdioTransport(mcp_server=mock_server)

        mock_stdin = MagicMock()
        mock_stdin.readline = MagicMock(side_effect=["not valid json\n", ""])
        mock_stdout = MagicMock()
        with patch("sys.stdin", mock_stdin), patch("sys.stdout", mock_stdout):
            transport.run()

        mock_server.handle_request.assert_not_called()
        written = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
        assert "-32700" in written
        assert "Parse error" in written

    def test_run_skips_empty_and_whitespace_lines(self):
        """Verify: run() skips empty lines and whitespace-only lines.

        Scenario: stdin has empty line, whitespace, valid JSON, then EOF
        Expected: handle_request called only once (for the valid JSON line)
        """
        mock_server = MagicMock()
        mock_server.handle_request.return_value = {"result": "ok"}
        transport = StdioTransport(mcp_server=mock_server)

        mock_stdin = MagicMock()
        mock_stdin.readline = MagicMock(side_effect=["\n", "   \n", '{"id": 1}\n', ""])
        mock_stdout = MagicMock()
        with patch("sys.stdin", mock_stdin), patch("sys.stdout", mock_stdout):
            transport.run()

        mock_server.handle_request.assert_called_once()

    def test_run_breaks_on_eof(self):
        """Verify: run() exits loop on EOF (empty readline).

        Scenario: stdin immediately returns empty string
        Expected: Loop exits, handle_request never called
        """
        mock_server = MagicMock()
        transport = StdioTransport(mcp_server=mock_server)

        mock_stdin = MagicMock()
        mock_stdin.readline = MagicMock(side_effect=[""])
        mock_stdout = MagicMock()
        with patch("sys.stdin", mock_stdin), patch("sys.stdout", mock_stdout):
            transport.run()

        mock_server.handle_request.assert_not_called()

    def test_run_handles_exception_from_handle_request(self):
        """Verify: run() catches generic Exception, breaks loop.

        Scenario: handle_request raises RuntimeError
        Expected: Exception caught, loop breaks (no crash)
        """
        mock_server = MagicMock()
        mock_server.handle_request.side_effect = RuntimeError("server crash")
        transport = StdioTransport(mcp_server=mock_server)

        mock_stdin = MagicMock()
        mock_stdin.readline = MagicMock(side_effect=['{"id": 1}\n'])
        mock_stdout = MagicMock()
        with patch("sys.stdin", mock_stdin), patch("sys.stdout", mock_stdout):
            transport.run()

        mock_server.handle_request.assert_called_once()

    def test_run_warns_when_api_key_empty(self, caplog):
        """Verify: run() logs warning when MCP_API_KEY is empty.

        Scenario: MCP_API_KEY not set in environment
        Expected: Warning logged about open stdio endpoint
        """
        mock_server = MagicMock()
        transport = StdioTransport(mcp_server=mock_server)

        mock_stdin = MagicMock()
        mock_stdin.readline = MagicMock(side_effect=[""])
        mock_stdout = MagicMock()
        with patch.dict(os.environ, {"MCP_API_KEY": ""}):
            with patch("sys.stdin", mock_stdin), patch("sys.stdout", mock_stdout):
                with caplog.at_level(logging.WARNING):
                    transport.run()
        assert "MCP_API_KEY is empty" in caplog.text

    def test_run_does_not_warn_when_api_key_set(self, caplog):
        """Verify: run() does not warn when MCP_API_KEY is set.

        Scenario: MCP_API_KEY set in environment
        Expected: No warning about empty key
        """
        mock_server = MagicMock()
        transport = StdioTransport(mcp_server=mock_server)

        mock_stdin = MagicMock()
        mock_stdin.readline = MagicMock(side_effect=[""])
        mock_stdout = MagicMock()
        with patch.dict(os.environ, {"MCP_API_KEY": "secret"}):
            with patch("sys.stdin", mock_stdin), patch("sys.stdout", mock_stdout):
                with caplog.at_level(logging.WARNING):
                    transport.run()
        assert "MCP_API_KEY is empty" not in caplog.text


class TestStartSseServer:
    """Test start_sse_server security checks."""

    def test_refuses_non_localhost_without_api_key(self):
        """Verify: refuses to start on non-localhost without MCP_API_KEY.

        Scenario: host=0.0.0.0, MCP_API_KEY not set
        Expected: RuntimeError with SECURITY message
        """
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MCP_API_KEY", None)
            with pytest.raises(RuntimeError) as exc_info:
                start_sse_server(MagicMock(), host="0.0.0.0", port=8901)
        assert "SECURITY" in str(exc_info.value)
        assert "MCP_API_KEY" in str(exc_info.value)

    @patch("uvicorn.run")
    def test_allows_localhost_without_api_key(self, mock_uvicorn):
        """Verify: allows 127.0.0.1 without MCP_API_KEY.

        Scenario: host=127.0.0.1, no MCP_API_KEY
        Expected: uvicorn.run called (no RuntimeError)
        """
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MCP_API_KEY", None)
            start_sse_server(MagicMock(), host="127.0.0.1", port=8901)
        mock_uvicorn.assert_called_once()

    @patch("uvicorn.run")
    def test_allows_non_localhost_with_api_key(self, mock_uvicorn):
        """Verify: allows non-localhost when MCP_API_KEY is set.

        Scenario: host=0.0.0.0, MCP_API_KEY=secret
        Expected: uvicorn.run called (no RuntimeError)
        """
        with patch.dict(os.environ, {"MCP_API_KEY": "secret"}):
            start_sse_server(MagicMock(), host="0.0.0.0", port=8901)
        mock_uvicorn.assert_called_once()

    @patch("uvicorn.run")
    def test_warns_when_mcp_host_env_is_non_localhost(self, mock_uvicorn, caplog):
        """Verify: logs warning when MCP_HOST env var is non-localhost.

        Scenario: MCP_HOST=192.168.1.1, host=127.0.0.1 (localhost)
        Expected: Warning logged about external accessibility
        """
        with patch.dict(
            os.environ,
            {"MCP_HOST": "192.168.1.1", "MCP_API_KEY": "key"},
        ):
            with caplog.at_level(logging.WARNING):
                start_sse_server(MagicMock(), host="127.0.0.1", port=8901)
        assert "non-localhost" in caplog.text or "MCP_HOST" in caplog.text


class TestMain:
    """Test main() entry point with argparse."""

    def test_stdio_transport_selected_by_default(self):
        """Verify: default transport is stdio, creates and runs StdioTransport.

        Scenario: `mcp_transport` with no --transport flag
        Expected: StdioTransport created and run() called
        """
        with patch.object(sys, "argv", ["mcp_transport"]):
            with patch("opc_manager.mcp_transport.StdioTransport") as mock_class:
                mock_instance = MagicMock()
                mock_class.return_value = mock_instance
                transport_main()
        mock_class.assert_called_once()
        mock_instance.run.assert_called_once()

    def test_stdio_transport_explicit(self):
        """Verify: --transport stdio creates StdioTransport and runs it.

        Scenario: `mcp_transport --transport stdio`
        Expected: StdioTransport created and run() called
        """
        with patch.object(sys, "argv", ["mcp_transport", "--transport", "stdio"]):
            with patch("opc_manager.mcp_transport.StdioTransport") as mock_class:
                mock_instance = MagicMock()
                mock_class.return_value = mock_instance
                transport_main()
        mock_class.assert_called_once()
        mock_instance.run.assert_called_once()

    def test_sse_transport_without_fastapi_exits_one(self):
        """Verify: --transport sse without fastapi exits with code 1.

        Scenario: SSE_AVAILABLE=False, --transport sse
        Expected: SystemExit(1)
        """
        with patch.object(sys, "argv", ["mcp_transport", "--transport", "sse"]):
            with patch("opc_manager.mcp_transport.SSE_AVAILABLE", False):
                with pytest.raises(SystemExit) as exc_info:
                    transport_main()
        assert exc_info.value.code == 1

    @patch("opc_manager.mcp_transport.SSE_AVAILABLE", True)
    @patch("opc_manager.mcp_transport.start_sse_server")
    @patch("opc_manager.mcp_transport.create_sse_app")
    def test_sse_transport_with_fastapi_starts_server(
        self, mock_create_app, mock_start
    ):
        """Verify: --transport sse with fastapi calls create_sse_app + start_sse_server.

        Scenario: SSE_AVAILABLE=True, --transport sse --host 127.0.0.1 --port 9999
        Expected: create_sse_app() and start_sse_server() called
        """
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app
        with patch.object(
            sys,
            "argv",
            [
                "mcp_transport",
                "--transport",
                "sse",
                "--host",
                "127.0.0.1",
                "--port",
                "9999",
            ],
        ):
            transport_main()
        mock_create_app.assert_called_once()
        mock_start.assert_called_once_with(mock_app, host="127.0.0.1", port=9999)
