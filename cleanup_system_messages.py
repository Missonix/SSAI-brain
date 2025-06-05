#!/usr/bin/env python3
"""
清理系统错误消息脚本
删除已经错误存储在角色历史聊天记录中的系统错误消息
"""

import asyncio
import logging
import json
import sys
import os
import redis.asyncio as redis

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mcp_agent'))

from mcp_agent.database_config import get_mysql_session, get_redis_client

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 需要清理的系统错误消息模式
SYSTEM_ERROR_PATTERNS = [
    "服务器暂时无法处理您的请求，请稍后再试",
    "AI服务暂时有点问题",
    "Google AI服务出现了一些问题",
    "遇到了一些技术问题",
    "⚠️ 地理位置限制",
    "⚠️ 网络连接错误", 
    "⚠️ 响应超时",
    "⚠️ API服务错误",
    "⚠️ Google AI服务错误",
    "⚠️ 系统错误",
    "网络连接好像有点问题",
    "响应有点慢，可能是网络问题",
    "AI服务暂时有点问题，可能是配额限制",
    "哈哈，看起来我这边的AI服务有点地理位置限制的问题"
]

async def cleanup_mysql_messages():
    """清理MySQL中的系统错误消息"""
    logger.info("🔄 开始清理MySQL中的系统错误消息...")
    
    try:
        from sqlalchemy import text
        deleted_count = 0
        
        async with get_mysql_session() as session:
            # 遍历每个错误模式
            for pattern in SYSTEM_ERROR_PATTERNS:
                # 查找匹配的消息
                query = text("""
                    SELECT message_id, session_id, message_content 
                    FROM conversation_messages 
                    WHERE sender_type = 'agent' 
                    AND message_content LIKE :pattern
                """)
                
                result = await session.execute(query, {"pattern": f"%{pattern}%"})
                messages = result.fetchall()
                
                if messages:
                    logger.info(f"发现 {len(messages)} 条包含模式 '{pattern}' 的消息")
                    
                    # 删除这些消息
                    for message in messages:
                        message_id, session_id, content = message
                        
                        delete_query = text("DELETE FROM conversation_messages WHERE message_id = :message_id")
                        await session.execute(delete_query, {"message_id": message_id})
                        
                        logger.info(f"删除消息 {message_id}: {content[:50]}...")
                        deleted_count += 1
            
            # 提交事务
            await session.commit()
        
        logger.info(f"✅ MySQL清理完成，共删除 {deleted_count} 条系统错误消息")
        return deleted_count
        
    except Exception as e:
        logger.error(f"❌ MySQL清理失败: {e}")
        return 0

async def cleanup_redis_messages():
    """清理Redis中的系统错误消息"""
    logger.info("🔄 开始清理Redis中的系统错误消息...")
    
    try:
        redis_client = await get_redis_client()
        
        # 获取所有session键
        session_keys = await redis_client.keys("session:*:messages")
        deleted_count = 0
        
        for session_key in session_keys:
            try:
                # 获取该session的所有消息
                messages = await redis_client.lrange(session_key, 0, -1)
                
                new_messages = []
                for msg_data in messages:
                    try:
                        # 解析消息
                        if isinstance(msg_data, bytes):
                            msg_str = msg_data.decode('utf-8')
                        else:
                            msg_str = str(msg_data)
                        
                        msg = json.loads(msg_str)
                        
                        # 检查是否是系统错误消息
                        is_system_error = False
                        if msg.get('sender_type') == 'agent':
                            content = msg.get('message_content', '')
                            for pattern in SYSTEM_ERROR_PATTERNS:
                                if pattern in content:
                                    logger.info(f"删除Redis消息: {content[:50]}...")
                                    is_system_error = True
                                    deleted_count += 1
                        
                        # 如果不是系统错误消息，保留
                        if not is_system_error:
                            new_messages.append(msg_data)
                    
                    except (json.JSONDecodeError, Exception) as e:
                        logger.warning(f"解析消息失败，保留原消息: {e}")
                        new_messages.append(msg_data)
                
                # 如果有变化，更新Redis
                if len(new_messages) < len(messages):
                    # 清空原列表
                    await redis_client.delete(session_key)
                    
                    # 重新添加清理后的消息
                    if new_messages:
                        await redis_client.rpush(session_key, *new_messages)
                        # 重新设置过期时间
                        await redis_client.expire(session_key, 86400)
                    
                    logger.info(f"会话 {session_key} 清理完成: {len(messages)} -> {len(new_messages)}")
            
            except Exception as e:
                logger.warning(f"处理会话 {session_key} 失败: {e}")
                continue
        
        logger.info(f"✅ Redis清理完成，共删除 {deleted_count} 条系统错误消息")
        return deleted_count
        
    except Exception as e:
        logger.error(f"❌ Redis清理失败: {e}")
        return 0

async def cleanup_inner_os_leak_messages():
    """清理Redis中包含内心OS泄露的消息"""
    try:
        redis_client = await get_redis_client()
        
        # 获取所有会话键
        session_keys = await redis_client.keys("session:*:messages")
        
        cleaned_count = 0
        total_sessions = len(session_keys)
        
        print(f"🔍 开始检查 {total_sessions} 个会话的消息...")
        
        for session_key in session_keys:
            session_id = session_key.decode('utf-8').split(':')[1] if isinstance(session_key, bytes) else session_key.split(':')[1]
            
            # 获取会话中的所有消息
            messages = await redis_client.lrange(session_key, 0, -1)
            
            for i, msg_json in enumerate(messages):
                try:
                    if isinstance(msg_json, bytes):
                        msg_str = msg_json.decode('utf-8')
                    else:
                        msg_str = str(msg_json)
                    
                    msg = json.loads(msg_str)
                    message_content = msg.get('message_content', '')
                    
                    # 检查是否包含内心OS泄露的模式
                    leak_patterns = [
                        "（稍微", "（解释", "（想想", "（不要透露", "（找个理由", "（态度要",
                        "（然后", "（但不要", "（策略", "（计划", "（内心OS：", "内心OS：",
                        "（内心想法：", "内心想法：", "（心里想：", "心里想："
                    ]
                    
                    has_leak = any(pattern in message_content for pattern in leak_patterns)
                    
                    if has_leak:
                        print(f"🚨 发现问题消息在会话 {session_id}:")
                        print(f"   内容: {message_content[:100]}...")
                        
                        # 删除这条消息
                        await redis_client.lrem(session_key, 1, msg_json)
                        cleaned_count += 1
                        print(f"   ✅ 已删除")
                
                except json.JSONDecodeError:
                    print(f"⚠️ 跳过无效JSON消息: {msg_json[:50]}...")
                except Exception as e:
                    print(f"❌ 处理消息时出错: {e}")
        
        print(f"\n🎉 清理完成！")
        print(f"📊 清理统计:")
        print(f"   - 检查的会话数: {total_sessions}")
        print(f"   - 删除的问题消息数: {cleaned_count}")
        
        await redis_client.close()
        
    except Exception as e:
        print(f"❌ 清理过程中出现错误: {e}")

async def main():
    """主函数"""
    logger.info("🧹 开始清理系统错误消息...")
    
    # 初始化数据库连接
    from mcp_agent.database_config import init_all_databases
    await init_all_databases()
    
    # 清理MySQL
    mysql_count = await cleanup_mysql_messages()
    
    # 清理Redis  
    redis_count = await cleanup_redis_messages()
    
    # 清理包含内心OS泄露的Redis消息
    await cleanup_inner_os_leak_messages()
    
    # 关闭数据库连接
    from mcp_agent.database_config import close_all_databases
    await close_all_databases()
    
    logger.info(f"🎉 清理完成！")
    logger.info(f"   MySQL: 删除 {mysql_count} 条消息")
    logger.info(f"   Redis: 删除 {redis_count} 条消息")
    logger.info(f"   总计: 删除 {mysql_count + redis_count} 条系统错误消息")

if __name__ == "__main__":
    asyncio.run(main()) 