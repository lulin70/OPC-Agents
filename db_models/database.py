"""数据库连接管理与会话工厂"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from db_models.models import Base
from web_app.config import settings

_engine = None
_SessionLocal = None


def get_engine():
    """获取数据库引擎（单例）"""
    global _engine
    if _engine is None:
        db_url = settings.DATABASE_URL
        engine_kwargs = {
            "echo": settings.DEBUG,
            "future": True,
        }
        if db_url.startswith("sqlite"):
            engine_kwargs.update({
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            })
        _engine = create_engine(db_url, **engine_kwargs)
        
        Base.metadata.create_all(_engine)
    return _engine


def get_session() -> Session:
    """获取数据库会话"""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return _SessionLocal()


def init_db():
    """初始化数据库，创建所有表"""
    engine = get_engine()
    Base.metadata.create_all(engine)
    print(f"[DB] Database initialized at {settings.DATABASE_URL}")


def reset_db():
    """重置数据库（删除所有表并重建）- 仅用于测试"""
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    print("[DB] Database reset complete")
