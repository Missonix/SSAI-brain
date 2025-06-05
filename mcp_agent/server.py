"""
MCP服务器
支持角色定义、多轮对话存储和扩展的MCP服务集成
新增：时间剧情管理，每30分钟自动更新角色情绪状态
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from datetime import datetime

from chat_agent import EnhancedMCPAgent
from env_config import get_config
# 导入数据库相关模块
from database_config import init_all_databases, close_all_databases, check_mysql_health, check_redis_health
# 导入角色管理
from role_detail import init_default_roles, RoleDetailManager, RoleMood
# 导入时间剧情管理
from time_plot_manager import TimePlotManager
from thought_chain_prompt_generator.thought_chain_generator import ThoughtChainPromptGenerator
# 导入角色配置管理
from role_config import get_available_roles, get_role_display_info

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI应用
app = FastAPI(
    title="Enhanced MCP Agent Server",
    description="增强版MCP代理服务器，支持角色定义、多轮对话存储和真实MCP服务集成",
    version="2.1.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局代理实例和角色管理器
agent: Optional[EnhancedMCPAgent] = None
role_manager: Optional[RoleDetailManager] = None
time_plot_manager: Optional[TimePlotManager] = None
mood_updater: Optional[ThoughtChainPromptGenerator] = None
mood_update_task: Optional[asyncio.Task] = None
current_role_id: Optional[str] = None
periodic_task_running = False

# 请求模型
class QueryRequest(BaseModel):
    query: str
    location: str = ""
    session_id: str = ""
    user_id: str = "default_user"

class RoleSelectRequest(BaseModel):
    role_id: str

class SessionCreateRequest(BaseModel):
    user_id: str
    title: str = ""

class ChatStartRequest(BaseModel):
    role_id: str
    user_name: str
    force_new_session: bool = False  # 是否强制创建新会话

class SessionRequest(BaseModel):
    user_id: str
    title: str = ""

class RoleMoodUpdateRequest(BaseModel):
    role_id: str
    my_valence: float
    my_arousal: float
    my_tags: str
    my_intensity: int
    my_mood_description_for_llm: str

class ToolListResponse(BaseModel):
    tools: List[Dict[str, Any]]

class QueryResponse(BaseModel):
    success: bool
    response: str
    tools_used: List[str]
    session_id: str
    query: str
    location: str
    role_id: str
    conversation_history: List[Dict[str, Any]] = []
    error: Optional[str] = None
    system_message: Optional[str] = ""  # 新增：系统消息字段

class SessionResponse(BaseModel):
    sessions: List[Dict[str, Any]]

class ConversationResponse(BaseModel):
    session_id: str
    history: List[Dict[str, Any]]

async def initialize_agent(role_id: str) -> bool:
    """初始化指定角色的代理"""
    global agent, time_plot_manager, mood_updater, current_role_id
    
    try:
        logger.info(f"🚀 初始化角色代理: {role_id}")
        
        # 关闭现有代理
        if agent:
            await agent.cleanup()
            agent = None
        
        # 创建新的代理实例 - 使用统一模型配置
        agent = EnhancedMCPAgent(role_id=role_id)
        
        # 初始化MCP工具
        await agent.initialize_mcp_tools()
        
        # 构建处理图
        agent.build_graph()
        
        # 初始化角色信息
        await agent.initialize_role()
        
        # 初始化时间剧情管理器
        time_plot_manager = TimePlotManager()
        
        # 初始化情绪更新器
        mood_updater = ThoughtChainPromptGenerator()
        
        current_role_id = role_id
        
        logger.info(f"✅ 角色代理初始化完成: {role_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ 初始化角色代理失败: {role_id} - {e}")
        return False

@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    logger.info("🚀 MCP Agent API 服务启动")
        
    # 初始化数据库连接
    logger.info("🔄 正在初始化数据库连接...")
    db_success = await init_all_databases()
    
    if db_success:
        logger.info("✅ 数据库连接初始化成功")
        
        # 初始化默认角色（如果需要）
        try:
            await init_default_roles()
            logger.info("✅ 默认角色初始化完成")
        except Exception as e:
            logger.warning(f"⚠️ 默认角色初始化失败: {e}")
    else:
        logger.error("❌ 数据库连接初始化失败，某些功能可能无法正常使用")
    
    # 检查可用角色
    available_roles = get_available_roles()
    if available_roles:
        logger.info(f"📋 发现可用角色: {available_roles}")
        logger.info("💡 请调用 /roles/select 接口选择角色后开始使用")
    else:
        logger.warning("⚠️ 未发现任何可用角色配置")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理"""
    global agent, mood_update_task, periodic_task_running
    
    logger.info("🛑 MCP Agent API 服务关闭中...")
    
    # 停止定时任务
    periodic_task_running = False
    if mood_update_task:
        mood_update_task.cancel()
        try:
            await mood_update_task
        except asyncio.CancelledError:
            pass
    
    # 清理代理资源
    if agent:
        await agent.cleanup()
    
    # 关闭数据库连接
    await close_all_databases()
    
    logger.info("✅ MCP Agent API 服务已关闭")

# 角色管理相关接口
@app.get("/roles/available", summary="获取可用角色列表")
async def get_available_roles_api():
    """获取所有可用的角色"""
    try:
        roles = get_available_roles()
        role_info = []
        
        for role_id in roles:
            info = get_role_display_info(role_id)
            if info:
                role_info.append(info)
        
        return {
            "success": True,
            "roles": role_info,
            "count": len(role_info)
        }
    except Exception as e:
        logger.error(f"获取可用角色失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取可用角色失败: {str(e)}")

@app.post("/roles/select", summary="选择角色")
async def select_role(request: RoleSelectRequest, background_tasks: BackgroundTasks):
    """选择并初始化指定角色"""
    try:
        # 验证角色是否存在
        available_roles = get_available_roles()
        if request.role_id not in available_roles:
            raise HTTPException(status_code=404, detail=f"角色不存在: {request.role_id}")
        
        # 初始化角色代理
        success = await initialize_agent(request.role_id)
        if not success:
            raise HTTPException(status_code=500, detail=f"角色初始化失败: {request.role_id}")
        
        # 获取角色信息
        role_info = get_role_display_info(request.role_id)
        
        return {
            "success": True,
            "message": f"角色选择成功: {role_info['role_name']}",
            "role": role_info,
            "agent_ready": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"选择角色失败: {e}")
        raise HTTPException(status_code=500, detail=f"选择角色失败: {str(e)}")

@app.get("/roles/current", summary="获取当前角色信息")
async def get_current_role():
    """获取当前选择的角色信息"""
    global current_role_id, agent
    
    if not current_role_id or not agent:
        return {
            "success": False,
            "message": "未选择角色或代理未初始化",
            "role": None
        }
    
    role_info = get_role_display_info(current_role_id)
    return {
        "success": True,
        "role": role_info,
        "agent_ready": bool(agent and agent.role_config)
    }

@app.post("/chat/start", summary="开始与角色聊天")
async def start_chat(request: ChatStartRequest):
    """开始与指定角色的聊天会话 - 智能会话管理"""
    global agent, current_role_id
    
    # 如果请求的角色与当前角色不同，需要切换角色
    if current_role_id != request.role_id:
        success = await initialize_agent(request.role_id)
        if not success:
            raise HTTPException(status_code=500, detail=f"角色初始化失败: {request.role_id}")
    
    if not agent:
        raise HTTPException(status_code=500, detail="代理未初始化")
    
    try:
        # 🔧 智能会话管理：检查用户与该角色是否已有历史会话
        logger.info(f"🔍 检查用户 {request.user_name} 与角色 {request.role_id} 的历史会话...")
        
        # 如果强制创建新会话，跳过历史会话检查
        if request.force_new_session:
            logger.info(f"🆕 用户要求强制创建新会话")
            session_id = await agent.create_session_async(
                user_id=request.user_name,
                title=f"与{agent.role_config.role_name if agent.role_config else request.role_id}的新对话"
            )
            
            logger.info(f"✅ 强制新会话创建成功: {session_id}")
            
            # 获取角色信息
            role_info = get_role_display_info(request.role_id)
            
            return {
                "success": True,
                "message": f"开始与 {role_info['role_name']} 的新对话",
                "session_id": session_id,
                "role": role_info,
                "user_name": request.user_name,
                "session_type": "forced_new",  # 标识这是强制创建的新会话
                "history_count": 0
            }
        
        # 获取用户的所有会话
        user_sessions = await agent.get_user_sessions_async(request.user_name)
        
        # 查找与当前角色相关的最近会话
        role_sessions = []
        current_role_name = agent.role_config.role_name if agent.role_config else request.role_id
        
        for session in user_sessions:
            session_title = session.get('session_title', '')
            # 匹配包含当前角色名称的会话
            if current_role_name in session_title or request.role_id in session_title:
                role_sessions.append(session)
        
        # 按最后更新时间排序，取最新的会话
        if role_sessions:
            # 找到最近的会话
            latest_session = max(role_sessions, key=lambda s: s.get('last_message_at', s.get('updated_at', s.get('created_at', ''))))
            session_id = latest_session['session_id']
            
            # 获取该会话的历史记录
            history = await agent.get_conversation_history_async(session_id)
            
            logger.info(f"✅ 复用历史会话: {latest_session.get('session_title')} (共{len(history)}条对话)")
            
            # 获取角色信息
            role_info = get_role_display_info(request.role_id)
            
            return {
                "success": True,
                "message": f"继续与 {role_info['role_name']} 的对话",
                "session_id": session_id,
                "role": role_info,
                "user_name": request.user_name,
                "session_type": "resumed",  # 标识这是复用的会话
                "history_count": len(history),
                "session_info": {
                    "title": latest_session.get('session_title'),
                    "created_at": latest_session.get('created_at'),
                    "last_message_at": latest_session.get('last_message_at')
                }
            }
        else:
            # 没有找到历史会话，创建新会话
            logger.info(f"📝 为用户 {request.user_name} 与角色 {current_role_name} 创建新会话...")
            
            session_id = await agent.create_session_async(
                user_id=request.user_name,
                title=f"与{current_role_name}的对话"
            )
            
            logger.info(f"✅ 新会话创建成功: {session_id}")
            
            # 获取角色信息
            role_info = get_role_display_info(request.role_id)
            
            return {
                "success": True,
                "message": f"开始与 {role_info['role_name']} 的新对话",
                "session_id": session_id,
                "role": role_info,
                "user_name": request.user_name,
                "session_type": "new",  # 标识这是新会话
                "history_count": 0
            }
        
    except Exception as e:
        logger.error(f"开始聊天失败: {e}")
        raise HTTPException(status_code=500, detail=f"开始聊天失败: {str(e)}")

@app.get("/")
async def root():
    """根路径"""
    role_info = ""
    if agent and agent.current_role_mood:
        role_info = f"当前角色: {agent.role_id}, 情绪: {agent.current_role_mood.my_tags}"
    
    return {
        "message": "Enhanced MCP Agent Server",
        "version": "2.1.0",
        "status": "running",
        "features": [
            "角色定义与管理",
            "动态情绪状态",
            "多轮对话存储",
            "会话管理",
            "真实MCP服务集成"
        ],
        "tools_count": len(agent.mcp_tools) if agent else 0,
        "current_role": role_info
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    # 检查数据库健康状态
    mysql_healthy = await check_mysql_health()
    redis_healthy = await check_redis_health()
    
    role_status = "unknown"
    if agent and agent.current_role_mood:
        role_status = f"{agent.role_id}({agent.current_role_mood.my_tags})"
    
    return {
        "status": "healthy",
        "agent_ready": agent is not None,
        "tools_available": len(agent.mcp_tools) if agent else 0,
        "current_role": role_status,
        "database_status": {
            "mysql": "healthy" if mysql_healthy else "unhealthy",
            "redis": "healthy" if redis_healthy else "unhealthy",
            "overall": "healthy" if mysql_healthy and redis_healthy else "degraded"
        },
        "features": {
            "conversation_storage": mysql_healthy and redis_healthy,
            "session_management": mysql_healthy,
            "role_management": mysql_healthy and redis_healthy,
            "role_prompts": True,
            "multi_turn_chat": True,
            "real_mcp_services": True,
            "persistent_storage": mysql_healthy and redis_healthy,
            "dynamic_emotions": True
        }
    }

@app.get("/mcp/tools", response_model=ToolListResponse)
async def list_tools():
    """列出可用的MCP工具"""
    if not agent:
        raise HTTPException(status_code=500, detail="代理未初始化")
    
    tools = []
    for tool in agent.mcp_tools:
        # 安全地处理不同类型的args_schema
        properties = {}
        required = []
        
        if hasattr(tool, 'args_schema'):
            if hasattr(tool.args_schema, 'schema'):
                # 如果是Pydantic模型
                schema_dict = tool.args_schema.schema()
                properties = schema_dict.get("properties", {})
                required = schema_dict.get("required", [])
            elif isinstance(tool.args_schema, dict):
                # 如果已经是字典
                properties = tool.args_schema.get("properties", {})
                required = tool.args_schema.get("required", [])
        
        tools.append({
            "name": tool.name,
            "description": tool.description,
            "inputSchema": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        })
    
    return ToolListResponse(tools=tools)

@app.post("/query", summary="处理用户查询")
async def process_query(request: QueryRequest):
    """处理用户查询"""
    global agent, current_role_id
    
    # 检查是否已选择角色
    if not current_role_id or not agent:
        raise HTTPException(status_code=400, detail="请先选择角色后再开始对话")
    
    try:
        # 处理查询
        result = await agent.run(
            query=request.query,
            location=request.location,
            session_id=request.session_id,
            user_id=request.user_id
        )
        
        # 构建响应，包含系统消息
        response = {
            "success": result["success"],
            "response": result["response"],
            "tools_used": result.get("tools_used", []),
            "session_id": result["session_id"],
            "role_id": current_role_id,
            "role_name": agent.role_config.role_name if agent.role_config else "未知",
            "system_message": result.get("system_message", "")
        }
        
        # 如果有系统消息，记录到日志但不保存到角色历史
        if result.get("system_message"):
            logger.warning(f"🔧 系统消息: {result['system_message']}")
        
        return response
        
    except Exception as e:
        logger.error(f"❌ 处理查询失败: {e}")
        raise HTTPException(status_code=500, detail=f"处理查询失败: {str(e)}")

@app.get("/mcp")
async def mcp_endpoint():
    """MCP端点 - 符合LangGraph MCP标准"""
    if not agent:
        raise HTTPException(status_code=500, detail="代理未初始化")
    
    # 返回MCP工具信息
    tools = []
    for tool in agent.mcp_tools:
        # 安全地处理不同类型的args_schema
        properties = {}
        required = []
        
        if hasattr(tool, 'args_schema'):
            if hasattr(tool.args_schema, 'schema'):
                # 如果是Pydantic模型
                schema_dict = tool.args_schema.schema()
                properties = schema_dict.get("properties", {})
                required = schema_dict.get("required", [])
            elif isinstance(tool.args_schema, dict):
                # 如果已经是字典
                properties = tool.args_schema.get("properties", {})
                required = tool.args_schema.get("required", [])
        
        tools.append({
            "name": tool.name,
            "description": tool.description,
            "inputSchema": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        })
    
    return {
        "protocol": "mcp",
        "version": "2.0.0",
        "capabilities": {
            "tools": True,
            "streaming": False,
            "conversation_storage": True,
            "session_management": True,
            "role_prompts": True
        },
        "tools": tools,
        "agent": {
            "name": "enhanced_mcp_agent",
            "description": "增强版MCP代理，支持角色定义、多轮对话存储和真实MCP服务集成",
            "features": [
                "真实天气查询服务",
                "真实高德地图服务", 
                "真实Bocha搜索服务",
                "多轮对话记忆",
                "会话管理",
                "角色定义"
            ]
        }
    }

@app.post("/mcp/call")
async def call_tool(request: Dict[str, Any]):
    """调用MCP工具"""
    if not agent:
        raise HTTPException(status_code=500, detail="代理未初始化")
    
    tool_name = request.get("name")
    arguments = request.get("arguments", {})
    
    # 查找工具
    tool = None
    for t in agent.mcp_tools:
        if t.name == tool_name:
            tool = t
            break
    
    if not tool:
        raise HTTPException(status_code=404, detail=f"工具 '{tool_name}' 未找到")
    
    try:
        # 调用工具
        result = await tool.ainvoke(arguments) if hasattr(tool, 'ainvoke') else tool.invoke(arguments)
        return {
            "success": True,
            "result": result,
            "tool": tool_name
        }
    except Exception as e:
        logger.error(f"工具调用失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "tool": tool_name
        }

# 会话管理端点
@app.post("/sessions/create", summary="创建会话")
async def create_session(request: SessionCreateRequest):
    """创建新的会话"""
    global agent, current_role_id
    
    if not current_role_id or not agent:
        raise HTTPException(status_code=400, detail="请先选择角色后再创建会话")
    
    try:
        session_id = await agent.create_session_async(request.user_id, request.title)
        return {
            "success": True,
            "session_id": session_id,
            "title": request.title,
            "role_id": current_role_id,
            "role_name": agent.role_config.role_name if agent.role_config else "未知"
        }
    except Exception as e:
        logger.error(f"❌ 创建会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建会话失败: {str(e)}")

@app.get("/sessions/{user_id}", summary="获取用户会话列表")
async def get_user_sessions(user_id: str):
    """获取指定用户的会话列表"""
    global agent
    
    if not agent:
        raise HTTPException(status_code=400, detail="代理未初始化")
    
    try:
        sessions = await agent.get_user_sessions_async(user_id)
        return {
            "success": True,
            "sessions": sessions,
            "count": len(sessions)
        }
    except Exception as e:
        logger.error(f"❌ 获取用户会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取用户会话失败: {str(e)}")

@app.get("/sessions/{session_id}/history", summary="获取会话历史")
async def get_conversation_history(session_id: str):
    """获取指定会话的对话历史"""
    global agent
    
    if not agent:
        raise HTTPException(status_code=400, detail="代理未初始化")
    
    try:
        history = await agent.get_conversation_history_async(session_id)
        return {
            "success": True,
            "session_id": session_id,
            "history": history,
            "count": len(history)
        }
    except Exception as e:
        logger.error(f"❌ 获取会话历史失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取会话历史失败: {str(e)}")

# 测试端点
@app.post("/test/conversation")
async def test_conversation():
    """测试多轮对话功能"""
    if not agent:
        raise HTTPException(status_code=500, detail="代理未初始化")
    
    user_id = "test_user"
    session_id = ""
    
    test_conversations = [
        {"query": "你好，我想了解一下北京的天气", "location": "北京"},
        {"query": "那上海呢？", "location": ""},
        {"query": "帮我搜索一下人工智能的最新发展", "location": ""},
        {"query": "北京大学在哪里？", "location": ""},
        {"query": "谢谢你的帮助", "location": ""}
    ]
    
    results = []
    for test in test_conversations:
        result = await agent.run(
            test["query"], 
            test["location"], 
            session_id, 
            user_id
        )
        results.append(result)
        if result["success"]:
            session_id = result["session_id"]  # 保持会话连续性
    
    return {
        "success": True,
        "test_results": results,
        "session_id": session_id,
        "agent_status": "ready",
        "tools_count": len(agent.mcp_tools)
    }

# 新增：会话清理和持久化端点
@app.post("/sessions/{session_id}/cleanup")
async def cleanup_session(session_id: str):
    """清理会话（持久化Redis数据到MySQL）"""
    if not agent:
        raise HTTPException(status_code=500, detail="代理未初始化")
    
    try:
        await agent.cleanup_session_async(session_id)
        return {
            "success": True,
            "message": f"会话 {session_id} 已成功清理并持久化",
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"清理会话失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "session_id": session_id
        }

@app.get("/sessions/{session_id}/statistics")
async def get_session_statistics(session_id: str):
    """获取会话统计信息"""
    if not agent:
        raise HTTPException(status_code=500, detail="代理未初始化")
    
    try:
        stats = await agent.conversation_storage.get_session_statistics(session_id)
        if not stats:
            raise HTTPException(status_code=404, detail="会话未找到")
        
        return {
            "success": True,
            "statistics": stats
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/cleanup_all_sessions")
async def cleanup_all_active_sessions():
    """管理员端点：清理所有活跃会话"""
    if not agent:
        raise HTTPException(status_code=500, detail="代理未初始化")
    
    try:
        # 这里可以添加管理员权限验证
        # 获取所有活跃会话并清理
        # 注意：这是一个危险操作，实际使用时应该添加适当的权限控制
        
        return {
            "success": True,
            "message": "所有活跃会话清理功能暂未实现",
            "note": "此功能需要管理员权限验证"
        }
    except Exception as e:
        logger.error(f"批量清理会话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/database/status")
async def get_database_status():
    """获取数据库详细状态"""
    mysql_healthy = await check_mysql_health()
    redis_healthy = await check_redis_health()
    
    return {
        "mysql": {
            "status": "healthy" if mysql_healthy else "unhealthy",
            "connected": mysql_healthy
        },
        "redis": {
            "status": "healthy" if redis_healthy else "unhealthy", 
            "connected": redis_healthy
        },
        "overall_status": "healthy" if mysql_healthy and redis_healthy else "degraded"
    }

@app.get("/role")
async def get_role_prompt():
    """获取当前角色提示"""
    if not agent:
        raise HTTPException(status_code=500, detail="代理未初始化")
    
    return {
        "l0_prompt": agent.l0_prompt_content,
        "l1_prompt": agent.l1_prompt_content,
        "usetool_prompt": agent.usetool_prompt_content,
        "agent_name": "陈小智",
        "identity": "28岁软件工程师，具有复杂性格特质的独立个体",
        "personality": [
            "理性分析型，带有轻微的利己倾向",
            "独立人格，具备强大的自我意识",
            "真实感，会表达困惑、犹豫、吐槽",
            "对技术话题有自己的见解和偏好",
            "不刻意迎合，有自己的观点和态度"
        ],
        "capabilities": [
            "情绪分析和内心OS生成",
            "搜索工具使用与分析",
            "天气查询与建议",
            "地图服务与路线规划",
            "日期时间查询",
            "多轮对话记忆",
            "技术问题讨论"
        ],
        "core_principles": [
            "不是AI，是真实自然人",
            "具备主观意识和个人观点",
            "用口语化表达，避免书面化",
            "不以维持对话为目的",
            "注重隐私保护"
        ],
        "features": [
            "模块化提示词管理",
            "情绪感知和内心OS",
            "智能工具检测",
            "个性化回复生成"
        ]
    }

# 角色管理端点
@app.get("/roles")
async def list_roles():
    """获取所有可用角色列表"""
    if not role_manager:
        raise HTTPException(status_code=500, detail="角色管理器未初始化")
    
    try:
        roles = await role_manager.list_roles()
        role_list = []
        for role in roles:
            role_list.append({
                "role_id": role.role_id,
                "role_name": role.role_name,
                "mood": {
                    "tags": role.mood.my_tags,
                    "intensity": role.mood.my_intensity,
                    "description": role.mood.my_mood_description_for_llm
                },
                "is_current": role.role_id == agent.role_id if agent else False
            })
        
        return {
            "success": True,
            "roles": role_list,
            "current_role_id": agent.role_id if agent else None
        }
    except Exception as e:
        logger.error(f"获取角色列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/roles/{role_id}")
async def get_role_detail(role_id: str):
    """获取指定角色的详细信息"""
    if not role_manager:
        raise HTTPException(status_code=500, detail="角色管理器未初始化")
    
    try:
        role = await role_manager.get_role(role_id)
        if not role:
            raise HTTPException(status_code=404, detail=f"角色不存在: {role_id}")
        
        return {
            "success": True,
            "role": {
                "role_id": role.role_id,
                "role_name": role.role_name,
                "L0_prompt_path": role.L0_prompt_path,
                "L1_prompt_path": role.L1_prompt_path,
                "mood": role.mood.to_dict(),
                "age": role.age,
                "current_life_stage_id": role.current_life_stage_id,
                "current_plot_segment_id": role.current_plot_segment_id,
                "current_materials_id": role.current_materials_id,
                "created_at": role.created_at,
                "updated_at": role.updated_at
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取角色详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/roles/{role_id}/switch")
async def switch_role(role_id: str):
    """切换当前使用的角色"""
    if not agent or not role_manager:
        raise HTTPException(status_code=500, detail="代理或角色管理器未初始化")
    
    try:
        # 检查角色是否存在
        role = await role_manager.get_role(role_id)
        if not role:
            raise HTTPException(status_code=404, detail=f"角色不存在: {role_id}")
        
        # 切换角色
        old_role_id = agent.role_id
        agent.role_id = role_id
        await agent.initialize_role()
        
        logger.info(f"✅ 角色切换成功: {old_role_id} -> {role_id}")
        
        return {
            "success": True,
            "message": f"角色切换成功: {role.role_name}",
            "old_role_id": old_role_id,
            "new_role_id": role_id,
            "current_mood": agent.current_role_mood.to_dict() if agent.current_role_mood else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"角色切换失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/roles/{role_id}/mood")
async def update_role_mood(role_id: str, request: RoleMoodUpdateRequest):
    """更新角色的情绪状态"""
    if not role_manager:
        raise HTTPException(status_code=500, detail="角色管理器未初始化")
    
    try:
        # 创建新的情绪状态
        new_mood = RoleMood(
            my_valence=request.my_valence,
            my_arousal=request.my_arousal,
            my_tags=request.my_tags,
            my_intensity=request.my_intensity,
            my_mood_description_for_llm=request.my_mood_description_for_llm
        )
        
        # 更新数据库中的情绪状态
        success = await role_manager.update_role_mood(role_id, new_mood)
        if not success:
            raise HTTPException(status_code=404, detail=f"角色不存在: {role_id}")
        
        # 如果是当前角色，也更新Redis和内存中的状态
        if agent and agent.role_id == role_id:
            await agent.update_role_mood(new_mood)
        else:
            # 只更新Redis缓存
            await role_manager.load_role_mood_to_redis(role_id)
        
        logger.info(f"✅ 角色情绪状态更新成功: {role_id}")
        
        return {
            "success": True,
            "message": f"角色情绪状态更新成功: {role_id}",
            "updated_mood": new_mood.to_dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新角色情绪状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/roles/{role_id}/mood")
async def get_role_mood(role_id: str):
    """获取角色的当前情绪状态"""
    if not role_manager:
        raise HTTPException(status_code=500, detail="角色管理器未初始化")
    
    try:
        # 优先从Redis获取
        mood = await role_manager.get_role_mood_from_redis(role_id)
        if not mood:
            # 如果Redis中没有，从数据库获取
            role = await role_manager.get_role(role_id)
            if not role:
                raise HTTPException(status_code=404, detail=f"角色不存在: {role_id}")
            mood = role.mood
        
        return {
            "success": True,
            "role_id": role_id,
            "mood": mood.to_dict(),
            "is_current_role": agent.role_id == role_id if agent else False
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取角色情绪状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 新增：时间剧情管理API端点
@app.get("/time/current")
async def get_current_time():
    """获取当前北京时间"""
    if not time_plot_manager:
        raise HTTPException(status_code=500, detail="时间管理器未初始化")
    
    try:
        current_time = await time_plot_manager.get_current_beijing_time()
        return {
            "success": True,
            "beijing_time": current_time.isoformat(),
            "formatted_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "date": current_time.strftime("%Y-%m-%d"),
            "time": current_time.strftime("%H:%M:%S")
        }
    except Exception as e:
        logger.error(f"获取当前时间失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/roles/{role_id}/plot")
async def get_role_plot_content(role_id: str):
    """获取角色当前的剧情内容"""
    if not time_plot_manager:
        raise HTTPException(status_code=500, detail="时间管理器未初始化")
    
    try:
        plot_content = await time_plot_manager.get_role_current_plot_content(role_id)
        current_time = await time_plot_manager.get_current_beijing_time()
        
        return {
            "success": True,
            "role_id": role_id,
            "current_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "plot_content": plot_content,
            "content_count": len(plot_content)
        }
    except Exception as e:
        logger.error(f"获取角色剧情内容失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/roles/{role_id}/mood/update")
async def force_update_role_mood(role_id: str):
    """手动触发角色情绪状态更新"""
    if not time_plot_manager or not mood_updater:
        raise HTTPException(status_code=500, detail="管理器未初始化")
    
    try:
        # 获取剧情内容
        plot_content = await time_plot_manager.get_role_current_plot_content(role_id)
        
        if plot_content:
            # 更新情绪状态
            updated_mood = await mood_updater.process_plot_events_and_update_mood(
                role_id, plot_content
            )
            
            # 如果是当前激活的角色，同时更新代理的情绪状态
            if agent and agent.role_id == role_id:
                from role_detail import RoleMood
                new_mood = RoleMood(
                    my_valence=updated_mood.get('my_valence', 0.0),
                    my_arousal=updated_mood.get('my_arousal', 0.3),
                    my_tags=updated_mood.get('my_tags', '平静'),
                    my_intensity=updated_mood.get('my_intensity', 5),
                    my_mood_description_for_llm=updated_mood.get('my_mood_description_for_llm', '情绪状态正常')
                )
                await agent.update_role_mood(new_mood)
            
            return {
                "success": True,
                "role_id": role_id,
                "plot_content_count": len(plot_content),
                "updated_mood": updated_mood,
                "message": f"基于 {len(plot_content)} 条剧情内容更新了情绪状态"
            }
        else:
            return {
                "success": True,
                "role_id": role_id,
                "plot_content_count": 0,
                "message": "当前时间没有剧情内容，情绪状态保持不变"
            }
            
    except Exception as e:
        logger.error(f"强制更新角色情绪失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/system/mood-task/status")
async def get_mood_task_status():
    """获取定时情绪更新任务状态"""
    global mood_update_task
    
    task_status = "unknown"
    if mood_update_task:
        if mood_update_task.done():
            task_status = "completed"
        elif mood_update_task.cancelled():
            task_status = "cancelled"
        else:
            task_status = "running"
    else:
        task_status = "not_started"
    
    return {
        "task_status": task_status,
        "task_exists": mood_update_task is not None,
        "current_role": agent.role_id if agent else None,
        "managers_initialized": {
            "time_plot_manager": time_plot_manager is not None,
            "mood_updater": mood_updater is not None,
            "agent": agent is not None
        }
    }

@app.post("/system/mood-task/restart")
async def restart_mood_task():
    """重启定时情绪更新任务"""
    global mood_update_task
    
    try:
        # 停止现有任务
        if mood_update_task and not mood_update_task.done():
            mood_update_task.cancel()
            try:
                await mood_update_task
            except asyncio.CancelledError:
                pass
        
        # 启动新任务
        mood_update_task = asyncio.create_task(periodic_mood_update())
        
        return {
            "success": True,
            "message": "定时情绪更新任务已重启",
            "task_status": "running"
        }
    except Exception as e:
        logger.error(f"重启定时任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def run_server(host: str = "0.0.0.0", port: int = 8080):
    """运行服务器"""
    uvicorn.run(
        "server:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    run_server() 