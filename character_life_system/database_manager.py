"""
角色生命系统数据库管理器
提供对角色生命大纲、剧情篇章、剧情片段和具体剧情的数据库操作
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, date
from sqlalchemy import text, and_, or_, desc, asc
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from character_life_system.models import (
    Base, LifePlotOutlines, LifeStages, PlotSegments, SpecificPlot,
    StageStatusEnum, SegmentStatusEnum, PlotStatusEnum,
    LifePlotOutlineData, LifeStageData, PlotSegmentData, SpecificPlotData
)

logger = logging.getLogger(__name__)

class CharacterLifeSystemManager:
    """角色生命系统数据库管理器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def create_all_tables(self):
        """创建所有角色生命系统相关表"""
        try:
            # 导入数据库配置
            from mcp_agent.database_config_forlife import get_mysql_session
            
            async with get_mysql_session() as session:
                self.logger.info("开始创建角色生命系统数据表...")
                
                # 1. 创建角色生命大纲表
                await self._create_life_plot_outlines_table(session)
                
                # 2. 创建剧情篇章表
                await self._create_life_stages_table(session)
                
                # 3. 创建剧情片段表
                await self._create_plot_segments_table(session)
                
                # 4. 创建具体剧情表
                await self._create_specific_plot_table(session)
                
                await session.commit()
                self.logger.info("✅ 角色生命系统数据表创建完成")
                
        except Exception as e:
            self.logger.error(f"❌ 创建角色生命系统数据表失败: {e}")
            raise
    
    async def _create_life_plot_outlines_table(self, session):
        """创建角色生命大纲表"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS life_plot_outlines (
            outline_id VARCHAR(64) PRIMARY KEY COMMENT '大纲ID',
            role_id VARCHAR(64) NOT NULL COMMENT '角色ID(外键)',
            role_name VARCHAR(255) NOT NULL COMMENT '角色名称',
            title TEXT NOT NULL COMMENT '大纲标题',
            birthday DATE NOT NULL COMMENT '角色生日',
            life INT NOT NULL DEFAULT 100 COMMENT '生命值/健康值',
            wealth VARCHAR(100) NOT NULL DEFAULT '普通' COMMENT '财富状况',
            overall_theme TEXT COMMENT '总体主题',
            version INT NOT NULL DEFAULT 1 COMMENT '版本号',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
            INDEX idx_role_id (role_id),
            INDEX idx_role_name (role_name),
            INDEX idx_created_at (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色生命大纲表';
        """
        await session.execute(text(create_table_sql))
    
    async def _create_life_stages_table(self, session):
        """创建剧情篇章表"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS life_stages (
            life_stage_id VARCHAR(64) PRIMARY KEY COMMENT '生命阶段ID',
            outline_id VARCHAR(64) NOT NULL COMMENT '大纲ID(外键)',
            sequence_order INT NOT NULL COMMENT '剧情阶段顺序',
            life_period VARCHAR(100) NOT NULL COMMENT '角色生命时间段',
            title VARCHAR(255) NOT NULL COMMENT '阶段标题',
            description_for_plot_llm TEXT COMMENT '对该阶段的宏观描述',
            stage_goals TEXT COMMENT '角色在此阶段的主要目标和动机',
            status ENUM('locked', 'active', 'completed') NOT NULL DEFAULT 'locked' COMMENT '状态',
            summary TEXT COMMENT '阶段总结',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
            FOREIGN KEY (outline_id) REFERENCES life_plot_outlines(outline_id) ON DELETE CASCADE,
            INDEX idx_outline_sequence (outline_id, sequence_order),
            INDEX idx_status (status),
            INDEX idx_life_period (life_period)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='剧情篇章表';
        """
        await session.execute(text(create_table_sql))
    
    async def _create_plot_segments_table(self, session):
        """创建剧情片段表"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS plot_segments (
            plot_segment_id VARCHAR(64) PRIMARY KEY COMMENT '剧情片段ID',
            life_stage_id VARCHAR(64) NOT NULL COMMENT '生命阶段ID(外键)',
            sequence_order_in_stage INT NOT NULL COMMENT '片段在阶段中的顺序',
            title VARCHAR(255) NOT NULL COMMENT '片段标题',
            life_age INT NOT NULL COMMENT '经历这个事件时的年龄',
            segment_prompt_for_plot_llm TEXT COMMENT '传递给剧情生成LLM的主要输入',
            duration_in_days_estimate INT NOT NULL DEFAULT 1 COMMENT '预估生成天数',
            expected_emotional_arc TEXT COMMENT '预期情感起伏',
            key_npcs_involved TEXT COMMENT '涉及的关键NPC',
            status ENUM('locked', 'active', 'completed', 'skipped') NOT NULL DEFAULT 'locked' COMMENT '状态',
            is_milestone_event BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否为重大转折点',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
            FOREIGN KEY (life_stage_id) REFERENCES life_stages(life_stage_id) ON DELETE CASCADE,
            INDEX idx_stage_sequence (life_stage_id, sequence_order_in_stage),
            INDEX idx_status (status),
            INDEX idx_milestone (is_milestone_event),
            INDEX idx_duration (duration_in_days_estimate),
            INDEX idx_life_age (life_age)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='剧情片段表';
        """
        await session.execute(text(create_table_sql))
    
    async def _create_specific_plot_table(self, session):
        """创建具体剧情表"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS specific_plot (
            plot_id VARCHAR(64) PRIMARY KEY COMMENT '剧情ID',
            plot_segment_id VARCHAR(64) NOT NULL COMMENT '剧情片段ID(外键)',
            plot_order INT NOT NULL COMMENT '剧情顺序',
            plot_date VARCHAR(50) NOT NULL COMMENT '剧情时间',
            plot_content_path VARCHAR(512) COMMENT '剧情内容存储路径',
            mood JSON NOT NULL COMMENT '情绪状态',
            status ENUM('locked', 'active', 'completed', 'skipped') NOT NULL DEFAULT 'locked' COMMENT '状态',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
            FOREIGN KEY (plot_segment_id) REFERENCES plot_segments(plot_segment_id) ON DELETE CASCADE,
            INDEX idx_segment_order (plot_segment_id, plot_order),
            INDEX idx_plot_date (plot_date),
            INDEX idx_status (status),
            INDEX idx_created_at (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='具体剧情表';
        """
        await session.execute(text(create_table_sql))
    
    # ==================== 角色生命大纲操作 ====================
    
    async def create_life_plot_outline(self, outline_data: LifePlotOutlineData) -> bool:
        """创建角色生命大纲"""
        try:
            from mcp_agent.database_config_forlife import get_mysql_session
            
            async with get_mysql_session() as session:
                outline = LifePlotOutlines(
                    outline_id=outline_data.outline_id,
                    role_id=outline_data.role_id,
                    role_name=outline_data.role_name,
                    title=outline_data.title,
                    birthday=outline_data.birthday,
                    life=outline_data.life,
                    wealth=outline_data.wealth,
                    overall_theme=outline_data.overall_theme,
                    version=outline_data.version
                )
                
                session.add(outline)
                await session.commit()
                
                self.logger.info(f"✅ 创建角色生命大纲成功: {outline_data.role_name}")
                return True
                
        except IntegrityError as e:
            self.logger.error(f"❌ 创建角色生命大纲失败(数据约束): {e}")
            return False
        except Exception as e:
            self.logger.error(f"❌ 创建角色生命大纲失败: {e}")
            return False
    
    async def get_life_plot_outline(self, outline_id: str) -> Optional[LifePlotOutlineData]:
        """获取角色生命大纲"""
        try:
            from mcp_agent.database_config_forlife import get_mysql_session
            
            async with get_mysql_session() as session:
                result = await session.execute(
                    text("SELECT * FROM life_plot_outlines WHERE outline_id = :outline_id"),
                    {"outline_id": outline_id}
                )
                row = result.fetchone()
                
                if row:
                    return LifePlotOutlineData(
                        outline_id=row.outline_id,
                        role_id=row.role_id,
                        role_name=row.role_name,
                        title=row.title,
                        birthday=row.birthday,
                        life=row.life,
                        wealth=row.wealth,
                        overall_theme=row.overall_theme,
                        version=row.version,
                        created_at=row.created_at,
                        updated_at=row.updated_at
                    )
                return None
                
        except Exception as e:
            self.logger.error(f"❌ 获取角色生命大纲失败: {e}")
            return None
    
    async def get_life_plot_outlines_by_role(self, role_id: str) -> List[LifePlotOutlineData]:
        """获取角色的所有生命大纲"""
        try:
            from mcp_agent.database_config_forlife import get_mysql_session
            
            async with get_mysql_session() as session:
                result = await session.execute(
                    text("SELECT * FROM life_plot_outlines WHERE role_id = :role_id ORDER BY version DESC"),
                    {"role_id": role_id}
                )
                rows = result.fetchall()
                
                outlines = []
                for row in rows:
                    outlines.append(LifePlotOutlineData(
                        outline_id=row.outline_id,
                        role_id=row.role_id,
                        role_name=row.role_name,
                        title=row.title,
                        birthday=row.birthday,
                        life=row.life,
                        wealth=row.wealth,
                        overall_theme=row.overall_theme,
                        version=row.version,
                        created_at=row.created_at,
                        updated_at=row.updated_at
                    ))
                
                return outlines
                
        except Exception as e:
            self.logger.error(f"❌ 获取角色生命大纲列表失败: {e}")
            return []
    
    # ==================== 生命阶段操作 ====================
    
    async def create_life_stage(self, stage_data: LifeStageData) -> bool:
        """创建生命阶段"""
        try:
            from mcp_agent.database_config_forlife import get_mysql_session
            
            async with get_mysql_session() as session:
                stage = LifeStages(
                    life_stage_id=stage_data.life_stage_id,
                    outline_id=stage_data.outline_id,
                    sequence_order=stage_data.sequence_order,
                    life_period=stage_data.life_period,
                    title=stage_data.title,
                    description_for_plot_llm=stage_data.description_for_plot_llm,
                    stage_goals=stage_data.stage_goals,
                    status=stage_data.status,
                    summary=stage_data.summary
                )
                
                session.add(stage)
                await session.commit()
                
                self.logger.info(f"✅ 创建生命阶段成功: {stage_data.title}")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ 创建生命阶段失败: {e}")
            return False
    
    async def get_life_stages_by_outline(self, outline_id: str) -> List[LifeStageData]:
        """获取大纲的所有生命阶段"""
        try:
            from mcp_agent.database_config_forlife import get_mysql_session
            
            async with get_mysql_session() as session:
                result = await session.execute(
                    text("SELECT * FROM life_stages WHERE outline_id = :outline_id ORDER BY sequence_order"),
                    {"outline_id": outline_id}
                )
                rows = result.fetchall()
                
                stages = []
                for row in rows:
                    stages.append(LifeStageData(
                        life_stage_id=row.life_stage_id,
                        outline_id=row.outline_id,
                        sequence_order=row.sequence_order,
                        life_period=row.life_period,
                        title=row.title,
                        description_for_plot_llm=row.description_for_plot_llm,
                        stage_goals=row.stage_goals,
                        status=StageStatusEnum(row.status),
                        summary=row.summary,
                        created_at=row.created_at,
                        updated_at=row.updated_at
                    ))
                
                return stages
                
        except Exception as e:
            self.logger.error(f"❌ 获取生命阶段列表失败: {e}")
            return []
    
    async def update_life_stage_status(self, life_stage_id: str, status: StageStatusEnum) -> bool:
        """更新生命阶段状态"""
        try:
            from mcp_agent.database_config_forlife import get_mysql_session
            
            async with get_mysql_session() as session:
                result = await session.execute(
                    text("UPDATE life_stages SET status = :status WHERE life_stage_id = :life_stage_id"),
                    {"status": status.value, "life_stage_id": life_stage_id}
                )
                await session.commit()
                
                if result.rowcount > 0:
                    self.logger.info(f"✅ 更新生命阶段状态成功: {life_stage_id} -> {status.value}")
                    return True
                else:
                    self.logger.warning(f"⚠️ 生命阶段不存在: {life_stage_id}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"❌ 更新生命阶段状态失败: {e}")
            return False
    
    # ==================== 剧情片段操作 ====================
    
    async def create_plot_segment(self, segment_data: PlotSegmentData) -> bool:
        """创建剧情片段"""
        try:
            from mcp_agent.database_config_forlife import get_mysql_session
            
            async with get_mysql_session() as session:
                segment = PlotSegments(
                    plot_segment_id=segment_data.plot_segment_id,
                    life_stage_id=segment_data.life_stage_id,
                    sequence_order_in_stage=segment_data.sequence_order_in_stage,
                    title=segment_data.title,
                    life_age=segment_data.life_age,
                    segment_prompt_for_plot_llm=segment_data.segment_prompt_for_plot_llm,
                    duration_in_days_estimate=segment_data.duration_in_days_estimate,
                    expected_emotional_arc=segment_data.expected_emotional_arc,
                    key_npcs_involved=segment_data.key_npcs_involved,
                    status=segment_data.status,
                    is_milestone_event=segment_data.is_milestone_event
                )
                
                session.add(segment)
                await session.commit()
                
                self.logger.info(f"✅ 创建剧情片段成功: {segment_data.title}")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ 创建剧情片段失败: {e}")
            return False
    
    async def get_plot_segments_by_stage(self, life_stage_id: str) -> List[PlotSegmentData]:
        """获取生命阶段的所有剧情片段"""
        try:
            from mcp_agent.database_config_forlife import get_mysql_session
            
            async with get_mysql_session() as session:
                result = await session.execute(
                    text("SELECT * FROM plot_segments WHERE life_stage_id = :life_stage_id ORDER BY sequence_order_in_stage"),
                    {"life_stage_id": life_stage_id}
                )
                rows = result.fetchall()
                
                segments = []
                for row in rows:
                    segments.append(PlotSegmentData(
                        plot_segment_id=row.plot_segment_id,
                        life_stage_id=row.life_stage_id,
                        sequence_order_in_stage=row.sequence_order_in_stage,
                        title=row.title,
                        life_age=row.life_age,
                        segment_prompt_for_plot_llm=row.segment_prompt_for_plot_llm,
                        duration_in_days_estimate=row.duration_in_days_estimate,
                        expected_emotional_arc=row.expected_emotional_arc,
                        key_npcs_involved=row.key_npcs_involved,
                        status=SegmentStatusEnum(row.status),
                        is_milestone_event=row.is_milestone_event,
                        created_at=row.created_at,
                        updated_at=row.updated_at
                    ))
                
                return segments
                
        except Exception as e:
            self.logger.error(f"❌ 获取剧情片段列表失败: {e}")
            return []
    
    async def update_plot_segment_status(self, plot_segment_id: str, status: SegmentStatusEnum) -> bool:
        """更新剧情片段状态"""
        try:
            from mcp_agent.database_config_forlife import get_mysql_session
            
            async with get_mysql_session() as session:
                result = await session.execute(
                    text("UPDATE plot_segments SET status = :status WHERE plot_segment_id = :plot_segment_id"),
                    {"status": status.value, "plot_segment_id": plot_segment_id}
                )
                await session.commit()
                
                if result.rowcount > 0:
                    self.logger.debug(f"✅ 更新剧情片段状态成功: {plot_segment_id} -> {status.value}")
                    return True
                else:
                    self.logger.warning(f"⚠️ 剧情片段不存在: {plot_segment_id}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"❌ 更新剧情片段状态失败: {e}")
            return False
    
    async def update_plot_segments_status_by_age(self, life_stage_id: str, current_age: int) -> bool:
        """根据年龄更新剧情片段状态"""
        try:
            from mcp_agent.database_config_forlife import get_mysql_session
            
            async with get_mysql_session() as session:
                # 1. 将life_age小于current_age的记录设为completed
                await session.execute(
                    text("UPDATE plot_segments SET status = 'completed' WHERE life_stage_id = :life_stage_id AND life_age < :current_age"),
                    {"life_stage_id": life_stage_id, "current_age": current_age}
                )
                
                # 2. 将life_age等于current_age的记录中序号最小的设为active，其他设为locked
                await session.execute(
                    text("UPDATE plot_segments SET status = 'locked' WHERE life_stage_id = :life_stage_id AND life_age = :current_age"),
                    {"life_stage_id": life_stage_id, "current_age": current_age}
                )
                
                # 3. 获取life_age等于current_age的最小序号记录并设为active
                result = await session.execute(
                    text("""
                    SELECT plot_segment_id FROM plot_segments 
                    WHERE life_stage_id = :life_stage_id AND life_age = :current_age 
                    ORDER BY sequence_order_in_stage LIMIT 1
                    """),
                    {"life_stage_id": life_stage_id, "current_age": current_age}
                )
                first_segment = result.fetchone()
                
                if first_segment:
                    await session.execute(
                        text("UPDATE plot_segments SET status = 'active' WHERE plot_segment_id = :plot_segment_id"),
                        {"plot_segment_id": first_segment.plot_segment_id}
                    )
                
                # 4. 将life_age大于current_age的记录设为locked
                await session.execute(
                    text("UPDATE plot_segments SET status = 'locked' WHERE life_stage_id = :life_stage_id AND life_age > :current_age"),
                    {"life_stage_id": life_stage_id, "current_age": current_age}
                )
                
                await session.commit()
                self.logger.info(f"✅ 根据年龄更新剧情片段状态成功: life_stage_id={life_stage_id}, age={current_age}")
                return True
                    
        except Exception as e:
            self.logger.error(f"❌ 根据年龄更新剧情片段状态失败: {e}")
            return False
    
    # ==================== 具体剧情操作 ====================
    
    async def create_specific_plot(self, plot_data: SpecificPlotData) -> bool:
        """创建具体剧情"""
        try:
            from mcp_agent.database_config_forlife import get_mysql_session
            
            async with get_mysql_session() as session:
                plot = SpecificPlot(
                    plot_id=plot_data.plot_id,
                    plot_segment_id=plot_data.plot_segment_id,
                    plot_order=plot_data.plot_order,
                    plot_date=plot_data.plot_date,
                    plot_content_path=plot_data.plot_content_path,
                    mood=plot_data.mood if plot_data.mood is not None else {},
                    status=plot_data.status
                )
                
                session.add(plot)
                await session.commit()
                
                self.logger.info(f"✅ 创建具体剧情成功: {plot_data.plot_date}")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ 创建具体剧情失败: {e}")
            return False
    
    async def get_specific_plots_by_segment(self, plot_segment_id: str) -> List[SpecificPlotData]:
        """获取剧情片段的所有具体剧情"""
        try:
            from mcp_agent.database_config_forlife import get_mysql_session
            
            async with get_mysql_session() as session:
                result = await session.execute(
                    text("SELECT * FROM specific_plot WHERE plot_segment_id = :plot_segment_id ORDER BY plot_order"),
                    {"plot_segment_id": plot_segment_id}
                )
                rows = result.fetchall()
                
                plots = []
                for row in rows:
                    plots.append(SpecificPlotData(
                        plot_id=row.plot_id,
                        plot_segment_id=row.plot_segment_id,
                        plot_order=row.plot_order,
                        plot_date=row.plot_date,
                        plot_content_path=row.plot_content_path,
                        mood=row.mood,
                        status=PlotStatusEnum(row.status),
                        created_at=row.created_at,
                        updated_at=row.updated_at
                    ))
                
                return plots
                
        except Exception as e:
            self.logger.error(f"❌ 获取具体剧情列表失败: {e}")
            return []

# 全局管理器实例
character_life_manager = CharacterLifeSystemManager() 