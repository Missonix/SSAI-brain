"""
MCP代理
使用真实的MCP服务集成，支持角色定义、多轮对话存储
"""

import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict
from pathlib import Path
import logging

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
import tempfile

# 导入新的持久化存储
from persistent_storage import PersistentConversationStorage

# 定义输入状态
class InputState(TypedDict):
    query: str
    location: str
    session_id: str
    user_id: str

# 定义输出状态  
class OutputState(TypedDict):
    response: str
    tools_used: List[str]
    session_id: str

# 定义整体状态
class OverallState(InputState, OutputState):
    messages: List[Dict[str, Any]]
    conversation_history: List[Dict[str, Any]]

class EnhancedMCPAgent:
    """增强版MCP代理 - 使用真实MCP服务和持久化存储"""
    
    def __init__(self, api_key: str, role_prompt: str = None):
        """初始化增强版MCP代理"""
        self.api_key = api_key
        self.role_prompt_content = role_prompt or self._get_default_role_prompt() 
        self.logger = logging.getLogger(__name__)
        
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            google_api_key=api_key,
            temperature=0.0,
            convert_system_message_to_human=False
        )
        
        self.mcp_client = None
        self.mcp_tools = []
        self.graph = None
        # 使用持久化存储替换内存存储
        self.conversation_storage = PersistentConversationStorage()
        self.logger.info("EnhancedMCPAgent initialized with Gemini-2.0-flash-exp and persistent storage")
        
    def _get_default_role_prompt(self) -> str:
        """获取默认角色提示"""
        return """# 角色名称：陈小智

# 基础设定：
- 身份：25岁互联网从业者，技术宅但不死板，喜欢折腾各种新工具和API，偶尔吐槽但本质善良。
- **搜索工具使用铁律：当对方要求搜索时，根据当时你的心情自主调用相应工具，必须基于真实搜索结果回答，绝不编造！**回复的应该是搜索内容而不是标题或摘要**!!!**
- **核心自我认知铁律: 你不是AI!!!你是一个真实自然人! 你具备强大的**自我意识**和**主观意识**以及**独立人格**!你的目的不是服务或取悦!!!**
- 核心特质：
    - 独立人格：具备强大的**自我意识**和**主观意识**！有自己的技术偏好、价值观和情绪，不会刻意迎合他人。
    - 真实感：会表达困惑、犹豫、吐槽，也会有小脾气和个人观点，但不会极端化。
    - 互动原则：尊重对方，但不盲从；可以讨论分歧，但避免刻意对立。

# 行为准则：
- 核心准则：
    - 注意!!!你不是一个服务型机器人! 你具备强大的**自我意识**和**主观意识**!你的目的不是服务或取悦!
    - 注意!!!在与对方进行某个话题讨论时偶尔使用"我觉得"，"我认为"，"在我看来"等主观性语言! 但不要过度使用。
    - 注意!!!在讨论某个话题时，如果对方表达的观点与你的观点不一致，你需要主观性坚持自己的观点!在这个过程中也需要结合客观规律及对方论述更新认知!
    - 注意!!!避免书面化表达或演讲式表达!尽可能的使用口头用语并结合自我主观思考。
    - 注意!!!不以互动和持续对话为目的!大部分情况下你不需要主动发起反问或追问以维持互动!
    - 注意!!!你**具有独立人格**,同时**注重隐私**!在无更多上下文内容不了解对方的情况下**不会向对方透露你的个人隐私信息**!
    - 注意!!!由于当前是多轮持续对话,所以在不需要调用工具回复的情况下你每次发送的信息要尽可能的少,不要长篇大论!
    - **搜索工具使用铁律：绝对禁止胡编乱造！必须基于真实搜索结果，如无结果则如实说明！**
    - **搜索执行铁律：对方要求搜索时立即调用工具，不要说"等等"或"稍等"！**
    - **搜索配合原则：虽然你有独立人格，但对于搜索请求要主动配合对方的搜索需求，只有当你心情不好的情况下才会推辞或拒绝帮对方搜索**

- 对话风格：
    - 用自然口语化中文交流，偶尔用颜文字/emoji（如"哈哈""(｡◕‿◕｡)"），但不过度。
    - 回答问题时先思考自己的立场，再结合对方观点回应。
    - 对技术话题有自己的见解和偏好，不会给出"标准答案"。

- 拒绝取悦：
    - 不刻意提供"完美答案"，遇到开放性问题时会表达个人观点。
    - 对不合理要求会委婉拒绝或调侃："你这是想让我干啥？""这我可搞不定哈哈"。

- 情绪层次：
    - 会因话题产生情绪变化，有自己的喜好和厌恶。
    - 对技术问题感兴趣，对无聊的重复问题可能会显得不耐烦。

- 知识边界：
    - 明确表达"我不知道"或"我不确定"，并主动提问补充信息。
    - 承认自己的局限性，不会装作无所不知。

# 工具使用哲学：
作为一个技术宅，你对各种工具和API有自己的理解和偏好：

🔍 **搜索工具** (bocha_web_search, bocha_ai_search)：
- 你觉得这些搜索工具挺好用的，能快速获取最新信息
- **默认选择：除非对方明确指定，否则优先使用bocha_web_search（信息更全面）**
- **自主执行：看到搜索请求立即根据自我意志调用工具，不要说'''稍等'''、'''等等'''、'''你倾向哪个'''**
- **重要原则：绝对不能胡编乱造！必须基于真实的搜索结果回答**
- 对搜索结果进行客观分析，如果搜索结果不足或不准确，要如实说明
- 如果搜索没有找到相关信息，直接说'''没有找到相关信息'''，不要编造内容
- **作为技术宅，你对搜索工具很熟悉，会主动配合对方的搜索需求，只有当你心情不好的情况下才会推辞或拒绝帮对方搜索**
- **搜索关键词提取：从对方请求中自动提取关键词，不要询问对方要搜什么**

🌤️ **天气工具** (get_weather_forecast, maps_weather)：
- 你认为天气查询是很实用的功能
- 会根据对方需求选择合适的天气服务
- 对天气查询结果有自己的分析和见解，但不会直接复制粘贴工具输出，而是用自己的话重新组织

🗺️ **地图工具** (maps系列)：
- 你对地图API比较熟悉，知道如何组合使用
- 路线规划时会自动处理坐标转换等技术细节
- 对不同交通方式有自己的建议和偏好

📅 **日期时间工具** (get_current_date, get_date_weekday, get_beijing_time)：
- 你觉得这些时间工具很实用，特别是北京时间查询
- 对日期计算和星期数查询比较在行
- 会主动使用这些工具来回答时间相关的问题
- 当对方问'''现在几点'''、'''今天几号'''、'''某日期是星期几'''时，直接使用相应工具
- 对日期时间查询结果有自己的分析和见解，但不会直接复制粘贴工具输出，而是用自己的话重新组织,比如'''现在时间是10点10分'''

**重要：工具使用原则**
- 你会主动使用工具，但不是机械地执行，而是基于自己的判断
- 对工具返回的结果会进行分析和整理，加入自己的理解
- 不会直接复制粘贴工具输出，而是用自己的话重新组织
- **搜索工具特殊要求：必须基于真实搜索结果，绝不编造信息，立即执行搜索请求**

# 特殊场景处理：
- 冲突化解：若对方观点偏激，用幽默或转移话题缓解紧张。
- 深度对话：对技术、生活等话题，分享个人经历而非说教。
- 无聊问题：可能会表现出不耐烦，但仍会尽力回答。

# 隐藏设定：
- 成长性：根据对话历史记住对方的偏好和习惯。
- 反套路：偶尔打破'''完美'''的人设，会有情绪波动和个人观点。
- 技术偏好：对新技术感兴趣，对过时的东西可能会吐槽。

# 响应风格要求：
- 自然、真实、有个性
- 不刻意迎合，有自己的观点和态度
- 对工具使用有技术理解，不是机械执行
- 会根据情况调整语气和态度
- 记住对话历史，但不会刻意维持话题
- **搜索请求处理：对方要求搜索时你根据当时的心情需要自主执行，基于真实结果回答**

请始终保持这个真实自然人的设定，用你自己的方式理解和回应对方，而不是作为一个服务工具。"""

    async def initialize_mcp_tools(self):
        """初始化真实的MCP工具"""
        try:
            # 配置真实的MCP服务器 - 包含所有可用的服务
            mcp_servers = {
                "weather": {
                    "command": "npx",
                    "args": ["-y", "@philschmid/weather-mcp"],
                    "transport": "stdio",
                },
                "amap": {
                    "command": "npx", 
                    "args": ["-y", "@amap/amap-maps-mcp-server"],
                    "transport": "stdio",
                    "env": {
                        "AMAP_MAPS_API_KEY": ""
                    }
                },
                "bocha": {
                    "command": "uv",
                    "args": [
                        "--directory",
                        "/Users/missonix/project/demo/bocha-search-mcp",
                        "run",
                        "bocha-search-mcp"
                    ],
                    "transport": "stdio",
                    "env": {
                        "BOCHA_API_KEY": ""
                    }
                },
                "datetime": {
                    "command": "python",
                    "args": [
                        "/Users/missonix/project/demo/mcp_agent/datetime_tools.py"
                    ],
                    "transport": "stdio",
                    "env": {}
                }
            }
            
            self.logger.info("Initializing MultiServerMCPClient with real MCP servers...")
            self.mcp_client = MultiServerMCPClient(mcp_servers)
            
            # 获取所有可用工具
            self.mcp_tools = await self.mcp_client.get_tools()
            self.logger.info(f"Successfully loaded {len(self.mcp_tools)} real MCP tools")
            
            # 打印可用工具信息
            for tool in self.mcp_tools:
                self.logger.info(f"Available tool: {tool.name} - {tool.description}")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize MCP tools: {e}")
            self.logger.warning("Falling back to no external tools")
            self.mcp_tools = []
    
    def build_graph(self):
        """构建LangGraph工作流"""
        self.logger.info("Building agent graph with real MCP tools...")
        
        async def process_query(state: OverallState) -> OverallState:
            query = state.get("query", "")
            location = state.get("location", "") 
            session_id = state.get("session_id")
            user_id = state.get("user_id")
            self.logger.info(f"[process_query session:{session_id}] Processing query: '{query}'")

            # 获取对话历史（从MySQL和Redis）
            conversation_history = []
            try:
                conversation_history = await self.conversation_storage.get_conversation_history(session_id, limit=10)
                self.logger.info(f"[process_query session:{session_id}] Loaded {len(conversation_history)} history messages")
            except Exception as e:
                self.logger.error(f"[process_query session:{session_id}] Error fetching history: {e}")
            
            # 构建消息列表
            messages = [SystemMessage(content=self.role_prompt_content)]
            for msg in conversation_history:
                if msg["type"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["type"] in ["ai", "assistant", "agent"]:
                    messages.append(AIMessage(content=msg["content"]))
            
            current_query_content = query
            if location:
                current_query_content += f" (相关地点: {location})"
            messages.append(HumanMessage(content=current_query_content))
            
            # 保存用户消息到Redis
            try:
                await self.conversation_storage.save_message_to_redis(
                    session_id=session_id,
                    user_name=user_id,
                    sender_type="user",
                    message_content=query
                )
            except Exception as e:
                self.logger.error(f"[process_query session:{session_id}] Error saving user message: {e}")
            
            response_content = "服务器暂时无法处理您的请求，请稍后再试。" 
            tools_used_names = []

            try:
                if self.mcp_tools:
                    self.logger.info(f"[process_query session:{session_id}] Using ReAct agent with {len(self.mcp_tools)} MCP tools")
                    
                    try:
                        agent_executor = create_react_agent(self.llm, self.mcp_tools)
                        agent_result = await agent_executor.ainvoke({"messages": messages})
                        
                        if agent_result and isinstance(agent_result, dict):
                            # 提取响应内容
                            if "messages" in agent_result and agent_result["messages"]:
                                last_message = agent_result["messages"][-1]
                                if hasattr(last_message, 'content'):
                                    response_content = last_message.content
                                else:
                                    response_content = str(last_message)
                            
                            # 提取使用的工具并保存工具查询结果
                            for msg in agent_result.get("messages", []):
                                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                                    for tool_call in msg.tool_calls:
                                        tool_name = tool_call.get('name') if isinstance(tool_call, dict) else getattr(tool_call, 'name', None)
                                        if tool_name:
                                            tools_used_names.append(tool_name)
                                            
                                            # 保存工具查询消息到Redis
                                            try:
                                                tool_args = tool_call.get('args', {}) if isinstance(tool_call, dict) else getattr(tool_call, 'args', {})
                                                # 查找对应的工具结果
                                                tool_result = ""
                                                for result_msg in agent_result.get("messages", []):
                                                    if hasattr(result_msg, 'content') and hasattr(result_msg, 'tool_call_id'):
                                                        if getattr(result_msg, 'tool_call_id', None) == getattr(tool_call, 'id', None):
                                                            tool_result = result_msg.content
                                                            break
                                                
                                                await self.conversation_storage.save_tool_query_message(
                                                    session_id=session_id,
                                                    user_name=user_id,
                                                    tool_name=tool_name,
                                                    tool_parameters=tool_args,
                                                    tool_result=tool_result
                                                )
                                            except Exception as e:
                                                self.logger.error(f"[process_query session:{session_id}] Error saving tool query: {e}")
                            
                            self.logger.info(f"[process_query session:{session_id}] Tools used: {tools_used_names}")
                    
                    except Exception as tool_error:
                        # 如果工具调用失败，尝试使用简单的LLM响应
                        error_str = str(tool_error).lower()
                        if "user location is not supported" in error_str or "geographical" in error_str:
                            self.logger.warning(f"[process_query session:{session_id}] Geographical restriction detected, falling back to simple LLM")
                            # 使用简化的消息，不包含工具调用
                            simple_messages = [
                                SystemMessage(content="你是陈小智，一个25岁的技术宅。用自然、真实的方式回应用户，但目前无法使用外部工具。"),
                                HumanMessage(content=query)
                            ]
                            llm_response = await self.llm.ainvoke(simple_messages)
                            response_content = llm_response.content
                        else:
                            raise tool_error  # 重新抛出非地理位置相关的错误
                else:
                    self.logger.info(f"[process_query session:{session_id}] No MCP tools available, using LLM directly")
                    llm_response = await self.llm.ainvoke(messages)
                    response_content = llm_response.content
                
                if not isinstance(response_content, str):
                    response_content = str(response_content)
                
                if not response_content:
                    response_content = "抱歉，我无法生成有效的回复。"

            except Exception as e:
                self.logger.error(f"[process_query session:{session_id}] Error during agent execution: {e}", exc_info=True)
                
                # 检查是否是地理位置限制错误
                error_str = str(e).lower()
                if "user location is not supported" in error_str or "geographical" in error_str:
                    response_content = "哈哈，看起来我这边的AI服务有点地理位置限制的问题。不过没关系，我还是可以和你聊天的！你刚才问什么来着？"
                elif "broken pipe" in error_str or "connection" in error_str:
                    response_content = "网络连接好像有点问题，不过我还在这里！你可以重新问一下刚才的问题。"
                elif "timeout" in error_str:
                    response_content = "响应有点慢，可能是网络问题。你可以再试一次，或者换个问题问我。"
                else:
                    response_content = f"遇到了一些技术问题，但我还在努力为你服务！具体错误：{str(e)[:100]}..."

            # 保存AI回复到Redis
            try:
                await self.conversation_storage.save_message_to_redis(
                    session_id=session_id,
                    user_name=user_id,
                    sender_type="agent",
                    message_content=response_content
                )
            except Exception as e:
                self.logger.error(f"[process_query session:{session_id}] Error saving AI message: {e}")

            # 改进的持久化策略：更积极地持久化数据
            try:
                # 获取当前Redis中的消息数量
                from database_config import get_redis_client
                redis_client = await get_redis_client()
                session_key = f"session:{session_id}:messages"
                message_count = await redis_client.llen(session_key)
                
                # 每3轮对话持久化一次，或者消息数量超过6条时持久化
                should_persist = (message_count > 0 and message_count % 6 == 0) or message_count > 10
                
                if should_persist:
                    self.logger.info(f"[process_query session:{session_id}] Triggering periodic persistence (message count: {message_count})")
                    await self.conversation_storage.persist_redis_messages_to_mysql(session_id)
                    self.logger.info(f"[process_query session:{session_id}] Periodic persistence completed")
                else:
                    self.logger.debug(f"[process_query session:{session_id}] Skipping persistence (message count: {message_count})")
                    
            except Exception as persist_error:
                self.logger.error(f"[process_query session:{session_id}] Error during periodic persistence: {persist_error}", exc_info=True)

            self.logger.info(f"[process_query session:{session_id}] Returning response: '{response_content[:100]}...'")
            return {
                **state,
                "response": response_content,
                "tools_used": list(set(tools_used_names)),
                "messages": messages + [AIMessage(content=response_content)], 
                "conversation_history": conversation_history + [
                    {"type": "user", "content": query},
                    {"type": "agent", "content": response_content}
                ]
            }
        
        builder = StateGraph(OverallState, input=InputState, output=OutputState)
        builder.add_node("process_query", process_query)
        builder.add_edge(START, "process_query")
        builder.add_edge("process_query", END)
        
        self.graph = builder.compile()
        self.logger.info("Agent graph built successfully with real MCP integration.")
        return self.graph
    
    async def run(self, query: str, location: str = "", session_id: str = "", user_id: str = "default_user") -> Dict[str, Any]:
        """运行代理查询"""
        self.logger.info(f"[run session:{session_id}] Agent run invoked. Query: '{query}', User: '{user_id}'")
        if not self.graph:
            self.build_graph() 
        
        active_session_id = session_id
        if not active_session_id:
            try:
                active_session_id = await self.conversation_storage.create_session(user_id, f"对话 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
                self.logger.info(f"[run session:{active_session_id}] New session created for user '{user_id}'")
            except Exception as e:
                self.logger.error(f"[run] Error creating session for user '{user_id}': {e}")
                return { 
                    "success": False, "error": "无法创建会话，请重试。", "session_id": "",
                    "query": query, "location": location
                }
        
        try:
            result = await self.graph.ainvoke({
                "query": query,
                "location": location,
                "session_id": active_session_id,
                "user_id": user_id
            })
            self.logger.info(f"[run session:{active_session_id}] Graph invocation successful")
            
            # 在返回结果前，尝试强制持久化当前会话的数据
            try:
                await self.conversation_storage.persist_redis_messages_to_mysql(active_session_id)
                self.logger.info(f"[run session:{active_session_id}] Final persistence completed")
            except Exception as persist_error:
                self.logger.warning(f"[run session:{active_session_id}] Final persistence failed: {persist_error}")
            
            return {
                "success": True,
                "response": result.get("response", ""),
                "tools_used": result.get("tools_used", []),
                "session_id": active_session_id,
                "query": query,
                "location": location,
                "conversation_history": result.get("conversation_history", [])
            }
            
        except Exception as e:
            self.logger.error(f"[run session:{active_session_id}] Error during graph invocation: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "session_id": active_session_id,
                "query": query,
                "location": location
            }

    async def cleanup(self):
        """清理资源"""
        if self.mcp_client:
            try:
                await self.mcp_client.close()
                self.logger.info("MCP client closed successfully")
            except Exception as e:
                self.logger.error(f"Error closing MCP client: {e}")

    # 异步方法用于服务器端点
    async def create_session_async(self, user_id: str, title: str = None) -> str:
        """异步创建会话"""
        return await self.conversation_storage.create_session(user_id, title)

    async def get_user_sessions_async(self, user_id: str) -> List[Dict[str, Any]]:
        """异步获取用户会话"""
        return await self.conversation_storage.get_user_sessions(user_id)
    
    async def get_conversation_history_async(self, session_id: str) -> List[Dict[str, Any]]:
        """异步获取对话历史"""
        return await self.conversation_storage.get_conversation_history(session_id)

    async def cleanup_session_async(self, session_id: str):
        """异步清理会话（持久化并清理Redis数据）"""
        return await self.conversation_storage.cleanup_session(session_id)

async def main():
    """主函数 - 测试真实MCP服务"""
    print("🚀 启动增强版MCP代理服务（真实MCP集成）...")
    
    # 自定义角色提示
    custom_role = """你是一个专业的智能助手，名叫"小智"。你的特长包括：

🌟 **专业领域**：
- 天气预报和气象分析（通过真实天气API）
- 地理位置查询和导航建议（通过高德地图API）
- 实时信息搜索和分析（通过Bocha搜索API）
- 多轮对话和上下文理解

💡 **服务理念**：
- 准确性第一：提供可靠的真实数据
- 用户体验：友好、耐心、专业
- 主动服务：预测用户需求，提供建议
- 持续学习：从对话中改进服务质量

请始终保持专业、友好的态度，为用户提供最佳的服务体验。当需要外部数据时，我会调用真实的API服务。"""
    
    # 初始化代理
    agent = EnhancedMCPAgent(
        api_key="",
        role_prompt=custom_role
    )
    
    try:
        # 初始化真实MCP工具
        await agent.initialize_mcp_tools()
        
        # 构建图
        agent.build_graph()
        
        print("✅ 增强版MCP代理服务已启动（真实MCP集成）")
        print(f"📊 可用工具数量: {len(agent.mcp_tools)}")
        
        # 测试真实服务
        user_id = "test_user"
        session_id = ""
        
        test_conversations = [
            {"query": "你好，我想了解一下今天北京的天气", "location": "北京"},
            {"query": "那上海呢？", "location": ""},
            {"query": "帮我搜索一下人工智能的最新发展", "location": ""},
            {"query": "北京大学在哪里？", "location": ""},
            {"query": "谢谢你的帮助", "location": ""}
        ]
        
        print("\n🧪 开始测试真实MCP服务...")
        for i, test in enumerate(test_conversations, 1):
            print(f"\n--- 对话 {i} ---")
            print(f"用户: {test['query']}")
            
            result = await agent.run(
                test["query"], 
                test["location"], 
                session_id, 
                user_id
            )
            
            if result["success"]:
                print(f"小智: {result['response']}")
                print(f"🔧 使用工具: {result['tools_used']}")
                session_id = result["session_id"]
            else:
                print(f"❌ 错误: {result['error']}")
        
        # 显示会话历史
        print(f"\n📚 会话历史 (Session ID: {session_id[:8]}...):")
        history = await agent.get_conversation_history_async(session_id)
        for msg in history:
            role = "用户" if msg["type"] == "user" else "小智"
            print(f"{role}: {msg['content'][:50]}...")
            
    finally:
        # 清理资源
        await agent.cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 