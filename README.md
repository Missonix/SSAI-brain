# 🤖 MCP智能助手

基于LangGraph MCP标准构建的Gemini-2.0-flash模型智能助手，集成天气查询、地图服务、搜索功能和持久化存储。

## ✨ 主要特性

- 🧠 **Gemini-2.0-flash模型**: 强大的AI对话能力
- 🔍 **智能搜索**: 集成Bocha搜索API，支持实时信息查询
- 🗺️ **地图服务**: 高德地图API，支持路线规划和地理位置查询
- 🌤️ **天气查询**: 实时天气信息和预报
- ⏰ **时间服务**: 日期时间查询和计算
- 💾 **持久化存储**: MySQL + Redis双层架构，永久保存对话历史
- 🔧 **MCP标准**: 完全符合LangGraph MCP接入标准

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <your-repo-url>
cd demo

# 安装依赖
cd mcp_agent
pip install -r requirements.txt
```

### 2. 配置数据库

确保MySQL和Redis服务正在运行，然后编辑 `mcp_agent/database.env`：

```env
# MySQL配置
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=ai_chat

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_password
```

### 3. 启动服务

```bash
# 启动MCP服务器
python start_server.py

# 新开终端，启动聊天客户端
python chat.py
```

### 4. 系统测试（可选）

在启动服务器后，可以运行快速测试验证系统状态：

```bash
# 运行系统测试
python quick_test.py
```

测试将验证：
- 🏥 服务器健康状态
- 📊 数据库连接状态
- 🔧 工具列表和功能
- 💬 基本查询功能
- 📋 会话管理功能

## 📁 项目结构

```
demo/
├── mcp_agent/                    # 主要代码目录
│   ├── enhanced_server.py        # MCP服务器
│   ├── enhanced_agent.py         # AI代理核心
│   ├── enhanced_client.py        # 客户端
│   ├── persistent_storage.py     # 持久化存储管理
│   ├── database_models.py        # 数据库模型
│   ├── database_config.py        # 数据库配置
│   ├── datetime_tools.py         # 时间工具
│   ├── start_server.py          # 服务器启动脚本
│   ├── chat.py                  # 聊天启动脚本
│   ├── quick_test.py            # 快速测试脚本
│   ├── database.env             # 数据库配置
│   ├── requirements.txt         # Python依赖
│   └── FINAL_USAGE.md          # 详细使用文档
├── mcp_config.json              # MCP服务配置
└── README.md                    # 项目说明
```

## 🔧 功能演示

### 智能搜索
```
您: 今天的热搜有哪些
小智: 今日热搜包括：今日娱乐头条、今日热卖官网...
🔧 使用了工具: bocha_web_search
```

### 路线规划
```
您: 帮我规划从天安门到苏州桥的地铁路线
小智: 从天安门到苏州桥，为你推荐以下路线...
🔧 使用了工具: maps_geo, maps_direction_transit_integrated
```

### 天气查询
```
您: 今天北京的天气怎么样
小智: 今天北京市多云，28度，东风1-3级...
🔧 使用了工具: maps_weather
```

### 时间查询
```
您: 现在几点了？
小智: 现在是北京时间 2024年1月15日 14:30:25
🔧 使用了工具: get_beijing_time
```

## 💾 持久化存储

- **会话管理**: 自动创建和管理聊天会话
- **历史记录**: MySQL长期存储，Redis临时缓存
- **工具记录**: 详细保存工具调用和结果
- **统计分析**: 消息数量、工具使用统计

## 🧪 测试和验证

### 快速测试
```bash
python quick_test.py
```

### 功能测试
```bash
python enhanced_client.py test_features
```

### 交互式演示
```bash
python enhanced_client.py demo_basic
```

## 📖 详细文档

查看 [`mcp_agent/FINAL_USAGE.md`](mcp_agent/FINAL_USAGE.md) 获取完整的使用指南和API文档。

## 🛠️ 技术栈

- **AI模型**: Google Gemini-2.0-flash-exp
- **框架**: LangGraph, FastAPI
- **数据库**: MySQL, Redis
- **API集成**: 高德地图, Bocha搜索
- **协议**: MCP 1.0.0 标准

## 📝 许可证

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request！

---

🎉 **开始与AI助手对话吧！** 运行 `python chat.py` 即可开始体验。 