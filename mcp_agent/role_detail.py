"""
角色详细信息模型
支持多角色管理和动态情绪状态
"""

import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class RoleMood:
    """角色情绪状态"""
    my_valence: float  # 情感效价 (-1.0 到 1.0)
    my_arousal: float  # 唤醒度 (0.0 到 1.0)
    my_tags: str       # 情绪标签
    my_intensity: int  # 情绪强度 (1-10)
    my_mood_description_for_llm: str  # 给LLM的情绪描述
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "my_valence": self.my_valence,
            "my_arousal": self.my_arousal,
            "my_tags": self.my_tags,
            "my_intensity": self.my_intensity,
            "my_mood_description_for_llm": self.my_mood_description_for_llm
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RoleMood':
        """从字典创建"""
        return cls(
            my_valence=data["my_valence"],
            my_arousal=data["my_arousal"],
            my_tags=data["my_tags"],
            my_intensity=data["my_intensity"],
            my_mood_description_for_llm=data["my_mood_description_for_llm"]
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'RoleMood':
        """从JSON字符串创建"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

@dataclass
class RoleDetail:
    """角色详细信息"""
    role_id: str
    role_name: str
    L0_prompt_path: str  # L0提示词路径
    L1_prompt_path: str  # L1提示词路径
    mood: RoleMood       # 角色情绪状态
    age: Optional[int] = None                    # 年龄
    current_life_stage_id: Optional[str] = None  # 当前生活阶段ID
    current_plot_segment_id: Optional[str] = None # 当前剧情段落ID
    current_materials_id: Optional[str] = None   # 当前材料ID
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "role_id": self.role_id,
            "role_name": self.role_name,
            "L0_prompt_path": self.L0_prompt_path,
            "L1_prompt_path": self.L1_prompt_path,
            "mood": self.mood.to_json(),
            "age": self.age,
            "current_life_stage_id": self.current_life_stage_id,
            "current_plot_segment_id": self.current_plot_segment_id,
            "current_materials_id": self.current_materials_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class RoleDetailManager:
    """角色详细信息管理器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def create_role_table(self):
        """创建角色详细信息表"""
        from database_config import get_mysql_session
        from sqlalchemy import text
        
        try:
            async with get_mysql_session() as session:
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS role_details (
                    role_id VARCHAR(64) PRIMARY KEY COMMENT '角色ID',
                    role_name VARCHAR(255) NOT NULL COMMENT '角色名称',
                    L0_prompt_path VARCHAR(512) NOT NULL COMMENT 'L0提示词文件路径',
                    L1_prompt_path VARCHAR(512) NOT NULL COMMENT 'L1提示词文件路径',
                    mood JSON NOT NULL COMMENT '角色情绪状态',
                    age INT COMMENT '年龄',
                    current_life_stage_id VARCHAR(64) COMMENT '当前生活阶段ID',
                    current_plot_segment_id VARCHAR(64) COMMENT '当前剧情段落ID',
                    current_materials_id VARCHAR(64) COMMENT '当前材料ID',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    INDEX idx_role_name (role_name)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色详细信息表';
                """
                
                await session.execute(text(create_table_sql))
                await session.commit()
                self.logger.info("✅ 角色详细信息表创建成功")
                
        except Exception as e:
            self.logger.error(f"❌ 创建角色详细信息表失败: {e}")
            raise
    
    async def create_role(self, role_detail: RoleDetail) -> bool:
        """创建角色"""
        from database_config import get_mysql_session
        from sqlalchemy import text
        
        try:
            async with get_mysql_session() as session:
                insert_sql = """
                INSERT INTO role_details (role_id, role_name, L0_prompt_path, L1_prompt_path, mood, age, current_life_stage_id, current_plot_segment_id, current_materials_id)
                VALUES (:role_id, :role_name, :L0_prompt_path, :L1_prompt_path, :mood, :age, :current_life_stage_id, :current_plot_segment_id, :current_materials_id)
                """
                
                await session.execute(text(insert_sql), {
                    "role_id": role_detail.role_id,
                    "role_name": role_detail.role_name,
                    "L0_prompt_path": role_detail.L0_prompt_path,
                    "L1_prompt_path": role_detail.L1_prompt_path,
                    "mood": role_detail.mood.to_json(),
                    "age": role_detail.age,
                    "current_life_stage_id": role_detail.current_life_stage_id,
                    "current_plot_segment_id": role_detail.current_plot_segment_id,
                    "current_materials_id": role_detail.current_materials_id
                })
                
                await session.commit()
                self.logger.info(f"✅ 角色创建成功: {role_detail.role_name} ({role_detail.role_id})")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ 角色创建失败: {e}")
            return False
    
    async def get_role(self, role_id: str) -> Optional[RoleDetail]:
        """获取角色信息"""
        from database_config import get_mysql_session
        from sqlalchemy import text
        
        try:
            async with get_mysql_session() as session:
                select_sql = """
                SELECT role_id, role_name, L0_prompt_path, L1_prompt_path, mood, age, current_life_stage_id, current_plot_segment_id, current_materials_id, created_at, updated_at
                FROM role_details WHERE role_id = :role_id
                """
                
                result = await session.execute(text(select_sql), {"role_id": role_id})
                row = result.fetchone()
                
                if row:
                    mood = RoleMood.from_json(row[4])
                    return RoleDetail(
                        role_id=row[0],
                        role_name=row[1],
                        L0_prompt_path=row[2],
                        L1_prompt_path=row[3],
                        mood=mood,
                        age=row[5],
                        current_life_stage_id=row[6],
                        current_plot_segment_id=row[7],
                        current_materials_id=row[8],
                        created_at=str(row[9]) if row[9] else None,
                        updated_at=str(row[10]) if row[10] else None
                    )
                return None
                
        except Exception as e:
            self.logger.error(f"❌ 获取角色信息失败: {e}")
            return None
    
    async def update_role_mood(self, role_id: str, mood: RoleMood) -> bool:
        """更新角色情绪状态"""
        from database_config import get_mysql_session
        from sqlalchemy import text
        
        try:
            async with get_mysql_session() as session:
                update_sql = """
                UPDATE role_details SET mood = :mood WHERE role_id = :role_id
                """
                
                result = await session.execute(text(update_sql), {
                    "mood": mood.to_json(),
                    "role_id": role_id
                })
                await session.commit()
                
                if result.rowcount > 0:
                    self.logger.info(f"✅ 角色情绪状态更新成功: {role_id}")
                    return True
                else:
                    self.logger.warning(f"⚠️ 角色不存在: {role_id}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"❌ 更新角色情绪状态失败: {e}")
            return False
    
    async def list_roles(self) -> List[RoleDetail]:
        """获取所有角色列表"""
        from database_config import get_mysql_session
        from sqlalchemy import text
        
        try:
            async with get_mysql_session() as session:
                select_sql = """
                SELECT role_id, role_name, L0_prompt_path, L1_prompt_path, mood, age, current_life_stage_id, current_plot_segment_id, current_materials_id, created_at, updated_at
                FROM role_details ORDER BY created_at DESC
                """
                
                result = await session.execute(text(select_sql))
                rows = result.fetchall()
                
                roles = []
                for row in rows:
                    mood = RoleMood.from_json(row[4])
                    roles.append(RoleDetail(
                        role_id=row[0],
                        role_name=row[1],
                        L0_prompt_path=row[2],
                        L1_prompt_path=row[3],
                        mood=mood,
                        age=row[5],
                        current_life_stage_id=row[6],
                        current_plot_segment_id=row[7],
                        current_materials_id=row[8],
                        created_at=str(row[9]) if row[9] else None,
                        updated_at=str(row[10]) if row[10] else None
                    ))
                
                return roles
                
        except Exception as e:
            self.logger.error(f"❌ 获取角色列表失败: {e}")
            return []
    
    async def load_role_mood_to_redis(self, role_id: str) -> bool:
        """将角色情绪状态加载到Redis"""
        from database_config import get_redis_client
        
        try:
            role_detail = await self.get_role(role_id)
            if not role_detail:
                self.logger.error(f"❌ 角色不存在: {role_id}")
                return False
            
            redis_client = await get_redis_client()
            redis_key = f"role_mood:{role_id}"
            
            # 存储角色情绪状态到Redis
            await redis_client.hset(redis_key, mapping=role_detail.mood.to_dict())
            # 设置过期时间24小时
            await redis_client.expire(redis_key, 86400)
            
            self.logger.info(f"✅ 角色情绪状态已加载到Redis: {role_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 加载角色情绪状态到Redis失败: {e}")
            return False
    
    async def get_role_mood_from_redis(self, role_id: str) -> Optional[RoleMood]:
        """从Redis获取角色情绪状态"""
        from database_config import get_redis_client
        
        try:
            redis_client = await get_redis_client()
            redis_key = f"role_mood:{role_id}"
            
            mood_data = await redis_client.hgetall(redis_key)
            
            if mood_data:
                # 转换Redis返回的字节数据
                mood_dict = {}
                for key, value in mood_data.items():
                    key = key.decode('utf-8') if isinstance(key, bytes) else key
                    value = value.decode('utf-8') if isinstance(value, bytes) else value
                    
                    # 转换数据类型
                    if key in ['my_valence', 'my_arousal']:
                        mood_dict[key] = float(value)
                    elif key == 'my_intensity':
                        mood_dict[key] = int(value)
                    else:
                        mood_dict[key] = value
                
                return RoleMood.from_dict(mood_dict)
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ 从Redis获取角色情绪状态失败: {e}")
            return None

# 预定义角色数据
DEFAULT_ROLES = [
    RoleDetail(
        role_id="chenxiaozhi_001",
        role_name="陈小智",
        L0_prompt_path="prompt/L0_prompt.txt",
        L1_prompt_path="prompt/L1_prompt.txt",
        mood=RoleMood(
            my_valence=0.1,
            my_arousal=0.4,
            my_tags="平静",
            my_intensity=4,
            my_mood_description_for_llm="今天状态还不错，比较平静，对技术问题比较感兴趣"
        )
    ),
    RoleDetail(
        role_id="chenxiaozhi_happy",
        role_name="陈小智(开心版)",
        L0_prompt_path="prompt/L0_prompt.txt",
        L1_prompt_path="prompt/L1_prompt.txt",
        mood=RoleMood(
            my_valence=0.7,
            my_arousal=0.6,
            my_tags="开心、兴奋",
            my_intensity=6,
            my_mood_description_for_llm="今天心情特别好，刚解决了一个技术难题，很有成就感"
        )
    ),
    RoleDetail(
        role_id="chenxiaozhi_tired",
        role_name="陈小智(疲惫版)",
        L0_prompt_path="prompt/L0_prompt.txt",
        L1_prompt_path="prompt/L1_prompt.txt",
        mood=RoleMood(
            my_valence=-0.3,
            my_arousal=0.2,
            my_tags="疲惫、烦躁",
            my_intensity=5,
            my_mood_description_for_llm="最近加班比较多，有点累，容易烦躁，但还是会努力回答问题"
        )
    )
]

async def init_default_roles():
    """初始化默认角色数据"""
    manager = RoleDetailManager()
    
    # 创建表
    await manager.create_role_table()
    
    # 检查并创建默认角色
    for role in DEFAULT_ROLES:
        existing_role = await manager.get_role(role.role_id)
        if not existing_role:
            await manager.create_role(role)
            # 加载到Redis
            await manager.load_role_mood_to_redis(role.role_id)
        else:
            logger.info(f"角色已存在，跳过创建: {role.role_name}")
            # 确保Redis有数据
            await manager.load_role_mood_to_redis(role.role_id) 