"""
MCP客户端
支持多轮对话、会话管理和真实MCP服务交互
新增：定时任务，每30分钟更新时间、获取剧情内容并更新情绪状态
"""

import asyncio
import aiohttp
import json
import os
import sys
from typing import Dict, Any, List
from datetime import datetime

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

# 新增导入
from time_plot_manager import TimePlotManager
from thought_chain_prompt_generator.thought_chain_generator import ThoughtChainPromptGenerator

class MCPClient:
    """MCP客户端"""
    
    def __init__(self, base_url: str = "http://localhost:8080", role_id: str = None):
        """初始化客户端"""
        self.base_url = base_url
        self.session_id = ""
        self.user_id = ""
        self.role_id = role_id
        self.current_role_name = ""
        
        # 新增：时间剧情管理器和情绪更新器
        self.time_plot_manager = TimePlotManager()
        self.mood_updater = ThoughtChainPromptGenerator()
        self.periodic_task = None
        
        print(f"💻 MCP客户端已初始化，服务器地址: {base_url}")
    
    async def get_available_roles(self) -> List[Dict[str, Any]]:
        """获取可用角色列表"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/roles/available") as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("roles", [])
                    else:
                        print(f"❌ 获取角色列表失败: {response.status}")
                        return []
        except Exception as e:
            print(f"❌ 获取角色列表异常: {e}")
            return []
    
    async def select_role(self, role_id: str) -> bool:
        """选择角色"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/roles/select",
                    json={"role_id": role_id}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("success"):
                            self.role_id = role_id
                            self.current_role_name = data.get("role", {}).get("role_name", "")
                            print(f"✅ 角色选择成功: {self.current_role_name}")
                            return True
                        else:
                            print(f"❌ 角色选择失败: {data.get('message', '未知错误')}")
                            return False
                    else:
                        error_text = await response.text()
                        print(f"❌ 角色选择失败: HTTP {response.status} - {error_text}")
                        return False
        except Exception as e:
            print(f"❌ 角色选择异常: {e}")
            return False
    
    async def start_chat(self, user_name: str) -> bool:
        """开始聊天会话 - 支持智能会话管理"""
        if not self.role_id:
            print("❌ 请先选择角色")
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/start",
                    json={"role_id": self.role_id, "user_name": user_name}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("success"):
                            self.session_id = data.get("session_id", "")
                            self.user_id = user_name
                            
                            # 显示会话信息
                            session_type = data.get("session_type", "unknown")
                            history_count = data.get("history_count", 0)
                            
                            if session_type == "resumed":
                                print(f"✅ 继续历史对话")
                                print(f"📚 找到 {history_count} 条历史对话记录")
                                session_info = data.get("session_info", {})
                                if session_info.get("last_message_at"):
                                    last_time = session_info["last_message_at"][:16].replace("T", " ")
                                    print(f"⏰ 上次对话: {last_time}")
                            else:
                                print(f"✅ 开始新的对话")
                            
                            print(f"👤 用户: {user_name}")
                            print(f"🤖 角色: {self.current_role_name}")
                            print(f"📝 会话ID: {self.session_id[:8]}...")
                            
                            # 如果是复用会话且有历史记录，显示最近几条
                            if session_type == "resumed" and history_count > 0:
                                print(f"\n💭 {self.current_role_name} 会记住你们之前的对话内容")
                                
                            return True
                        else:
                            print(f"❌ 开始聊天失败: {data.get('message', '未知错误')}")
                            return False
                    else:
                        error_text = await response.text()
                        print(f"❌ 开始聊天失败: HTTP {response.status} - {error_text}")
                        return False
        except Exception as e:
            print(f"❌ 开始聊天异常: {e}")
            return False

    async def query(self, message: str, location: str = "") -> Dict[str, Any]:
        """发送查询消息"""
        if not self.session_id:
            print("❌ 请先开始聊天会话")
            return {"success": False, "error": "未开始会话"}
        
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "query": message,
                    "location": location,
                    "session_id": self.session_id,
                    "user_id": self.user_id
                }
                
                async with session.post(
                    f"{self.base_url}/query",
                    json=data
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        print(f"❌ 查询失败: HTTP {response.status} - {error_text}")
                        return {"success": False, "error": f"HTTP {response.status}"}
        except Exception as e:
            print(f"❌ 查询异常: {e}")
            return {"success": False, "error": str(e)}
    
    async def interactive_chat(self):
        """交互式聊天模式"""
        if not self.role_id:
            print("❌ 未选择角色，无法开始聊天")
            return
        
        if not self.session_id:
            print("❌ 未开始会话，无法聊天")
            return
        
        print(f"\n💬 开始与 {self.current_role_name} 聊天")
        print("📝 输入消息开始对话，输入 'quit' 退出聊天")
        print("=" * 50)
        
        while True:
            try:
                # 获取用户输入
                user_input = input(f"\n👤 {self.user_id}: ").strip()
                
                if user_input.lower() in ['quit', 'exit', '退出', 'q']:
                    print("👋 聊天结束")
                    break
                
                if not user_input:
                    continue
                
                # 发送查询
                print("🤔 思考中...")
                result = await self.query(user_input)
                
                if result.get("success"):
                    response = result.get("response", "")
                    tools_used = result.get("tools_used", [])
                    
                    print(f"\n🤖 {self.current_role_name}: {response}")
                    
                    if tools_used:
                        print(f"🔧 使用了工具: {', '.join(tools_used)}")
                else:
                    print(f"❌ 对话失败: {result.get('error', '未知错误')}")
                    
            except KeyboardInterrupt:
                print("\n👋 聊天中断")
                break
            except Exception as e:
                print(f"❌ 聊天异常: {e}")

async def demo_enhanced_client():
    """演示客户端的基本连接和信息获取功能。"""
    print("🚀 启动MCP客户端演示 (基本连接测试)...")
    print("----------------------------------------------------")
    print("此演示仅测试连接，不包含交互式对话。")
    print("如需与AI助手对话，请运行: python chat.py")
    print("或: python client.py interactive")
    print("----------------------------------------------------")

    async with EnhancedMCPClient() as client:
        try:
            # 1. 健康检查
            print("\n1️⃣ 健康检查...")
            health = await client.health_check()
            print(f"服务状态: {health}")
            
            if not health.get("agent_ready"):
                print("❌ 代理未就绪，请先启动服务器 (python server.py)")
                return
            else:
                print("✅ 服务器连接成功，代理已就绪。")

            # 2. 获取角色信息
            print("\n2️⃣ 获取角色信息...")
            role_info = await client.get_role_info()
            print(f"代理名称: {role_info.get('agent_name')}")
            print(f"能力: {role_info.get('capabilities')}")

            # 3. 获取MCP信息
            print("\n3️⃣ 获取MCP信息...")
            mcp_info = await client.get_mcp_info()
            print(f"MCP协议版本: {mcp_info.get('version')}")
            print(f"可用功能: {mcp_info.get('agent', {}).get('features', [])}")
            print(f"可用工具数量: {len(mcp_info.get('tools', []))}")

            print("\n基本连接测试完成。")
            
        except aiohttp.client_exceptions.ClientConnectorError as e:
            print(f"❌ 连接服务器失败: {e}")
            print("💡 请确保MCP服务器 (server.py) 正在运行并且网络连接正常。")
        except Exception as e:
            print(f"❌ 客户端演示发生错误: {e}")

async def interactive_enhanced_client():
    """交互式客户端 - 优化用户体验"""
    print("🎯 欢迎使用MCP智能助手客户端！")
    print("=" * 50)
    
    async with EnhancedMCPClient() as client:
        try:
            # 检查服务状态
            print("🔄 正在连接服务器...")
            health = await client.health_check()
            if not health.get("agent_ready"):
                print("❌ 服务器未就绪，请先启动MCP服务器")
                print("💡 提示：运行 'python server.py' 启动服务器")
                return
            
            # 获取角色信息
            role_info = await client.get_role_info()
            agent_name = role_info.get("agent_name", "智能助手")
            capabilities = role_info.get("capabilities", [])
            
            print(f"✅ 成功连接到服务器！")
            print(f"🤖 当前助手: {agent_name}")
            print(f"🔧 助手能力: {', '.join(capabilities)}")
            print("=" * 50)
            
            # 简化用户设置
            print("\n📝 用户设置")
            user_id = input("请输入您的用户名 (默认: user): ").strip() or "user"
            print(f"👋 您好，{user_id}！")
            
            # 智能会话管理
            await _smart_session_setup(client, user_id, agent_name)
            
            # 显示帮助信息
            print(f"\n💬 现在您可以开始与{agent_name}对话了！")
            print("💡 输入 'help' 查看可用命令，输入 'quit' 退出")
            print("=" * 50)
            
            # 主对话循环
            conversation_count = 0
            while True:
                try:
                    # 动态提示符
                    prompt = f"\n[{conversation_count + 1}] 您: " if conversation_count > 0 else f"\n👤 您: "
                    user_input = input(prompt).strip()
                    
                    if not user_input:
                        print("💭 请输入您的问题或命令...")
                        continue
                    
                    # 处理退出命令
                    if user_input.lower() in ['quit', 'exit', '退出', 'q']:
                        print(f"\n👋 再见，{user_id}！感谢使用{agent_name}的服务！")
                        print("🌟 期待下次与您的对话！")
                        break
                    
                    # 处理帮助命令
                    elif user_input.lower() in ['help', '帮助', 'h']:
                        _show_help_menu(agent_name)
                        continue
                    
                    # 处理其他命令
                    elif await _handle_special_commands(client, user_input, user_id, agent_name):
                        continue
                    
                    # 处理正常对话
                    print("🔄 正在思考...")
                    result = await client.query(user_input)
                    
                    if result.get("success"):
                        response = result['response']
                        tools_used = result.get('tools_used', [])
                        
                        print(f"🤖 {agent_name}: {response}")
                        
                        # 显示工具使用信息
                        if tools_used:
                            tool_names = ', '.join(tools_used)
                            print(f"🔧 使用了工具: {tool_names}")
                        
                        conversation_count += 1
                        
                        # 每5轮对话提示一次功能
                        if conversation_count % 5 == 0:
                            print(f"\n💡 提示：您已进行了{conversation_count}轮对话。输入 'history' 查看历史记录")
                    else:
                        error_msg = result.get('error', '未知错误')
                        print(f"❌ 抱歉，处理您的请求时出现了问题: {error_msg}")
                        print("💡 请尝试重新表述您的问题，或输入 'help' 查看帮助")
                        
                except KeyboardInterrupt:
                    print(f"\n\n👋 检测到中断信号，正在退出...")
                    print(f"感谢使用{agent_name}的服务！")
                    break
                except Exception as e:
                    print(f"❌ 发生意外错误: {e}")
                    print("💡 请重试，或输入 'quit' 退出程序")
                    
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            print("💡 请确保服务器正在运行，然后重试")

async def _smart_session_setup(client, user_id: str, agent_name: str):
    """智能会话设置"""
    try:
        # 获取用户现有会话
        sessions_result = await client.get_user_sessions(user_id)
        sessions = sessions_result.get("sessions", [])
        
        if not sessions:
            # 没有现有会话，创建新会话
            print("📝 为您创建新的对话会话...")
            title = f"与{agent_name}的对话"
            session_result = await client.create_session(user_id, title)
            if session_result.get("success"):
                client.current_session_id = session_result.get("session_id", "")
                print(f"✅ 会话创建成功")
            else:
                print(f"⚠️ 会话创建失败，将使用临时会话")
        else:
            # 有现有会话，询问用户选择
            print(f"\n📋 找到您的 {len(sessions)} 个历史会话:")
            
            # 显示最近的3个会话
            recent_sessions = sessions[:3]
            for i, session in enumerate(recent_sessions, 1):
                last_update = session.get('last_message_at', session.get('updated_at', ''))[:10] if session.get('last_message_at') or session.get('updated_at') else '未知'
                print(f"  {i}. {session.get('session_title', '未命名会话')} (最后更新: {last_update})")
            
            print("  n. 创建新会话")
            
            choice = input("\n请选择会话 (1-3/n，默认: 1): ").strip().lower()
            
            if choice == 'n':
                title = input("请输入新会话标题 (可选): ").strip() or f"与{agent_name}的新对话"
                session_result = await client.create_session(user_id, title)
                if session_result.get("success"):
                    client.current_session_id = session_result.get("session_id", "")
                    print(f"✅ 新会话 '{title}' 创建成功")
            elif choice in ['1', '2', '3', '']:
                try:
                    index = int(choice) - 1 if choice else 0
                    if 0 <= index < len(recent_sessions):
                        selected_session = recent_sessions[index]
                        client.current_session_id = selected_session['session_id']
                        print(f"✅ 已切换到会话: {selected_session.get('session_title', '未命名会话')}")
                        
                        # 显示最近几条对话
                        history_result = await client.get_conversation_history(selected_session['session_id'])
                        history = history_result.get("history", [])
                        if history:
                            print(f"📚 最近的对话记录 (共{len(history)}条):")
                            for msg in history[-3:]:
                                role = "您" if msg["type"] in ["user", "human"] else agent_name
                                content = msg["content"][:50] + "..." if len(msg["content"]) > 50 else msg["content"]
                                print(f"  {role}: {content}")
                    else:
                        print("⚠️ 无效选择，创建新会话")
                        session_result = await client.create_session(user_id)
                        if session_result.get("success"):
                            client.current_session_id = session_result.get("session_id", "")
                except ValueError:
                    print("⚠️ 无效输入，创建新会话")
                    session_result = await client.create_session(user_id)
                    if session_result.get("success"):
                        client.current_session_id = session_result.get("session_id", "")
                    
    except Exception as e:
        print(f"⚠️ 会话设置失败: {e}，将使用临时会话")

def _show_help_menu(agent_name: str):
    """显示帮助菜单"""
    print(f"""
🔧 {agent_name} 可用命令:

💬 对话命令:
  - 直接输入问题与{agent_name}对话
  - history    查看当前会话的对话历史
  - clear      清屏
  
🛠️ 工具命令:
  - tools      查看可用工具列表
  - weather    快速查询天气 (例: weather 北京)
  - search     快速搜索位置 (例: search 北京大学)
  - info       快速搜索信息 (例: info 人工智能)
  
📋 会话管理:
  - sessions   查看所有会话列表
  - new        创建新会话
  - switch     切换会话
  
😊 情绪状态管理:
  - mood       查看当前情绪状态
  - update-mood 手动更新情绪状态
  - plot       查看当前剧情内容
  
🔧 系统命令:
  - status     查看服务状态
  - role       查看助手信息
  - help       显示此帮助信息
  - quit       退出程序

💡 提示: 您可以直接问问题，{agent_name}会自动选择合适的工具来帮助您！
本客户端已启用定时情绪更新功能，每30分钟自动更新{agent_name}的情绪状态。
""")

async def _handle_special_commands(client, user_input: str, user_id: str, agent_name: str) -> bool:
    """处理特殊命令，返回True表示已处理"""
    command = user_input.lower().split()[0]
    
    try:
        # 新增：情绪状态相关命令
        if command == 'mood':
            mood = await client.get_current_mood()
            if mood:
                print(f"😊 {agent_name} 当前情绪状态:")
                print(f"  情感标签: {mood.get('my_tags', '未知')}")
                print(f"  情感强度: {mood.get('my_intensity', 0)}/10")
                print(f"  情感效价: {mood.get('my_valence', 0):.2f} (负值消极，正值积极)")
                print(f"  情感唤醒: {mood.get('my_arousal', 0):.2f} (0平静，1激动)")
                print(f"  心情描述: {mood.get('my_mood_description_for_llm', '未知')}")
            else:
                print(f"❌ 无法获取 {agent_name} 的情绪状态")
            return True
            
        elif command == 'update-mood':
            print(f"🔄 手动更新 {agent_name} 的情绪状态...")
            updated_mood = await client.force_update_mood()
            if updated_mood:
                print(f"✅ 情绪状态更新完成: {updated_mood.get('my_tags', '未知')} "
                      f"(强度: {updated_mood.get('my_intensity', 0)}/10)")
            else:
                print("❌ 情绪状态更新失败")
            return True
            
        elif command == 'plot':
            print(f"📖 获取 {agent_name} 当前的剧情内容...")
            plot_content = await client.time_plot_manager.get_role_current_plot_content(client.role_id)
            if plot_content:
                print(f"找到 {len(plot_content)} 条剧情内容:")
                for i, content in enumerate(plot_content, 1):
                    print(f"  {i}. {content}")
            else:
                print("当前时间没有找到剧情内容")
            return True
        
        # 原有命令保持不变
        elif command == 'tools':
            tools = await client.list_tools()
            print("📋 可用工具:")
            for tool in tools.get("tools", []):
                print(f"  🔧 {tool['name']}: {tool['description']}")
            return True
            
        elif command == 'history':
            if client.current_session_id:
                history_result = await client.get_conversation_history(client.current_session_id)
                history = history_result.get("history", [])
                if history:
                    print(f"📚 对话历史 (共{len(history)}条):")
                    for i, msg in enumerate(history[-10:], 1):
                        role = "您" if msg["type"] == "human" else agent_name
                        content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
                        print(f"  {i}. {role}: {content}")
                else:
                    print("📝 当前会话还没有对话记录")
            else:
                print("❌ 当前没有活跃的会话")
            return True
            
        elif command == 'sessions':
            sessions_result = await client.get_user_sessions(user_id)
            sessions = sessions_result.get("sessions", [])
            if sessions:
                print(f"📋 您的会话列表 (共{len(sessions)}个):")
                for i, session in enumerate(sessions[:10], 1):
                    status = "🟢 当前" if session['session_id'] == client.current_session_id else "⚪"
                    print(f"  {i}. {status} {session['title']} ({session['updated_at'][:10]})")
            else:
                print("📝 您还没有任何会话记录")
            return True
            
        elif command == 'new':
            title = ' '.join(user_input.split()[1:]) if len(user_input.split()) > 1 else ""
            if not title:
                title = input("请输入新会话标题: ").strip() or f"与{agent_name}的对话"
            session_result = await client.create_session(user_id, title)
            if session_result.get("success"):
                print(f"✅ 新会话 '{title}' 创建成功")
            else:
                print(f"❌ 会话创建失败: {session_result.get('error')}")
            return True
            
        elif command == 'status':
            health = await client.health_check()
            print(f"🏥 服务状态:")
            print(f"  服务器状态: {'✅ 正常' if health.get('status') == 'healthy' else '❌ 异常'}")
            print(f"  代理状态: {'✅ 就绪' if health.get('agent_ready') else '❌ 未就绪'}")
            print(f"  可用工具: {health.get('tools_available', 0)} 个")
            print(f"  当前角色: {health.get('current_role', '未知')}")
            
            # 显示定时任务状态
            print(f"  定时任务: {'✅ 运行中' if client._is_running else '❌ 未运行'}")
            return True
            
        elif command == 'role':
            role_info = await client.get_role_info()
            print(f"🤖 助手信息:")
            print(f"  名称: {role_info.get('agent_name', '未知')}")
            print(f"  能力: {', '.join(role_info.get('capabilities', []))}")
            print(f"  当前角色ID: {client.role_id}")
            return True
            
        elif command == 'clear':
            import os
            os.system('clear' if os.name == 'posix' else 'cls')
            print(f"🤖 {agent_name}: 屏幕已清理，我们继续对话吧！")
            return True
            
        elif command == 'weather':
            location = ' '.join(user_input.split()[1:])
            if not location:
                location = input("请输入城市名称: ").strip()
            if location:
                result = await client.call_tool("get_weather", {"location": location})
                if result.get("success"):
                    print(f"🌤️ {location}天气: {result['result']}")
                else:
                    print(f"❌ 天气查询失败: {result.get('error')}")
            return True
            
        elif command == 'search':
            query = ' '.join(user_input.split()[1:])
            if not query:
                query = input("请输入搜索关键词: ").strip()
            if query:
                result = await client.call_tool("search_location", {"query": query})
                if result.get("success"):
                    print(f"📍 位置信息: {result['result']}")
                else:
                    print(f"❌ 位置搜索失败: {result.get('error')}")
            return True
            
        elif command == 'info':
            query = ' '.join(user_input.split()[1:])
            if not query:
                query = input("请输入搜索内容: ").strip()
            if query:
                result = await client.call_tool("bocha_search", {"query": query})
                if result.get("success"):
                    print(f"🔍 搜索结果: {result['result']}")
                else:
                    print(f"❌ 信息搜索失败: {result.get('error')}")
            return True
            
    except Exception as e:
        print(f"❌ 命令执行失败: {e}")
        
    return False

async def main():
    """主函数 - 角色选择和聊天"""
    print("🎭 MCP多角色聊天客户端")
    print("=" * 50)
    
    # 初始化客户端
    client = MCPClient()
    
    try:
        # 1. 获取可用角色
        print("📋 获取可用角色...")
        roles = await client.get_available_roles()
        
        if not roles:
            print("❌ 未找到可用角色")
            return
        
        # 2. 显示角色选择
        print("\n🎭 可用角色:")
        for i, role in enumerate(roles, 1):
            print(f"  {i}. {role['role_name']} ({role['age']}岁)")
            print(f"     职业: {role['profession']}")
            print(f"     描述: {role['description']}")
            print(f"     情绪: {role['mood_tags']} (强度: {role['mood_intensity']}/10)")
            print()
        
        # 3. 用户选择角色
        while True:
            try:
                choice = input("请选择角色编号: ").strip()
                choice_num = int(choice)
                if 1 <= choice_num <= len(roles):
                    selected_role = roles[choice_num - 1]
                    break
                else:
                    print(f"❌ 请输入 1-{len(roles)} 之间的数字")
            except ValueError:
                print("❌ 请输入有效的数字")
            except KeyboardInterrupt:
                print("\n👋 退出")
                return
        
        # 4. 选择角色
        success = await client.select_role(selected_role['role_id'])
        if not success:
            print("❌ 角色选择失败")
            return
        
        # 5. 输入用户名
        while True:
            user_name = input("请输入您的用户名: ").strip()
            if user_name:
                break
            print("❌ 用户名不能为空")
        
        # 6. 开始聊天会话
        success = await client.start_chat(user_name)
        if not success:
            print("❌ 聊天会话启动失败")
            return
        
        # 7. 进入交互式聊天
        await client.interactive_chat()
        
    except KeyboardInterrupt:
        print("\n👋 程序中断")
    except Exception as e:
        print(f"❌ 程序异常: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 