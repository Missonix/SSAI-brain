"""
数据库配置文件
包含MySQL和Redis的连接配置和管理
"""

import os
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import AsyncAdaptedQueuePool
from sqlalchemy import text
import aioredis
from database_models import Base
from dotenv import load_dotenv

# 加载环境变量
load_dotenv('database.env')

logger = logging.getLogger(__name__)

# 数据库配置
class DatabaseConfig:
    """数据库配置类"""
    
    def __init__(self):
        # MySQL配置
        self.mysql_host = os.getenv('MYSQL_HOST', 'localhost')
        self.mysql_port = int(os.getenv('MYSQL_PORT', '3306'))
        self.mysql_user = os.getenv('MYSQL_USER', 'root')
        self.mysql_password = os.getenv('MYSQL_PASSWORD', 'lpllz2233233')
        self.mysql_database = os.getenv('MYSQL_DATABASE', 'ai_chat')
        
        # Redis配置
        self.redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.redis_port = int(os.getenv('REDIS_PORT', '6379'))
        self.redis_password = os.getenv('REDIS_PASSWORD', '123456')
        self.redis_db = int(os.getenv('REDIS_DB', '0'))
        
        # 连接池配置
        self.mysql_pool_size = int(os.getenv('MYSQL_POOL_SIZE', '10'))
        self.mysql_max_overflow = int(os.getenv('MYSQL_MAX_OVERFLOW', '20'))
        
        # Redis连接池配置
        self.redis_max_connections = int(os.getenv('REDIS_MAX_CONNECTIONS', '10'))
        
    @property
    def mysql_url(self) -> str:
        """获取MySQL连接URL"""
        return f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
    
    @property
    def redis_url(self) -> str:
        """获取Redis连接URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        else:
            return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

# 全局配置实例
db_config = DatabaseConfig()

# 数据库引擎和会话
mysql_engine = None
async_session_maker = None
redis_client = None

async def init_mysql():
    """初始化MySQL连接"""
    global mysql_engine, async_session_maker
    
    try:
        # 创建异步引擎
        mysql_engine = create_async_engine(
            db_config.mysql_url,
            poolclass=AsyncAdaptedQueuePool,
            pool_size=db_config.mysql_pool_size,
            max_overflow=db_config.mysql_max_overflow,
            pool_pre_ping=True,
            pool_recycle=3600,  # 1小时回收连接
            echo=False  # 设置为True可以看到SQL日志
        )
        
        # 创建会话工厂
        async_session_maker = async_sessionmaker(
            mysql_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # 创建表
        async with mysql_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("✅ MySQL数据库连接初始化成功")
        return True
        
    except Exception as e:
        logger.error(f"❌ MySQL数据库连接初始化失败: {e}")
        return False

async def init_redis():
    """初始化Redis连接"""
    global redis_client
    
    try:
        # 创建Redis连接池
        redis_client = aioredis.from_url(
            db_config.redis_url,
            max_connections=db_config.redis_max_connections,
            retry_on_timeout=True,
            decode_responses=True  # 自动解码响应为字符串
        )
        
        # 测试连接
        await redis_client.ping()
        
        logger.info("✅ Redis连接初始化成功")
        return True
        
    except Exception as e:
        logger.error(f"❌ Redis连接初始化失败: {e}")
        return False

async def close_mysql():
    """关闭MySQL连接"""
    global mysql_engine
    if mysql_engine:
        await mysql_engine.dispose()
        logger.info("MySQL连接已关闭")

async def close_redis():
    """关闭Redis连接"""
    global redis_client
    if redis_client:
        await redis_client.close()
        logger.info("Redis连接已关闭")

def get_mysql_session() -> AsyncSession:
    """获取MySQL会话"""
    if not async_session_maker:
        raise RuntimeError("MySQL未初始化，请先调用init_mysql()")
    return async_session_maker()

async def get_redis_client():
    """获取Redis客户端"""
    if not redis_client:
        raise RuntimeError("Redis未初始化，请先调用init_redis()")
    return redis_client

# 数据库健康检查
async def check_mysql_health() -> bool:
    """检查MySQL连接健康状态"""
    try:
        async with get_mysql_session() as session:
            result = await session.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        logger.error(f"MySQL健康检查失败: {e}")
        return False

async def check_redis_health() -> bool:
    """检查Redis连接健康状态"""
    try:
        client = await get_redis_client()
        await client.ping()
        return True
    except Exception as e:
        logger.error(f"Redis健康检查失败: {e}")
        return False

# 初始化所有数据库连接
async def init_all_databases():
    """初始化所有数据库连接"""
    mysql_ok = await init_mysql()
    redis_ok = await init_redis()
    
    if mysql_ok and redis_ok:
        logger.info("🎉 所有数据库连接初始化成功")
        return True
    else:
        logger.error("❌ 数据库连接初始化失败")
        return False

# 关闭所有数据库连接
async def close_all_databases():
    """关闭所有数据库连接"""
    await close_mysql()
    await close_redis()
    logger.info("所有数据库连接已关闭") 