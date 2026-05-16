"""
SkillMarketplaceAPI — FastAPI REST服务

提供技能市场的HTTP API端点：
- POST /api/v1/keys — 创建API Key
- POST /api/v1/skills — 注册技能
- PUT /api/v1/skills/{skill_id}/approve — 审核技能
- GET /api/v1/skills — 发现技能
- GET /api/v1/skills/{skill_id} — 获取技能详情
- POST /api/v1/skills/{skill_id}/execute — 调用技能
- GET /api/v1/stats — 市场统计

启动方式：
  uvicorn opc_manager.skill_marketplace_api:app --host 0.0.0.0 --port 8900
"""

import logging
import os
import time
from typing import Dict, List, Optional, Any

from .version import __version__

logger = logging.getLogger(__name__)

FASTAPI_AVAILABLE = False
try:
    from fastapi import FastAPI, HTTPException, Header, Depends, Query
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    FASTAPI_AVAILABLE = True
except ImportError:
    pass

if FASTAPI_AVAILABLE:
    from .skill_marketplace import (
        SkillMarketplace, MarketplaceSkill, PermissionLevel, SkillStatus,
        ExternalSkillMarketplace,
    )

    app = FastAPI(
        title="OPC-Agents Skill Marketplace API",
        version=__version__,
        description="技能市场REST API — 注册/发现/调用技能",
    )

    _allowed_origins = os.environ.get("MARKETPLACE_CORS_ORIGINS", "http://localhost:8501,http://localhost:8900").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    marketplace = SkillMarketplace()
    external_marketplace = ExternalSkillMarketplace()
    _rate_limit_store: Dict[str, List[float]] = {}
    MAX_REQUEST_BODY_BYTES = 1_000_000

    @app.middleware("http")
    async def limit_request_size(request, call_next):
        if request.method in ("POST", "PUT"):
            body = await request.body()
            if len(body) > MAX_REQUEST_BODY_BYTES:
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=413, content={"error": "Request body too large"})
        return await call_next(request)

    class SkillRegisterRequest(BaseModel):
        skill_id: str
        name: str
        description: str
        version: str = "1.0.0"
        category: str = "general"
        author: str = "anonymous"
        dependencies: List[str] = []
        config: Dict[str, Any] = {}

    class SkillExecuteRequest(BaseModel):
        parameters: Dict[str, Any] = {}

    class APIKeyCreateRequest(BaseModel):
        name: str
        permissions: List[str] = ["read"]
        rate_limit: int = 100

    def _get_api_key(x_api_key: str = Header(None)) -> str:
        if not x_api_key:
            raise HTTPException(status_code=401, detail="Missing X-API-Key header")
        key_info = marketplace.authenticate(x_api_key)
        if not key_info:
            raise HTTPException(status_code=401, detail="Invalid API key")
        now = time.time()
        requests = _rate_limit_store.get(x_api_key, [])
        requests = [t for t in requests if now - t < 60]
        if len(requests) >= key_info.rate_limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        requests.append(now)
        _rate_limit_store[x_api_key] = requests
        return x_api_key

    def _check_permission(api_key: str, required: PermissionLevel) -> None:
        if not marketplace.check_permission(api_key, required):
            raise HTTPException(status_code=403, detail=f"Insufficient permissions: {required.value} required")

    @app.post("/api/v1/keys")
    async def create_api_key(request: APIKeyCreateRequest):
        perms = [PermissionLevel(p) for p in request.permissions]
        raw_key = marketplace.create_api_key(request.name, perms, request.rate_limit)
        return {"success": True, "api_key": raw_key, "name": request.name}

    @app.post("/api/v1/skills")
    async def register_skill(request: SkillRegisterRequest, api_key: str = Depends(_get_api_key)):
        _check_permission(api_key, PermissionLevel.WRITE)
        skill = MarketplaceSkill(
            skill_id=request.skill_id, name=request.name,
            description=request.description, version=request.version,
            category=request.category, author=request.author,
            dependencies=request.dependencies, config=request.config,
        )
        result = marketplace.register_skill(skill, api_key)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        return result

    @app.put("/api/v1/skills/{skill_id}/approve")
    async def approve_skill(skill_id: str, api_key: str = Depends(_get_api_key)):
        _check_permission(api_key, PermissionLevel.WRITE)
        result = marketplace.approve_skill(skill_id, api_key)
        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["error"])
        return result

    @app.get("/api/v1/skills")
    async def discover_skills(
        category: Optional[str] = Query(None),
        keyword: Optional[str] = Query(None),
    ):
        results = marketplace.discover_skills(category=category, keyword=keyword)
        return {"skills": results, "total": len(results)}

    @app.get("/api/v1/skills/{skill_id}")
    async def get_skill(skill_id: str):
        skill = marketplace.get_skill(skill_id)
        if not skill:
            raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")
        return skill

    @app.post("/api/v1/skills/{skill_id}/execute")
    async def execute_skill(skill_id: str, request: SkillExecuteRequest, api_key: str = Depends(_get_api_key)):
        _check_permission(api_key, PermissionLevel.EXECUTE)
        result = marketplace.execute_skill(skill_id, request.parameters, api_key)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        return result

    @app.get("/api/v1/stats")
    async def get_stats():
        return marketplace.get_stats()

    @app.get("/api/v1/categories")
    async def list_categories():
        return {"categories": marketplace.list_categories()}

    @app.get("/api/v1/marketplace/skills")
    async def list_marketplace_skills(
        query: Optional[str] = Query(None),
        category: Optional[str] = Query(None),
    ):
        result = external_marketplace.search_skills(query or "", category or "")
        return result

    @app.get("/api/v1/marketplace/stats")
    async def get_marketplace_stats():
        internal_stats = marketplace.get_stats()
        external_installed = external_marketplace.list_installed()
        return {
            **internal_stats,
            "external_skills": external_installed.get("total", 0),
        }

    @app.post("/api/v1/marketplace/{skill_id}/install")
    async def install_skill(skill_id: str, source: str = "opc_official"):
        result = external_marketplace.install_skill(skill_id, source)
        if not result.get("success") and not result.get("requires_confirmation"):
            raise HTTPException(status_code=400, detail=result.get("error", "Installation failed"))
        return result

    @app.delete("/api/v1/marketplace/{skill_id}/uninstall")
    async def uninstall_skill(skill_id: str):
        result = external_marketplace.uninstall_skill(skill_id)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("error", "Skill not found"))
        return result

    @app.get("/api/v1/marketplace/installed")
    async def list_installed_skills():
        return external_marketplace.list_installed()

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "version": __version__}

else:
    app = None
    logger.warning("FastAPI not available. Install with: pip install fastapi uvicorn")
