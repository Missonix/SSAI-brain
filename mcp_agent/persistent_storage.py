"""
持久化存储管理器
实现MySQL和Redis的会话和消息存储逻辑
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import select, update, desc, func, text
from sqlalchemy.orm import selectinload

from database_config import get_mysql_session, get_redis_client
from database_models import ChatSession, ChatMessage

logger = logging.getLogger(__name__)

class PersistentConversationStorage:
    """持久化对话存储管理器"""
    
    def __init__(self):
        """初始化持久化存储管理器"""
        self.logger = logging.getLogger(__name__)
        # Redis键前缀
        self.redis_session_prefix = "chat_session:"
        self.redis_messages_prefix = "chat_messages:"
        self.redis_temp_prefix = "temp_chat:"
        
    # ==================== 会话管理 ====================
    
    async def create_session(self, user_name: str, title: str = None) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        now = datetime.now()
        
        try:
            # 在MySQL中创建会话记录
            async with get_mysql_session() as db_session:
                new_session = ChatSession(
                    session_id=session_id,
                    user_name=user_name,
                    session_title=title or f"会话 {now.strftime('%Y-%m-%d %H:%M')}",
                    created_at=now,
                    last_message_at=now,
                    total_message_count=0,
                    user_message_count=0,
                    agent_message_count=0,
                    status='active'
                )
                db_session.add(new_session)
                await db_session.commit()
                
            # 在Redis中初始化会话缓存
            redis_client = await get_redis_client()
            session_data = {
                'session_id': session_id,
                'user_name': user_name,
                'session_title': title or f"会话 {now.strftime('%Y-%m-%d %H:%M')}",
                'created_at': now.isoformat(),
                'last_message_at': now.isoformat(),
                'message_count': 0,
                'status': 'active'
            }
            
            await redis_client.hset(
                f"{self.redis_session_prefix}{session_id}",
                mapping=session_data
            )
            
            # 设置会话过期时间（24小时）
            await redis_client.expire(f"{self.redis_session_prefix}{session_id}", 86400)
            
            # 初始化消息列表
            await redis_client.delete(f"{self.redis_messages_prefix}{session_id}")
            
            self.logger.info(f"✅ 会话创建成功: {session_id} (用户: {user_name})")
            return session_id
            
        except Exception as e:
            self.logger.error(f"❌ 会话创建失败: {e}")
            raise
    
    async def get_user_sessions(self, user_name: str, limit: int = 20) -> List[Dict[str, Any]]:
        """获取用户的所有会话"""
        try:
            async with get_mysql_session() as db_session:
                # 查询用户的会话，按最后消息时间排序
                stmt = select(ChatSession).where(
                    ChatSession.user_name == user_name,
                    ChatSession.status == 'active'
                ).order_by(desc(ChatSession.last_message_at)).limit(limit)
                
                result = await db_session.execute(stmt)
                sessions = result.scalars().all()
                
                return [session.to_dict() for session in sessions]
                
        except Exception as e:
            self.logger.error(f"❌ 获取用户会话失败: {e}")
            return []
    
    async def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        try:
            # 先尝试从Redis获取
            redis_client = await get_redis_client()
            session_data = await redis_client.hgetall(f"{self.redis_session_prefix}{session_id}")
            
            if session_data:
                return session_data
            
            # Redis中没有，从MySQL获取
            async with get_mysql_session() as db_session:
                stmt = select(ChatSession).where(ChatSession.session_id == session_id)
                result = await db_session.execute(stmt)
                session = result.scalar_one_or_none()
                
                if session:
                    return session.to_dict()
                    
            return None
            
        except Exception as e:
            self.logger.error(f"❌ 获取会话信息失败: {e}")
            return None
    
    # ==================== 消息管理 ====================
    
    async def save_message_to_redis(self, session_id: str, user_name: str, 
                                  sender_type: str, message_content: str,
                                  is_tool_query: bool = False, tool_name: str = None,
                                  tool_query_result: str = None, tool_parameters: str = None,
                                  extra_metadata: Dict[str, Any] = None) -> str:
        """保存消息到Redis临时存储"""
        try:
            redis_client = await get_redis_client()
            
            # 生成消息ID
            message_id = str(uuid.uuid4())
            
            # 获取当前会话的消息数量作为序号
            session_key = f"session:{session_id}:messages"
            message_count = await redis_client.llen(session_key)
            
            # 构建消息数据
            message_data = {
                'message_id': message_id,
                'session_id': session_id,
                'user_name': user_name,
                'sender_type': sender_type,
                'message_content': message_content,
                'is_tool_query': is_tool_query,
                'tool_name': tool_name,
                'tool_query_result': tool_query_result,
                'tool_parameters': tool_parameters,
                'message_order': message_count + 1,
                'created_at': datetime.now().isoformat(),
                'extra_metadata': json.dumps(extra_metadata or {})
            }
            
            # 保存到Redis列表
            await redis_client.lpush(session_key, json.dumps(message_data))
            
            # 设置过期时间（24小时）
            await redis_client.expire(session_key, 86400)
            
            self.logger.info(f"[save_message_to_redis] Message saved to Redis: {message_id}")
            return message_id
            
        except Exception as e:
            self.logger.error(f"[save_message_to_redis] Error saving message to Redis: {e}")
            raise
    
    async def get_conversation_history_from_mysql(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """从MySQL获取对话历史"""
        try:
            async with get_mysql_session() as db_session:
                # 查询消息，按消息顺序排序
                stmt = select(ChatMessage).where(
                    ChatMessage.session_id == session_id
                ).order_by(ChatMessage.message_order).limit(limit)
                
                result = await db_session.execute(stmt)
                messages = result.scalars().all()
                
                return [msg.to_conversation_format() for msg in messages]
                
        except Exception as e:
            self.logger.error(f"❌ 从MySQL获取对话历史失败: {e}")
            return []
    
    async def get_conversation_history_from_redis(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """从Redis获取对话历史"""
        try:
            redis_client = await get_redis_client()
            session_key = f"session:{session_id}:messages"
            
            # 获取最近的消息（Redis中是倒序存储的）
            messages_data = await redis_client.lrange(session_key, 0, limit - 1)
            
            conversation_history = []
            for msg_data_str in reversed(messages_data):  # 反转以获得正确的时间顺序
                try:
                    msg_data = json.loads(msg_data_str)
                    conversation_history.append({
                        'type': msg_data['sender_type'],
                        'content': msg_data['message_content'] or '',
                        'timestamp': msg_data['created_at'],
                        'metadata': {
                            'message_id': msg_data['message_id'],
                            'is_tool_query': msg_data.get('is_tool_query', False),
                            'tool_name': msg_data.get('tool_name'),
                            'tool_query_result': msg_data.get('tool_query_result'),
                            'tool_parameters': msg_data.get('tool_parameters'),
                            'message_order': msg_data.get('message_order', 0),
                            'extra_metadata': json.loads(msg_data['extra_metadata']) if msg_data['extra_metadata'] else {}
                        }
                    })
                except json.JSONDecodeError as e:
                    self.logger.error(f"[get_conversation_history_from_redis] JSON decode error: {e}")
                    continue
            
            self.logger.info(f"[get_conversation_history_from_redis] Retrieved {len(conversation_history)} messages from Redis")
            return conversation_history
            
        except Exception as e:
            self.logger.error(f"[get_conversation_history_from_redis] Error retrieving from Redis: {e}")
            return []
    
    async def get_conversation_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取完整对话历史（MySQL + Redis）"""
        try:
            # 先从MySQL获取历史消息
            mysql_messages = await self.get_conversation_history_from_mysql(session_id, limit)
            self.logger.info(f"[get_conversation_history] Retrieved {len(mysql_messages)} messages from MySQL")
            
            # 再从Redis获取当前会话的临时消息
            redis_messages = await self.get_conversation_history_from_redis(session_id, limit)
            self.logger.info(f"[get_conversation_history] Retrieved {len(redis_messages)} messages from Redis")
            
            # 合并消息（去重并按时间排序）
            all_messages = mysql_messages + redis_messages
            
            # 按时间戳排序
            all_messages.sort(key=lambda x: x['timestamp'])
            
            # 去重（基于message_id）
            seen_ids = set()
            unique_messages = []
            for msg in all_messages:
                msg_id = msg['metadata'].get('message_id')
                if msg_id and msg_id not in seen_ids:
                    seen_ids.add(msg_id)
                    unique_messages.append(msg)
                elif not msg_id:  # 没有message_id的消息也保留
                    unique_messages.append(msg)
            
            # 返回最新的limit条消息
            final_messages = unique_messages[-limit:] if len(unique_messages) > limit else unique_messages
            self.logger.info(f"[get_conversation_history] Returning {len(final_messages)} unique messages (MySQL: {len(mysql_messages)}, Redis: {len(redis_messages)})")
            
            return final_messages
            
        except Exception as e:
            self.logger.error(f"❌ 获取对话历史失败: {e}")
            return []
    
    # ==================== 持久化操作 ====================
    
    async def persist_redis_messages_to_mysql(self, session_id: str) -> bool:
        """将Redis中的消息持久化到MySQL"""
        try:
            redis_client = await get_redis_client()
            session_key = f"session:{session_id}:messages"
            
            # 获取所有Redis消息
            messages_data = await redis_client.lrange(session_key, 0, -1)
            
            if not messages_data:
                self.logger.info(f"[persist_redis_messages_to_mysql] No messages to persist for session {session_id}")
                return True
            
            async with get_mysql_session() as session:
                # 获取当前MySQL中该会话的最大消息序号
                result = await session.execute(
                    text("SELECT COALESCE(MAX(message_order), 0) FROM chat_messages WHERE session_id = :session_id"),
                    {"session_id": session_id}
                )
                max_order = result.scalar() or 0
                
                # 处理Redis消息（注意Redis中是倒序存储的）
                messages_to_insert = []
                persisted_message_ids = []
                for i, msg_data_str in enumerate(reversed(messages_data)):
                    try:
                        msg_data = json.loads(msg_data_str)
                        
                        # 检查消息是否已存在
                        msg_id = msg_data.get('message_id')
                        if msg_id:
                            existing = await session.execute(
                                text("SELECT message_id FROM chat_messages WHERE message_id = :message_id"),
                                {"message_id": msg_id}
                            )
                            if existing.scalar():
                                persisted_message_ids.append(msg_id)
                                continue  # 消息已存在，跳过
                        
                        # 准备插入数据
                        message = ChatMessage(
                            message_id=msg_data['message_id'],
                            session_id=session_id,
                            sender_type=msg_data['sender_type'],
                            message_content=msg_data['message_content'],
                            is_tool_query=msg_data.get('is_tool_query', False),
                            tool_query_result=msg_data.get('tool_query_result'),
                            tool_name=msg_data.get('tool_name'),
                            tool_parameters=msg_data.get('tool_parameters'),
                            message_order=max_order + i + 1,
                            created_at=datetime.fromisoformat(msg_data['created_at']),
                            extra_metadata=msg_data['extra_metadata'] if msg_data['extra_metadata'] else None
                        )
                        messages_to_insert.append(message)
                        persisted_message_ids.append(msg_id)
                        
                    except (json.JSONDecodeError, KeyError) as e:
                        self.logger.error(f"[persist_redis_messages_to_mysql] Error processing message: {e}")
                        continue
                
                # 批量插入消息
                if messages_to_insert:
                    session.add_all(messages_to_insert)
                    await session.commit()
                    
                    # 更新会话统计
                    await self._update_session_statistics(session, session_id)
                    
                    self.logger.info(f"[persist_redis_messages_to_mysql] Persisted {len(messages_to_insert)} messages to MySQL")
                
                # 不要立即清理Redis，而是标记已持久化的消息
                # 为已持久化的消息添加标记，但保留在Redis中以便快速访问
                for msg_data_str in messages_data:
                    try:
                        msg_data = json.loads(msg_data_str)
                        msg_id = msg_data.get('message_id')
                        if msg_id in persisted_message_ids:
                            msg_data['persisted_to_mysql'] = True
                            # 更新Redis中的消息数据
                            await redis_client.lrem(session_key, 1, msg_data_str)
                            await redis_client.lpush(session_key, json.dumps(msg_data))
                    except Exception as e:
                        self.logger.error(f"[persist_redis_messages_to_mysql] Error updating Redis message: {e}")
                        continue
                
                # 延长Redis过期时间到2小时，而不是立即删除
                await redis_client.expire(session_key, 7200)
                
                return True
                
        except Exception as e:
            self.logger.error(f"[persist_redis_messages_to_mysql] Error persisting messages: {e}")
            return False
    
    async def cleanup_session(self, session_id: str):
        """清理会话（持久化并删除Redis数据）"""
        try:
            # 持久化消息
            success = await self.persist_redis_messages_to_mysql(session_id)
            
            if success:
                # 清理Redis数据 - 使用正确的键名
                redis_client = await get_redis_client()
                await redis_client.delete(f"session:{session_id}:messages")
                await redis_client.delete(f"{self.redis_session_prefix}{session_id}")
                
                self.logger.info(f"✅ 会话清理完成: {session_id}")
            else:
                self.logger.warning(f"⚠️ 会话持久化失败，保留Redis数据: {session_id}")
                
        except Exception as e:
            self.logger.error(f"❌ 会话清理失败: {e}")
    
    # ==================== 工具消息特殊处理 ====================
    
    async def save_tool_query_message(self, session_id: str, user_name: str,
                                    tool_name: str, tool_parameters: Dict[str, Any],
                                    tool_result: str) -> str:
        """保存工具查询消息"""
        return await self.save_message_to_redis(
            session_id=session_id,
            user_name=user_name,
            sender_type="tool",
            message_content=f"工具调用: {tool_name}",
            is_tool_query=True,
            tool_name=tool_name,
            tool_query_result=tool_result,
            tool_parameters=json.dumps(tool_parameters),
            extra_metadata={'tool_execution': True}
        )
    
    # ==================== 统计和监控 ====================
    
    async def get_session_statistics(self, session_id: str) -> Dict[str, Any]:
        """获取会话统计信息"""
        try:
            async with get_mysql_session() as db_session:
                # 获取会话基本信息
                stmt = select(ChatSession).where(ChatSession.session_id == session_id)
                result = await db_session.execute(stmt)
                session = result.scalar_one_or_none()
                
                if not session:
                    return {}
                
                # 获取消息统计
                msg_stmt = select(
                    func.count(ChatMessage.message_id).label('total_messages'),
                    func.sum(func.case([(ChatMessage.sender_type == 'user', 1)], else_=0)).label('user_messages'),
                    func.sum(func.case([(ChatMessage.sender_type == 'agent', 1)], else_=0)).label('agent_messages'),
                    func.sum(func.case([(ChatMessage.is_tool_query == True, 1)], else_=0)).label('tool_queries')
                ).where(ChatMessage.session_id == session_id)
                
                msg_result = await db_session.execute(msg_stmt)
                stats = msg_result.first()
                
                return {
                    'session_info': session.to_dict(),
                    'message_stats': {
                        'total_messages': stats.total_messages or 0,
                        'user_messages': stats.user_messages or 0,
                        'agent_messages': stats.agent_messages or 0,
                        'tool_queries': stats.tool_queries or 0
                    }
                }
                
        except Exception as e:
            self.logger.error(f"❌ 获取会话统计失败: {e}")
            return {}

    async def _update_session_statistics(self, db_session, session_id: str):
        """更新会话统计信息"""
        try:
            # 计算消息统计
            msg_stats = await db_session.execute(
                text("""
                    SELECT 
                        COUNT(*) as total_count,
                        SUM(CASE WHEN sender_type = 'user' THEN 1 ELSE 0 END) as user_count,
                        SUM(CASE WHEN sender_type = 'agent' THEN 1 ELSE 0 END) as agent_count,
                        MAX(created_at) as last_message_time
                    FROM chat_messages 
                    WHERE session_id = :session_id
                """),
                {"session_id": session_id}
            )
            stats = msg_stats.first()
            
            if stats:
                # 更新会话表
                await db_session.execute(
                    text("""
                        UPDATE chat_sessions 
                        SET 
                            total_message_count = :total_count,
                            user_message_count = :user_count,
                            agent_message_count = :agent_count,
                            last_message_at = :last_message_time
                        WHERE session_id = :session_id
                    """),
                    {
                        "session_id": session_id,
                        "total_count": stats.total_count or 0,
                        "user_count": stats.user_count or 0,
                        "agent_count": stats.agent_count or 0,
                        "last_message_time": stats.last_message_time or datetime.now()
                    }
                )
                await db_session.commit()
                
        except Exception as e:
            self.logger.error(f"[_update_session_statistics] Error updating session statistics: {e}") 