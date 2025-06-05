# 统一模型配置管理器

本项目使用统一的模型配置管理器来管理所有LLM模型的配置，包括API密钥、模型名称、base URL等参数。

## 🎯 主要特性

- **统一配置管理**: 所有模型配置集中在一个地方管理
- **多提供商支持**: 支持Gemini、OpenAI、Claude、Qwen、GLM等多个模型提供商
- **环境变量覆盖**: 支持通过环境变量动态配置
- **自动环境设置**: 自动设置对应的环境变量
- **类型安全**: 使用TypeScript风格的类型提示

## 📁 文件结构

```
mcp_agent/
├── model_config.py              # 统一模型配置管理器
├── model_config_example.py      # 使用示例
└── MODEL_CONFIG_README.md       # 本文档
```

## 🚀 快速开始

### 1. 基本使用

```python
from model_config import get_langchain_llm, get_genai_model, get_model_config

# 获取当前配置
config = get_model_config()
print(f"当前使用: {config.provider.value} - {config.model_name}")

# 获取LangChain LLM实例
llm = get_langchain_llm()

# 获取Google GenerativeAI模型实例
model = get_genai_model()
```

### 2. 配置切换

```python
from model_config import switch_model, update_model_config

# 切换到不同的模型
switch_model("openai", "gpt-4")           # 切换到OpenAI GPT-4
switch_model("gemini", "gemini-1.5-pro") # 切换到Gemini 1.5 Pro

# 更新配置参数
update_model_config(temperature=0.5, max_tokens=2000)
```

## ⚙️ 配置方式

### 1. 默认配置

默认使用Gemini 2.0 Flash模型：

```python
DEFAULT_CONFIG = {
    "provider": ModelProvider.GEMINI,
    "model_name": "gemini-2.0-flash-exp",
    "api_key": "",
    "temperature": 0.0,
    "timeout": 30
}
```

### 2. 环境变量配置

可以通过以下环境变量覆盖默认配置：

```bash
# 模型提供商和名称
export MODEL_PROVIDER=gemini
export MODEL_NAME=gemini-2.0-flash-exp

# API密钥（根据提供商选择对应的环境变量）
export GOOGLE_API_KEY=your_google_api_key
export OPENAI_API_KEY=your_openai_api_key
export ANTHROPIC_API_KEY=your_claude_api_key
export DASHSCOPE_API_KEY=your_qwen_api_key
export GLM_API_KEY=your_glm_api_key

# 其他参数
export MODEL_TEMPERATURE=0.0
export MODEL_MAX_TOKENS=2000
export MODEL_TIMEOUT=30
export MODEL_BASE_URL=https://api.openai.com/v1
```

### 3. 代码中动态配置

```python
from model_config import model_manager

# 更新配置
model_manager.update_config(
    provider="openai",
    model_name="gpt-4",
    api_key="your_api_key",
    temperature=0.7
)
```

## 🔧 支持的模型提供商

### Gemini (Google)
```python
switch_model("gemini", "gemini-2.0-flash-exp")
switch_model("gemini", "gemini-1.5-pro")
```

### OpenAI
```python
switch_model("openai", "gpt-4")
switch_model("openai", "gpt-3.5-turbo")
```

### Qwen (阿里云)
```python
switch_model("qwen", "qwen-turbo")
```

## 📝 使用示例

### 在项目中使用

```python
# chat_agent.py
from model_config import get_langchain_llm, get_model_config

class EnhancedMCPAgent:
    def __init__(self, role_id: str = None):
        # 使用统一的模型配置
        self.llm = get_langchain_llm()
        
        # 记录当前使用的模型配置
        model_config = get_model_config()
        self.logger.info(f"🤖 使用模型: {model_config.provider.value} - {model_config.model_name}")
```

```python
# thought_chain_generator.py
from model_config import get_genai_model, get_model_config

class ThoughtChainPromptGenerator:
    def __init__(self):
        # 使用统一的模型配置
        self.model = get_genai_model()
        model_config = get_model_config()
        self.logger.info(f"✅ 使用模型: {model_config.model_name}")
```

### 运行示例

```bash
cd mcp_agent
python model_config_example.py
```

## 🔄 迁移指南

### 从硬编码配置迁移

**之前的代码:**
```python
# 硬编码API密钥和模型
api_key = ""
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.0-flash-exp')

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-exp",
    google_api_key=api_key,
    temperature=0.0
)
```

**迁移后的代码:**
```python
# 使用统一配置
from model_config import get_genai_model, get_langchain_llm

model = get_genai_model()
llm = get_langchain_llm()
```

### 构造函数参数迁移

**之前:**
```python
def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash-exp"):
    self.api_key = api_key
    genai.configure(api_key=api_key)
    self.model = genai.GenerativeModel(model_name)
```

**迁移后:**
```python
def __init__(self):
    self.model = get_genai_model()
    model_config = get_model_config()
    self.logger.info(f"✅ 使用模型: {model_config.model_name}")
```

## 🛠️ 高级功能

### 1. 获取提供商信息

```python
from model_config import model_manager

info = model_manager.get_provider_info()
print(f"提供商: {info['provider']}")
print(f"模型: {info['model_name']}")
print(f"有API密钥: {info['has_api_key']}")
```

### 2. 获取特定配置

```python
# 获取LangChain配置
langchain_config = model_manager.get_langchain_config()

# 获取GenAI配置
genai_config = model_manager.get_genai_config()
```

### 3. 预定义模板切换

```python
from model_config import ModelProvider

# 使用预定义模板
success = model_manager.switch_to_template(
    ModelProvider.OPENAI, 
    "gpt-4"
)
```

## ⚠️ 注意事项

1. **API密钥安全**: 不要在代码中硬编码API密钥，使用环境变量
2. **模型兼容性**: 确保切换模型时API密钥正确配置
3. **错误处理**: 模型初始化失败时会抛出异常，需要适当处理
4. **环境变量优先级**: 环境变量会覆盖默认配置

## 🐛 故障排除

### 常见问题

1. **模型初始化失败**
   ```
   ❌ ThoughtChainGenerator初始化失败: genai配置仅适用于Gemini模型
   ```
   解决方案: 检查当前配置的提供商是否与使用的模型匹配

2. **API密钥错误**
   ```
   ❌ API密钥无效或未设置
   ```
   解决方案: 检查对应提供商的环境变量是否正确设置

3. **模型不支持**
   ```
   ❌ 暂不支持的LangChain提供商: xxx
   ```
   解决方案: 检查是否使用了支持的模型提供商

### 调试方法

```python
from model_config import get_model_config

# 检查当前配置
config = get_model_config()
print(f"提供商: {config.provider}")
print(f"模型: {config.model_name}")
print(f"API密钥: {config.api_key[:10]}..." if config.api_key else "未设置")
```

## 📚 相关文档

- [model_config.py](./model_config.py) - 核心配置管理器
- [model_config_example.py](./model_config_example.py) - 使用示例
- [chat_agent.py](./chat_agent.py) - 在聊天代理中的使用
- [thought_chain_generator.py](../thought_chain_prompt_generator/thought_chain_generator.py) - 在思维链生成器中的使用 