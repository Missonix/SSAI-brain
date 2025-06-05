"""
生命阶段状态更新和摘要生成模块
根据角色年龄更新生命阶段状态，为已完成阶段生成摘要
"""

import json
import logging
import re
import sys
import os
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import google.generativeai as genai
import asyncio
import shutil

# 导入统一模型配置管理器
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'mcp_agent'))
from model_config import get_genai_model, get_model_config

# 添加mcp_agent路径以便导入database_config
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from character_life_system.database_manager import character_life_manager
from character_life_system.models import StageStatusEnum

logger = logging.getLogger(__name__)

class LifeStageUpdaterConfig:
    """生命阶段更新器配置类"""
    
    # 重试配置
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 2
    
    # 文件路径配置
    PAST_EXPERIENCE_BASE_DIR = "character_summaries"  # 过往经历总结基础目录
    DAILY_PLOT_BASE_DIR = "character_plots"  # 日常剧情基础目录
    
    # 生成配置
    MAX_L0_PROMPT_LENGTH = 500
    
    @classmethod
    def get_api_key(cls) -> str:
        """获取API密钥，使用统一配置"""
        from model_config import get_model_config
        config = get_model_config()
        return config.api_key
    
    @classmethod
    def get_model_name(cls) -> str:
        """获取模型名称，使用统一配置"""
        from model_config import get_model_config
        config = get_model_config()
        return config.model_name

class LifeStageUpdater:
    """生命阶段状态更新器和摘要生成器"""
    
    def __init__(self):
        """初始化更新器"""
        self.logger = logging.getLogger(__name__)
        
        # 使用统一的模型配置
        try:
            self.model = get_genai_model()
            model_config = get_model_config()
            self.logger.info(f"✅ LifeStageUpdater初始化成功 - 使用模型: {model_config.model_name}")
        except Exception as e:
            self.logger.error(f"❌ LifeStageUpdater初始化失败: {e}")
            raise
    
    async def update_all_life_stage_status(self):
        """更新所有角色的生命阶段状态"""
        try:
            self.logger.info("开始更新所有角色的生命阶段状态...")
            
            # 获取所有角色
            from mcp_agent.database_config_forlife import get_mysql_session
            from sqlalchemy import text
            
            async with get_mysql_session() as session:
                # 获取所有有年龄信息的角色
                result = await session.execute(
                    text("SELECT role_id, age FROM role_details WHERE age IS NOT NULL")
                )
                roles = result.fetchall()
            
            if not roles:
                self.logger.warning("没有找到有年龄信息的角色")
                return
            
            updated_count = 0
            for role in roles:
                role_id = role.role_id
                age = role.age
                
                success = await self._update_role_life_stage_status(role_id, age)
                if success:
                    updated_count += 1
                    self.logger.info(f"✅ 角色 {role_id} 生命阶段状态更新成功")
                else:
                    self.logger.error(f"❌ 角色 {role_id} 生命阶段状态更新失败")
            
            self.logger.info(f"生命阶段状态更新完成，成功更新 {updated_count}/{len(roles)} 个角色")
            
        except Exception as e:
            self.logger.error(f"更新生命阶段状态时发生错误: {e}")
            raise
    
    async def _update_role_life_stage_status(self, role_id: str, age: int) -> bool:
        """更新指定角色的生命阶段状态"""
        try:
            # 获取角色的生命大纲
            outlines = await character_life_manager.get_life_plot_outlines_by_role(role_id)
            if not outlines:
                self.logger.warning(f"角色 {role_id} 没有生命大纲")
                return False
            
            outline_id = outlines[0].outline_id
            
            # 获取该角色的所有生命阶段
            stages = await character_life_manager.get_life_stages_by_outline(outline_id)
            if not stages:
                self.logger.warning(f"角色 {role_id} 没有生命阶段")
                return False
            
            # 更新每个阶段的状态
            for stage in stages:
                new_status = self._determine_stage_status(age, stage.life_period)
                if new_status != stage.status:
                    success = await character_life_manager.update_life_stage_status(
                        stage.life_stage_id, new_status
                    )
                    if success:
                        self.logger.debug(f"阶段 {stage.title} 状态更新为: {new_status.value}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"更新角色 {role_id} 生命阶段状态失败: {e}")
            return False
    
    def _determine_stage_status(self, age: int, life_period: str) -> StageStatusEnum:
        """根据年龄和生命时期确定阶段状态"""
        try:
            # 解析life_period，例如 "23-26岁" -> (23, 26)
            period_range = self._parse_life_period(life_period)
            if not period_range:
                return StageStatusEnum.LOCKED
            
            start_age, end_age = period_range
            
            if start_age <= age <= end_age:
                return StageStatusEnum.ACTIVE
            elif age > end_age:
                return StageStatusEnum.COMPLETED
            else:  # age < start_age
                return StageStatusEnum.LOCKED
                
        except Exception as e:
            self.logger.error(f"解析生命时期失败: {life_period}, {e}")
            return StageStatusEnum.LOCKED
    
    def _parse_life_period(self, life_period: str) -> Optional[Tuple[int, int]]:
        """解析生命时期字符串，返回年龄范围"""
        try:
            # 匹配模式如 "23-26岁", "0-6岁" 等
            pattern = r'(\d+)-(\d+)岁'
            match = re.match(pattern, life_period.strip())
            
            if match:
                start_age = int(match.group(1))
                end_age = int(match.group(2))
                return (start_age, end_age)
            
            return None
            
        except Exception as e:
            self.logger.error(f"解析生命时期字符串失败: {life_period}, {e}")
            return None
    
    async def generate_completed_stage_summaries(self):
        """为所有已完成且没有摘要的生命阶段生成摘要"""
        try:
            self.logger.info("开始为已完成的生命阶段生成摘要...")
            
            # 获取所有需要生成摘要的阶段
            stages_to_process = await self._get_stages_need_summary()
            
            if not stages_to_process:
                self.logger.info("没有需要生成摘要的生命阶段")
                return
            
            self.logger.info(f"找到 {len(stages_to_process)} 个需要生成摘要的生命阶段")
            
            success_count = 0
            for stage_info in stages_to_process:
                success = await self._generate_stage_summary(stage_info)
                if success:
                    success_count += 1
                    self.logger.info(f"✅ 生命阶段摘要生成成功: {stage_info['title']}")
                else:
                    self.logger.error(f"❌ 生命阶段摘要生成失败: {stage_info['title']}")
            
            self.logger.info(f"摘要生成完成，成功生成 {success_count}/{len(stages_to_process)} 个摘要")
            
        except Exception as e:
            self.logger.error(f"生成摘要时发生错误: {e}")
            raise
    
    async def _get_stages_need_summary(self) -> List[Dict[str, Any]]:
        """获取所有需要生成摘要的生命阶段"""
        try:
            from mcp_agent.database_config_forlife import get_mysql_session
            from sqlalchemy import text
            
            async with get_mysql_session() as session:
                # 查询所有status为completed且summary为null的阶段，同时获取角色信息
                query_sql = """
                SELECT 
                    ls.life_stage_id,
                    ls.life_period,
                    ls.title,
                    ls.description_for_plot_llm,
                    ls.stage_goals,
                    rd.role_name,
                    rd.age,
                    rd.L0_prompt_path
                FROM life_stages ls
                JOIN life_plot_outlines lpo ON ls.outline_id = lpo.outline_id
                JOIN role_details rd ON lpo.role_id = rd.role_id
                WHERE ls.status = 'completed' AND (ls.summary IS NULL OR ls.summary = '')
                ORDER BY rd.role_name, ls.sequence_order
                """
                
                result = await session.execute(text(query_sql))
                rows = result.fetchall()
                
                stages_info = []
                for row in rows:
                    stages_info.append({
                        'life_stage_id': row.life_stage_id,
                        'life_period': row.life_period,
                        'title': row.title,
                        'description_for_plot_llm': row.description_for_plot_llm,
                        'stage_goals': row.stage_goals,
                        'role_name': row.role_name,
                        'age': row.age,
                        'L0_prompt_path': row.L0_prompt_path
                    })
                
                return stages_info
                
        except Exception as e:
            self.logger.error(f"获取需要生成摘要的阶段失败: {e}")
            return []
    
    async def _generate_stage_summary(self, stage_info: Dict[str, Any]) -> bool:
        """为指定阶段生成摘要"""
        try:
            # 1. 获取L0_prompt内容
            l0_prompt_content = await self._load_l0_prompt_content(stage_info['L0_prompt_path'])
            
            # 2. 构建生成摘要的提示词
            prompt = self._build_summary_generation_prompt(stage_info, l0_prompt_content)
            
            # 3. 调用LLM生成摘要
            summary = await self._generate_summary_with_llm(prompt)
            if not summary:
                return False
            
            # 4. 更新数据库
            success = await self._update_stage_summary(stage_info['life_stage_id'], summary)
            return success
            
        except Exception as e:
            self.logger.error(f"生成阶段摘要失败: {e}")
            return False
    
    async def _load_l0_prompt_content(self, l0_prompt_path: str) -> str:
        """加载L0提示词内容"""
        try:
            # 构建完整路径
            if l0_prompt_path.startswith('/'):
                file_path = Path(l0_prompt_path)
            else:
                file_path = Path.cwd() / l0_prompt_path
            
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return content.strip()
            else:
                self.logger.warning(f"L0提示词文件不存在: {file_path}")
                return "文件不存在"
                
        except Exception as e:
            self.logger.error(f"加载L0提示词失败: {e}")
            return "加载失败"
    
    def _build_summary_generation_prompt(self, stage_info: Dict[str, Any], l0_prompt_content: str) -> str:
        """构建生成摘要的提示词"""
        
        prompt = f"""你是一个专业的人物传记作家，需要为角色的人生阶段生成一个精炼而深刻的摘要。

**角色基本信息：**
- 角色名称：{stage_info['role_name']}
- 当前年龄：{stage_info['age']}岁
- 角色背景：{l0_prompt_content[:LifeStageUpdaterConfig.MAX_L0_PROMPT_LENGTH]}...

**人生阶段信息：**
- 阶段时期：{stage_info['life_period']}
- 阶段标题：{stage_info['title']}
- 阶段描述：{stage_info['description_for_plot_llm']}
- 阶段目标：{stage_info['stage_goals']}

**任务要求：**
请为这个已经完成的人生阶段写一个深刻而精炼的摘要，要求：

1. **时间背景**：简要说明这个阶段发生的时间和大环境
2. **核心经历**：概述在这个阶段角色的主要经历和重要事件
3. **成长收获**：描述角色在这个阶段的主要成长和收获
4. **影响意义**：说明这个阶段对角色后续人生的影响和意义
5. **情感基调**：体现这个阶段的整体情感色彩和心路历程

**写作要求：**
- 以第三人称视角描述
- 语言要有文学性和感染力
- 字数控制在200-300字
- 要体现角色的个性特点
- 突出这个阶段的独特价值
- 与角色的整体人生轨迹保持一致

**输出格式：**
直接返回摘要内容，不需要其他格式标记。

请开始生成这个人生阶段的摘要："""

        return prompt
    
    async def _generate_summary_with_llm(self, prompt: str) -> Optional[str]:
        """使用LLM生成摘要"""
        max_retries = LifeStageUpdaterConfig.MAX_RETRIES
        retry_delay = LifeStageUpdaterConfig.INITIAL_RETRY_DELAY
        
        for attempt in range(max_retries):
            try:
                self.logger.debug(f"正在调用Gemini API生成摘要... (尝试 {attempt + 1}/{max_retries})")
                
                # 调用Gemini API
                response = self.model.generate_content(prompt)
                summary = response.text.strip()
                
                if summary:
                    self.logger.debug(f"生成摘要长度: {len(summary)} 字符")
                    return summary
                else:
                    self.logger.error("LLM返回空摘要")
                    if attempt < max_retries - 1:
                        self.logger.info(f"等待 {retry_delay} 秒后重试...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                        
            except Exception as e:
                self.logger.error(f"LLM生成摘要失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    self.logger.info(f"等待 {retry_delay} 秒后重试...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                    
        self.logger.error("所有重试尝试都失败了")
        return None
    
    async def _update_stage_summary(self, life_stage_id: str, summary: str) -> bool:
        """更新生命阶段的摘要"""
        try:
            from mcp_agent.database_config_forlife import get_mysql_session
            from sqlalchemy import text
            
            async with get_mysql_session() as session:
                update_sql = """
                UPDATE life_stages 
                SET summary = :summary 
                WHERE life_stage_id = :life_stage_id
                """
                
                result = await session.execute(text(update_sql), {
                    'summary': summary,
                    'life_stage_id': life_stage_id
                })
                await session.commit()
                
                return result.rowcount > 0
                
        except Exception as e:
            self.logger.error(f"更新摘要失败: {e}")
            return False

    async def generate_past_experience_summaries(self):
        """为所有角色生成过往经历总结并存储到文件"""
        try:
            self.logger.info("开始生成角色过往经历总结...")
            
            # 获取所有有已完成阶段的角色
            roles_with_completed_stages = await self._get_roles_with_completed_stages()
            
            if not roles_with_completed_stages:
                self.logger.info("没有找到有已完成阶段的角色")
                return
            
            self.logger.info(f"找到 {len(roles_with_completed_stages)} 个角色需要生成过往经历总结")
            
            success_count = 0
            for role_name, stages in roles_with_completed_stages.items():
                success = await self._generate_role_past_experience_summary(role_name, stages)
                if success:
                    success_count += 1
                    self.logger.info(f"✅ 角色 {role_name} 过往经历总结生成成功")
                else:
                    self.logger.error(f"❌ 角色 {role_name} 过往经历总结生成失败")
            
            self.logger.info(f"过往经历总结生成完成，成功生成 {success_count}/{len(roles_with_completed_stages)} 个总结")
            
        except Exception as e:
            self.logger.error(f"生成过往经历总结时发生错误: {e}")
            raise
    
    async def _get_roles_with_completed_stages(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取所有有已完成阶段的角色及其阶段信息"""
        try:
            from mcp_agent.database_config_forlife import get_mysql_session
            from sqlalchemy import text
            
            async with get_mysql_session() as session:
                # 查询所有status为completed且有summary的阶段
                query_sql = """
                SELECT 
                    rd.role_name,
                    ls.life_period,
                    ls.title,
                    ls.stage_goals,
                    ls.summary
                FROM life_stages ls
                JOIN life_plot_outlines lpo ON ls.outline_id = lpo.outline_id
                JOIN role_details rd ON lpo.role_id = rd.role_id
                WHERE ls.status = 'completed' AND ls.summary IS NOT NULL AND ls.summary != ''
                ORDER BY rd.role_name, ls.sequence_order
                """
                
                result = await session.execute(text(query_sql))
                rows = result.fetchall()
                
                # 按角色分组
                roles_stages = {}
                for row in rows:
                    role_name = row.role_name
                    if role_name not in roles_stages:
                        roles_stages[role_name] = []
                    
                    roles_stages[role_name].append({
                        'life_period': row.life_period,
                        'title': row.title,
                        'stage_goals': row.stage_goals,
                        'summary': row.summary
                    })
                
                return roles_stages
                
        except Exception as e:
            self.logger.error(f"获取角色已完成阶段失败: {e}")
            return {}
    
    async def _generate_role_past_experience_summary(self, role_name: str, stages: List[Dict[str, Any]]) -> bool:
        """为特定角色生成过往经历总结并保存到文件"""
        try:
            # 0. 获取role_id
            role_id = await self._get_role_id_by_name(role_name)
            if not role_id:
                self.logger.error(f"无法获取角色 {role_name} 的role_id")
                return False
            
            # 1. 检查文件是否已存在
            summaries_dir = Path(LifeStageUpdaterConfig.PAST_EXPERIENCE_BASE_DIR) / role_id
            file_path = summaries_dir / f"{role_name}_summary.txt"
            
            if file_path.exists():
                self.logger.info(f"⏭️ 角色 {role_name} 的过往经历总结文件已存在，跳过生成")
                return True
            
            # 2. 构建过往经历总结的提示词
            prompt = self._build_past_experience_prompt(role_name, stages)
            
            # 3. 调用LLM生成过往经历总结
            past_summary = await self._generate_past_experience_with_llm(prompt)
            if not past_summary:
                return False
            
            # 4. 保存到文件
            success = await self._save_past_experience_summary(role_id, role_name, past_summary)
            return success
            
        except Exception as e:
            self.logger.error(f"生成角色 {role_name} 过往经历总结失败: {e}")
            return False
    
    def _build_past_experience_prompt(self, role_name: str, stages: List[Dict[str, Any]]) -> str:
        """构建过往经历总结的提示词"""
        
        # 构建阶段信息
        stages_info = []
        for i, stage in enumerate(stages, 1):
            stage_text = f"""
{i}. 【{stage['life_period']}】{stage['title']}
   阶段目标：{stage['stage_goals']}
   阶段总结：{stage['summary']}
"""
            stages_info.append(stage_text)
        
        stages_content = "\n".join(stages_info)
        
        prompt = f"""你是一个专业的人物传记编撰者，需要基于角色的各个人生阶段信息，生成一个简洁而全面的过往经历总结。

**角色信息：**
角色名称：{role_name}

**已完成的人生阶段：**
{stages_content}

**任务要求：**
请基于以上各个人生阶段的信息，为{role_name}编写一个过往经历总结，要求：

1. **整体概述**：简要概括角色的整个成长轨迹和核心特征
2. **关键转折**：突出各个阶段的重要转折点和成长节点
3. **性格塑造**：体现角色在不同阶段的性格发展和特质形成
4. **能力建构**：说明角色通过各阶段积累的核心能力和经验
5. **价值观念**：反映角色价值观念的形成和演变过程

**写作要求：**
- 以第三人称视角描述
- 语言简洁而有力度
- 字数严格控制在300字以内
- 逻辑清晰，层次分明
- 突出角色的个人特色
- 体现各阶段间的连贯性和递进关系

**输出格式：**
直接返回过往经历总结内容，不需要任何标题或格式标记。

请开始生成{role_name}的过往经历总结："""

        return prompt
    
    async def _generate_past_experience_with_llm(self, prompt: str) -> Optional[str]:
        """使用LLM生成过往经历总结"""
        max_retries = LifeStageUpdaterConfig.MAX_RETRIES
        retry_delay = LifeStageUpdaterConfig.INITIAL_RETRY_DELAY
        
        for attempt in range(max_retries):
            try:
                self.logger.debug(f"正在调用Gemini API生成过往经历总结... (尝试 {attempt + 1}/{max_retries})")
                
                # 调用Gemini API
                response = self.model.generate_content(prompt)
                past_summary = response.text.strip()
                
                if past_summary:
                    self.logger.debug(f"生成过往经历总结长度: {len(past_summary)} 字符")
                    return past_summary
                else:
                    self.logger.error("LLM返回空的过往经历总结")
                    if attempt < max_retries - 1:
                        self.logger.info(f"等待 {retry_delay} 秒后重试...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                        
            except Exception as e:
                self.logger.error(f"LLM生成过往经历总结失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    self.logger.info(f"等待 {retry_delay} 秒后重试...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                    
        self.logger.error("所有重试尝试都失败了")
        return None
    
    async def _save_past_experience_summary(self, role_id: str, role_name: str, past_summary: str) -> bool:
        """保存过往经历总结到文件"""
        try:
            # 创建过往经历总结目录
            summaries_dir = Path(LifeStageUpdaterConfig.PAST_EXPERIENCE_BASE_DIR) / role_id
            summaries_dir.mkdir(exist_ok=True)
            
            # 文件路径
            file_path = summaries_dir / f"{role_name}_summary.txt"
            
            # 生成文件内容
            content = f"""# {role_name} - 过往经历总结

## 生成时间
{self._get_current_time()}

## 过往经历总结
{past_summary}
"""
            
            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.logger.info(f"✅ 过往经历总结已保存到: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存过往经历总结失败: {e}")
            return False
    
    def _get_current_time(self) -> str:
        """获取当前时间字符串"""
        from datetime import datetime
        return datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")

    async def generate_plot_segments_for_active_stages(self):
        """为所有状态为active的生命阶段生成剧情片段"""
        try:
            self.logger.info("开始为活跃生命阶段生成剧情片段...")
            
            # 获取所有状态为active的生命阶段
            active_stages = await self._get_active_life_stages()
            
            if not active_stages:
                self.logger.info("没有找到状态为active的生命阶段")
                return
            
            self.logger.info(f"找到 {len(active_stages)} 个活跃生命阶段需要生成剧情片段")
            
            success_count = 0
            for stage_info in active_stages:
                success = await self._generate_plot_segments_for_stage(stage_info)
                if success:
                    success_count += 1
                    self.logger.info(f"✅ 生命阶段 {stage_info['title']} 剧情片段生成成功")
                else:
                    self.logger.error(f"❌ 生命阶段 {stage_info['title']} 剧情片段生成失败")
            
            self.logger.info(f"剧情片段生成完成，成功生成 {success_count}/{len(active_stages)} 个阶段的剧情片段")
            
        except Exception as e:
            self.logger.error(f"生成剧情片段时发生错误: {e}")
            raise
    
    async def generate_daily_plots_for_active_segments(self):
        """为所有状态为active的剧情片段生成具体日常剧情（带解锁逻辑）"""
        try:
            self.logger.info("🔓 开始剧情解锁逻辑检查...")
            
            # 1. 获取当前北京时间和最大剧情日期
            current_beijing_time = self._get_beijing_time()
            max_plot_date = await self._get_max_plot_date()
            
            self.logger.info(f"📅 当前北京时间: {current_beijing_time}")
            self.logger.info(f"📅 最大剧情日期: {max_plot_date or '无'}")
            
            # 2. 判断是否需要解锁新剧情
            if max_plot_date and current_beijing_time > max_plot_date:
                self.logger.info("🔓 当前时间大于最大剧情日期，开始解锁新剧情...")
                
                # 2.1 清除剧情文件和数据
                clear_success = await self._clear_plot_files_and_data()
                if not clear_success:
                    self.logger.error("❌ 清除剧情数据失败")
                    return
                
                # 2.2 推进剧情片段状态
                advance_success = await self._advance_plot_segment_status()
                if not advance_success:
                    self.logger.error("❌ 推进剧情片段状态失败")
                    return
                
                self.logger.info("✅ 剧情解锁完成，开始生成新剧情...")
                
            elif max_plot_date and current_beijing_time <= max_plot_date:
                self.logger.info("⏸️ 当前时间未超过最大剧情日期，执行默认程序...")
            else:
                self.logger.info("🆕 没有现有剧情记录，开始首次生成...")
            
            # 3. 执行剧情生成（原有逻辑）
            self.logger.info("📅 开始为活跃剧情片段生成具体日常剧情...")
            
            # 获取所有状态为active的剧情片段
            active_segments = await self._get_active_plot_segments()
            
            if not active_segments:
                self.logger.info("没有找到状态为active的剧情片段")
                return
            
            self.logger.info(f"找到 {len(active_segments)} 个活跃剧情片段需要生成具体日常剧情")
            
            success_count = 0
            for segment_info in active_segments:
                success = await self._generate_daily_plots_for_segment(segment_info)
                if success:
                    success_count += 1
                    self.logger.info(f"✅ 剧情片段 {segment_info['title']} 日常剧情生成成功")
                else:
                    self.logger.error(f"❌ 剧情片段 {segment_info['title']} 日常剧情生成失败")
            
            self.logger.info(f"日常剧情生成完成，成功生成 {success_count}/{len(active_segments)} 个片段的日常剧情")
            
        except Exception as e:
            self.logger.error(f"生成日常剧情时发生错误: {e}")
            raise
    
    async def _get_active_life_stages(self) -> List[Dict[str, Any]]:
        """获取所有状态为active的生命阶段"""
        try:
            from mcp_agent.database_config_forlife import get_mysql_session
            from sqlalchemy import text
            
            async with get_mysql_session() as session:
                # 查询所有status为active的阶段，同时获取角色信息
                query_sql = """
                SELECT 
                    ls.life_stage_id,
                    ls.life_period,
                    ls.title,
                    ls.description_for_plot_llm,
                    ls.stage_goals,
                    rd.role_name,
                    rd.age,
                    rd.L0_prompt_path
                FROM life_stages ls
                JOIN life_plot_outlines lpo ON ls.outline_id = lpo.outline_id
                JOIN role_details rd ON lpo.role_id = rd.role_id
                WHERE ls.status = 'active'
                ORDER BY rd.role_name, ls.sequence_order
                """
                
                result = await session.execute(text(query_sql))
                rows = result.fetchall()
                
                stages_info = []
                for row in rows:
                    stages_info.append({
                        'life_stage_id': row.life_stage_id,
                        'life_period': row.life_period,
                        'title': row.title,
                        'description_for_plot_llm': row.description_for_plot_llm,
                        'stage_goals': row.stage_goals,
                        'role_name': row.role_name,
                        'age': row.age,
                        'L0_prompt_path': row.L0_prompt_path
                    })
                
                return stages_info
                
        except Exception as e:
            self.logger.error(f"获取活跃生命阶段失败: {e}")
            return []
    
    async def _generate_plot_segments_for_stage(self, stage_info: Dict[str, Any]) -> bool:
        """为指定生命阶段生成剧情片段"""
        try:
            # 1. 检查是否已有剧情片段
            existing_segments = await character_life_manager.get_plot_segments_by_stage(stage_info['life_stage_id'])
            if existing_segments:
                self.logger.info(f"生命阶段 {stage_info['title']} 已有 {len(existing_segments)} 个剧情片段，跳过生成")
                # 更新现有片段状态
                await self._update_segments_status_by_age(stage_info['life_stage_id'], stage_info['age'])
                return True
            
            # 2. 获取L0_prompt内容
            l0_prompt_content = await self._load_l0_prompt_content(stage_info['L0_prompt_path'])
            
            # 3. 获取过往经历总结
            past_experience = await self._load_past_experience_summary(stage_info['role_name'])
            
            # 4. 构建剧情片段生成的提示词
            prompt = self._build_plot_segment_generation_prompt(stage_info, l0_prompt_content, past_experience)
            
            # 5. 调用LLM生成剧情片段
            segments_data = await self._generate_plot_segments_with_llm(prompt)
            if not segments_data:
                return False
            
            # 6. 处理和存储生成的剧情片段
            success = await self._process_and_store_plot_segments(stage_info, segments_data)
            
            return success
            
        except Exception as e:
            self.logger.error(f"生成阶段剧情片段失败: {e}")
            return False
    
    async def _load_past_experience_summary(self, role_name: str) -> str:
        """加载角色过往经历总结"""
        try:
            # 获取role_id
            role_id = await self._get_role_id_by_name(role_name)
            if not role_id:
                self.logger.warning(f"无法获取角色 {role_name} 的role_id")
                return "暂无过往经历总结"
            
            # 构建过往经历总结文件路径
            summaries_dir = Path(LifeStageUpdaterConfig.PAST_EXPERIENCE_BASE_DIR) / role_id
            file_path = summaries_dir / f"{role_name}_summary.txt"
            
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 提取过往经历总结部分
                lines = content.split('\n')
                summary_start = False
                summary_lines = []
                
                for line in lines:
                    if line.strip() == "## 过往经历总结":
                        summary_start = True
                        continue
                    elif line.strip().startswith("---") or line.strip().startswith("#") and summary_start:
                        break
                    elif summary_start and line.strip():
                        summary_lines.append(line.strip())
                
                return '\n'.join(summary_lines)
            else:
                self.logger.warning(f"过往经历总结文件不存在: {file_path}")
                return "暂无过往经历总结"
                
        except Exception as e:
            self.logger.error(f"加载过往经历总结失败: {e}")
            return "加载失败"
    
    def _build_plot_segment_generation_prompt(self, stage_info: Dict[str, Any], l0_prompt_content: str, past_experience: str) -> str:
        """构建剧情片段生成的提示词"""
        
        prompt = f"""你是一个专业的剧情设计师，需要为角色的当前人生阶段设计具体的剧情片段。

**角色基本信息：**
- 角色名称：{stage_info['role_name']}
- 当前年龄：{stage_info['age']}岁
- 角色背景：{l0_prompt_content[:LifeStageUpdaterConfig.MAX_L0_PROMPT_LENGTH]}...

**过往经历总结：**
{past_experience}

**当前人生阶段信息：**
- 阶段时期：{stage_info['life_period']}
- 阶段标题：{stage_info['title']}
- 阶段描述：{stage_info['description_for_plot_llm']}
- 阶段目标：{stage_info['stage_goals']}

**任务要求：**
请为这个正在经历的人生阶段设计4-6个具体的剧情片段，每个片段要求：

1. **sequence_order_in_stage**: 片段在阶段中的顺序 (从1开始递增)
2. **title**: 片段标题，要具体生动 (如："准备重要的考试"、"负责重要的项目"、"gap半年去旅行")
3. **life_age**: 经历这个事件时的年龄 (基于阶段时期合理分配，可以是同一年龄的不同事件)
4. **segment_prompt_for_plot_llm**: 核心内容描述，这是传递给详细剧情生成LLM的主要输入，需要描述：
   - 片段的核心事件和情境
   - 主要参与人物和关系
   - 期望的发展方向和可能的冲突点
   - 不要包含后续未解锁片段的信息
5. **duration_in_days_estimate**: 预估剧情天数 (1-30天，考虑事件复杂度)
6. **expected_emotional_arc**: 情感起伏描述 (如："初期紧张焦虑 -> 过程中努力奋斗 -> 结果揭晓时的成就感或失落")
7. **key_npcs_involved**: 涉及的关键NPC及其角色 (同事、朋友、家人等)
8. **is_milestone_event**: 是否为重大转折点 (true/false，影响记忆重要性)

**设计原则：**
- 片段要符合角色的年龄特征和社会背景
- 要与角色的过往经历和性格特点保持一致
- 各片段间要有逻辑连贯性，体现成长进程
- 要包含不同类型的事件（工作、学习、生活、社交等）
- 重大转折点要合理分布，不宜过多
- 考虑中国社会文化背景和时代特色

**输出格式：**
请严格按照JSON格式返回，示例：
```json
{{
  "plot_segments": [
    {{
      "sequence_order_in_stage": 1,
      "title": "片段标题",
      "life_age": 28,
      "segment_prompt_for_plot_llm": "详细的片段描述...",
      "duration_in_days_estimate": 7,
      "expected_emotional_arc": "情感变化描述...",
      "key_npcs_involved": "NPC描述...",
      "is_milestone_event": false
    }}
  ]
}}
```

请开始为{stage_info['role_name']}的"{stage_info['title']}"阶段设计剧情片段："""

        return prompt
    
    async def _generate_plot_segments_with_llm(self, prompt: str) -> Optional[Dict[str, Any]]:
        """使用LLM生成剧情片段数据"""
        try:
            self.logger.debug("正在调用Gemini API生成剧情片段...")
            
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
                self.logger.info(f"成功解析JSON，包含 {len(data.get('plot_segments', []))} 个剧情片段")
                return data
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON解析失败: {e}")
                self.logger.debug(f"原始响应: {response_text}")
                return None
                
        except Exception as e:
            self.logger.error(f"LLM生成剧情片段失败: {e}")
            return None
    
    async def _process_and_store_plot_segments(self, stage_info: Dict[str, Any], segments_data: Dict[str, Any]) -> bool:
        """处理和存储生成的剧情片段数据"""
        try:
            from character_life_system.models import PlotSegmentData, SegmentStatusEnum
            import uuid
            
            segments = segments_data.get('plot_segments', [])
            success_count = 0
            
            for segment in segments:
                try:
                    # 验证必需字段
                    required_fields = ['sequence_order_in_stage', 'title', 'life_age', 'segment_prompt_for_plot_llm', 
                                     'duration_in_days_estimate', 'expected_emotional_arc', 'key_npcs_involved', 'is_milestone_event']
                    if not all(field in segment for field in required_fields):
                        self.logger.warning(f"跳过不完整的片段数据: {segment}")
                        continue
                    
                    # 创建PlotSegmentData对象
                    segment_data = PlotSegmentData(
                        plot_segment_id=str(uuid.uuid4()),
                        life_stage_id=stage_info['life_stage_id'],
                        sequence_order_in_stage=int(segment['sequence_order_in_stage']),
                        title=segment['title'],
                        life_age=int(segment['life_age']),
                        segment_prompt_for_plot_llm=segment['segment_prompt_for_plot_llm'],
                        duration_in_days_estimate=int(segment['duration_in_days_estimate']),
                        expected_emotional_arc=segment['expected_emotional_arc'],
                        key_npcs_involved=segment['key_npcs_involved'],
                        status=SegmentStatusEnum.LOCKED,  # 默认为锁定状态
                        is_milestone_event=bool(segment['is_milestone_event'])
                    )
                    
                    # 存储到数据库
                    if await character_life_manager.create_plot_segment(segment_data):
                        success_count += 1
                        self.logger.debug(f"✅ 剧情片段创建成功: {segment_data.title}")
                    else:
                        self.logger.error(f"❌ 剧情片段创建失败: {segment_data.title}")
                
                except Exception as e:
                    self.logger.error(f"处理片段数据时出错: {e}, 数据: {segment}")
                    continue
            
            if success_count > 0:
                # 根据年龄更新片段状态
                await self._update_segments_status_by_age(stage_info['life_stage_id'], stage_info['age'])
                
            self.logger.info(f"成功创建 {success_count}/{len(segments)} 个剧情片段")
            return success_count > 0
            
        except Exception as e:
            self.logger.error(f"处理和存储剧情片段失败: {e}")
            return False
    
    async def _update_segments_status_by_age(self, life_stage_id: str, current_age: int):
        """根据年龄更新剧情片段状态"""
        try:
            success = await character_life_manager.update_plot_segments_status_by_age(life_stage_id, current_age)
            if success:
                self.logger.debug(f"✅ 剧情片段状态更新成功: life_stage_id={life_stage_id}, age={current_age}")
            else:
                self.logger.warning(f"⚠️ 剧情片段状态更新失败: life_stage_id={life_stage_id}, age={current_age}")
        except Exception as e:
            self.logger.error(f"更新剧情片段状态失败: {e}")

    async def _get_active_plot_segments(self) -> List[Dict[str, Any]]:
        """获取所有状态为active的剧情片段及其相关信息"""
        try:
            from mcp_agent.database_config_forlife import get_mysql_session
            from sqlalchemy import text
            
            async with get_mysql_session() as session:
                # 查询所有status为active的剧情片段，同时获取角色信息
                query_sql = """
                SELECT 
                    ps.plot_segment_id,
                    ps.life_stage_id,
                    ps.sequence_order_in_stage,
                    ps.title,
                    ps.life_age,
                    ps.segment_prompt_for_plot_llm,
                    ps.duration_in_days_estimate,
                    ps.expected_emotional_arc,
                    ps.key_npcs_involved,
                    rd.role_name,
                    rd.age,
                    rd.L0_prompt_path
                FROM plot_segments ps
                JOIN life_stages ls ON ps.life_stage_id = ls.life_stage_id
                JOIN life_plot_outlines lpo ON ls.outline_id = lpo.outline_id
                JOIN role_details rd ON lpo.role_id = rd.role_id
                WHERE ps.status = 'active'
                ORDER BY rd.role_name, ps.sequence_order_in_stage
                """
                
                result = await session.execute(text(query_sql))
                rows = result.fetchall()
                
                segments_info = []
                for row in rows:
                    segments_info.append({
                        'plot_segment_id': row.plot_segment_id,
                        'life_stage_id': row.life_stage_id,
                        'sequence_order_in_stage': row.sequence_order_in_stage,
                        'title': row.title,
                        'life_age': row.life_age,
                        'segment_prompt_for_plot_llm': row.segment_prompt_for_plot_llm,
                        'duration_in_days_estimate': row.duration_in_days_estimate,
                        'expected_emotional_arc': row.expected_emotional_arc,
                        'key_npcs_involved': row.key_npcs_involved,
                        'role_name': row.role_name,
                        'age': row.age,
                        'L0_prompt_path': row.L0_prompt_path
                    })
                
                return segments_info
                
        except Exception as e:
            self.logger.error(f"获取活跃剧情片段失败: {e}")
            return []

    def _get_current_date(self) -> str:
        """获取当前日期字符串"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")

    def _calculate_plot_date(self, base_date: str, days_offset: int) -> str:
        """计算剧情日期"""
        try:
            from datetime import datetime, timedelta
            base_dt = datetime.strptime(base_date, "%Y-%m-%d")
            target_dt = base_dt + timedelta(days=days_offset)
            return target_dt.strftime("%Y-%m-%d")
        except Exception as e:
            self.logger.error(f"计算日期失败: {e}")
            return base_date

    async def _generate_daily_plots_for_segment(self, segment_info: Dict[str, Any]) -> bool:
        """为指定剧情片段生成具体日常剧情"""
        try:
            # 1. 检查是否已有具体剧情
            existing_plots = await character_life_manager.get_specific_plots_by_segment(segment_info['plot_segment_id'])
            if existing_plots:
                self.logger.info(f"剧情片段 {segment_info['title']} 已有 {len(existing_plots)} 个具体剧情，跳过生成")
                return True
            
            # 2. 获取历史经历事件（同一life_stage_id下status为completed的剧情片段）
            historical_events = await self._get_historical_events(segment_info['life_stage_id'])
            
            # 3. 获取L0_prompt内容
            l0_prompt_content = await self._load_l0_prompt_content(segment_info['L0_prompt_path'])
            
            # 4. 获取过往经历总结
            past_experience = await self._load_past_experience_summary(segment_info['role_name'])
            
            # 5. 循环生成每一天的剧情
            duration_days = segment_info['duration_in_days_estimate']
            base_date = self._get_current_date()  # 使用当前日期作为基准
            
            # 存储上一天的摘要和心情，用于下一天的生成
            previous_summary = ""
            previous_mood = ""
            
            for day in range(1, duration_days + 1):
                success = await self._generate_single_day_plot(
                    segment_info, historical_events, l0_prompt_content, 
                    past_experience, day, base_date, previous_summary, previous_mood
                )
                
                if success:
                    # 获取刚生成的当天摘要和心情，用于下一天
                    daily_plot_data = await self._get_latest_daily_plot_data(segment_info['plot_segment_id'], day)
                    if daily_plot_data:
                        previous_summary = daily_plot_data.get('summary', '')
                        previous_mood = daily_plot_data.get('mood_text', '')
                    
                    self.logger.debug(f"✅ 第{day}天剧情生成成功")
                else:
                    self.logger.error(f"❌ 第{day}天剧情生成失败")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"生成剧情片段日常剧情失败: {e}")
            return False

    async def _get_historical_events(self, life_stage_id: str) -> List[Dict[str, Any]]:
        """获取历史经历事件（同一life_stage_id下status为completed的剧情片段）"""
        try:
            from mcp_agent.database_config_forlife import get_mysql_session
            from sqlalchemy import text
            
            async with get_mysql_session() as session:
                query_sql = """
                SELECT 
                    sequence_order_in_stage,
                    life_age,
                    segment_prompt_for_plot_llm,
                    key_npcs_involved
                FROM plot_segments 
                WHERE life_stage_id = :life_stage_id AND status = 'completed'
                ORDER BY sequence_order_in_stage ASC
                """
                
                result = await session.execute(text(query_sql), {"life_stage_id": life_stage_id})
                rows = result.fetchall()
                
                historical_events = []
                for row in rows:
                    historical_events.append({
                        'sequence_order_in_stage': row.sequence_order_in_stage,
                        'life_age': row.life_age,
                        'segment_prompt_for_plot_llm': row.segment_prompt_for_plot_llm,
                        'key_npcs_involved': row.key_npcs_involved
                    })
                
                return historical_events
                
        except Exception as e:
            self.logger.error(f"获取历史经历事件失败: {e}")
            return []

    async def _generate_single_day_plot(self, segment_info: Dict[str, Any], historical_events: List[Dict[str, Any]], 
                                       l0_prompt_content: str, past_experience: str, day: int, base_date: str, 
                                       previous_summary: str, previous_mood: str) -> bool:
        """生成单日的具体剧情"""
        try:
            # 1. 构建详细的prompt
            detailed_prompt = self._build_daily_plot_prompt(
                segment_info, historical_events, l0_prompt_content, past_experience, 
                day, base_date, previous_summary, previous_mood
            )
            
            # 2. 调用LLM生成日常剧情
            daily_plot_content = await self._generate_daily_plot_with_llm(detailed_prompt)
            if not daily_plot_content:
                return False
            
            # 3. 解析LLM生成的内容，提取摘要和心情
            parsed_content = self._parse_daily_plot_content(daily_plot_content)
            
            # 4. 计算日期
            plot_date = self._calculate_plot_date(base_date, day - 1)
            
            # 5. 获取role_id
            role_id = await self._get_role_id_by_name(segment_info['role_name'])
            if not role_id:
                self.logger.error(f"无法获取角色 {segment_info['role_name']} 的role_id")
                return False
            
            # 6. 保存情景prompt到文件
            plot_content_path = await self._save_daily_plot_to_file(
                segment_info['role_name'], segment_info['title'], day, daily_plot_content, 
                role_id, plot_date
            )
            
            # 7. 存储到具体剧情表
            success = await self._save_daily_plot_to_database(
                segment_info['plot_segment_id'], day, plot_date, 
                plot_content_path, parsed_content['mood']
            )
            
            return success
            
        except Exception as e:
            self.logger.error(f"生成单日剧情失败: {e}")
            return False

    def _build_daily_plot_prompt(self, segment_info: Dict[str, Any], historical_events: List[Dict[str, Any]], 
                               l0_prompt_content: str, past_experience: str, day: int, base_date: str, 
                               previous_summary: str, previous_mood: str) -> str:
        """构建日常剧情生成的详细prompt"""
        
        # 构建历史经历事件描述
        historical_prompt = ""
        if historical_events:
            historical_prompt = "**已经历的事件：**\n"
            for i, event in enumerate(historical_events, 1):
                historical_prompt += f"{i}. 【{event['life_age']}岁】顺序{event['sequence_order_in_stage']}\n"
                historical_prompt += f"   事件描述：{event['segment_prompt_for_plot_llm']}\n"
                historical_prompt += f"   涉及人物：{event['key_npcs_involved']}\n\n"
        else:
            historical_prompt = "**已经历的事件：** 暂无\n\n"
        
        # 构建当前要经历的事件描述
        current_event_prompt = f"""**当前要经历的事件：**
- 事件顺序：第{segment_info['sequence_order_in_stage']}个
- 事件标题：{segment_info['title']}
- 角色年龄：{segment_info['life_age']}岁
- 事件描述：{segment_info['segment_prompt_for_plot_llm']}
- 持续天数：{segment_info['duration_in_days_estimate']}天
- 情感起伏：{segment_info['expected_emotional_arc']}
- 涉及人物：{segment_info['key_npcs_involved']}"""
        
        # 构建上一天的情况（如果存在）
        previous_context = ""
        if day > 1 and (previous_summary or previous_mood):
            previous_context = f"""
**昨天的情况回顾：**
- 昨天摘要：{previous_summary}
- 昨天心情：{previous_mood}
"""
        
        # 计算当前日期
        current_date = self._calculate_plot_date(base_date, day - 1)
        
        prompt = f"""你是一个专业的剧情编剧和演员，需要为我即将饰演的角色生成详细的日常剧情。

**我的基本信息：**
- 我的名称：{segment_info['role_name']}
- 我当前年龄：{segment_info['age']}岁
- 我的背景：{l0_prompt_content[:LifeStageUpdaterConfig.MAX_L0_PROMPT_LENGTH]}...

**过往经历总结：**
{past_experience}

{historical_prompt}

{current_event_prompt}

{previous_context}

**当前任务：**
请为我生成第{day}天的详细日常剧情，日期为{current_date}。

**要求：**
1. 严格按照时间段、事件、人物情绪的结构输出
2. 同一时间段的内容放置在同一行内
3. 时间段要合理，涵盖一整天的全部活动(包含吃饭睡觉工作娱乐生活)
4. 事件要与当前要经历的事件主题相关
5. 人物情绪要符合情感起伏的设定
6. 严禁出现任何与当前要经历的事件无关的内容，比如：`好的，陈小智的第1天剧情如下：`

**输出格式：**
## 第{day}天
## 日期:{current_date}

8:30-10:00 [具体事件内容]，心情平静地开始新的一天
10:00-12:00 [具体事件内容]，感到[具体情绪]
12:00-13:00 [具体事件内容]，表现出[具体情绪]
...（继续一整天的安排）

摘要：今天我{segment_info['role_name']}[简要描述主要事件和体验]
人物心情：[详细描述当天的整体情绪状态和变化]

请开始生成第{day}天的详细剧情："""

        return prompt

    def _calculate_plot_date(self, base_date: str, days_offset: int) -> str:
        """计算剧情日期"""
        try:
            from datetime import datetime, timedelta
            base_dt = datetime.strptime(base_date, "%Y-%m-%d")
            target_dt = base_dt + timedelta(days=days_offset)
            return target_dt.strftime("%Y-%m-%d")
        except Exception as e:
            self.logger.error(f"计算日期失败: {e}")
            return base_date
    
    async def _generate_daily_plot_with_llm(self, prompt: str) -> Optional[str]:
        """使用LLM生成日常剧情"""
        max_retries = LifeStageUpdaterConfig.MAX_RETRIES
        retry_delay = LifeStageUpdaterConfig.INITIAL_RETRY_DELAY
        
        for attempt in range(max_retries):
            try:
                self.logger.debug(f"正在调用Gemini API生成日常剧情... (尝试 {attempt + 1}/{max_retries})")
                
                # 调用Gemini API
                response = self.model.generate_content(prompt)
                daily_plot = response.text.strip()
                
                if daily_plot:
                    self.logger.debug(f"生成日常剧情长度: {len(daily_plot)} 字符")
                    return daily_plot
                else:
                    self.logger.error("LLM返回空的日常剧情")
                    if attempt < max_retries - 1:
                        self.logger.info(f"等待 {retry_delay} 秒后重试...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                        
            except Exception as e:
                self.logger.error(f"LLM生成日常剧情失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    self.logger.info(f"等待 {retry_delay} 秒后重试...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                    
        self.logger.error("所有重试尝试都失败了")
        return None
    
    def _parse_daily_plot_content(self, content: str) -> Dict[str, Any]:
        """解析日常剧情内容，提取摘要和心情"""
        try:
            lines = content.split('\n')
            summary = ""
            mood_text = ""
            
            for line in lines:
                line = line.strip()
                if line.startswith("摘要："):
                    summary = line[3:].strip()
                elif line.startswith("人物心情："):
                    mood_text = line[5:].strip()
            
            # 构建mood的JSON格式
            mood_json = {
                "mood_text": mood_text,
                "emotional_state": "unknown",  # 可以后续通过分析得出
                "timestamp": self._get_current_time()
            }
            
            return {
                "summary": summary,
                "mood_text": mood_text,
                "mood": mood_json
            }
            
        except Exception as e:
            self.logger.error(f"解析日常剧情内容失败: {e}")
            return {
                "summary": "",
                "mood_text": "",
                "mood": {"mood_text": "", "emotional_state": "unknown", "timestamp": self._get_current_time()}
            }

    async def _save_daily_plot_to_file(self, role_name: str, segment_title: str, day: int, content: str, 
                                      role_id: str, plot_date: str) -> str:
        """保存日常剧情到文件"""
        try:
            # 创建情景剧情存储目录
            plots_dir = Path(LifeStageUpdaterConfig.DAILY_PLOT_BASE_DIR)
            plots_dir.mkdir(exist_ok=True)
            
            # 创建角色剧情子目录：role_id_plot格式
            role_plot_dir = plots_dir / f"{role_id}_plot"
            role_plot_dir.mkdir(exist_ok=True)
            
            # 文件名：日期_title.txt
            safe_title = segment_title.replace("/", "_").replace("\\", "_").replace(":", "_").replace("?", "_")
            filename = f"{plot_date}_{safe_title}.txt"
            file_path = role_plot_dir / filename
            
            # 写入内容
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.logger.debug(f"✅ 日常剧情已保存到: {file_path}")
            return str(file_path)
            
        except Exception as e:
            self.logger.error(f"保存日常剧情文件失败: {e}")
            return ""

    async def _save_daily_plot_to_database(self, plot_segment_id: str, day: int, plot_date: str, 
                                         plot_content_path: str, mood: Dict[str, Any]) -> bool:
        """保存日常剧情到数据库"""
        try:
            from character_life_system.models import SpecificPlotData, PlotStatusEnum
            import uuid
            
            # 创建SpecificPlotData对象
            plot_data = SpecificPlotData(
                plot_id=str(uuid.uuid4()),
                plot_segment_id=plot_segment_id,
                plot_order=day,
                plot_date=plot_date,
                plot_content_path=plot_content_path,
                mood=mood,
                status=PlotStatusEnum.LOCKED  # 默认为锁定状态
            )
            
            # 存储到数据库
            success = await character_life_manager.create_specific_plot(plot_data)
            if success:
                self.logger.debug(f"✅ 日常剧情数据库记录创建成功: 第{day}天")
            else:
                self.logger.error(f"❌ 日常剧情数据库记录创建失败: 第{day}天")
            
            return success
            
        except Exception as e:
            self.logger.error(f"保存日常剧情到数据库失败: {e}")
            return False

    async def _get_latest_daily_plot_data(self, plot_segment_id: str, day: int) -> Optional[Dict[str, Any]]:
        """获取最新生成的日常剧情数据（用于获取摘要和心情）"""
        try:
            # 获取指定片段的所有具体剧情
            plots = await character_life_manager.get_specific_plots_by_segment(plot_segment_id)
            
            # 找到指定天数的剧情
            for plot in plots:
                if plot.plot_order == day:
                    # 读取文件内容并解析
                    if plot.plot_content_path and Path(plot.plot_content_path).exists():
                        with open(plot.plot_content_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        parsed = self._parse_daily_plot_content(content)
                        return {
                            "summary": parsed["summary"],
                            "mood_text": parsed["mood_text"]
                        }
            
            return None
            
        except Exception as e:
            self.logger.error(f"获取最新日常剧情数据失败: {e}")
            return None

    async def _get_role_id_by_name(self, role_name: str) -> Optional[str]:
        """根据角色名称获取role_id"""
        try:
            from mcp_agent.database_config_forlife import get_mysql_session
            from sqlalchemy import text
            
            async with get_mysql_session() as session:
                query_sql = "SELECT role_id FROM role_details WHERE role_name = :role_name"
                result = await session.execute(text(query_sql), {"role_name": role_name})
                row = result.fetchone()
                
                if row:
                    return row.role_id
                else:
                    return None
                    
        except Exception as e:
            self.logger.error(f"获取角色role_id失败: {e}")
            return None

    def _get_beijing_time(self) -> str:
        """获取当前北京时间"""
        try:
            from datetime import datetime, timezone, timedelta
            # 北京时间是UTC+8
            beijing_tz = timezone(timedelta(hours=8))
            beijing_time = datetime.now(beijing_tz)
            return beijing_time.strftime("%Y-%m-%d")
        except Exception as e:
            self.logger.error(f"获取北京时间失败: {e}")
            return datetime.now().strftime("%Y-%m-%d")
    
    async def _get_max_plot_date(self) -> Optional[str]:
        """获取具体剧情表中的最大plot_date"""
        try:
            from mcp_agent.database_config_forlife import get_mysql_session
            from sqlalchemy import text
            
            async with get_mysql_session() as session:
                query_sql = "SELECT MAX(plot_date) as max_date FROM specific_plot"
                result = await session.execute(text(query_sql))
                row = result.fetchone()
                
                if row and row.max_date:
                    return str(row.max_date)
                else:
                    return None
                    
        except Exception as e:
            self.logger.error(f"获取最大剧情日期失败: {e}")
            return None

    async def _clear_plot_files_and_data(self):
        """清除character_plots中的详细剧情prompt文件和具体剧情表的所有记录"""
        try:
            # 1. 清除character_plots目录中的文件
            plots_dir = Path(LifeStageUpdaterConfig.DAILY_PLOT_BASE_DIR)
            if plots_dir.exists():
                file_count = 0
                for role_plot_dir in plots_dir.iterdir():
                    if role_plot_dir.is_dir() and role_plot_dir.name.endswith("_plot"):
                        files = list(role_plot_dir.glob("*.txt"))
                        file_count += len(files)
                        # 删除该角色的所有剧情文件
                        shutil.rmtree(role_plot_dir)
                
                self.logger.info(f"✅ 清除了 {file_count} 个剧情文件")
            
            # 2. 清除具体剧情表的所有记录
            from mcp_agent.database_config_forlife import get_mysql_session
            from sqlalchemy import text
            
            async with get_mysql_session() as session:
                # 获取删除前的记录数量
                count_result = await session.execute(text("SELECT COUNT(*) as count FROM specific_plot"))
                count_row = count_result.fetchone()
                record_count = count_row.count
                
                # 删除所有记录
                if record_count > 0:
                    await session.execute(text("DELETE FROM specific_plot"))
                    await session.commit()
                    self.logger.info(f"✅ 清除了 {record_count} 个具体剧情数据库记录")
                else:
                    self.logger.info("ℹ️ 具体剧情表中没有记录需要清除")
            
            return True
            
        except Exception as e:
            self.logger.error(f"清除剧情文件和数据失败: {e}")
            return False

    async def _advance_life_stage_status(self) -> bool:
        """将active的生命阶段更新为completed，并激活下一个阶段或生成新阶段"""
        try:
            from mcp_agent.database_config_forlife import get_mysql_session
            from sqlalchemy import text
            
            async with get_mysql_session() as session:
                # 1. 清空剧情片段表的所有记录
                delete_segments = "DELETE FROM plot_segments"
                await session.execute(text(delete_segments))
                self.logger.info("✅ 清空了剧情片段表的所有记录")
                
                # 2. 获取所有active的生命阶段
                query_active = """
                SELECT life_stage_id, outline_id, sequence_order
                FROM life_stages 
                WHERE status = 'active'
                """
                active_result = await session.execute(text(query_active))
                active_stages = active_result.fetchall()
                
                if not active_stages:
                    self.logger.info("ℹ️ 没有找到active状态的生命阶段")
                    return False
                
                advanced_count = 0
                is_last_stage = False
                
                for stage in active_stages:
                    # 3. 将当前active阶段更新为completed
                    update_completed = """
                    UPDATE life_stages 
                    SET status = 'completed' 
                    WHERE life_stage_id = :stage_id
                    """
                    await session.execute(text(update_completed), {"stage_id": stage.life_stage_id})
                    
                    # 4. 查找下一个阶段（同一outline_id下sequence_order+1）
                    query_next = """
                    SELECT life_stage_id 
                    FROM life_stages 
                    WHERE outline_id = :outline_id 
                    AND sequence_order = :next_order 
                    AND status = 'locked'
                    """
                    next_result = await session.execute(text(query_next), {
                        "outline_id": stage.outline_id,
                        "next_order": stage.sequence_order + 1
                    })
                    next_stage = next_result.fetchone()
                    
                    if next_stage:
                        # 5. 激活下一个阶段
                        update_active = """
                        UPDATE life_stages 
                        SET status = 'active' 
                        WHERE life_stage_id = :stage_id
                        """
                        await session.execute(text(update_active), {"stage_id": next_stage.life_stage_id})
                        advanced_count += 1
                        self.logger.info(f"✅ 生命阶段推进成功: {stage.life_stage_id} -> {next_stage.life_stage_id}")
                    else:
                        # 当前阶段是最后一个，需要生成新的生命阶段
                        is_last_stage = True
                        self.logger.info(f"ℹ️ 生命阶段 {stage.life_stage_id} 是最后一个，需要生成新的生命阶段")
                        # 传递outline_id给生成方法
                        await self._generate_new_life_stages(stage.outline_id)
                
                await session.commit()
                
                if is_last_stage:
                    self.logger.info("✅ 已生成新的生命阶段")
                    return True
                else:
                    self.logger.info(f"✅ 成功推进 {advanced_count} 个生命阶段")
                    return advanced_count > 0
                
        except Exception as e:
            self.logger.error(f"推进生命阶段状态失败: {e}")
            return False

    async def _advance_plot_segment_status(self) -> bool:
        """将active的剧情片段更新为completed，并激活下一个片段"""
        try:
            from mcp_agent.database_config_forlife import get_mysql_session
            from sqlalchemy import text
            
            async with get_mysql_session() as session:
                # 1. 获取所有active的剧情片段
                query_active = """
                SELECT plot_segment_id, life_stage_id, sequence_order_in_stage
                FROM plot_segments 
                WHERE status = 'active'
                """
                active_result = await session.execute(text(query_active))
                active_segments = active_result.fetchall()
                
                if not active_segments:
                    self.logger.info("ℹ️ 没有找到active状态的剧情片段")
                    return False
                
                advanced_count = 0
                is_last_segment = False
                
                for segment in active_segments:
                    # 2. 将当前active片段更新为completed
                    update_completed = """
                    UPDATE plot_segments 
                    SET status = 'completed' 
                    WHERE plot_segment_id = :segment_id
                    """
                    await session.execute(text(update_completed), {"segment_id": segment.plot_segment_id})
                    
                    # 3. 查找下一个片段（同一life_stage_id下sequence_order_in_stage+1）
                    query_next = """
                    SELECT plot_segment_id 
                    FROM plot_segments 
                    WHERE life_stage_id = :life_stage_id 
                    AND sequence_order_in_stage = :next_order 
                    AND status = 'locked'
                    """
                    next_result = await session.execute(text(query_next), {
                        "life_stage_id": segment.life_stage_id,
                        "next_order": segment.sequence_order_in_stage + 1
                    })
                    next_segment = next_result.fetchone()
                    
                    if next_segment:
                        # 4. 激活下一个片段
                        update_active = """
                        UPDATE plot_segments 
                        SET status = 'active' 
                        WHERE plot_segment_id = :segment_id
                        """
                        await session.execute(text(update_active), {"segment_id": next_segment.plot_segment_id})
                        advanced_count += 1
                        self.logger.info(f"✅ 剧情片段推进成功: {segment.plot_segment_id} -> {next_segment.plot_segment_id}")
                    else:
                        # 当前片段是最后一个，需要推进生命阶段
                        is_last_segment = True
                        self.logger.info(f"ℹ️ 剧情片段 {segment.plot_segment_id} 是最后一个，需要推进生命阶段")
                
                await session.commit()
                
                if is_last_segment:
                    # 如果是最后一个片段，需要推进生命阶段
                    return await self._advance_life_stage_status()
                else:
                    self.logger.info(f"✅ 成功推进 {advanced_count} 个剧情片段")
                    return advanced_count > 0
                
        except Exception as e:
            self.logger.error(f"推进剧情片段状态失败: {e}")
            return False

    async def _generate_new_life_stages(self, outline_id: str) -> bool:
        """生成新的生命阶段内容并存储到life_stages表"""
        try:
            from mcp_agent.database_config_forlife import get_mysql_session
            from sqlalchemy import text
            
            # 1. 获取角色信息和生命大纲信息
            async with get_mysql_session() as session:
                query_info = """
                SELECT 
                    rd.role_name, rd.L0_prompt_path, rd.age,
                    lpo.title, lpo.overall_theme, lpo.life, lpo.wealth, lpo.birthday
                FROM life_plot_outlines lpo
                JOIN role_details rd ON lpo.role_id = rd.role_id
                WHERE lpo.outline_id = :outline_id
                """
                result = await session.execute(text(query_info), {"outline_id": outline_id})
                info = result.fetchone()
                
                if not info:
                    self.logger.error(f"无法获取outline_id {outline_id} 的信息")
                    return False
                
                # 2. 获取当前最大的sequence_order
                query_max_order = """
                SELECT MAX(sequence_order) as max_order 
                FROM life_stages 
                WHERE outline_id = :outline_id
                """
                max_result = await session.execute(text(query_max_order), {"outline_id": outline_id})
                max_row = max_result.fetchone()
                next_sequence_order = (max_row.max_order if max_row.max_order else 0) + 1
                
                # 3. 构建生成新生命阶段的prompt
                prompt = self._build_new_life_stage_prompt(info, next_sequence_order)
                
                # 4. 调用LLM生成新的生命阶段
                new_stages_data = await self._generate_new_life_stages_with_llm(prompt)
                if not new_stages_data:
                    return False
                
                # 5. 存储生成的生命阶段
                success = await self._store_new_life_stages(outline_id, new_stages_data, next_sequence_order)
                return success
                
        except Exception as e:
            self.logger.error(f"生成新生命阶段失败: {e}")
            return False
    
    def _build_new_life_stage_prompt(self, info, next_sequence_order: int) -> str:
        """构建生成新生命阶段的提示词"""
        
        prompt = f"""你是一个专业的人生规划师和剧情设计师，需要为角色设计下一个人生阶段。

**角色基本信息：**
- 角色名称：{info.role_name}
- 当前年龄：{info.age}岁
- 生日：{info.birthday}
- 生命大纲标题：{info.title}
- 整体主题：{info.overall_theme}
- 生活背景：{info.life}
- 财富状况：{info.wealth}

**当前情况：**
- 即将开始第 {next_sequence_order} 个生命阶段
- 角色已经历了前面的人生阶段，现在需要设计接下来的发展

**任务要求：**
请设计接下来的2-3个生命阶段，每个阶段要求：

1. **life_period**: 生命时期（如："29-32岁"）
2. **title**: 阶段标题，要具体生动
3. **description_for_plot_llm**: 阶段描述，详细描述这个阶段的主要特征和发展方向
4. **stage_goals**: 阶段目标，明确这个阶段要达成的具体目标
5. **sequence_order**: 阶段顺序（从{next_sequence_order}开始递增）

**设计原则：**
- 要符合角色的年龄发展轨迹
- 与角色的背景和整体主题保持一致
- 每个阶段要有明确的发展重点
- 时间跨度要合理，一般3-4年一个阶段
- 要体现人生的自然过渡和成长

**输出格式：**
请严格按照JSON格式返回：
```json
{{
  "life_stages": [
    {{
      "life_period": "年龄范围",
      "title": "阶段标题",
      "description_for_plot_llm": "详细描述...",
      "stage_goals": "阶段目标...",
      "sequence_order": {next_sequence_order}
    }}
  ]
}}
```

请开始为{info.role_name}设计下一个人生阶段："""

        return prompt
    
    async def _generate_new_life_stages_with_llm(self, prompt: str) -> Optional[Dict[str, Any]]:
        """使用LLM生成新的生命阶段数据"""
        max_retries = LifeStageUpdaterConfig.MAX_RETRIES
        retry_delay = LifeStageUpdaterConfig.INITIAL_RETRY_DELAY
        
        for attempt in range(max_retries):
            try:
                self.logger.debug(f"正在调用Gemini API生成新生命阶段... (尝试 {attempt + 1}/{max_retries})")
                
                # 调用Gemini API
                response = self.model.generate_content(prompt)
                response_text = response.text
                
                self.logger.info(f"LLM响应长度: {len(response_text)} 字符")
                
                # 提取JSON内容
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                
                if json_start == -1 or json_end == 0:
                    self.logger.error("LLM响应中未找到有效的JSON格式")
                    if attempt < max_retries - 1:
                        self.logger.info(f"等待 {retry_delay} 秒后重试...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    return None
                
                json_content = response_text[json_start:json_end]
                
                # 解析JSON
                try:
                    data = json.loads(json_content)
                    self.logger.info(f"成功解析JSON，包含 {len(data.get('life_stages', []))} 个新生命阶段")
                    return data
                except json.JSONDecodeError as e:
                    self.logger.error(f"JSON解析失败: {e}")
                    if attempt < max_retries - 1:
                        self.logger.info(f"等待 {retry_delay} 秒后重试...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                        
            except Exception as e:
                self.logger.error(f"LLM生成新生命阶段失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    self.logger.info(f"等待 {retry_delay} 秒后重试...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                    
        self.logger.error("所有重试尝试都失败了")
        return None
    
    async def _store_new_life_stages(self, outline_id: str, stages_data: Dict[str, Any], start_sequence_order: int) -> bool:
        """存储新生成的生命阶段数据"""
        try:
            from character_life_system.models import LifeStageData, StageStatusEnum
            import uuid
            
            stages = stages_data.get('life_stages', [])
            success_count = 0
            
            for i, stage in enumerate(stages):
                try:
                    # 验证必需字段
                    required_fields = ['life_period', 'title', 'description_for_plot_llm', 'stage_goals']
                    if not all(field in stage for field in required_fields):
                        self.logger.warning(f"跳过不完整的阶段数据: {stage}")
                        continue
                    
                    # 创建LifeStageData对象
                    stage_data = LifeStageData(
                        life_stage_id=str(uuid.uuid4()),
                        outline_id=outline_id,
                        sequence_order=start_sequence_order + i,
                        life_period=stage['life_period'],
                        title=stage['title'],
                        description_for_plot_llm=stage['description_for_plot_llm'],
                        stage_goals=stage['stage_goals'],
                        status=StageStatusEnum.ACTIVE if i == 0 else StageStatusEnum.LOCKED,  # 第一个阶段设为活跃
                        summary=None
                    )
                    
                    # 存储到数据库
                    if await character_life_manager.create_life_stage(stage_data):
                        success_count += 1
                        self.logger.debug(f"✅ 生命阶段创建成功: {stage_data.title}")
                    else:
                        self.logger.error(f"❌ 生命阶段创建失败: {stage_data.title}")
                
                except Exception as e:
                    self.logger.error(f"处理阶段数据时出错: {e}, 数据: {stage}")
                    continue
            
            self.logger.info(f"成功创建 {success_count}/{len(stages)} 个新生命阶段")
            return success_count > 0
            
        except Exception as e:
            self.logger.error(f"存储新生命阶段失败: {e}")
            return False

async def update_life_stages_and_generate_summaries(skip_llm_steps: bool = False):
    """更新生命阶段状态并生成摘要的主函数"""
    try:
        # 初始化数据库连接
        from mcp_agent.database_config_forlife import init_all_databases
        db_success = await init_all_databases()
        if not db_success:
            print("❌ 数据库连接初始化失败")
            return
        
        # 创建更新器
        updater = LifeStageUpdater()
        
        print("🔄 步骤1: 更新生命阶段状态...")
        await updater.update_all_life_stage_status()
        print("✅ 生命阶段状态更新完成")
        
        if skip_llm_steps:
            print("\n⏭️ 跳过LLM相关步骤，直接进入剧情片段生成...")
        else:
            print("\n📝 步骤2: 为已完成阶段生成摘要...")
            await updater.generate_completed_stage_summaries()
            print("✅ 摘要生成完成")
            
            print("\n📄 步骤3: 生成角色过往经历总结...")
            await updater.generate_past_experience_summaries()
            print("✅ 过往经历总结生成完成")
        
        print("\n🎬 步骤4: 为活跃阶段生成剧情片段...")
        await updater.generate_plot_segments_for_active_stages()
        print("✅ 剧情片段生成完成")
        
        print("\n📅 步骤5: 为活跃剧情片段生成具体日常剧情...")
        await updater.generate_daily_plots_for_active_segments()
        print("✅ 日常剧情生成完成")
        
        print("\n🎉 所有处理完成！")
        
    except Exception as e:
        print(f"❌ 处理过程中发生错误: {e}")
        raise

async def quick_update_only_status():
    """仅更新状态，不调用LLM"""
    await update_life_stages_and_generate_summaries(skip_llm_steps=True)

if __name__ == "__main__":
    import asyncio
    import logging
    
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
    
    # 运行更新器
    asyncio.run(update_life_stages_and_generate_summaries()) 