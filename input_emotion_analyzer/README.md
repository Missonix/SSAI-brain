# 输入解析与情感初步感知模块 (OpenAI 兼容模式, 异步)

这是一个基于豆包大模型（通过火山引擎OpenAI兼容API异步调用）的输入解析与情感初步感知模块，能够同时进行用户意图识别和情感分析。为了提高性能，模块内部使用 `asyncio` 和 `openai.AsyncOpenAI` 实现API的并发调用。

## ❗ 重要变更：SDK切换 与 异步执行

-   **SDK**: 使用标准的 `openai` Python库。
-   **异步执行**: 核心分析逻辑（`analyze`方法）已转换为异步 (`async def`)，使用 `asyncio.gather` 并发执行意图和情感分析API调用，以提升性能。
-   **外部调用**: 调用本模块的 `analyze` 方法时，需要在异步上下文中执行，并使用 `await`。
-   **过程打印**: 移除了模块内部的非错误相关的过程打印信息，以便作为库更干净地被调用。

## 功能特性

### 1. 意图识别器
- 识别用户意图类型（挑衅、强迫、寻求安慰、询问信息等）
- 判断是否需要工具支持
- 推荐合适的调用工具

### 2. 情感分析器
- 多维度情感分析：valence（效价）、arousal（唤醒度）、dominance（控制感）
- 情感标签识别
- 情感强度评估
- 情感触发因素分析
- 置信度评估

### 3. 预配置工具库
- **搜索工具**: `bocha_web_search`, `bocha_ai_search`
- **天气工具**: `get_weather_forecast`, `maps_weather`
- **地图工具**: `maps系列`
- **日期时间工具**: `get_current_date`, `get_date_weekday`, `get_beijing_time`

## 安装依赖

进入模块目录并运行安装脚本：

```bash
cd input_emotion_analyzer
./install.sh
```

## 🚀 关键：API与Endpoint配置 (OpenAI 兼容模式)

要成功运行此模块，您**必须**正确配置您的火山引擎API密钥、OpenAI兼容的API Base URL以及一个有效的**Endpoint ID**（作为模型名称）。

1.  🔑 **API Key**: 您的火山引擎API密钥。
2.  🌐 **API Base URL**: 火山引擎OpenAI兼容API地址 (默认为 `https://ark.cn-beijing.volces.com/api/v3`)。
3.  ⚙️ **Endpoint ID (作为 Model Name)**: **至关重要**，您在火山引擎创建的推理接入点的ID。

### 如何获取并配置 Endpoint ID：

1.  **登录火山引擎控制台**: [https://console.volcengine.com/ark](https://console.volcengine.com/ark)
2.  **导航至在线推理**: 在左侧菜单中，找到并点击 "模型市场" -> "模型列表"，选择需要的模型，然后点击 "创建自定义推理接入点"，或者直接在左侧菜单选择 "在线推理" -> "推理接入点管理"。
3.  **创建推理接入点**:
    *   选择您希望使用的基础模型（例如 `doubao-1.5-pro-32k`）。
    *   配置推理接入点参数（如名称、副本数等）。
    *   点击创建。
4.  **获取Endpoint ID**: 创建成功后，在 "推理接入点管理" 列表中，您会看到您的接入点，并找到其 **Endpoint ID**。它通常以 `ep-` 开头，例如 `ep-xxxxxxxxxxxx-xxxxx`。
5.  **更新配置文件**: 打开 `input_emotion_analyzer/config.py` 文件，修改以下行：
    ```python
    class Config:
        DOUBAO_API_KEY = "您的火山引擎API密钥"
        DOUBAO_API_BASE = "https://ark.cn-beijing.volces.com/api/v3" 
        DOUBAO_MODEL_NAME = "您获取到的实际Endpoint ID" 
    ```

### ⚙️ 配置测试与验证 (异步模式)

使用更新后的异步测试脚本：

```bash
python3 test_config.py
```
该脚本现在以异步方式运行测试，并提供相应的指南。

## ❓ 问题排查: "endpoint invalid" 或类似API错误

如果您在运行代码时遇到API错误，特别是包含 "endpoint invalid", "model not found", 或状态码 400/404 的错误：

```
❌ OpenAI API调用错误: Request failed due to InvalidParameter, status_code: 400, request_id: ..., 
error: {'code': 'InvalidParameter', 'message': 'The parameter `model` specified in the request are not valid: endpoint invalid...'} 
```

这几乎总是意味着 `config.py` 中的 `DOUBAO_MODEL_NAME` 不是一个有效的、属于您账户的、且已成功启动的 **Endpoint ID**，或者 `DOUBAO_API_BASE` 不正确。

**解决方法**：

1.  **仔细按照上述 "如何获取并配置 Endpoint ID" 的步骤操作。**
2.  **确认 `DOUBAO_API_BASE`** 是否为火山引擎当前推荐的OpenAI兼容API地址。
3.  确保您复制的 Endpoint ID 完全正确，没有多余的空格或字符。
4.  确认您选择的推理接入点已成功部署且正在运行。
5.  确认您的 API Key 具有调用该 Endpoint 的权限，并且区域一致。
6.  运行 `python3 test_config.py` 脚本，它会提供更具体的指导和交互式配置帮助。

## 使用方法 (异步调用)

配置完成后，您需要以异步方式调用模块：

### 外部调用示例 (例如您的 `test.py`):

```python
import asyncio
import json
from input_emotion_analyzer import InputEmotionAnalyzer # 导入方式不变

async def run_analyzer():
    analyzer = InputEmotionAnalyzer() # 初始化不变
    user_input = "我今天心情很糟糕，能帮我查查明天的天气吗？"
    
    try:
        result = await analyzer.analyze(user_input) # 使用 await 调用
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        error_output = {"error": True, "message": str(e), "details": repr(e)}
        print(json.dumps(error_output, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(run_analyzer())
```

### 初始化时直接提供配置 (异步):

```python
import asyncio
from input_emotion_analyzer import InputEmotionAnalyzer

async def run_with_direct_config():
    analyzer = InputEmotionAnalyzer(
        api_key="YOUR_API_KEY",
        api_base="YOUR_OPENAI_COMPATIBLE_API_BASE_FOR_VOLCENGINE",
        model_name="YOUR_VOLCENGINE_ENDPOINT_ID"
    )
    user_input = "测试一下"
    result = await analyzer.analyze(user_input)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(run_with_direct_config())
```

### 输出格式

```json
{
    "intention_result": {
        "intention": "寻求安慰",
        "need_tool": "true",
        "tool": ["get_weather_forecast"]
    },
    "emotion_result": {
        "valence": -0.6,
        "arousal": 0.4,
        "dominance": 0.3,
        "tags": "悲伤",
        "intensity": 6,
        "mood_description_for_llm": "用户情绪低落，需要情感支持",
        "trigger": "个人状态不佳",
        "confidence": 0.85,
        "reason": "用户明确表达了负面情绪和求助需求"
    }
}
```

### 单独使用意图识别或情感分析

```python
# 仅进行意图识别
intention_result = analyzer.analyze_intention(user_input)

# 仅进行情感分析
emotion_result = analyzer.analyze_emotion(user_input)
```

## 详细测试 (模块内部示例)

模块内部的 `example.py` 也已更新为异步执行：

```bash
python3 example.py
```

## 主要类和方法

### `InputEmotionAnalyzer`
-   `async def analyze(self, user_input: str) -> Dict[str, Any]`：**异步**综合分析。
-   `async def analyze_intention(self, user_input: str) -> Optional[Dict[str, Any]]`：**异步**意图分析。
-   `async def analyze_emotion(self, user_input: str) -> Optional[Dict[str, Any]]`：**异步**情感分析。
-   `get_available_tools(self) -> Dict[str, List[str]]`：(同步) 获取工具列表。

## 注意事项

1.  **异步环境**: 调用本模块的核心功能需要 `asyncio` 环境。
2.  **配置**: 正确的API Key, API Base URL, 和 Endpoint ID 仍然是成功运行的前提。

## 扩展性

该模块设计时考虑了扩展性：
- 可以轻松添加新的工具类型。
- 可以自定义意图类型和情感标签。
- 支持替换不同的大模型后端（需相应调整API调用逻辑）。

## 配置说明

### API配置
- **API Key**: `4a9c6c92-91fa-4087-beb3-4a894d0ce586`
- **API Base**: `https://ark.cn-beijing.volces.com/api/v3`
- **Model Name**: `doubao-1.5-pro-32k-250115`

### 自定义配置

可以通过修改 `config.py` 文件来自定义：
- 工具库配置
- 情感维度范围
- 意图类型列表
- 情感标签列表

## 测试

运行以下命令进行测试：

```bash
python analyzer.py
```

这将运行内置的测试用例，展示不同类型输入的分析结果。

## 主要类和方法

### InputEmotionAnalyzer

主要方法：
- `analyze(user_input)`: 综合分析用户输入
- `analyze_intention(user_input)`: 仅分析意图
- `analyze_emotion(user_input)`: 仅分析情感
- `get_available_tools()`: 获取可用工具列表

## 注意事项

1. 确保网络连接正常，以便调用豆包API。
2. API密钥和Endpoint ID必须有效并具备足够的调用额度。
3. 模型响应可能会因网络状况而有延迟。

## 扩展性

该模块设计时考虑了扩展性：
- 可以轻松添加新的工具类型。
- 可以自定义意图类型和情感标签。
- 支持替换不同的大模型后端（需相应调整API调用逻辑）。

## 配置说明

### API配置
- **API Key**: `4a9c6c92-91fa-4087-beb3-4a894d0ce586`
- **API Base**: `https://ark.cn-beijing.volces.com/api/v3`
- **Model Name**: `doubao-1.5-pro-32k-250115`

### 自定义配置

可以通过修改 `config.py` 文件来自定义：
- 工具库配置
- 情感维度范围
- 意图类型列表
- 情感标签列表

## 测试

运行以下命令进行测试：

```bash
python analyzer.py
```

这将运行内置的测试用例，展示不同类型输入的分析结果。

## 主要类和方法

### InputEmotionAnalyzer

主要方法：
- `analyze(user_input)`: 综合分析用户输入
- `analyze_intention(user_input)`: 仅分析意图
- `analyze_emotion(user_input)`: 仅分析情感
- `get_available_tools()`: 获取可用工具列表

## 注意事项

1. 确保网络连接正常，以便调用豆包API
2. API密钥需要有效并具备足够的调用额度
3. 模型响应可能会因网络状况而有延迟
4. 建议对重要应用场景添加错误处理和重试机制

## 错误处理

模块内置了完善的错误处理机制：
- API调用失败时返回默认值
- JSON解析错误时进行格式修复
- 网络异常时提供友好的错误提示

## 扩展性

该模块设计时考虑了扩展性：
- 可以轻松添加新的工具类型
- 可以自定义意图类型和情感标签
- 支持替换不同的大模型后端 