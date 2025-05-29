"""
数据库模型定义
包含会话表和聊天记录表的SQLAlchemy模型
"""

from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

class ChatSession(Base):
    """会话表模型"""
    __tablename__ = 'chat_sessions'
    
    # 会话ID (主键)
    session_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # 用户名称
    user_name = Column(String(100), nullable=False, index=True)
    
    # 会话标题
    session_title = Column(String(200), nullable=True)
    
    # 聊天会话建立时间
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    
    # 最新消息时间
    last_message_at = Column(DateTime, nullable=False, default=datetime.now)
    
    # 消息数量
    total_message_count = Column(Integer, nullable=False, default=0)
    
    # 用户发送消息数
    user_message_count = Column(Integer, nullable=False, default=0)
    
    # Agent发送消息数
    agent_message_count = Column(Integer, nullable=False, default=0)
    
    # 会话状态 (active, archived, deleted)
    status = Column(String(20), nullable=False, default='active')
    
    # 关联的聊天记录
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        Index('idx_user_created', 'user_name', 'created_at'),
        Index('idx_user_last_message', 'user_name', 'last_message_at'),
        Index('idx_status_created', 'status', 'created_at'),
    )
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'session_id': self.session_id,
            'user_name': self.user_name,
            'session_title': self.session_title,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_message_at': self.last_message_at.isoformat() if self.last_message_at else None,
            'total_message_count': self.total_message_count,
            'user_message_count': self.user_message_count,
            'agent_message_count': self.agent_message_count,
            'status': self.status
        }

class ChatMessage(Base):
    """聊天记录表模型"""
    __tablename__ = 'chat_messages'
    
    # 消息ID (主键)
    message_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # 会话ID (外键)
    session_id = Column(String(36), ForeignKey('chat_sessions.session_id'), nullable=False, index=True)
    
    # 消息发送方 (user, agent, system, tool)
    sender_type = Column(String(20), nullable=False, index=True)
    
    # 消息内容
    message_content = Column(Text, nullable=True)
    
    # 是否为工具查询消息
    is_tool_query = Column(Boolean, nullable=False, default=False)
    
    # 工具查询结果
    tool_query_result = Column(Text, nullable=True)
    
    # 使用的工具名称
    tool_name = Column(String(100), nullable=True)
    
    # 工具查询参数
    tool_parameters = Column(Text, nullable=True)
    
    # 消息发送时间
    created_at = Column(DateTime, nullable=False, default=datetime.now, index=True)
    
    # 消息序号 (在会话中的顺序)
    message_order = Column(Integer, nullable=False)
    
    # 消息元数据 (JSON格式存储额外信息)
    extra_metadata = Column(Text, nullable=True)
    
    # 关联的会话
    session = relationship("ChatSession", back_populates="messages")
    
    # 索引
    __table_args__ = (
        Index('idx_session_order', 'session_id', 'message_order'),
        Index('idx_session_created', 'session_id', 'created_at'),
        Index('idx_sender_created', 'sender_type', 'created_at'),
        Index('idx_tool_query', 'is_tool_query', 'created_at'),
    )
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'message_id': self.message_id,
            'session_id': self.session_id,
            'sender_type': self.sender_type,
            'message_content': self.message_content,
            'is_tool_query': self.is_tool_query,
            'tool_query_result': self.tool_query_result,
            'tool_name': self.tool_name,
            'tool_parameters': self.tool_parameters,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'message_order': self.message_order,
            'message_metadata': self.extra_metadata
        }
    
    def to_conversation_format(self):
        """转换为对话格式"""
        return {
            'type': self.sender_type,
            'content': self.message_content or '',
            'timestamp': self.created_at.isoformat() if self.created_at else None,
            'metadata': {
                'message_id': self.message_id,
                'is_tool_query': self.is_tool_query,
                'tool_name': self.tool_name,
                'tool_query_result': self.tool_query_result,
                'tool_parameters': self.tool_parameters,
                'message_order': self.message_order,
                'extra_metadata': self.extra_metadata
            }
        } 