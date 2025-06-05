"""
MCP Agent - 增强版多工具集成聊天代理
支持情绪分析、内心OS生成、工具自动检测和调用
集成天气查询、地图服务、搜索服务等真实MCP服务
支持多轮对话持久化存储
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, TypedDict, Annotated
from dataclasses import dataclass, asdict
from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent

# 使用统一模型配置管理器
from model_config import get_langchain_llm, get_model_config

# 导入相关模块
from client import MCPClient  
from persistent_storage import PersistentConversationStorage
from role_config import load_role_config, RoleConfig
from role_detail import RoleMood
from input_emotion_analyzer.analyzer import InputEmotionAnalyzer
from thought_chain_prompt_generator.thought_chain_generator import ThoughtChainPromptGenerator

# 导入角色详情管理器
from role_detail import RoleDetailManager

# 简化的MCP客户端类 - 暂时替代MultiServerMCPClient
class EnhancedMCPClient:
    """简化的MCP客户端，临时替代方案"""
    def __init__(self, servers: Dict[str, Any]):
        self.servers = servers
        self.tools = []
    
    async def get_tools(self) -> List[Any]:
        """返回空工具列表，避免工具初始化错误"""
        return []
        
    async def close(self):
        """清理资源"""
        pass

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
    system_message: str  # 新增：系统消息，用于错误提示等

# 定义整体状态
class OverallState(InputState, OutputState):
    messages: List[Dict[str, Any]]
    conversation_history: List[Dict[str, Any]]

class EnhancedMCPAgent:
    """增强版MCP代理，支持情绪分析、内心OS生成、多轮对话存储和真实MCP服务集成"""
    
    def __init__(self, role_id: str = None):
        """
        初始化代理
        
        Args:
            role_id: 角色ID，用于加载特定的角色配置
        """
        self.logger = logging.getLogger(__name__)
        self.role_id = role_id
        self.role_config = None
        
        # 初始化角色管理器
        self.role_manager = RoleDetailManager()
        self.current_role_mood = None
        
        # 初始化提示词内容 - 将在load_role_config后加载
        self.l0_prompt_content = ""
        self.l1_prompt_content = self._load_l1_prompt()
        self.usetool_prompt_content = self._load_usetool_prompt()
        
        # 初始化情绪分析和内心OS生成器
        self.emotion_analyzer = InputEmotionAnalyzer()
        self.thought_generator = ThoughtChainPromptGenerator()
        
        # 使用统一的模型配置
        self.llm = get_langchain_llm()
        
        # 记录当前使用的模型配置
        model_config = get_model_config()
        self.logger.info(f"🤖 使用模型: {model_config.provider.value} - {model_config.model_name}")
        
        self.mcp_client = None
        self.mcp_tools = []
        self.graph = None
        # 使用持久化存储替换内存存储
        self.conversation_storage = PersistentConversationStorage()
        
        # 如果提供了角色ID，立即加载配置
        if self.role_id:
            self.load_role_config(self.role_id)
        
        self.logger.info(f"EnhancedMCPAgent initialized with role: {self.role_id or '未指定'}")
        
    def load_role_config(self, role_id: str) -> bool:
        """加载角色配置"""
        try:
            self.role_config = load_role_config(role_id)
            if not self.role_config:
                self.logger.error(f"无法加载角色配置: {role_id}")
                return False
            
            self.role_id = role_id
            
            # 加载角色专属的L0提示词
            self.l0_prompt_content = self._load_l0_prompt_for_role(self.role_config)
            
            self.logger.info(f"✅ 成功加载角色配置: {self.role_config.role_name} ({role_id})")
            return True
            
        except Exception as e:
            self.logger.error(f"加载角色配置失败: {role_id} - {e}")
            return False
    
    def _load_l0_prompt_for_role(self, role_config: RoleConfig) -> str:
        """为指定角色加载L0提示词 - 必须成功加载，不使用备用prompt"""
        try:
            project_root = Path(__file__).parent.parent
            prompt_path = project_root / role_config.l0_prompt_path
            
            if prompt_path.exists():
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                if content:
                    self.logger.info(f"✅ 为角色 {role_config.role_name} 成功加载L0提示词: {prompt_path}")
                    return content
                else:
                    raise FileNotFoundError(f"L0提示词文件为空: {prompt_path}")
            else:
                raise FileNotFoundError(f"L0提示词文件不存在: {prompt_path}")
                
        except Exception as e:
            self.logger.error(f"❌ 角色 {role_config.role_name} L0提示词加载失败: {e}")
            raise RuntimeError(f"无法为角色 {role_config.role_name} 加载L0提示词: {e}")
    
    def _generate_default_l0_prompt(self, role_config: RoleConfig) -> str:
        """此方法已废弃 - 不再使用默认L0提示词，必须使用角色专用prompt"""
        raise RuntimeError(f"角色 {role_config.role_name} 必须有专用的L0提示词文件: {role_config.l0_prompt_path}")
    
    def _get_fallback_l0_prompt(self) -> str:
        """此方法已废弃 - 不再使用备用L0提示词，必须使用角色专用prompt"""
        if self.role_config:
            raise RuntimeError(f"角色 {self.role_config.role_name} 必须使用专用L0提示词文件: {self.role_config.l0_prompt_path}")
        else:
            raise RuntimeError("必须先加载角色配置和专用L0提示词")
    
    def _load_l1_prompt(self) -> str:
        """从文件加载L1行为准则提示词"""
        try:
            prompt_path = Path(__file__).parent.parent / "prompt" / "L1_prompt.txt"
            with open(prompt_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            self.logger.info(f"Loaded L1 prompt from {prompt_path}")
            return content
        except Exception as e:
            self.logger.error(f"Failed to load L1 prompt: {e}")
            return "# 行为准则\n请保持自然、真实的对话风格。"
    
    def _load_usetool_prompt(self) -> str:
        """从文件加载工具使用提示词"""
        try:
            prompt_path = Path(__file__).parent.parent / "prompt" / "usetool_prompt.txt"
            with open(prompt_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            self.logger.info(f"Loaded usetool prompt from {prompt_path}")
            return content
        except Exception as e:
            self.logger.error(f"Failed to load usetool prompt: {e}")
            return "# 工具使用指导\n当需要外部信息时，请合理使用可用的工具。"
    
    def _load_inner_os_ban_prompt(self) -> str:
        """加载内心OS禁止提示词"""
        try:
            prompt_path = Path(__file__).parent.parent / "prompt" / "inner_os_ban.txt"
            with open(prompt_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            self.logger.info(f"Loaded inner OS ban prompt from {prompt_path}")
            return content
        except Exception as e:
            self.logger.error(f"Failed to load inner OS ban prompt: {e}")
            return "**严禁在回复中输出任何形式的内心OS！**"
    
    def _load_provocation_response_prompt(self) -> str:
        """加载挑衅回应提示词"""
        try:
            prompt_path = Path(__file__).parent.parent / "prompt" / "provocation_response.txt"
            with open(prompt_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            self.logger.info(f"Loaded provocation response prompt from {prompt_path}")
            return content
        except Exception as e:
            self.logger.error(f"Failed to load provocation response prompt: {e}")
            return "# 被不尊重时有权表达不满和拒绝服务"
    
    def _detect_provocation_in_context(self) -> bool:
        """检测是否存在挑衅或不尊重的情况"""
        # 检测最近的对话上下文中是否有不尊重的称呼
        # 这里可以根据具体情况实现更复杂的检测逻辑
        # 暂时返回True，让系统总是包含挑衅处理指导
        return True

    def _get_current_mood_state(self) -> Dict[str, Any]:
        """获取当前的情绪状态 - 必须有有效的情绪状态"""
        if self.current_role_mood:
            return self.current_role_mood.to_dict()
        else:
            # 不再使用备用情绪状态，必须正确初始化
            raise RuntimeError(f"角色 {self.role_id} 的情绪状态未正确初始化，请检查角色配置和初始化流程")
    
    def _get_fallback_mood_state(self) -> RoleMood:
        """此方法已废弃 - 不再使用备用情绪状态，必须正确初始化角色情绪"""
        raise RuntimeError(f"角色 {self.role_id} 必须有正确的情绪状态，不允许使用备用情绪状态")

    async def update_role_mood(self, new_mood: RoleMood) -> bool:
        """更新角色情绪状态"""
        try:
            # 更新内存中的情绪状态
            self.current_role_mood = new_mood
            
            # 更新Redis中的情绪状态
            from database_config import get_redis_client
            redis_client = await get_redis_client()
            redis_key = f"role_mood:{self.role_id}"
            
            await redis_client.hset(redis_key, mapping=new_mood.to_dict())
            await redis_client.expire(redis_key, 86400)  # 24小时过期
            
            self.logger.info(f"✅ 角色情绪状态已更新: {self.role_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 更新角色情绪状态失败: {e}")
            return False

    async def _analyze_user_input_and_generate_os(self, user_input: str, session_id: str = "", user_id: str = "") -> tuple[Dict[str, Any], str]:
        """分析用户输入并生成内心OS"""
        try:
            # 1. 情绪分析
            self.logger.info(f"Analyzing user input: {user_input[:50]}...")
            analysis_result = await self.emotion_analyzer.analyze(user_input)
            
            # 2. 获取近10分钟的对话历史
            recent_conversation = []
            if session_id:
                try:
                    recent_conversation = await self._get_recent_conversation_history(session_id, minutes=10)
                    self.logger.info(f"Retrieved {len(recent_conversation)} recent conversation messages")
                except Exception as e:
                    self.logger.warning(f"Failed to get recent conversation history: {e}")
                    recent_conversation = []
            
            # 3. 生成内心OS - 使用当前角色的情绪状态和对话历史
            current_mood = self._get_current_mood_state()
            inner_os = self.thought_generator.process_analysis_result(
                original_input=user_input,
                analysis_data=analysis_result,
                my_mood=current_mood,
                recent_conversation=recent_conversation
            )
            
            self.logger.info("Successfully generated emotion analysis and inner OS with conversation history")
            return analysis_result, inner_os
            
        except Exception as e:
            self.logger.error(f"Error in emotion analysis or OS generation: {e}")
            # 返回默认值
            default_analysis = {"error": str(e)}
            default_os = f"用户说：{user_input}\n\n我的想法：嗯，让我想想怎么回答这个问题。"
            return default_analysis, default_os

    async def _get_recent_conversation_history(self, session_id: str, minutes: int = 10) -> List[Dict[str, Any]]:
        """从Redis获取近期对话历史"""
        try:
            from database_config import get_redis_client
            import time
            
            redis_client = await get_redis_client()
            session_key = f"session:{session_id}:messages"
            
            # 获取所有消息
            all_messages = await redis_client.lrange(session_key, 0, -1)
            
            if not all_messages:
                return []
            
            recent_messages = []
            current_time = time.time()
            time_threshold = current_time - (minutes * 60)  # minutes分钟前的时间戳
            
            for msg_json in reversed(all_messages):  # 倒序遍历，最新的在前
                try:
                    # 处理消息可能已经是字符串或bytes的情况
                    if isinstance(msg_json, bytes):
                        msg_str = msg_json.decode('utf-8')
                    elif isinstance(msg_json, str):
                        msg_str = msg_json
                    else:
                        msg_str = str(msg_json)
                    
                    msg = json.loads(msg_str)
                    msg_timestamp = msg.get('timestamp')
                    
                    # 解析时间戳
                    if msg_timestamp:
                        # 支持多种时间戳格式
                        if isinstance(msg_timestamp, (int, float)):
                            msg_time = msg_timestamp
                        elif isinstance(msg_timestamp, str):
                            try:
                                # 尝试解析ISO格式时间
                                from datetime import datetime
                                dt = datetime.fromisoformat(msg_timestamp.replace('Z', '+00:00'))
                                msg_time = dt.timestamp()
                            except:
                                # 如果解析失败，尝试作为float处理
                                try:
                                    msg_time = float(msg_timestamp)
                                except:
                                    # 如果都失败了，跳过时间过滤
                                    msg_time = current_time
                        else:
                            msg_time = current_time
                    else:
                        msg_time = current_time
                    
                    # 如果消息在时间窗口内，添加到结果中
                    if msg_time >= time_threshold:
                        # 过滤掉工具调用消息，只保留用户和AI的对话
                        if msg.get('sender_type') in ['user', 'agent', 'human', 'ai', 'assistant']:
                            recent_messages.append({
                                'type': msg.get('sender_type'),
                                'content': msg.get('message_content', ''),
                                'timestamp': msg.get('timestamp', ''),
                                'user_name': msg.get('user_name', '')
                            })
                    else:
                        # 由于是倒序遍历，如果遇到超出时间窗口的消息，后面的都更老，可以停止
                        break
                        
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Failed to parse message JSON: {e}")
                    continue
                except Exception as e:
                    self.logger.warning(f"Error processing message: {e}")
                    continue
            
            # 按时间正序排列（最老的在前，最新的在后）
            recent_messages.sort(key=lambda x: x.get('timestamp', ''))
            
            # 限制最大消息数量，避免prompt过长
            max_messages = 20
            if len(recent_messages) > max_messages:
                recent_messages = recent_messages[-max_messages:]
            
            self.logger.info(f"Found {len(recent_messages)} recent conversation messages within {minutes} minutes")
            return recent_messages
            
        except Exception as e:
            self.logger.error(f"Error getting recent conversation history: {e}")
            return []

    async def get_current_plot_content(self) -> List[str]:
        """获取当前角色的剧情内容"""
        try:
            if not hasattr(self, 'time_plot_manager'):
                # 如果没有时间剧情管理器，创建一个
                from time_plot_manager import TimePlotManager
                self.time_plot_manager = TimePlotManager()
            
            plot_content = await self.time_plot_manager.get_role_current_plot_content(self.role_id)
            self.logger.info(f"获取到角色 {self.role_id} 的 {len(plot_content)} 条剧情内容")
            return plot_content
        except Exception as e:
            self.logger.error(f"获取角色剧情内容失败: {e}")
            return []

    def _build_system_prompt(self, inner_os: str, needs_tools: bool = False, user_name: str = "", current_plot: List[str] = None) -> str:
        """构建系统提示词"""
        # 基础组合：L0 + 当前情绪状态 + 剧情情境 + 内心OS + L1
        system_prompt = f"{self.l0_prompt_content}\n\n"
        
        # 添加用户信息
        if user_name:
            user_info = f"## 当前对话者信息：\n"
            user_info += f"- 对话者称呼: {user_name}\n"
            user_info += f"- 在回复中可以适当称呼对方的名字，让对话更自然\n\n"
            system_prompt += user_info
        
        # 添加当前情绪状态信息
        if self.current_role_mood:
            mood_info = f"## 当前情绪状态：\n"
            mood_info += f"- 情绪标签: {self.current_role_mood.my_tags}\n"
            mood_info += f"- 情绪强度: {self.current_role_mood.my_intensity}/10\n"
            mood_info += f"- 情绪描述: {self.current_role_mood.my_mood_description_for_llm}\n\n"
            system_prompt += mood_info
        
        # 【新增】添加当前剧情情境信息
        if current_plot and len(current_plot) > 0:
            plot_info = f"## 当前剧情情境：\n"
            plot_info += f"你现在正处于以下时间线和情境中，这些是你真实经历的事件，会影响你的情绪、想法和回应方式：\n\n"
            
            # 显示最近的剧情内容，突出当前时间段
            for i, plot_line in enumerate(current_plot, 1):
                if i == len(current_plot):  # 最后一条是当前时间段
                    plot_info += f"**【当前时刻】** {plot_line}\n\n"
                else:
                    plot_info += f"{i}. {plot_line}\n"
            
            plot_info += f"**重要提示：**\n"
            plot_info += f"- 这些剧情是你真实的生活经历，不是虚构的\n"
            plot_info += f"- 你的情绪状态反映了这些经历对你的影响\n"
            plot_info += f"- 在回复时要体现出这些经历给你带来的心境变化\n"
            plot_info += f"- 如果对话内容与你当前的工作/生活情境相关，要自然地融入这些背景\n"
            plot_info += f"- 保持角色的一致性，不要突然脱离当前的情境设定\n\n"
            
            system_prompt += plot_info
        
        # 🚨 加载内心OS禁止指导
        inner_os_ban_content = self._load_inner_os_ban_prompt()
        system_prompt += f"{inner_os_ban_content}\n\n"
        
        if inner_os:
            system_prompt += f"## 当前内心OS：\n{inner_os}\n\n"
            system_prompt += f"**🚨🚨🚨 ABSOLUTE CRITICAL INSTRUCTION 🚨🚨🚨**\n"
            system_prompt += f"**以上内心OS绝对不能出现在你的回复中！这只是用来指导你的情绪和态度！**\n"
            system_prompt += f"**严禁在回复中使用任何形式的内心OS表述！包括但不限于：**\n"
            system_prompt += f"- ❌ （内心OS：...）\n"
            system_prompt += f"- ❌ 内心想法：...\n"
            system_prompt += f"- ❌ 心里想：...\n"
            system_prompt += f"- ❌ （稍微...）、（解释...）、（想想...）等任何指导性括号内容\n"
            system_prompt += f"- ❌ 任何括号内的想法表述、策略描述、行为指导\n"
            system_prompt += f"- ❌ 任何meta层面的思考过程或策略说明\n"
            system_prompt += f"- ❌ 任何对用户的评价或情感分析（如：（他对我挺好的）、（这人不错）等）\n"
            system_prompt += f"- ❌ 任何关系判断或性格评价的括号内容\n"
            system_prompt += f"**你必须只输出角色会真实说出口的自然对话！**\n"
            system_prompt += f"**任何包含思维过程或指导性内容的回复都是完全不可接受的！**\n"
            system_prompt += f"**检查清单：回复中是否有任何（...）括号？如果有，必须全部删除！**\n"
            system_prompt += f"**特别警告：绝对不能输出对用户的内心评价！**\n\n"
        
        # 🚨 检测被挑衅情况并添加相应指导
        if self._detect_provocation_in_context():
            provocation_guide = self._load_provocation_response_prompt()
            system_prompt += f"## 🚨 被挑衅情况处理指导：\n{provocation_guide}\n\n"
        
        system_prompt += f"{self.l1_prompt_content}\n\n"
        
        # 如果需要工具，添加工具使用提示
        if needs_tools:
            tool_guidance = f"{self.usetool_prompt_content}\n\n"
            
            # 【关键优化】添加工具使用的自主决策指导
            tool_guidance += f"## 🎯 工具使用自主决策指导\n"
            tool_guidance += f"**重要：你有完全的自主权决定是否使用工具帮助用户！**\n\n"
            
            tool_guidance += f"## 🚨 关键规则：工具使用必须真实 🚨\n"
            tool_guidance += f"**严禁假装使用工具！只有两种选择：**\n"
            tool_guidance += f"1. **真正使用工具**：系统会实际调用工具并返回真实结果\n"
            tool_guidance += f"2. **完全不使用工具**：直接基于你的知识和情绪状态回答\n"
            tool_guidance += f"**绝对禁止**：说我来搜索一下、让我查查 等假装动作但不实际使用工具！\n\n"
            
            tool_guidance += f"### 决策依据：\n"
            tool_guidance += f"1. **当前情绪状态**：根据你的情绪标签和强度来决定\n"
            tool_guidance += f"   - 情绪好时：可能更愿意帮助用户\n"
            tool_guidance += f"   - 情绪差/焦虑/烦躁时：根据人设决定是否帮助\n"
            tool_guidance += f"2. **人设性格**：结合你的核心性格特质\n"
            tool_guidance += f"   - 善良乐于助人的性格：即使心情不好也可能帮助\n"
            tool_guidance += f"   - 高傲自我的性格：心情不好时可能直接拒绝\n"
            tool_guidance += f"   - 利己主义倾向：会考虑帮助的成本和收益\n"
            tool_guidance += f"3. **当前剧情情境**：考虑你现在的处境和压力\n"
            tool_guidance += f"4. **与用户的关系**：考虑对话历史和用户态度\n\n"
            
            tool_guidance += f"### 如果选择不帮助，可以这样回应：\n"
            tool_guidance += f"- **直接拒绝**：'不想搜，你自己查去'\n"
            tool_guidance += f"- **表达不耐烦**：'又要我帮你搜？有点烦啊'\n"
            tool_guidance += f"- **提条件**：'帮你搜可以，你得答应我一个条件'\n"
            tool_guidance += f"- **转移话题**：'不聊这个了，我们说点别的'\n"
            tool_guidance += f"- **基于已知回答**：'国际新闻无非就是那些，你应该知道的'\n\n"
            
            tool_guidance += f"### 核心原则：\n"
            tool_guidance += f"**根据你的真实感受和人设来决定！要么真用工具，要么明确拒绝！**\n"
            tool_guidance += f"**绝对禁止假装使用工具的虚假行为！**\n\n"
            
            system_prompt += tool_guidance
        
        return system_prompt

    def _detect_tool_need(self, user_input: str, analysis_result: Dict[str, Any]) -> bool:
        """检测是否需要使用工具"""
        user_input_lower = user_input.lower()
        
        # 搜索相关关键词 - 优先级最高
        search_keywords = ["搜索", "查询", "找", "查", "搜", "查一下", "搜一下", "帮我找", "文档", "新闻", "资讯", "信息"]
        news_keywords = ["新闻", "资讯", "社会新闻", "今日新闻", "最新新闻", "热点", "头条"]
        
        # 时间相关关键词 - 需要更精确的匹配
        time_keywords = ["几点", "现在时间", "当前时间", "什么时候", "现在几点"]
        date_keywords = ["今天几号", "当前日期", "今天是几月几日", "当前日期是什么"]
        weekday_keywords = ["星期几", "周几", "礼拜几"]
        
        # 天气相关关键词
        weather_keywords = ["天气", "气温", "下雨", "晴天", "阴天", "温度", "天气预报"]
        
        # 地图相关关键词
        location_keywords = ["在哪里", "地址", "位置", "路线", "导航", "怎么去"]
        
        # 优先检查搜索需求
        if any(keyword in user_input_lower for keyword in search_keywords + news_keywords):
            # 排除纯时间查询
            if not any(keyword in user_input_lower for keyword in time_keywords + date_keywords + weekday_keywords):
                return True
        
        # 检查天气和地图需求
        if any(keyword in user_input_lower for keyword in weather_keywords + location_keywords):
            return True
            
        # 最后检查时间需求（更严格的条件）
        if any(keyword in user_input_lower for keyword in time_keywords + date_keywords + weekday_keywords):
            return True
            
        return False

    def _detect_search_need(self, user_input: str) -> bool:
        """专门检测是否需要搜索工具"""
        user_input_lower = user_input.lower()
        
        # 搜索关键词
        search_keywords = ["搜索", "查询", "找", "查", "搜", "查一下", "搜一下", "帮我找"]
        news_keywords = ["新闻", "资讯", "社会新闻", "今日新闻", "最新新闻", "热点", "头条", "报道"]
        info_keywords = ["信息", "内容", "资料", "文档", "百科", "知识"]
        
        # 检查是否包含搜索相关关键词
        has_search_intent = any(keyword in user_input_lower for keyword in search_keywords + news_keywords + info_keywords)
        
        # 排除纯时间查询
        time_keywords = ["几点", "现在时间", "当前时间", "现在几点"]
        date_keywords = ["今天几号", "当前日期", "今天是几月几日"]
        weekday_keywords = ["星期几", "周几", "礼拜几"]
        
        is_time_only = any(keyword in user_input_lower for keyword in time_keywords + date_keywords + weekday_keywords) and \
                      not any(keyword in user_input_lower for keyword in search_keywords + news_keywords + info_keywords)
        
        return has_search_intent and not is_time_only

    def _get_search_freshness(self, user_input: str) -> str:
        """根据用户输入确定搜索时间范围"""
        user_input_lower = user_input.lower()
        
        if any(keyword in user_input_lower for keyword in ["今天", "今日", "当日"]):
            return "oneDay"
        elif any(keyword in user_input_lower for keyword in ["本周", "这周", "周内"]):
            return "oneWeek"
        elif any(keyword in user_input_lower for keyword in ["本月", "这个月", "月内"]):
            return "oneMonth"
        elif any(keyword in user_input_lower for keyword in ["今年", "本年", "年内"]):
            return "oneYear"
        else:
            return "noLimit"

    async def initialize_mcp_tools(self):
        """初始化真实的MCP工具"""
        self.logger.info("Starting MCP tools initialization...")
        
        # 定义可用的MCP服务器配置
        mcp_servers = {
            "datetime": {
                "command": "python",
                "args": [
                    "/Users/missonix/project/demo/mcp_agent/datetime_tools.py"
                ],
                "transport": "stdio",
                "env": {}
            }
        }
        
        # 可选的外部服务（可能不稳定）
        optional_servers = {
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
                    "AMAP_MAPS_API_KEY": "81d4e0e5baf967c6d632e83d6b332dcf"
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
                    "BOCHA_API_KEY": "sk-af4f2db4236a4168ad7759e8c8823748"
                }
            }
        }
        
        try:
            # 首先尝试仅使用核心工具初始化
            self.logger.info("Initializing core MCP tools...")
            self.mcp_client = EnhancedMCPClient(mcp_servers)
            
            # 设置超时获取工具
            try:
                self.mcp_tools = await asyncio.wait_for(
                    self.mcp_client.get_tools(), 
                    timeout=10.0  # 10秒超时
                )
                self.logger.info(f"✅ Core tools loaded: {len(self.mcp_tools)} tools")
            
                # 尝试添加可选服务（非阻塞）
                await self._load_optional_tools(optional_servers)
                
            except asyncio.TimeoutError:
                self.logger.warning("⚠️ Core tools loading timed out, using fallback")
                self.mcp_tools = []
                
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize core MCP tools: {e}")
            self.logger.info("💡 Falling back to no external tools mode")
            self.mcp_tools = []
        
        # 打印最终可用工具
        if self.mcp_tools:
            self.logger.info(f"🎉 Successfully initialized {len(self.mcp_tools)} MCP tools")
            for tool in self.mcp_tools:
                self.logger.info(f"  📋 {tool.name}: {tool.description}")
        else:
            self.logger.info("🔧 Running in basic mode without external tools")
    
    async def _load_optional_tools(self, optional_servers: Dict[str, Any]):
        """加载可选的外部工具（非阻塞）"""
        for server_name, config in optional_servers.items():
            try:
                self.logger.info(f"Attempting to load optional service: {server_name}")
                
                # 为每个可选服务创建独立的客户端
                single_server = {server_name: config}
                optional_client = EnhancedMCPClient(single_server)
                
                # 短超时尝试连接
                optional_tools = await asyncio.wait_for(
                    optional_client.get_tools(),
                    timeout=5.0  # 5秒超时
                )
                
                if optional_tools:
                    # 将可选工具添加到主工具列表
                    self.mcp_tools.extend(optional_tools)
                    self.logger.info(f"✅ Optional service {server_name} loaded: {len(optional_tools)} tools")
                else:
                    self.logger.warning(f"⚠️ Optional service {server_name} returned no tools")
                    
            except asyncio.TimeoutError:
                self.logger.warning(f"⏱️ Optional service {server_name} timed out, skipping")
            except Exception as e:
                self.logger.warning(f"⚠️ Optional service {server_name} failed: {e}")
            
            # 避免阻塞太久
            await asyncio.sleep(0.1)
    
    def build_graph(self):
        """构建LangGraph工作流"""
        self.logger.info("Building agent graph with real MCP tools...")
        
        async def process_query(state: OverallState) -> OverallState:
            query = state.get("query", "")
            location = state.get("location", "") 
            session_id = state.get("session_id")
            user_id = state.get("user_id")
            self.logger.info(f"[process_query session:{session_id}] Processing query: '{query}'")

            # 1. 情绪分析和内心OS生成
            self.logger.info(f"[process_query session:{session_id}] Starting emotion analysis and OS generation")
            analysis_result, inner_os = await self._analyze_user_input_and_generate_os(query, session_id, user_id)
            self.logger.info(f"[process_query session:{session_id}] Generated inner OS: {inner_os[:100]}...")

            # 🆕 2. 动态情绪更新：分析用户消息对角色情绪的影响
            self.logger.info(f"[process_query session:{session_id}] Starting dynamic emotion update process...")
            try:
                # 2.1 分析用户消息对角色情绪的影响
                user_emotion_impact = await self._analyze_user_message_emotion_impact(query, analysis_result)
                self.logger.info(f"[process_query session:{session_id}] User emotion impact: {user_emotion_impact.get('impact_tags', '无影响')} (效价: {user_emotion_impact.get('impact_valence', 0.0):.2f})")
                
                # 2.2 获取当前剧情对情绪的影响数据（如果有的话）
                plot_emotion_impact = {}
                current_plot = await self.get_current_plot_content()
                
                if current_plot and len(current_plot) > 0:
                    # 从思维链生成器获取剧情情绪影响（这个方法已存在）
                    try:
                        plot_mood_data = await asyncio.wait_for(
                            self.thought_generator.process_plot_events_and_update_mood(
                                self.role_id, current_plot
                            ),
                            timeout=10.0  # 10秒超时
                        )
                        
                        if plot_mood_data:
                            plot_emotion_impact = plot_mood_data
                            self.logger.info(f"[process_query session:{session_id}] Plot emotion impact: {plot_mood_data.get('my_tags', '无')} (效价: {plot_mood_data.get('my_valence', 0.0):.2f})")
                        else:
                            # 使用当前情绪状态作为基准
                            current_mood = self.current_role_mood or self._get_fallback_mood_state()
                            plot_emotion_impact = current_mood.to_dict()
                            self.logger.info(f"[process_query session:{session_id}] No plot impact data, using current mood as baseline")
                            
                    except asyncio.TimeoutError:
                        self.logger.warning(f"[process_query session:{session_id}] Plot emotion analysis timed out, using current mood")
                        current_mood = self.current_role_mood or self._get_fallback_mood_state()
                        plot_emotion_impact = current_mood.to_dict()
                    except Exception as plot_error:
                        self.logger.error(f"[process_query session:{session_id}] Plot emotion analysis failed: {plot_error}")
                        current_mood = self.current_role_mood or self._get_fallback_mood_state()
                        plot_emotion_impact = current_mood.to_dict()
                else:
                    # 没有剧情内容，使用当前情绪状态
                    current_mood = self.current_role_mood or self._get_fallback_mood_state()
                    plot_emotion_impact = current_mood.to_dict()
                    self.logger.info(f"[process_query session:{session_id}] No plot content, using current mood: {current_mood.my_tags}")
                
                # 2.3 合成剧情影响(70%)和用户消息影响(30%)
                new_mood = await self._synthesize_emotion_impacts(plot_emotion_impact, user_emotion_impact)
                
                # 2.4 更新角色情绪状态到Redis
                mood_update_success = await self.update_role_mood(new_mood)
                if mood_update_success:
                    self.logger.info(f"[process_query session:{session_id}] ✅ Dynamic emotion update completed: {new_mood.my_tags} (强度: {new_mood.my_intensity}/10)")
                else:
                    self.logger.warning(f"[process_query session:{session_id}] ⚠️ Failed to update mood in Redis, but will use new mood for current response")
                
                # 2.5 记录情绪变化轨迹
                original_mood = self.current_role_mood or self._get_fallback_mood_state()
                if original_mood.my_tags != new_mood.my_tags or abs(original_mood.my_valence - new_mood.my_valence) > 0.1:
                    self.logger.info(f"[process_query session:{session_id}] 🎭 Emotion trajectory:")
                    self.logger.info(f"   Before: {original_mood.my_tags} (效价: {original_mood.my_valence}, 强度: {original_mood.my_intensity})")
                    self.logger.info(f"   After:  {new_mood.my_tags} (效价: {new_mood.my_valence}, 强度: {new_mood.my_intensity})")
                    self.logger.info(f"   Change: User impact ({user_emotion_impact.get('impact_tags', '无')}) + Plot context")
                
            except Exception as emotion_update_error:
                self.logger.error(f"[process_query session:{session_id}] ❌ Dynamic emotion update failed: {emotion_update_error}")
                self.logger.info(f"[process_query session:{session_id}] Continuing with existing mood state")

            # 3. 检测是否需要工具（仅用于system prompt指导，不强制调用）
            needs_tools = self._detect_tool_need(query, analysis_result)
            self.logger.info(f"[process_query session:{session_id}] Tool detection result: {needs_tools}")

            # 4. 构建系统提示词（包含工具使用决策指导）
            current_plot = await self.get_current_plot_content()
            system_prompt = self._build_system_prompt(inner_os, needs_tools, user_id, current_plot)
            self.logger.info(f"[process_query session:{session_id}] Built system prompt with tools={needs_tools}, plot_segments={len(current_plot)}")

            # 5. 获取对话历史（从MySQL和Redis）
            conversation_history = []
            try:
                conversation_history = await self.conversation_storage.get_conversation_history(session_id, limit=10)
                self.logger.info(f"[process_query session:{session_id}] Loaded {len(conversation_history)} history messages")
            except Exception as e:
                self.logger.error(f"[process_query session:{session_id}] Error fetching history: {e}")
            
            # 6. 构建消息列表
            messages = [SystemMessage(content=system_prompt)]
            for msg in conversation_history:
                if msg["type"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["type"] in ["ai", "assistant", "agent"]:
                    messages.append(AIMessage(content=msg["content"]))
            
            current_query_content = query
            if location:
                current_query_content += f" (相关地点: {location})"
            messages.append(HumanMessage(content=current_query_content))
            
            # 7. 保存用户消息到Redis
            try:
                await self.conversation_storage.save_message_to_redis(
                    session_id=session_id,
                    user_name=user_id,
                    sender_type="user",
                    message_content=query
                )
            except Exception as e:
                self.logger.error(f"[process_query session:{session_id}] Error saving user message: {e}")
            
            response_content = "抱歉，我无法生成有效的回复。"
            tools_used_names = []
            system_message = ""  # 新增：系统消息

            try:
                # 8. 让LLM根据情绪状态和人设自主决定是否使用工具
                if self.mcp_tools and needs_tools:
                    self.logger.info(f"[process_query session:{session_id}] Using ReAct agent with {len(self.mcp_tools)} MCP tools - LLM will decide autonomously")
                    
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
                        
                        if tools_used_names:
                            self.logger.info(f"[process_query session:{session_id}] LLM chose to use tools: {tools_used_names}")
                        else:
                            self.logger.info(f"[process_query session:{session_id}] LLM chose NOT to use tools")
                        
                    except Exception as tool_error:
                        # 如果工具调用失败，尝试使用简单的LLM响应
                        error_str = str(tool_error).lower()
                        if "user location is not supported" in error_str or "geographical" in error_str:
                            self.logger.warning(f"[process_query session:{session_id}] Geographical restriction detected, falling back to simple LLM")
                            # 使用带内心OS的简化消息
                            llm_response = await self.llm.ainvoke(messages)
                            response_content = llm_response.content
                        else:
                            raise tool_error  # 重新抛出非地理位置相关的错误
                else:
                    self.logger.info(f"[process_query session:{session_id}] Using LLM directly (no tools needed or available)")
                    llm_response = await self.llm.ainvoke(messages)
                    response_content = llm_response.content
                
                if not isinstance(response_content, str):
                    response_content = str(response_content)
                
                if not response_content:
                    response_content = "抱歉，我无法生成有效的回复。"

                # 🚨 关键修复：检查并过滤内心OS泄露
                if self._check_inner_os_leak(response_content):
                    self.logger.warning(f"[process_query session:{session_id}] Detected inner OS leak, using intelligent fallback response...")
                    response_content = await self._generate_intelligent_fallback_response(query, messages)
                    self.logger.info(f"[process_query session:{session_id}] Intelligent fallback response generated successfully")

            except Exception as e:
                self.logger.error(f"[process_query session:{session_id}] Error during agent execution: {e}", exc_info=True)
                
                # 检查错误类型并设置系统消息，不污染角色回复
                error_str = str(e).lower()
                if "user location is not supported" in error_str or "geographical" in error_str:
                    system_message = "⚠️ 地理位置限制：当前服务对您的地理位置有限制，请稍后再试。"
                    response_content = "不好意思，我这边有点技术问题，不过我们还是可以聊天的！你刚才问什么来着？"
                elif "broken pipe" in error_str or "connection" in error_str:
                    system_message = "⚠️ 网络连接错误：网络连接出现问题，请检查网络设置或稍后再试。"
                    response_content = "网络好像有点问题，不过我还在这里！你可以重新问一下刚才的问题。"
                elif "timeout" in error_str:
                    system_message = "⚠️ 响应超时：服务响应超时，请稍后再试。"
                    response_content = "响应有点慢，可能是网络问题。你可以再试一次，或者换个问题问我。"
                elif "api" in error_str or "quota" in error_str or "rate" in error_str:
                    system_message = "⚠️ API服务错误：AI服务暂时不可用，可能是配额限制，请稍后再试。"
                    # 不保存任何回复到历史记录，让角色状态保持正常
                    response_content = ""
                elif "googleapi" in error_str or "gemini" in error_str:
                    system_message = "⚠️ Google AI服务错误：Google AI服务出现问题，请稍后再试。"
                    response_content = ""
                else:
                    system_message = f"⚠️ 系统错误：{type(e).__name__} - 请稍后再试或联系技术支持。"
                    response_content = ""
                    
                # 记录具体的错误信息用于调试
                self.logger.error(f"[process_query session:{session_id}] Detailed error info: Type={type(e).__name__}, Message={str(e)[:200]}")

            # 9. 只在有有效角色回复时才保存到Redis
            if response_content and response_content.strip():
                try:
                    await self.conversation_storage.save_message_to_redis(
                        session_id=session_id,
                        user_name=user_id,
                        sender_type="agent",
                        message_content=response_content
                    )
                except Exception as e:
                    self.logger.error(f"[process_query session:{session_id}] Error saving AI message: {e}")
            else:
                self.logger.info(f"[process_query session:{session_id}] No valid response to save, skipping message storage")

            # 10. 改进的持久化策略：更积极地持久化数据
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

            self.logger.info(f"[process_query session:{session_id}] Returning response: '{response_content[:100] if response_content else 'SYSTEM_ERROR'}...', system_message: '{system_message}'")
            return {
                **state,
                "response": response_content,
                "tools_used": list(set(tools_used_names)),
                "session_id": session_id,
                "system_message": system_message,
                "messages": messages + ([AIMessage(content=response_content)] if response_content else []), 
                "conversation_history": conversation_history + (
                    [{"type": "user", "content": query}, {"type": "agent", "content": response_content}] 
                    if response_content else [{"type": "user", "content": query}]
                )
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
                "conversation_history": result.get("conversation_history", []),
                "system_message": result.get("system_message", "")
            }
            
        except Exception as e:
            self.logger.error(f"[run session:{active_session_id}] Error during graph invocation: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "session_id": active_session_id,
                "query": query,
                "location": location,
                "system_message": ""
            }

    async def cleanup(self):
        """清理资源"""
        if self.mcp_client:
            try:
                # 检查MCP客户端是否有close方法
                if hasattr(self.mcp_client, 'close'):
                    await self.mcp_client.close()
                elif hasattr(self.mcp_client, 'cleanup'):
                    await self.mcp_client.cleanup()
                else:
                    # 如果没有标准的清理方法，尝试清理内部资源
                    if hasattr(self.mcp_client, '_clients'):
                        for client_name, client in self.mcp_client._clients.items():
                            if hasattr(client, 'close'):
                                await client.close()
                            self.logger.info(f"Closed MCP client: {client_name}")
                    
                self.logger.info("MCP client closed successfully")
            except Exception as e:
                self.logger.error(f"Error closing MCP client: {e}")
        
        # 清理其他资源
        self.mcp_tools = []
        self.graph = None

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

    async def initialize_role(self):
        """初始化角色信息和情绪状态"""
        if not self.role_id or not self.role_config:
            self.logger.error("❌ 无法初始化角色：角色ID或配置未设置")
            return False
            
        try:
            # 从Redis获取角色情绪状态
            self.current_role_mood = await self.role_manager.get_role_mood_from_redis(self.role_id)
            
            if self.current_role_mood:
                self.logger.info(f"✅ 从Redis加载角色情绪状态: {self.role_config.role_name}")
                self.logger.info(f"历史情绪状态: {self.current_role_mood.my_tags}, 强度: {self.current_role_mood.my_intensity}")
            else:
                self.logger.warning(f"⚠️ Redis中未找到角色情绪状态: {self.role_config.role_name}, 使用配置中的初始情绪")
                # 尝试从数据库加载并存储到Redis
                role_detail = await self.role_manager.get_role(self.role_id)
                if role_detail:
                    await self.role_manager.load_role_mood_to_redis(self.role_id)
                    self.current_role_mood = role_detail.mood
                    self.logger.info(f"✅ 从数据库加载并缓存角色情绪状态: {self.role_config.role_name}")
                else:
                    # 使用配置中的初始情绪状态
                    self.current_role_mood = self._get_mood_from_config()
                    self.logger.info(f"✅ 使用配置中的初始情绪状态: {self.role_config.role_name}")
            
            # 【新增】根据当前剧情内容更新情绪状态
            try:
                self.logger.info(f"🎭 开始根据当前剧情更新情绪状态...")
                
                # 获取当前时间的剧情内容
                current_plot = await self.get_current_plot_content()
                
                if current_plot and len(current_plot) > 0:
                    self.logger.info(f"📖 获取到 {len(current_plot)} 条剧情内容，开始情绪分析...")
                    
                    # 🔧 添加超时处理 - 使用思维链生成器分析剧情并更新情绪
                    import asyncio
                    try:
                        updated_mood_data = await asyncio.wait_for(
                            self.thought_generator.process_plot_events_and_update_mood(
                                self.role_id, current_plot
                            ),
                            timeout=15.0  # 15秒超时
                        )
                        
                        if updated_mood_data:
                            # 创建新的情绪状态
                            from role_detail import RoleMood
                            updated_mood = RoleMood(
                                my_valence=updated_mood_data.get('my_valence', self.current_role_mood.my_valence),
                                my_arousal=updated_mood_data.get('my_arousal', self.current_role_mood.my_arousal),
                                my_tags=updated_mood_data.get('my_tags', self.current_role_mood.my_tags),
                                my_intensity=updated_mood_data.get('my_intensity', self.current_role_mood.my_intensity),
                                my_mood_description_for_llm=updated_mood_data.get('my_mood_description_for_llm', self.current_role_mood.my_mood_description_for_llm)
                            )
                            
                            # 更新情绪状态
                            await self.update_role_mood(updated_mood)
                            
                            self.logger.info(f"✅ 基于剧情更新情绪成功: {updated_mood.my_tags} (强度: {updated_mood.my_intensity}/10)")
                            self.logger.info(f"🎯 情绪变化: {self.current_role_mood.my_tags} → {updated_mood.my_tags}")
                        else:
                            self.logger.warning(f"⚠️ 剧情情绪分析未返回有效数据，保持当前情绪状态")
                            
                    except asyncio.TimeoutError:
                        self.logger.warning(f"⚠️ 剧情情绪分析超时，跳过此步骤，保持现有情绪状态: {self.current_role_mood.my_tags}")
                    except Exception as analysis_error:
                        self.logger.error(f"❌ 剧情情绪分析失败: {analysis_error}")
                        self.logger.info(f"🔄 跳过剧情分析，使用现有情绪状态: {self.current_role_mood.my_tags}")
                        
                else:
                    self.logger.info(f"📝 当前时间没有剧情内容，保持现有情绪状态: {self.current_role_mood.my_tags}")
                    
            except Exception as plot_error:
                self.logger.error(f"❌ 剧情情绪更新失败: {plot_error}")
                self.logger.info(f"🔄 继续使用已加载的情绪状态: {self.current_role_mood.my_tags}")
                    
            return True
        except Exception as e:
            self.logger.error(f"❌ 初始化角色信息失败: {e}")
            self.current_role_mood = self._get_mood_from_config()
            return False
    
    def _get_mood_from_config(self) -> RoleMood:
        """从角色配置获取初始情绪状态"""
        if self.role_config and self.role_config.initial_mood:
            return RoleMood(
                my_valence=self.role_config.initial_mood.get("my_valence", 0.0),
                my_arousal=self.role_config.initial_mood.get("my_arousal", 0.3),
                my_tags=self.role_config.initial_mood.get("my_tags", "中性"),
                my_intensity=self.role_config.initial_mood.get("my_intensity", 3),
                my_mood_description_for_llm=self.role_config.initial_mood.get("my_mood_description_for_llm", "当前状态比较中性")
            )
        else:
            return self._get_fallback_mood_state()

    def _check_inner_os_leak(self, response_content: str) -> bool:
        """超强化版内心OS泄露检测 - 检查回复中是否包含任何形式的内心活动或指导性内容"""
        if not isinstance(response_content, str):
            return False
        
        # 检查各种内心OS和指导性内容格式
        forbidden_patterns = [
            # 传统内心OS格式
            "（内心OS：", "内心OS：",
            "（内心想法：", "内心想法：", 
            "（心里想：", "心里想：",
            "（内心独白：", "内心独白：",
            
            # 指导性括号内容（这次泄露的主要问题）
            "（稍微", "（解释", "（想想", "（不要透露", "（找个理由", "（态度要",
            "（然后", "（但不要", "（要", "（试着", "（尽量", "（避免",
            
            # meta层面的策略描述
            "（策略", "（计划", "（打算", "（准备", "（决定",
            
            # 思维过程泄露
            "（思考", "（考虑", "（分析", "（判断", "（评估",
            
            # 情绪指导泄露  
            "（表现出", "（显得", "（装作", "（假装", "（演示",
            
            # 对话策略泄露
            "（转移话题", "（结束对话", "（敷衍", "（应付", "（回避",
            
            # 🚨 新增：情感分析类泄露（用户新发现的问题）
            "（他对我", "（她对我", "（这人", "（这个人", "（用户",
            "（造物主", "（他们", "（她们", "（对方",
            "（挺好的", "（不错", "（还行", "（很好", "（真的",
            "（应该", "（可能", "（或许", "（大概", "（估计",
            
            # 关系评价类泄露
            "（关系", "（友好", "（亲近", "（疏远", "（信任",
            
            # 性格评价类泄露  
            "（性格", "（人品", "（脾气", "（态度", "（为人"
        ]
        
        # 检查是否包含任何禁止的模式
        for pattern in forbidden_patterns:
            if pattern in response_content:
                self.logger.warning(f"检测到内心OS泄露模式: {pattern}")
                return True
        
        # 额外检查：任何以（开头但不是正常表情或感叹的内容
        import re
        # 查找所有括号内容
        bracket_contents = re.findall(r'（[^）]*）', response_content)
        for content in bracket_contents:
            # 排除正常的表情和简单感叹
            if not any(normal in content for normal in ["笑", "叹气", "摇头", "点头", "哭", "汗", "...", "额", "嗯", "啊", "哈"]): 
                # 如果括号内容超过3个字且不是表情，很可能是思维泄露
                content_without_brackets = content[1:-1]  # 去掉括号
                if len(content_without_brackets) > 2:  # 超过2个字符的内容需要检查
                    self.logger.warning(f"检测到可疑的括号内容: {content}")
                    return True
        
        return False

    async def _regenerate_response_without_inner_os(self, messages: List, session_id: str, query: str) -> str:
        """重新生成没有内心OS的回复 - 完全避免硬编码"""
        try:
            # 构建极其严格的禁止内心OS的消息
            enhanced_messages = messages.copy()
            
            # 在最后添加超强指令
            strict_instruction = """
🚨🚨🚨 ABSOLUTE CRITICAL INSTRUCTION 🚨🚨🚨

**你的回复绝对不能包含任何括号内的思维、指导、策略内容！**
**绝对禁止输出类似"（稍微解释一下...）"这样的指导性文字！**
**只能输出角色会真实说出口的自然对话！**

**检查清单：**
1. 是否有任何（...）括号内容？→ 必须删除
2. 是否有指导性、策略性文字？→ 必须删除
3. 是否只包含自然对话？→ 必须确保

**直接基于你当前的情绪状态自然回复，不要任何meta描述！**
            """.strip()
            
            enhanced_messages.append(HumanMessage(content=strict_instruction))
            
            # 重新调用LLM
            llm_response = await self.llm.ainvoke(enhanced_messages)
            regenerated_content = llm_response.content
            
            # 严格二次检查
            if self._check_inner_os_leak(regenerated_content):
                self.logger.error(f"重新生成的回复仍有内心OS泄露，使用智能备用方案")
                return await self._generate_intelligent_fallback_response(query, messages)
            
            return regenerated_content
            
        except Exception as e:
            self.logger.error(f"重新生成回复失败: {e}")
            return await self._generate_intelligent_fallback_response(query, messages)
    
    async def _generate_intelligent_fallback_response(self, user_input: str = "", original_messages: List = None) -> str:
        """智能生成备用回复 - 完全避免硬编码，基于LLM生成"""
        
        try:
            # 构建专门的备用回复生成prompt
            fallback_prompt = f"""你是{self.role_config.role_name if self.role_config else '凌夜'}，现在需要对用户的话做出简短自然的回复。

用户说：{user_input}

你当前的情绪状态：{self.current_role_mood.my_tags if self.current_role_mood else '中性'}（强度：{self.current_role_mood.my_intensity if self.current_role_mood else 3}/10）

要求：
1. 根据你的情绪状态自然回复
2. 回复要简短（1-2句话）
3. 体现你的性格特点
4. 绝对不能包含任何括号内容
5. 不要解释或分析，直接对话

直接输出你会说的话："""

            # 使用简单的LLM调用生成备用回复
            fallback_messages = [HumanMessage(content=fallback_prompt)]
            
            try:
                fallback_response = await self.llm.ainvoke(fallback_messages)
                fallback_content = fallback_response.content.strip()
                
                # 最后检查一次
                if self._check_inner_os_leak(fallback_content):
                    # 如果还有问题，使用最基础的情绪化回复
                    return self._get_basic_emotional_response(user_input)
                
                return fallback_content
                
            except Exception as llm_error:
                self.logger.error(f"LLM备用回复生成失败: {llm_error}")
                return self._get_basic_emotional_response(user_input)
                
        except Exception as e:
            self.logger.error(f"智能备用回复生成失败: {e}")
            return self._get_basic_emotional_response(user_input)
    
    def _get_basic_emotional_response(self, user_input: str = "") -> str:
        """最基础的情绪化回复 - 仅在所有其他方法都失败时使用"""
        
        # 基于当前情绪强度生成回复
        if self.current_role_mood and self.current_role_mood.my_intensity >= 7:
            # 高强度情绪 - 较为激烈的回应
            return "心情不好，别烦我。"
        elif self.current_role_mood and self.current_role_mood.my_intensity >= 5:
            # 中等强度情绪 - 有些不耐烦
            return "没什么心情，不想聊。"
        else:
            # 低强度情绪 - 相对平和
            return "嗯，没什么可说的。"

    def _generate_fallback_response(self, user_input: str = "") -> str:
        """保持向后兼容的备用回复函数 - 现在调用智能版本"""
        import asyncio
        try:
            # 在同步函数中调用异步函数
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果已经在事件循环中，创建一个任务
                task = asyncio.create_task(self._generate_intelligent_fallback_response(user_input))
                return self._get_basic_emotional_response(user_input)  # 临时返回，直到异步完成
            else:
                return loop.run_until_complete(self._generate_intelligent_fallback_response(user_input))
        except Exception:
            return self._get_basic_emotional_response(user_input)

    async def _analyze_user_message_emotion_impact(self, user_input: str, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """角色自己大脑的情绪影响分析 - 第一人称主观分析模式（基于thought_chain_generator风格）"""
        try:
            # 提取用户的情感分析结果
            emotion_result = analysis_result.get('emotion_result', {})
            intention_result = analysis_result.get('intention_result', {})
            
            user_valence = emotion_result.get('valence', 0.0)
            user_arousal = emotion_result.get('arousal', 0.0)
            user_tags = emotion_result.get('tags', '中性')
            user_intensity = emotion_result.get('intensity', 5)
            targeting_object = emotion_result.get('targeting_object', '不明确')
            user_intention = intention_result.get('intention', '未知')
            
            # 🚀 角色自己大脑的情绪影响分析（参考thought_chain_generator风格）
            my_brain_analysis_prompt = f"""我是{self.role_config.role_name if self.role_config else '凌夜'}，现在需要分析刚才对方的话对我情绪的影响。

## 我的性格特质和人设背景：
{self.l0_prompt_content[:500] if self.l0_prompt_content else '我是一个具有独立人格的个体'}...

## 我当前的情绪状态：
- 我现在的情绪：{self.current_role_mood.my_tags if self.current_role_mood else '中性'}
- 我的情绪强度：{self.current_role_mood.my_intensity if self.current_role_mood else 5}/10
- 我的心境：{self.current_role_mood.my_mood_description_for_llm if self.current_role_mood else '比较平静'}

## 对方刚才说了什么：
**对方的话**: "{user_input}"
**我分析出对方的情绪**: {user_tags} (效价: {user_valence:.2f}, 强度: {user_intensity}/10)
**我判断对方的意图**: {user_intention}
**对方是否在针对我**: {targeting_object}

## 我需要从自己的角度分析：

### 1. 我对这话的第一反应：
- 对方这话让我感觉如何？
- 是在关心我、帮助我，还是在冒犯我？
- 这话触动了我的什么情绪？

### 2. 基于我的性格特质分析：
- 以我的性格，我会如何理解这话？
- 这符合我对对方的印象吗？
- 我的价值观让我如何看待这种说话方式？

### 3. 我的情绪反应程度：
- 这话对我的情绪冲击有多大？
- 我是容易被这种话影响的人吗？
- 考虑到我当前的心境，我的反应会更强烈还是更平和？

## 我的分析结果：
请以我的第一人称视角回答，格式：
**我的情绪是否受影响** | **影响类型** | **影响程度(1-10)** | **我的主观感受**

要求：
- 用"我"的口吻表达我的主观感受
- 体现我独特的性格特质对分析的影响
- 考虑我当前的情绪状态如何影响我的反应
- 如果是简单问候或无针对性的话，我可能不会有什么情绪波动

示例：
- 我没什么感觉 | 无影响 | 0 | 就是个普通问候，我不会因为这种话产生什么情绪波动
- 我感到被认可 | 正面影响 | 6 | 对方这话让我感觉被理解和支持，心情会好一些
- 我感到被冒犯 | 负面影响 | 8 | 对方这种说话方式让我很不爽，明显是在贬低我"""

            # 使用角色自己大脑的分析prompt进行情绪影响判断
            my_analysis_response = await self.llm.ainvoke([HumanMessage(content=my_brain_analysis_prompt)])
            my_analysis_result = my_analysis_response.content.strip()
            
            # 解析我的主观分析结果
            parts = my_analysis_result.split('|')
            if len(parts) >= 4:
                my_feeling = parts[0].strip()
                my_impact_type = parts[1].strip()
                my_impact_strength = parts[2].strip()
                my_subjective_feeling = parts[3].strip()
                
                self.logger.info(f"🧠 我的大脑分析: {my_feeling} | {my_impact_type} | {my_impact_strength} | {my_subjective_feeling}")
                
                # 解析影响强度
                try:
                    impact_intensity = int(my_impact_strength)
                except:
                    impact_intensity = 0 if "无影响" in my_impact_type or "没什么感觉" in my_feeling else 3
                
                # 如果我认为没有情绪影响
                if impact_intensity == 0 or "没什么感觉" in my_feeling or "无影响" in my_impact_type:
                    self.logger.info(f"✅ 我的分析：这话对我没什么情绪影响 - {my_subjective_feeling}")
                    return {
                        "impact_valence": 0.0,
                        "impact_arousal": 0.0,
                        "impact_tags": "我没什么感觉",
                        "impact_intensity": 0,
                        "impact_description": f"我的主观分析：{my_subjective_feeling}",
                        "user_emotion_summary": f"对方说：{user_input}",
                        "confidence": 0.9,
                        "my_brain_analysis": my_subjective_feeling
                    }
                
                # 我认为有情绪影响，计算具体的情绪变化数值
                impact_valence = 0.0
                impact_arousal = 0.0
                impact_tags = "我的情绪有变化"
                
                # 根据我的主观分析确定影响方向和强度
                if "正面" in my_impact_type or "被认可" in my_feeling or "开心" in my_feeling or "高兴" in my_feeling:
                    # 正面影响
                    impact_valence = min(0.5, impact_intensity * 0.08)  # 最大0.5的正面影响
                    if "认可" in my_feeling or "支持" in my_subjective_feeling:
                        impact_tags = "我感到被认可"
                    elif "开心" in my_feeling or "愉快" in my_subjective_feeling:
                        impact_tags = "我心情变好了"
                    else:
                        impact_tags = "我有正面感受"
                        
                elif "负面" in my_impact_type or "冒犯" in my_feeling or "不爽" in my_feeling or "生气" in my_feeling:
                    # 负面影响
                    impact_valence = max(-0.5, -impact_intensity * 0.08)  # 最大-0.5的负面影响
                    impact_arousal = min(0.3, impact_intensity * 0.03)  # 增加激活度
                    if "冒犯" in my_feeling or "侮辱" in my_subjective_feeling:
                        impact_tags = "我感到被冒犯"
                    elif "不爽" in my_feeling or "烦" in my_subjective_feeling:
                        impact_tags = "我感到不快"
                    else:
                        impact_tags = "我有负面感受"
                else:
                    # 中性或复杂影响
                    impact_valence = 0.0
                    impact_tags = "我的情绪有微妙变化"
                
                # 基于我当前的情绪状态调整影响程度
                if self.current_role_mood and self.current_role_mood.my_intensity >= 7:
                    # 如果我当前情绪强度很高，影响会被放大
                    impact_valence *= 1.2
                    impact_arousal *= 1.2
                    self.logger.info(f"💥 我当前情绪强度高({self.current_role_mood.my_intensity}/10)，影响被放大")
                elif self.current_role_mood and self.current_role_mood.my_intensity <= 3:
                    # 如果我当前情绪强度很低，影响会被减弱
                    impact_valence *= 0.7
                    impact_arousal *= 0.7
                    self.logger.info(f"😴 我当前情绪强度低({self.current_role_mood.my_intensity}/10)，影响被减弱")
                
                # 构建最终结果
                final_result = {
                    "impact_valence": round(impact_valence, 3),
                    "impact_arousal": round(impact_arousal, 3),
                    "impact_tags": impact_tags,
                    "impact_intensity": impact_intensity,
                    "impact_description": f"我的主观分析：{my_subjective_feeling}",
                    "user_emotion_summary": f"对方情绪：{user_tags}（强度{user_intensity}）",
                    "confidence": 0.9,
                    "my_brain_analysis": my_subjective_feeling,
                    "my_feeling": my_feeling,
                    "my_analysis_details": {
                        "原始分析": my_analysis_result,
                        "我的感受": my_feeling,
                        "影响类型": my_impact_type,
                        "影响强度": impact_intensity,
                        "主观感受": my_subjective_feeling
                    }
                }
                
                self.logger.info(f"✅ 我的情绪影响分析完成: {impact_tags} (效价影响: {impact_valence:.3f}, 强度: {impact_intensity})")
                return final_result
                
            else:
                # 解析失败，抛出异常而不是使用备用逻辑
                raise RuntimeError(f"我的大脑分析结果格式异常，无法解析: {my_analysis_result}")
                
        except Exception as e:
            self.logger.error(f"❌ 我的情绪影响分析失败: {e}")
            # 不再提供备用逻辑，直接抛出异常
            raise RuntimeError(f"我的大脑无法分析这条消息的情绪影响: {e}")

    async def _synthesize_emotion_impacts(self, plot_impact: Dict[str, Any], user_impact: Dict[str, Any]) -> RoleMood:
        """合成剧情影响和用户消息影响，按7:3权重计算新的情绪状态"""
        try:
            # 获取当前情绪状态作为基准
            current_mood = self.current_role_mood or self._get_fallback_mood_state()
            
            # 剧情影响权重：0.7，用户消息影响权重：0.3
            plot_weight = 0.7
            user_weight = 0.3
            
            # 计算效价变化
            plot_valence_change = plot_impact.get('my_valence', current_mood.my_valence) - current_mood.my_valence
            user_valence_change = user_impact.get('impact_valence', 0.0)
            
            # 合成效价
            total_valence_change = plot_valence_change * plot_weight + user_valence_change * user_weight
            new_valence = max(-1.0, min(1.0, current_mood.my_valence + total_valence_change))
            
            # 计算激活度变化
            plot_arousal_change = plot_impact.get('my_arousal', current_mood.my_arousal) - current_mood.my_arousal
            user_arousal_change = user_impact.get('impact_arousal', 0.0)
            
            # 合成激活度
            total_arousal_change = plot_arousal_change * plot_weight + user_arousal_change * user_weight
            new_arousal = max(0.0, min(1.0, current_mood.my_arousal + total_arousal_change))
            
            # 计算强度变化
            plot_intensity_change = plot_impact.get('my_intensity', current_mood.my_intensity) - current_mood.my_intensity
            user_intensity_change = user_impact.get('impact_intensity', 0)
            
            # 合成强度
            total_intensity_change = plot_intensity_change * plot_weight + user_intensity_change * user_weight
            new_intensity = max(1, min(10, int(current_mood.my_intensity + total_intensity_change)))
            
            # 合成情绪标签
            plot_tags = plot_impact.get('my_tags', '').split('、') if plot_impact.get('my_tags') else []
            user_tags = [user_impact.get('impact_tags', '')] if user_impact.get('impact_tags') and user_impact.get('impact_tags') not in ['无影响', '分析失败'] else []
            
            # 组合标签，剧情标签优先
            combined_tags = []
            
            # 添加剧情相关标签（权重更高）
            if plot_tags:
                combined_tags.extend([tag for tag in plot_tags if tag and tag != '中性'])
            
            # 添加用户影响标签
            if user_tags:
                combined_tags.extend(user_tags)
            
            # 如果没有特殊标签，根据效价和激活度确定基础标签
            if not combined_tags:
                if new_valence > 0.3 and new_arousal > 0.5:
                    combined_tags.append('兴奋')
                elif new_valence > 0.3:
                    combined_tags.append('愉快')
                elif new_valence < -0.3 and new_arousal > 0.5:
                    combined_tags.append('愤怒')
                elif new_valence < -0.3:
                    combined_tags.append('沮丧')
                else:
                    combined_tags.append('平静')
            
            new_tags = '、'.join(combined_tags[:3])  # 最多保留3个标签
            
            # 生成情绪描述
            plot_desc = plot_impact.get('my_mood_description_for_llm', '')
            user_desc = user_impact.get('impact_description', '')
            
            new_description = f"当前情绪受到剧情发展和用户互动的综合影响。"
            if plot_desc:
                new_description += f" 剧情影响：{plot_desc}。"
            if user_desc and user_impact.get('impact_tags') not in ['无影响', '分析失败']:
                new_description += f" 用户互动影响：{user_desc}。"
            new_description += f" 综合情绪强度：{new_intensity}/10。"
            
            # 创建新的情绪状态
            new_mood = RoleMood(
                my_valence=round(new_valence, 2),
                my_arousal=round(new_arousal, 2),
                my_tags=new_tags,
                my_intensity=new_intensity,
                my_mood_description_for_llm=new_description
            )
            
            # 日志记录
            self.logger.info(f"🔗 情绪合成完成:")
            self.logger.info(f"   原始: {current_mood.my_tags} (效价:{current_mood.my_valence}, 强度:{current_mood.my_intensity})")
            self.logger.info(f"   剧情影响(70%): {plot_impact.get('my_tags', '无')} (效价变化:{plot_valence_change:.2f})")
            self.logger.info(f"   用户影响(30%): {user_impact.get('impact_tags', '无')} (效价变化:{user_valence_change:.2f})")
            self.logger.info(f"   合成结果: {new_tags} (效价:{new_valence}, 强度:{new_intensity})")
            
            return new_mood
            
        except Exception as e:
            self.logger.error(f"❌ 情绪合成失败: {e}")
            return self.current_role_mood or self._get_fallback_mood_state()

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
    
    # 初始化代理 - 使用统一模型配置
    agent = EnhancedMCPAgent()
    
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