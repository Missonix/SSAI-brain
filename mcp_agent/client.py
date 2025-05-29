"""
MCP客户端
支持多轮对话、会话管理和真实MCP服务交互
"""

import asyncio
import aiohttp
import json
from typing import Dict, Any, List
from datetime import datetime

class EnhancedMCPClient:
    def __init__(self, base_url: str = "http://localhost:8080"):
        """初始化增强版MCP客户端"""
        self.base_url = base_url
        self.session = None
        self.current_session_id = ""
        self.current_user_id = "default_user"
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        async with self.session.get(f"{self.base_url}/health") as response:
            return await response.json()
    
    async def get_role_info(self) -> Dict[str, Any]:
        """获取角色信息"""
        async with self.session.get(f"{self.base_url}/role") as response:
            return await response.json()
    
    async def list_tools(self) -> Dict[str, Any]:
        """列出可用工具"""
        async with self.session.get(f"{self.base_url}/mcp/tools") as response:
            return await response.json()
    
    async def create_session(self, user_id: str, title: str = "") -> Dict[str, Any]:
        """创建新会话"""
        data = {
            "user_id": user_id,
            "title": title
        }
        async with self.session.post(
            f"{self.base_url}/sessions/create",
            json=data
        ) as response:
            result = await response.json()
            if result.get("success"):
                self.current_session_id = result["session_id"]
                self.current_user_id = user_id
            return result
    
    async def get_user_sessions(self, user_id: str) -> Dict[str, Any]:
        """获取用户的所有会话"""
        async with self.session.get(f"{self.base_url}/sessions/{user_id}") as response:
            return await response.json()
    
    async def get_conversation_history(self, session_id: str) -> Dict[str, Any]:
        """获取会话的对话历史"""
        async with self.session.get(f"{self.base_url}/conversations/{session_id}") as response:
            return await response.json()
    
    async def query(self, query: str, location: str = "", session_id: str = "", user_id: str = "") -> Dict[str, Any]:
        """发送查询请求（支持多轮对话）"""
        data = {
            "query": query,
            "location": location,
            "session_id": session_id or self.current_session_id,
            "user_id": user_id or self.current_user_id
        }
        async with self.session.post(
            f"{self.base_url}/mcp/query",
            json=data
        ) as response:
            result = await response.json()
            if result.get("success") and result.get("session_id"):
                self.current_session_id = result["session_id"]
            return result
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用特定工具"""
        data = {
            "name": tool_name,
            "arguments": arguments
        }
        async with self.session.post(
            f"{self.base_url}/mcp/call",
            json=data
        ) as response:
            return await response.json()
    
    async def get_mcp_info(self) -> Dict[str, Any]:
        """获取MCP端点信息"""
        async with self.session.get(f"{self.base_url}/mcp") as response:
            return await response.json()
    
    async def test_conversation(self) -> Dict[str, Any]:
        """测试多轮对话功能"""
        async with self.session.post(f"{self.base_url}/test/conversation") as response:
            return await response.json()

async def demo_enhanced_client():
    """演示增强版客户端的基本连接和信息获取功能。"""
    print("🚀 启动增强版MCP客户端演示 (基本连接测试)...")
    print("----------------------------------------------------")
    print("此演示仅测试连接，不包含交互式对话。")
    print("如需与AI助手对话，请运行: python chat.py")
    print("或: python enhanced_client.py interactive")
    print("----------------------------------------------------")

    async with EnhancedMCPClient() as client:
        try:
            # 1. 健康检查
            print("\n1️⃣ 健康检查...")
            health = await client.health_check()
            print(f"服务状态: {health}")
            
            if not health.get("agent_ready"):
                print("❌ 代理未就绪，请先启动服务器 (python enhanced_server.py)")
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
            print("💡 请确保MCP服务器 (enhanced_server.py) 正在运行并且网络连接正常。")
        except Exception as e:
            print(f"❌ 客户端演示发生错误: {e}")

async def interactive_enhanced_client():
    """交互式增强版客户端 - 优化用户体验"""
    print("🎯 欢迎使用增强版MCP智能助手客户端！")
    print("=" * 50)
    
    async with EnhancedMCPClient() as client:
        try:
            # 检查服务状态
            print("🔄 正在连接服务器...")
            health = await client.health_check()
            if not health.get("agent_ready"):
                print("❌ 服务器未就绪，请先启动MCP服务器")
                print("💡 提示：运行 'python enhanced_server.py' 启动服务器")
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
  
🔧 系统命令:
  - status     查看服务状态
  - role       查看助手信息
  - help       显示此帮助信息
  - quit       退出程序

💡 提示: 您可以直接问问题，{agent_name}会自动选择合适的工具来帮助您！
""")

async def _handle_special_commands(client, user_input: str, user_id: str, agent_name: str) -> bool:
    """处理特殊命令，返回True表示已处理"""
    command = user_input.lower().split()[0]
    
    try:
        if command == 'tools':
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
            return True
            
        elif command == 'role':
            role_info = await client.get_role_info()
            print(f"🤖 助手信息:")
            print(f"  名称: {role_info.get('agent_name', '未知')}")
            print(f"  能力: {', '.join(role_info.get('capabilities', []))}")
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

async def test_enhanced_features():
    """测试增强功能 (例如服务器端的多轮对话测试接口)。"""
    print("🧪 测试增强版MCP服务器功能...")
    print("----------------------------------------------------")
    print("此功能用于测试服务器是否能正确处理多轮对话等。")
    print("----------------------------------------------------")
    
    async with EnhancedMCPClient() as client:
        try:
            # 检查服务器是否在线
            health = await client.health_check()
            if not health.get("agent_ready"):
                print("❌ 代理未就绪，无法进行测试。请先启动服务器。")
                return

            # 测试服务器的多轮对话功能
            print("\n🔄 测试服务器内置的多轮对话测试接口 (/test/conversation)...")
            test_result = await client.test_conversation()
            
            if test_result.get("success") and test_result.get("test_results"):
                print("✅ 服务器多轮对话测试接口调用成功。")
                session_id = test_result.get("session_id")
                print(f"📝 测试会话ID (来自服务器): {session_id[:8]}...")
                
                # 查看测试会话的历史
                if session_id:
                    history_result = await client.get_conversation_history(session_id)
                    history = history_result.get("history", [])
                    print(f"📚 测试会话包含 {len(history)} 条消息。")
                    if history:
                        print("🔍 最后几条消息示例:")
                        for msg in history[-3:]:
                            role = "👤 用户" if msg["type"] == "human" else "🤖 助手"
                            content = msg["content"][:70] + "..." if len(msg["content"]) > 70 else msg["content"]
                            print(f"    {role}: {content}")
            elif test_result.get("error"):
                print(f"❌ 服务器多轮对话测试接口调用失败: {test_result.get('error')}")
            else:
                print("⚠️ 服务器多轮对话测试接口未返回预期的成功结果。")
                print(f"服务器响应: {test_result}")

            print("\n增强功能测试完成。")

        except aiohttp.client_exceptions.ClientConnectorError as e:
            print(f"❌ 连接服务器失败: {e}")
            print("💡 请确保MCP服务器 (enhanced_server.py) 正在运行并且网络连接正常。")
        except Exception as e:
            print(f"❌ 测试增强功能时发生错误: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "interactive":
            asyncio.run(interactive_enhanced_client())
        elif sys.argv[1] == "test_features": # Renamed from "test"
            asyncio.run(test_enhanced_features())
        elif sys.argv[1] == "demo_basic": # New option for basic demo
            asyncio.run(demo_enhanced_client())
        else:
            print(f"未知命令: {sys.argv[1]}")
            print("用法: python enhanced_client.py [interactive | test_features | demo_basic]")
    else:
        # 默认行为：显示提示，引导用户使用 interactive 或 chat.py
        print("🚀 欢迎使用增强版MCP客户端！")
        print("----------------------------------------------------")
        print("如需与AI助手进行交互式对话，请运行:")
        print("  python chat.py")
        print("或者:")
        print("  python enhanced_client.py interactive")
        print("----------------------------------------------------")
        print("其他可用命令:")
        print("  python enhanced_client.py demo_basic     (运行基本连接和服务信息演示)")
        print("  python enhanced_client.py test_features  (测试服务器的高级功能接口)")
        print("----------------------------------------------------") 