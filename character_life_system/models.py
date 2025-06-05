"""
角色生命系统数据库模型
包含角色生命大纲、剧情篇章、剧情片段和具体剧情的数据模型
"""

from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, ForeignKey, Index, Date, Enum, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, date
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import uuid
import enum

Base = declarative_base()

class StageStatusEnum(enum.Enum):
    """剧情阶段状态枚举"""
    LOCKED = "locked"
    ACTIVE = "active" 
    COMPLETED = "completed"

class SegmentStatusEnum(enum.Enum):
    """剧情片段状态枚举"""
    LOCKED = "locked"
    ACTIVE = "active"
    COMPLETED = "completed"
    SKIPPED = "skipped"

class PlotStatusEnum(enum.Enum):
    """具体剧情状态枚举"""
    LOCKED = "locked"
    ACTIVE = "active"
    COMPLETED = "completed"
    SKIPPED = "skipped"

class LifePlotOutlines(Base):
    """角色生命大纲表"""
    __tablename__ = 'life_plot_outlines'
    
    # 大纲ID (主键)
    outline_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # 角色ID (外键，关联到role_details表)
    role_id = Column(String(64), nullable=False, index=True)
    
    # 角色名称
    role_name = Column(String(255), nullable=False)
    
    # 大纲标题
    title = Column(Text, nullable=False)
    
    # 角色生日
    birthday = Column(Date, nullable=False)
    
    # 生命值/健康值
    life = Column(Integer, nullable=False, default=100)
    
    # 财富状况
    wealth = Column(String(100), nullable=False, default="普通")
    
    # 总体主题
    overall_theme = Column(Text, nullable=True)
    
    # 版本号
    version = Column(Integer, nullable=False, default=1)
    
    # 创建时间
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    
    # 更新时间
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    
    # 关联的生命阶段
    life_stages = relationship("LifeStages", back_populates="outline", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        Index('idx_role_id', 'role_id'),
        Index('idx_role_name', 'role_name'),
        Index('idx_created_at', 'created_at'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'outline_id': self.outline_id,
            'role_id': self.role_id,
            'role_name': self.role_name,
            'title': self.title,
            'birthday': self.birthday.isoformat() if self.birthday else None,
            'life': self.life,
            'wealth': self.wealth,
            'overall_theme': self.overall_theme,
            'version': self.version,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class LifeStages(Base):
    """剧情篇章表"""
    __tablename__ = 'life_stages'
    
    # 生命阶段ID (主键)
    life_stage_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # 大纲ID (外键)
    outline_id = Column(String(64), ForeignKey('life_plot_outlines.outline_id'), nullable=False, index=True)
    
    # 剧情阶段顺序
    sequence_order = Column(Integer, nullable=False)
    
    # 角色生命时间段
    life_period = Column(String(100), nullable=False)
    
    # 阶段标题
    title = Column(String(255), nullable=False)
    
    # 对该阶段的宏观描述，指导该阶段所有剧情片段的基调和核心冲突
    description_for_plot_llm = Column(Text, nullable=True)
    
    # 角色在此阶段的主要目标和动机
    stage_goals = Column(Text, nullable=True)
    
    # 状态
    status = Column(Enum(StageStatusEnum), nullable=False, default=StageStatusEnum.LOCKED)
    
    # 阶段总结 (默认为null, 由下游任务生成更新内容)
    summary = Column(Text, nullable=True)
    
    # 创建时间
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    
    # 更新时间
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    
    # 关联的大纲
    outline = relationship("LifePlotOutlines", back_populates="life_stages")
    
    # 关联的剧情片段
    plot_segments = relationship("PlotSegments", back_populates="life_stage", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        Index('idx_outline_sequence', 'outline_id', 'sequence_order'),
        Index('idx_status', 'status'),
        Index('idx_life_period', 'life_period'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'life_stage_id': self.life_stage_id,
            'outline_id': self.outline_id,
            'sequence_order': self.sequence_order,
            'life_period': self.life_period,
            'title': self.title,
            'description_for_plot_llm': self.description_for_plot_llm,
            'stage_goals': self.stage_goals,
            'status': self.status.value if self.status else None,
            'summary': self.summary,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class PlotSegments(Base):
    """剧情片段表"""
    __tablename__ = 'plot_segments'
    
    # 剧情片段ID (主键)
    plot_segment_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # 生命阶段ID (外键)
    life_stage_id = Column(String(64), ForeignKey('life_stages.life_stage_id'), nullable=False, index=True)
    
    # 片段在阶段中的顺序
    sequence_order_in_stage = Column(Integer, nullable=False)
    
    # 片段标题
    title = Column(String(255), nullable=False)
    
    # 经历这个事件时的年龄
    life_age = Column(Integer, nullable=False)
    
    # 核心内容。这是传递给"剧情生成LLM"的主要输入
    segment_prompt_for_plot_llm = Column(Text, nullable=True)
    
    # 这个片段大约会生成多少"天"的剧情
    duration_in_days_estimate = Column(Integer, nullable=False, default=1)
    
    # 指导此片段中角色可能经历的情感起伏
    expected_emotional_arc = Column(Text, nullable=True)
    
    # 涉及的关键NPC及其在此片段中的角色
    key_npcs_involved = Column(Text, nullable=True)
    
    # 状态
    status = Column(Enum(SegmentStatusEnum), nullable=False, default=SegmentStatusEnum.LOCKED)
    
    # 标记是否为重大转折点，影响记忆的"清晰度"和"重要性"
    is_milestone_event = Column(Boolean, nullable=False, default=False)
    
    # 创建时间
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    
    # 更新时间
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    
    # 关联的生命阶段
    life_stage = relationship("LifeStages", back_populates="plot_segments")
    
    # 关联的具体剧情
    specific_plots = relationship("SpecificPlot", back_populates="plot_segment", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        Index('idx_stage_sequence', 'life_stage_id', 'sequence_order_in_stage'),
        Index('idx_status', 'status'),
        Index('idx_milestone', 'is_milestone_event'),
        Index('idx_duration', 'duration_in_days_estimate'),
        Index('idx_life_age', 'life_age'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'plot_segment_id': self.plot_segment_id,
            'life_stage_id': self.life_stage_id,
            'sequence_order_in_stage': self.sequence_order_in_stage,
            'title': self.title,
            'life_age': self.life_age,
            'segment_prompt_for_plot_llm': self.segment_prompt_for_plot_llm,
            'duration_in_days_estimate': self.duration_in_days_estimate,
            'expected_emotional_arc': self.expected_emotional_arc,
            'key_npcs_involved': self.key_npcs_involved,
            'status': self.status.value if self.status else None,
            'is_milestone_event': self.is_milestone_event,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class SpecificPlot(Base):
    """具体剧情表"""
    __tablename__ = 'specific_plot'
    
    # 剧情ID (主键)
    plot_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # 剧情片段ID (外键)
    plot_segment_id = Column(String(64), ForeignKey('plot_segments.plot_segment_id'), nullable=False, index=True)
    
    # 剧情顺序
    plot_order = Column(Integer, nullable=False)
    
    # 剧情时间 (如2025-06-01 am)
    plot_date = Column(String(50), nullable=False)
    
    # 剧情内容存储的路径位置
    plot_content_path = Column(String(512), nullable=True)
    
    # 情绪状态
    mood = Column(JSON, nullable=False, default=lambda: {})
    
    # 状态
    status = Column(Enum(PlotStatusEnum), nullable=False, default=PlotStatusEnum.LOCKED)
    
    # 创建时间
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    
    # 更新时间
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    
    # 关联的剧情片段
    plot_segment = relationship("PlotSegments", back_populates="specific_plots")
    
    # 索引
    __table_args__ = (
        Index('idx_segment_order', 'plot_segment_id', 'plot_order'),
        Index('idx_plot_date', 'plot_date'),
        Index('idx_status', 'status'),
        Index('idx_created_at', 'created_at'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'plot_id': self.plot_id,
            'plot_segment_id': self.plot_segment_id,
            'plot_order': self.plot_order,
            'plot_date': self.plot_date,
            'plot_content_path': self.plot_content_path,
            'mood': self.mood,
            'status': self.status.value if self.status else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

# 数据类定义，用于业务逻辑层
@dataclass
class LifePlotOutlineData:
    """角色生命大纲数据类"""
    outline_id: str
    role_id: str
    role_name: str
    title: str
    birthday: date
    life: int
    wealth: str
    overall_theme: Optional[str] = None
    version: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class LifeStageData:
    """生命阶段数据类"""
    life_stage_id: str
    outline_id: str
    sequence_order: int
    life_period: str
    title: str
    description_for_plot_llm: Optional[str] = None
    stage_goals: Optional[str] = None
    status: StageStatusEnum = StageStatusEnum.LOCKED
    summary: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class PlotSegmentData:
    """剧情片段数据类"""
    plot_segment_id: str
    life_stage_id: str
    sequence_order_in_stage: int
    title: str
    life_age: int
    segment_prompt_for_plot_llm: Optional[str] = None
    duration_in_days_estimate: int = 1
    expected_emotional_arc: Optional[str] = None
    key_npcs_involved: Optional[str] = None
    status: SegmentStatusEnum = SegmentStatusEnum.LOCKED
    is_milestone_event: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class SpecificPlotData:
    """具体剧情数据类"""
    plot_id: str
    plot_segment_id: str
    plot_order: int
    plot_date: str
    plot_content_path: Optional[str] = None
    mood: Dict[str, Any] = None
    status: PlotStatusEnum = PlotStatusEnum.LOCKED
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None 