"""FastAPI Web 应用后端 - OPC-Agents v3.0"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import logging

from web_app.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info(f"[Startup] {settings.APP_NAME} v{settings.APP_VERSION} starting...")
    
    from db_models.database import init_db
    init_db()
    
    yield
    
    logger.info("[Shutdown] Application shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="一人公司智能助手 - OPC-Agents Web API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
async def health_check():
    """系统健康检查"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "llm_provider": settings.LLM_PROVIDER,
        "database": settings.DATABASE_URL.split("://")[0] if "://" in settings.DATABASE_URL else "unknown",
    }


@app.get("/api/v1/info")
async def app_info():
    """应用信息"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "features": {
            "business_types": 6,
            "persona_variants": 6,
            "scenarios": 9,
            "flywheel_levels": 3,
            "llm_enabled": settings.LLM_PROVIDER != "mock" or True,
            "db_persistence": True,
        },
        "supported_business_types": [bt.value for bt in __import__("opc_manager.business_types", fromlist=["BusinessType"]).BusinessType],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_app.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
