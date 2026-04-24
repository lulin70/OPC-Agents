"""Web应用配置 - 环境变量加载"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用全局配置"""
    
    APP_NAME: str = "OPC-Agents V3"
    APP_VERSION: str = "3.0.0"
    DEBUG: bool = False
    
    # 数据库配置
    DATABASE_URL: str = "sqlite:///./opc_agents_v3.db"
    
    # LLM 配置
    LLM_PROVIDER: str = "moka"
    LLM_API_KEY: Optional[str] = None
    LLM_BASE_URL: Optional[str] = None
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_MAX_TOKENS: int = 500
    LLM_TEMPERATURE: float = 0.3
    LLM_TIMEOUT_SECONDS: float = 60.0
    LLM_COST_BUDGET_DAILY: float = 5.0

    SECRET_KEY: str = os.environ.get("SECRET_KEY", "")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    
    # 限流配置
    RATE_LIMIT_PER_MINUTE: int = 100
    
    # CORS 配置
    CORS_ORIGINS: list = ["http://localhost:8501", "http://localhost:8000"]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
