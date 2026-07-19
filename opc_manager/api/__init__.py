"""OPC-Agents API package — 用户反馈与指标 REST API。

子模块:
  - models: Pydantic v2 模型（请求/响应）
  - feedback_routes: /api/v1/feedback 系列端点
  - metrics_routes: /api/v1/metrics 系列端点

本模块同时承载共享依赖（认证、限流），供两个 routes 文件复用，
避免新建 dependencies.py 增加 P3 阶段文件数。
"""

import hashlib
import time
from typing import Any, Dict, List

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

__all__ = [
    "models",
    "feedback_routes",
    "metrics_routes",
    "get_current_user",
    "require_admin",
    "rate_limit_check",
    "rate_limit_middleware",
    "reset_rate_limit_store",
    "DEFAULT_RATE_LIMIT_PER_MIN",
    "BATCH_RATE_LIMIT_PER_MIN",
    "EXPORT_COOLDOWN_SECONDS",
]

# 限流参数（API_DESIGN §2 限流策略）
DEFAULT_RATE_LIMIT_PER_MIN = 60
BATCH_RATE_LIMIT_PER_MIN = 5
EXPORT_COOLDOWN_SECONDS = 3600  # /metrics/export 单用户 1 小时冷却

# 共享限流存储：滑动窗口
# 结构: {key: [timestamp, timestamp, ...]}
_rate_limit_store: Dict[str, List[float]] = {}


def reset_rate_limit_store() -> None:
    """测试用：清空限流存储。"""
    _rate_limit_store.clear()


def _client_key(request: Request) -> str:
    """提取客户端标识：X-API-Key 优先，回退到 client host。"""
    api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
    if api_key:
        return hashlib.sha256(api_key.encode()).hexdigest()[:16]
    return request.client.host if request.client else "unknown"


def rate_limit_check(
    request: Request, limit_per_min: int = DEFAULT_RATE_LIMIT_PER_MIN
) -> None:
    """滑动窗口限流检查。超出抛 429 + Retry-After 头。"""
    key = _client_key(request)
    now = time.time()
    window = 60.0
    requests = _rate_limit_store.get(key, [])
    # 清理过期记录
    requests = [t for t in requests if now - t < window]
    if len(requests) >= limit_per_min:
        retry_after = max(1, int(window - (now - requests[0])))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {limit_per_min} req/min",
            headers={"Retry-After": str(retry_after)},
        )
    requests.append(now)
    _rate_limit_store[key] = requests


async def rate_limit_middleware(request: Request, call_next: Any) -> Any:
    """FastAPI 中间件：对所有 /api/v1 路径应用 60 req/min 限流。

    /health 与 OPTIONS 预检跳过；/api/v1/feedback/batch 由路由内单独限流到 5 req/min。

    注意：在 middleware 中抛 HTTPException 不会被 FastAPI exception handler
    捕获，必须在这里直接返回 JSONResponse。
    """
    path = request.url.path
    if path == "/health" or request.method == "OPTIONS" or not path.startswith("/api/v1"):
        return await call_next(request)
    # /api/v1/feedback/batch 由路由内单独更严格限流，此处放过避免双重计数
    if path == "/api/v1/feedback/batch":
        return await call_next(request)
    try:
        rate_limit_check(request, DEFAULT_RATE_LIMIT_PER_MIN)
    except HTTPException as exc:
        # middleware 中抛出的 HTTPException 不会经过 exception_handler，
        # 需要手动转换为 JSONResponse 才能正常返回 429 给客户端。
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "rate_limited",
                "detail": exc.detail,
                "request_id": getattr(request.state, "request_id", ""),
            },
            headers=exc.headers or None,
        )
    return await call_next(request)


def get_current_user(
    request: Request, x_api_key: str = Header(None, alias="X-API-Key")
) -> Dict[str, str]:
    """从 X-API-Key 标头认证用户（简化版 JWT 替代）。

    约定：
      - 未携带 X-API-Key → 401
      - 以 "admin-" 开头的 key → role=admin
      - 其他非空 key → role=user，user_id 即 key 全值
      - 空 key → 401
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未认证或 token 过期",
            headers={"WWW-Authenticate": 'Bearer realm="opc-agents"'},
        )
    if x_api_key.startswith("admin-"):
        return {"user_id": x_api_key, "role": "admin"}
    return {"user_id": x_api_key, "role": "user"}


def require_admin(user: Dict[str, str] = Depends(get_current_user)) -> Dict[str, str]:
    """要求 admin 角色。依赖 get_current_user 解析 X-API-Key。"""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要 admin 权限",
        )
    return user
