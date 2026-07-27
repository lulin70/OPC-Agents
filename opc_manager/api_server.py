"""OPC-Agents API Server — FastAPI 聚合入口（v0.5.0 P3）。

启动方式:
  uvicorn opc_manager.api_server:app --host 0.0.0.0 --port 8900

聚合路由:
  - /api/v1/feedback/*   反馈 API
  - /api/v1/metrics/*    指标 API
  - /health              健康检查
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from opc_manager.api import rate_limit_middleware
from opc_manager.api.feedback_routes import router as feedback_router
from opc_manager.api.metrics_routes import router as metrics_router
from opc_manager.version import __version__ as API_VERSION

logger = logging.getLogger(__name__)

app = FastAPI(
    title="OPC-Agents API",
    version=API_VERSION,
    description="用户反馈与指标采集 API（v0.5.0 P3）",
)

# CORS — API_DESIGN §2 通用约定
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://localhost:8501",
        "http://localhost:8900",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _rate_limit(request: Request, call_next: Any) -> Any:
    """挂载共享限流中间件（60 req/min）。"""
    return await rate_limit_middleware(request, call_next)


@app.middleware("http")
async def _request_id_injector(request: Request, call_next: Any) -> Any:
    """为每个请求注入 request_id，便于错误响应追溯。"""
    import uuid as _uuid

    request.state.request_id = str(_uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


# 统一异常处理 — API_DESIGN §6.3
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # prompt injection / XSS 命中危险模式时返回 400（业务规则失败），
    # 其他 Pydantic 字段校验失败仍返回 422。
    request_id = getattr(request.state, "request_id", "")
    for err in exc.errors():
        msg = str(err.get("msg", ""))
        ctx = err.get("ctx") or {}
        if "恶意内容" in msg or "恶意内容" in str(ctx):
            return JSONResponse(
                status_code=400,
                content={
                    "error": "bad_request",
                    "detail": "输入包含潜在恶意内容",
                    "request_id": request_id,
                },
            )
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "detail": exc.errors(),
            "request_id": request_id,
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "error": "bad_request",
            "detail": str(exc),
            "request_id": getattr(request.state, "request_id", ""),
        },
    )


# 注册路由
app.include_router(feedback_router)
app.include_router(metrics_router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    """健康检查端点。"""
    return {"status": "ok", "version": API_VERSION}


@app.get("/", tags=["root"])
async def root() -> dict:
    """根路径：返回 API 元信息。"""
    return {
        "name": "OPC-Agents API",
        "version": API_VERSION,
        "docs": "/docs",
        "health": "/health",
    }
