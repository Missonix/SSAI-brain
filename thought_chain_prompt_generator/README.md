# 思维链Prompt生成模块 (优化版)

## 简介

这个模块用于接收前一层意图识别和情感分析模块的结果以及用户的原始输入，结合从`prompt/L0_prompt.txt`文件加载的性格特质和人设背景，以及通过参数传入的当前情绪状态，生成极具主观意识和情绪化的思维链prompt，用于传入下一层LLM中指导prompt做情绪及意图方向的决策。

## 功能特点

- 🤖 基于Gemini 2.0 Flash模型的智能prompt生成
- 🎯 结合意图识别和情感分析结果
- 💭 生成第一人称视角的思维链prompt
- 📁 **NEW** 从`prompt/L0_prompt.txt`文件自动加载性格特质和人设背景
- 😭 通过参数灵活控制当前情绪状态
- 🎭 支持自定义性格特质文件，适应不同角色需求
- 🛡️ 内置错误处理和备用方案
- 📊 支持多种情绪和意图类型
- ⚡ 性格特质一次加载，情绪状态灵活调整

## 系统架构

```
项目根目录/
├── prompt/
│   └── L0_prompt.txt          # 性格特质和人设背景文件
├── thought_chain_prompt_generator/
│   ├── thought_chain_generator.py  # 主模块
│   ├── enhanced_example_usage.py   # 使用示例
│   └── ...
```

## 安装依赖

```bash
pip install -r requirements.txt
```

## 快速开始

### 1. 准备性格特质文件

在项目根目录下的`prompt/L0_prompt.txt`文件中定义性格特质：

```text
我是一个具有复杂性格特质的独立个体。

## 我的核心性格特质：
- 性格类型：理性分析型，带有轻微的利己倾向
- 特质程度：理性分析0.8，利己倾向0.3
- 特质稳定度：0.7

## 我的人设背景：
我是一个28岁的软件工程师...

## 我的价值观：
- 效率至上
- 实用主义
- 适度自私
- 理性决策

## 我的思维模式：
- 习惯先分析问题的本质
- 喜欢评估不同选择的利弊
- 会考虑事情对我自己的影响
```

### 2. 基础使用

```python
from thought_chain_generator import ThoughtChainPromptGenerator

# 创建生成器实例（自动加载性格特质文件）
generator = ThoughtChainPromptGenerator()

# 准备数据
original_input = "受不了了，一天也不想上班了，地球快点爆炸"
analysis_data = {
    "intention_result": {
        "intention": "抱怨",
        "aim": "没有明确目的",
        "targeting_object": "上班这件事",
        # ... 其他字段
    },
    "emotion_result": {
        "valence": -0.8,
        "arousal": 0.8,
        "dominance": 0.1,
        "tags": "愤怒、烦躁",
        # ... 其他字段
    }
}

# 当前情绪状态（只包含情绪相关字段）
my_mood = {
    "my_valence": 0.4,
    "my_arousal": 0.6,
    "my_tags": "愉悦",
    "my_intensity": 6,
    "my_mood_description_for_llm": "今天天气很好,我心情愉悦"
}

# 生成思维链prompt
thought_chain = generator.process_analysis_result(
    original_input=original_input,
    analysis_data=analysis_data,
    my_mood=my_mood
)

print(thought_chain)
```

### 3. 使用自定义性格特质文件

```python
# 使用自定义性格特质文件
generator = ThoughtChainPromptGenerator(
    character_prompt_file="/path/to/custom_character.txt"
)

# 或者动态更换性格特质文件
generator.update_character_prompt_file("/path/to/new_character.txt")
```

### 4. 不提供情绪状态

```python
# 如果不提供my_mood参数，仍然可以基于性格特质生成思维链
thought_chain = generator.process_analysis_result(
    original_input=original_input,
    analysis_data=analysis_data
    # 不提供my_mood参数
)
```

## 数据格式

### 输入数据格式

#### 意图识别结果（intention_result）
```json
{
    "intention": "抱怨",
    "aim": "没有明确目的",
    "targeting_object": "上班这件事",
    "need_tool": "false",
    "tool": [],
    "reason": "识别原因说明",
    "confidence": "0.9"
}
```

#### 情感分析结果（emotion_result）
```json
{
    "valence": -0.8,
    "arousal": 0.8,
    "dominance": 0.1,
    "tags": "愤怒、烦躁",
    "intensity": 8,
    "mood_description_for_llm": "情绪描述",
    "trigger": "触发原因",
    "targeting_object": "针对对象",
    "confidence": 0.9,
    "reason": "分析原因"
}
```

#### 我的当前情绪（my_mood）
```json
{
    "my_valence": 0.4,
    "my_arousal": 0.6,
    "my_tags": "愉悦",
    "my_intensity": 6,
    "my_mood_description_for_llm": "今天天气很好,我心情愉悦"
}
```

**字段说明：**
- `my_valence`: 我的情感效价 (-1到1，负值表示消极，正值表示积极)
- `my_arousal`: 我的情感唤醒度 (0-1，表示情绪激活程度)
- `my_tags`: 我的情感标签（如：愉悦、担忧、平静等）
- `my_intensity`: 我的情感强度 (0-10，表示情绪强烈程度)
- `my_mood_description_for_llm`: 我的心情描述

### 性格特质文件格式 (L0_prompt.txt)

性格特质文件应包含以下内容：

```text
## 我的核心性格特质：
描述性格类型、特质程度、稳定度等

## 我的人设背景：
详细的背景故事和身份设定

## 我的价值观：
核心价值观和原则

## 我的思维模式：
思考习惯和决策方式

## 我的社交倾向：
社交行为和人际关系偏好
```

### 输出格式

模块会生成一段以"我"为第一人称视角的思维链prompt，融合从文件加载的性格特质和通过参数传入的情绪状态，用于指导下游LLM进行情绪和意图相关的决策。生成的思维链将具有：

- **强烈的个性色彩**：基于文件中定义的性格特质和人设背景
- **情绪化特征**：当前情绪状态会影响思考过程
- **个性化判断**：同样的输入在不同情绪下产生不同的解读
- **价值观导向**：体现文件中定义的价值观和思维模式

## 运行示例

```bash
# 运行优化版示例代码
python enhanced_example_usage.py

# 运行主模块测试
python thought_chain_generator.py
```

## API参考

### ThoughtChainPromptGenerator

#### 初始化参数
- `api_key` (str): Gemini API密钥
- `character_prompt_file` (str, 可选): 性格特质文件路径，默认为`../prompt/L0_prompt.txt`

#### 主要方法

##### `generate_thought_chain_prompt(original_input, intention_result, emotion_result, my_mood=None)`
生成思维链prompt的核心方法。

**参数:**
- `original_input` (str): 用户原始输入
- `intention_result` (Dict): 意图识别结果
- `emotion_result` (Dict): 情感分析结果
- `my_mood` (Dict, 可选): 我当前的情绪状态

**返回:**
- `str`: 生成的思维链prompt

##### `process_analysis_result(original_input, analysis_data, my_mood=None)`
处理分析结果的便捷方法。

**参数:**
- `original_input` (str): 用户原始输入
- `analysis_data` (Dict): 包含intention_result和emotion_result的字典
- `my_mood` (Dict, 可选): 我当前的情绪状态

**返回:**
- `str`: 生成的思维链prompt

##### `get_character_info()`
获取当前加载的性格特质信息。

**返回:**
- `str`: 性格特质和人设背景内容

##### `update_character_prompt_file(new_file_path)`
更新性格特质文件路径并重新加载。

**参数:**
- `new_file_path` (str): 新的性格特质文件路径

**返回:**
- `bool`: 是否成功加载

##### `reload_character_prompt(new_file_path=None)`
重新加载性格特质文件。

**参数:**
- `new_file_path` (str, 可选): 新的文件路径

**返回:**
- `bool`: 是否成功加载

## 优化优势

### 相比之前版本的改进：

1. **分离关注点**：
   - 性格特质和人设：从文件加载，相对稳定
   - 情绪状态：通过参数传入，灵活变化

2. **更好的维护性**：
   - 性格特质可以在文件中详细编辑
   - 不需要在代码中硬编码性格参数

3. **更高的灵活性**：
   - 支持多个不同的性格特质文件
   - 可以动态切换角色设定

4. **更清晰的接口**：
   - `my_mood`参数只包含情绪相关字段
   - 接口语义更明确

## 使用场景

1. **个性化聊天机器人**: 为不同角色创建不同的性格特质文件
2. **情感陪伴应用**: 固定性格，动态调整情绪状态
3. **角色扮演游戏**: 为每个NPC创建独特的性格文件
4. **客服系统**: 根据不同客服角色使用不同的性格设定
5. **心理健康支持**: 创建专业心理咨询师的性格特质

## 错误处理

模块内置了完善的错误处理机制：
- 性格特质文件未找到时使用默认设定
- API调用失败时使用备用prompt（同样考虑性格特质）
- 包含详细的日志记录
- 异常情况下不会中断程序运行

## 注意事项

1. 确保`prompt/L0_prompt.txt`文件存在且格式正确
2. 性格特质文件应使用UTF-8编码
3. API密钥要有效且有足够的配额
4. 建议在生产环境中配置适当的日志级别
5. 性格特质文件的内容会直接影响生成效果，需要仔细编写

## 许可证

本项目遵循MIT许可证。 