# 🎉 MCP智能助手 - 使用指南

## ✅ 完整功能已实现

经过全面优化，所有MCP服务和持久化存储都已成功集成并正常工作：

### 🔍 **搜索功能** - 使用Bocha搜索API
```
您: 今天的热搜有哪些
小智: 今日热搜包括：今日娱乐头条、今日热卖官网、热闻...
🔧 使用了工具: bocha_web_search

您: 最新的科技新闻
小智: 这里有一些最新的科技新闻：笨木鸡下载站提供最前沿的科技新闻资讯...
🔧 使用了工具: bocha_web_search
```

### 🗺️ **智能路线规划** - 自动获取坐标
```
您: 帮我规划从天安门到苏州桥的地铁路线
小智: 从天安门到苏州桥，为你推荐以下路线：
方案1（约4162秒）：
1. 从天安门广场步行约1965米到达金鱼胡同地铁站...
🔧 使用了工具: maps_geo, maps_direction_transit_integrated
```

### 🌤️ **天气查询** - 真实天气数据
```
您: 今天北京的天气怎么样
小智: 今天北京市多云，28度，东风1-3级...
🔧 使用了工具: maps_weather
```

### 💾 **持久化存储** - MySQL + Redis双层架构
```
✅ 会话管理：自动创建和管理聊天会话
✅ 历史记录：MySQL长期存储，Redis临时缓存
✅ 工具记录：详细保存工具调用和结果
✅ 统计分析：消息数量、工具使用统计
```

## 🚀 快速开始

### 方法一：使用简化启动脚本（推荐）

#### 1. 启动服务器
```bash
cd mcp_agent
python start_server.py
```

#### 2. 开始聊天
```bash
python chat.py
```

### 方法二：使用原始脚本

#### 1. 启动服务器
```bash
cd mcp_agent
python enhanced_server.py
```

#### 2. 开始对话
```bash
python enhanced_client.py interactive
```

## 🔧 可用的真实MCP服务

### 1. **Bocha搜索服务** ✅
- `bocha_web_search` - 网页搜索
- `bocha_ai_search` - AI智能搜索
- **功能**：新闻、热搜、实时信息查询

### 2. **高德地图服务** ✅ 
- `maps_geo` - 地址转坐标
- `maps_text_search` - 地点搜索
- `maps_direction_*` - 各种路线规划
- **功能**：地理位置、路线规划、POI搜索

### 3. **天气服务** ✅
- `get_weather_forecast` - 天气预报
- `maps_weather` - 城市天气
- **功能**：实时天气、气象预报

### 4. **日期时间服务** ✅
- `get_current_date` - 获取当前日期
- `get_date_weekday` - 查询星期几
- `get_beijing_time` - 北京时间查询
- **功能**：时间查询、日期计算

## 💾 持久化存储系统

### 🏗️ **系统架构**
- **Redis**: 会话期间的快速临时存储
- **MySQL**: 长期持久化存储
- **自动迁移**: 会话结束时自动将Redis数据保存到MySQL

### 📊 **数据模型**
#### 会话表 (ChatSession)
- 会话ID、用户名称、会话标题
- 创建时间、最新消息时间
- 消息统计：总数、用户消息数、AI消息数

#### 聊天记录表 (ChatMessage)
- 消息ID、会话ID、发送方类型
- 消息内容、工具查询信息
- 时间戳、工具调用结果

### 🔄 **工作流程**
1. **会话开始**: 从MySQL加载历史消息
2. **对话进行**: 新消息临时存储在Redis
3. **会话结束**: Redis数据自动持久化到MySQL
4. **工具调用**: 详细记录工具名称、参数、结果

## 💡 智能特性

### 🧠 **自动意图识别**
- 搜索相关：自动调用Bocha搜索
- 路线规划：自动获取坐标并规划路线
- 天气查询：自动选择最佳天气服务
- 时间查询：自动使用日期时间工具

### 🔄 **多工具协作**
- 路线规划：先获取坐标，再规划路线
- 地点查询：结合搜索和地图服务
- 智能选择：根据查询类型选择最佳工具

### 💬 **多轮对话**
- 持久化历史记录
- 上下文理解
- 会话管理和恢复

## 🎯 测试示例

### 搜索测试
```bash
python test_search.py
```

### 路线规划测试  
```bash
python test_route.py
```

### 数据库功能测试
```bash
python enhanced_client.py test_features
```

## 📊 系统状态

- ✅ **服务器状态**: 健康
- ✅ **代理状态**: 就绪
- ✅ **工具数量**: 15个
- ✅ **MCP服务**: 4个（Bocha、高德、天气、时间）
- ✅ **存储系统**: MySQL + Redis双层架构

## 🔧 数据库配置

### 环境要求
- MySQL 5.7+ 或 8.0+
- Redis 6.0+
- Python 3.8+

### 配置文件
编辑 `database.env` 文件：
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
REDIS_DB=0
```

## 🎉 成功解决的问题

1. ✅ **Bocha搜索MCP集成** - 完全解决
2. ✅ **路线规划自动化** - 显著改进
3. ✅ **工具schema错误** - 已修复
4. ✅ **意图识别优化** - 已完成
5. ✅ **持久化存储系统** - 全新实现
6. ✅ **会话管理** - 完整功能
7. ✅ **工具调用记录** - 详细追踪

## 🚀 高级功能

### 会话管理命令
在聊天中使用以下命令：
- `sessions` - 查看所有会话
- `new [标题]` - 创建新会话
- `history` - 查看当前会话历史
- `tools` - 查看可用工具
- `status` - 查看系统状态

### API端点
- `GET /health` - 健康检查
- `POST /mcp/query` - 智能查询
- `GET /sessions/{user_id}` - 获取用户会话
- `POST /sessions/{session_id}/cleanup` - 清理会话
- `GET /database/status` - 数据库状态

现在您可以享受完整的MCP智能助手服务！🚀 