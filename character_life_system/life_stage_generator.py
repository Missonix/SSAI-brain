"""
角色生命阶段生成器
基于角色基本信息和背景，生成角色的生命阶段详细信息
"""

import asyncio
import logging
import json
import os
import sys
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import google.generativeai as genai

# 导入统一模型配置管理器
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'mcp_agent'))
from model_config import get_genai_model, get_model_config

# 添加mcp_agent路径以便导入database_config
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from database_config_forlife import (
    init_all_databases, close_all_databases,
    get_redis_client, close_redis, check_mysql_health, check_redis_health
)
from character_life_system.models import (
    LifeStageData, StageStatusEnum
)

logger = logging.getLogger(__name__)

class LifeStageGenerator:
    """生命阶段生成器"""
    
    def __init__(self):
        """
        初始化生命阶段生成器
        """
        self.logger = logging.getLogger(__name__)
        
        # 使用统一的模型配置
        try:
            self.model = get_genai_model()
            model_config = get_model_config()
            self.logger.info(f"✅ LifeStageGenerator初始化成功 - 使用模型: {model_config.model_name}")
        except Exception as e:
            self.logger.error(f"❌ LifeStageGenerator初始化失败: {e}")
            raise
        
    async def generate_life_stages_for_role(self, role_id: str) -> bool:
        """为指定角色生成生命阶段"""
        try:
            self.logger.info(f"开始为角色 {role_id} 生成生命阶段...")
            
            # 1. 获取角色基础信息
            role_info = await self._get_role_basic_info(role_id)
            if not role_info:
                self.logger.error(f"无法获取角色 {role_id} 的基础信息")
                return False
            
            # 2. 获取角色生命大纲信息
            outline_info = await self._get_role_outline_info(role_id)
            if not outline_info:
                self.logger.error(f"无法获取角色 {role_id} 的生命大纲信息")
                return False
            
            # 3. 构建生成提示词
            prompt = self._build_life_stage_generation_prompt(role_info, outline_info)
            
            # 4. 调用LLM生成生命阶段
            life_stages_data = await self._generate_life_stages_with_llm(prompt)
            if not life_stages_data:
                self.logger.error("LLM生成生命阶段失败")
                return False
            
            # 5. 验证和处理生成的数据
            processed_stages = self._process_generated_stages(life_stages_data, outline_info['outline_id'])
            
            # 6. 存储到数据库
            success_count = 0
            for stage_data in processed_stages:
                # 直接插入数据库而不使用character_life_manager
                try:
                    from mcp_agent.database_config import get_mysql_session
                    from sqlalchemy import text
                    
                    async with get_mysql_session() as session:
                        insert_sql = """
                        INSERT INTO life_stages (
                            life_stage_id, outline_id, sequence_order, life_period, 
                            title, description_for_plot_llm, stage_goals, status
                        ) VALUES (
                            :life_stage_id, :outline_id, :sequence_order, :life_period, 
                            :title, :description_for_plot_llm, :stage_goals, :status
                        )
                        """
                        
                        await session.execute(text(insert_sql), {
                            'life_stage_id': stage_data.life_stage_id,
                            'outline_id': stage_data.outline_id,
                            'sequence_order': stage_data.sequence_order,
                            'life_period': stage_data.life_period,
                            'title': stage_data.title,
                            'description_for_plot_llm': stage_data.description_for_plot_llm,
                            'stage_goals': stage_data.stage_goals,
                            'status': stage_data.status.value
                        })
                        await session.commit()
                        
                    success_count += 1
                    self.logger.info(f"✅ 生命阶段创建成功: {stage_data.title}")
                        
                except Exception as e:
                    self.logger.error(f"❌ 生命阶段创建失败: {stage_data.title} - {e}")
                    continue
            
            self.logger.info(f"生命阶段生成完成，成功创建 {success_count}/{len(processed_stages)} 个阶段")
            return success_count > 0
            
        except Exception as e:
            self.logger.error(f"生成生命阶段时发生错误: {e}")
            return False
    
    async def _get_role_basic_info(self, role_id: str) -> Optional[Dict[str, Any]]:
        """从role_details表获取角色基础信息"""
        try:
            from mcp_agent.database_config import get_mysql_session
            from sqlalchemy import text
            
            async with get_mysql_session() as session:
                result = await session.execute(
                    text("SELECT role_name, L0_prompt_path FROM role_details WHERE role_id = :role_id"),
                    {"role_id": role_id}
                )
                row = result.fetchone()
                
                if row:
                    return {
                        "role_name": row.role_name,
                        "L0_prompt_path": row.L0_prompt_path
                    }
                return None
                
        except Exception as e:
            self.logger.error(f"获取角色基础信息失败: {e}")
            return None
    
    async def _get_role_outline_info(self, role_id: str) -> Optional[Dict[str, Any]]:
        """从LifePlotOutlines表获取角色生命大纲信息"""
        try:
            from mcp_agent.database_config import get_mysql_session
            from sqlalchemy import text
            
            async with get_mysql_session() as session:
                result = await session.execute(
                    text("""
                    SELECT outline_id, role_name, title, overall_theme, life, wealth, birthday 
                    FROM life_plot_outlines 
                    WHERE role_id = :role_id 
                    ORDER BY version DESC 
                    LIMIT 1
                    """),
                    {"role_id": role_id}
                )
                row = result.fetchone()
                
                if row:
                    return {
                        "outline_id": row.outline_id,
                        "role_name": row.role_name,
                        "title": row.title,
                        "overall_theme": row.overall_theme,
                        "life": row.life,
                        "wealth": row.wealth,
                        "birthday": row.birthday
                    }
                return None
            
        except Exception as e:
            self.logger.error(f"获取角色生命大纲信息失败: {e}")
            return None
    
    def _build_life_stage_generation_prompt(self, role_info: Dict[str, Any], outline_info: Dict[str, Any]) -> str:
        """构建生命阶段生成提示词"""
        
        # 计算当前年龄
        if isinstance(outline_info['birthday'], str):
            birthday = datetime.strptime(outline_info['birthday'], '%Y-%m-%d').date()
        else:
            birthday = outline_info['birthday']
        
        current_year = datetime.now().year
        current_age = current_year - birthday.year
        
        prompt = f"""你是一个专业的角色生命轨迹设计师，需要为角色设计完整的人生阶段规划。

**角色信息：**
- 角色名称：{role_info['role_name']}
- 生命大纲标题：{outline_info['title']}
- 总体主题：{outline_info['overall_theme']}
- 生日：{birthday} (当前约{current_age}岁)
- 生命值：{outline_info['life']}/100
- 财富状况：{outline_info['wealth']}

**任务要求：**
请为此角色设计完整的人生阶段，从出生到当前年龄或预期寿命。每个阶段需要包含以下信息：

1. **sequence_order**: 阶段序号 (从1开始)
2. **life_period**: 人物年龄时间段 (格式如："0-6岁", "7-12岁", "18-22岁", "23-30岁"等)
3. **title**: 阶段标题 (如："幼儿时期", "小学时代", "大学时代", "初入职场", "职业发展期", "中年危机与蜕变"等)
4. **description_for_plot_llm**: 对该阶段的宏观描述，要详细描述这个阶段的背景环境、主要特征、核心冲突和发展趋势。这将指导该阶段所有剧情片段的基调。(150-300字)
5. **stage_goals**: 角色在此阶段的主要目标和动机，包括外在目标和内在成长需求。(100-200字)

**设计原则：**
- 阶段划分要符合人类成长的自然规律
- 要考虑中国社会文化背景和教育体系
- 每个阶段要有明确的特色和发展重点
- 阶段间要有逻辑连贯性和成长递进关系
- 要结合角色的总体主题和个人特质
- 至少设计6-8个主要人生阶段
- 重点关注对剧情发展有重要意义的阶段

**输出格式：**
请严格按照JSON格式返回，示例：
```json
{{
  "life_stages": [
    {{
      "sequence_order": 1,
      "life_period": "0-6岁",
      "title": "幼儿时期",
      "description_for_plot_llm": "这是角色人格形成的关键时期...",
      "stage_goals": "基础认知能力发展，安全感建立..."
    }},
    {{
      "sequence_order": 2,
      "life_period": "7-12岁", 
      "title": "小学时代",
      "description_for_plot_llm": "开始接受正规教育...",
      "stage_goals": "学习基础知识，培养学习习惯..."
    }}
  ]
}}
```

请开始生成此角色的完整人生阶段规划："""

        return prompt
    
    async def _generate_life_stages_with_llm(self, prompt: str) -> Optional[Dict[str, Any]]:
        """使用LLM生成生命阶段数据"""
        try:
            self.logger.info("正在调用Gemini API生成生命阶段...")
            
            # 调用Gemini API
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            self.logger.info(f"LLM响应长度: {len(response_text)} 字符")
            
            # 提取JSON内容
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                self.logger.error("LLM响应中未找到有效的JSON格式")
                return None
            
            json_content = response_text[json_start:json_end]
            
            # 解析JSON
            try:
                data = json.loads(json_content)
                self.logger.info(f"成功解析JSON，包含 {len(data.get('life_stages', []))} 个生命阶段")
                return data
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON解析失败: {e}")
                self.logger.debug(f"原始响应: {response_text}")
                return None
                
        except Exception as e:
            self.logger.error(f"LLM生成失败: {e}")
            return None
    
    def _process_generated_stages(self, life_stages_data: Dict[str, Any], outline_id: str) -> List[LifeStageData]:
        """处理和验证生成的生命阶段数据"""
        processed_stages = []
        
        stages = life_stages_data.get('life_stages', [])
        for stage in stages:
            try:
                # 验证必需字段
                required_fields = ['sequence_order', 'life_period', 'title', 'description_for_plot_llm', 'stage_goals']
                if not all(field in stage for field in required_fields):
                    self.logger.warning(f"跳过不完整的阶段数据: {stage}")
                    continue
                
                # 创建LifeStageData对象
                stage_data = LifeStageData(
                    life_stage_id=str(uuid.uuid4()),
                    outline_id=outline_id,
                    sequence_order=int(stage['sequence_order']),
                    life_period=stage['life_period'],
                    title=stage['title'],
                    description_for_plot_llm=stage['description_for_plot_llm'],
                    stage_goals=stage['stage_goals'],
                    status=StageStatusEnum.LOCKED,  # 默认为锁定状态
                    summary=None
                )
                
                processed_stages.append(stage_data)
                
            except Exception as e:
                self.logger.error(f"处理阶段数据时出错: {e}, 数据: {stage}")
                continue
        
        # 按sequence_order排序
        processed_stages.sort(key=lambda x: x.sequence_order)
        
        # 将第一个阶段设为active状态
        if processed_stages:
            processed_stages[0].status = StageStatusEnum.ACTIVE
        
        self.logger.info(f"成功处理 {len(processed_stages)} 个生命阶段")
        return processed_stages

async def generate_life_stages_for_all_roles():
    """为所有角色生成生命阶段"""
    try:
        # 初始化数据库连接
        from mcp_agent.database_config import init_all_databases
        db_success = await init_all_databases()
        if not db_success:
            print("❌ 数据库连接初始化失败")
            return
        
        # 手动初始化character_life_manager的数据库连接
        # 修复数据库配置路径问题
        import character_life_system.database_manager as dm
        original_import = dm.character_life_manager.__class__.__dict__.get('create_life_plot_outline')
        
        # 创建生成器
        generator = LifeStageGenerator()
        
        # 获取所有有生命大纲的角色
        from mcp_agent.database_config import get_mysql_session
        from sqlalchemy import text
        
        async with get_mysql_session() as session:
            result = await session.execute(
                text("SELECT DISTINCT role_id FROM life_plot_outlines")
            )
            role_ids = [row.role_id for row in result.fetchall()]
        
        if not role_ids:
            print("❌ 没有找到任何角色的生命大纲")
            return
        
        print(f"🎭 找到 {len(role_ids)} 个角色需要生成生命阶段")
        
        # 为每个角色生成生命阶段
        for role_id in role_ids:
            print(f"\n📝 正在为角色 {role_id} 生成生命阶段...")
            
            # 手动检查是否已有生命阶段，避免使用有问题的character_life_manager
            async with get_mysql_session() as session:
                # 首先获取角色的outline_id
                outline_result = await session.execute(
                    text("SELECT outline_id FROM life_plot_outlines WHERE role_id = :role_id LIMIT 1"),
                    {"role_id": role_id}
                )
                outline_row = outline_result.fetchone()
                
                if not outline_row:
                    print(f"⚠️ 角色 {role_id} 没有生命大纲，跳过")
                    continue
                
                outline_id = outline_row.outline_id
            
            # 检查是否已有生命阶段
            async with get_mysql_session() as session:
                stage_result = await session.execute(
                    text("SELECT COUNT(*) as count FROM life_stages WHERE outline_id = :outline_id"),
                    {"outline_id": outline_id}
                )
                stage_count = stage_result.fetchone().count
            
                if stage_count > 0:
                    print(f"⚠️ 角色 {role_id} 已有 {stage_count} 个生命阶段，跳过生成")
                    continue
            
            success = await generator.generate_life_stages_for_role(role_id)
            if success:
                print(f"✅ 角色 {role_id} 生命阶段生成成功")
            else:
                print(f"❌ 角色 {role_id} 生命阶段生成失败")
        
        print("\n🎉 所有角色的生命阶段生成完成！")
        
    except Exception as e:
        print(f"❌ 生成过程中发生错误: {e}")
        raise

if __name__ == "__main__":
    import asyncio
    import logging
    
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
    
    # 运行生成器
    asyncio.run(generate_life_stages_for_all_roles()) 