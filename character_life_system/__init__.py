"""
角色生命系统模块
提供角色生命大纲、剧情篇章、剧情片段和具体剧情的完整管理功能
"""

from character_life_system.models import (
    # 数据库模型
    LifePlotOutlines, 
    LifeStages, 
    PlotSegments, 
    SpecificPlot,
    # 枚举类
    StageStatusEnum,
    SegmentStatusEnum, 
    PlotStatusEnum,
    # 数据类
    LifePlotOutlineData,
    LifeStageData,
    PlotSegmentData,
    SpecificPlotData
)

from character_life_system.database_manager import (
    CharacterLifeSystemManager,
    character_life_manager
)

from character_life_system.life_stage_generator import (
    LifeStageGenerator,
    generate_life_stages_for_all_roles
)

from character_life_system.life_stage_updater import (
    LifeStageUpdater,
    update_life_stages_and_generate_summaries
)

__all__ = [
    # 数据库模型
    'LifePlotOutlines',
    'LifeStages', 
    'PlotSegments',
    'SpecificPlot',
    # 枚举类
    'StageStatusEnum',
    'SegmentStatusEnum',
    'PlotStatusEnum', 
    # 数据类
    'LifePlotOutlineData',
    'LifeStageData',
    'PlotSegmentData',
    'SpecificPlotData',
    # 管理器
    'CharacterLifeSystemManager',
    'character_life_manager',
    # 生成器
    'LifeStageGenerator',
    'generate_life_stages_for_all_roles',
    # 更新器
    'LifeStageUpdater',
    'update_life_stages_and_generate_summaries'
] 