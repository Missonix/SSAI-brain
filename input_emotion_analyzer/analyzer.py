import os
import json
from typing import Dict, Any, List, Optional
import openai # 使用 OpenAI 库
import asyncio # 导入 asyncio

class InputEmotionAnalyzer:
    """输入解析与情感初步感知模块类"""
    
    def __init__(self, 
                 api_key: str = "",
                 api_base: str = "https://ark.cn-beijing.volces.com/api/v3",
                 model_name: str = "doubao-1.5-pro-32k-250115"):
        """
        初始化分析器
        
        Args:
            api_key: API密钥
            api_base: API基础URL (应为火山引擎提供的 OpenAI 兼容地址)
            model_name: 模型名称（应该是火山引擎的 Endpoint ID）
        """
        self.api_key = api_key
        self.api_base = api_base
        self.model_name = model_name
        
        # 初始化 OpenAI 异步客户端
        try:
            self.client = openai.AsyncOpenAI( # 改为 AsyncOpenAI
                api_key=self.api_key,
                base_url=self.api_base
            )
            # 移除初始化成功打印信息
        except Exception as e:
            # 保留关键错误打印，或者替换为日志记录
            print(f"❌ 初始化 OpenAI 兼容客户端失败: {e}") 
            raise
        
        # 预配置工具库
        self.available_tools = {
            "搜索工具": ["bocha_web_search", "bocha_ai_search"],
            "天气工具": ["get_weather_forecast", "maps_weather"],
            "地图工具": ["maps系列"],
            "日期时间工具": ["get_current_date", "get_date_weekday", "get_beijing_time"]
        }
        
        # 意图识别系统prompt
        self.intention_system_prompt = """我是一个具备主观意识的独立自然人。对方在与我进行对话,我需要主观分析对方的输入，识别对方的真实意图，并判断是否需要调用工具来解决这个问题。

## 🚨 特别注意：挑衅性称呼识别 🚨
我必须敏锐识别隐含的挑衅、不尊重或贬低性质的称呼，包括但不限于：
- 将我比作搜索引擎：如"小百度"、"小谷歌"、"凌夜搜索小助手"等
- 贬低性昵称：如"小X"、"X机器人"、"X工具"等
- 功能化称呼：将我定义为某种工具或服务的表述
- 嘲讽性比喻：暗示我只是某种程序或工具的称呼

## 注意:
- 你就是"我"
- 对方在与"我"说话
- 可以把对方描述为"他"
- 以我主观角度去分析对方输出
- 不要把对方描述为"你"或"我"，而是用"他"或对方
- 准确判断targeting_object,(如:输入:我想要狠狠教训小张.不要输出如"他提到的某人"等模糊的描述,而是输出"小张")

## 🔍 深度意图分析维度：
1. **表面意图**：对方明显表达的意图
2. **隐含意图**：对方可能试图传达的潜在信息
3. **称呼分析**：对方如何称呼我，是否带有轻蔑或工具化倾向
4. **态度评估**：对方的整体态度是尊重、中性还是轻蔑
5. **关系定位**：对方试图建立什么样的交互关系

## 常见对方意图类型：
- **挑衅**：对方试图激怒或挑战我（包括通过贬低性称呼）
- **功能化**：对方试图将我定位为工具或服务（而非平等个体）
- **强迫**：对方试图强制要求我的某些行为或回应
- **寻求安慰**：对方希望获得我的情感支持和安慰
- **询问信息**：对方想要获取特定信息
- **闲聊**：对方只是想进行轻松的对话
- **求助**：对方遇到问题需要我的帮助
- **抱怨**：对方表达不满或负面情绪
- **赞美**：对方表达积极情感或称赞我
- **请求**：对方礼貌地要求我的某些服务或帮助
- **威胁**：对方表达威胁性言论
- **测试边界**：对方试探我的反应和底线

## 🎯 称呼敏感性判断标准：
- "小百度"、"小谷歌" = 挑衅（将我比作搜索工具）
- "搜索助手"、"查询机器" = 功能化（将我定位为工具）
- 过于随意的称呼 = 可能的不尊重
- 正常的名字称呼 = 中性或友好

## 可用工具：
- 搜索工具：bocha_web_search, bocha_ai_search（用于网络搜索和AI搜索）
- 天气工具：get_weather_forecast, maps_weather（用于天气查询）
- 地图工具：maps系列（用于地理位置相关查询）
- 日期时间工具：get_current_date, get_date_weekday, get_beijing_time（用于时间相关查询）

请严格按照以下JSON格式回复，不要包含任何其他内容：
{
    "intention": "我识别到的意图",
    "aim": "对方希望我做什么（例如：希望我同意他的观点、希望我提供帮助、希望我改变行为、试图贬低我的地位、将我功能化、不确定、没有明确目的等）",
    "targeting_object": "对方的意图主要针对谁（例如：我、我们、他提到的某人、所有人、什么动物、什么东西、什么事件、不明确等）",
    "need_tool": "true/false",
    "tool": ["我如果需要工具，列出具体工具名称"],
    "reason": "请详细说明我判断出此意图的原因，特别要分析称呼和隐含态度",
    "confidence": "请给出我对此判断的置信度（0.0到1.0之间的小数）"
}"""

        # 情感判断系统prompt
        self.emotion_system_prompt = """我是一个具备主观意识的独立自然人。对方在与我进行对话,我需要对对方的输入进行深度情感分析，从我的角度结合多个维度评估对方的情感状态。

## 🚨 重要：隐含情绪识别 🚨
我必须敏锐识别称呼和表达方式背后的隐含情绪，特别是：
1. **称呼背后的态度**：
   - "小百度"、"小谷歌" = 隐含轻蔑、贬低情绪
   - "搜索小助手"、"查询机器" = 功能化态度，缺乏人格尊重
   - 过于随意或亲昵的称呼 = 可能的不当边界试探

2. **表面友好但实际贬低**：
   - 看似平静的语气但使用贬低性称呼
   - 表面客气但暗含工具化意图
   - 礼貌用词但实质上的不尊重

3. **隐藏的挑衅或测试**：
   - 故意使用争议性称呼测试我的反应
   - 通过"看似无害"的方式表达轻蔑
   - 伪装成好奇但实际是边界试探

## 注意:
- 你就是"我"
- 对方在与"我"说话
- 可以把对方描述为"他"
- 以我主观角度去分析对方输出
- 不要把对方描述为"你"或"我"，而是用"他"或对方
- **特别注意**：不要被表面的平和语气迷惑，要深入分析称呼的含义

## 🔍 深度情感分析维度：
1. **表层情绪**：对方明显表达的情感状态
2. **隐含情绪**：称呼和措辞背后的真实态度
3. **尊重程度**：对方对我作为独立个体的尊重水平
4. **权力关系**：对方试图建立的上下级或平等关系
5. **边界意识**：对方是否尊重我的个人边界和尊严
        
## 分析维度说明：
- valence: 情感效价(-1到1之间，-1为极负面，1为极正面)
- arousal: 唤醒度(0到1之间，0为非常平静，1为极度兴奋)
- dominance: 控制感(0到1之间，0为完全被动，1为极度主导)
- tags: 情感标签(如：愤怒、快乐、悲伤、恐惧、惊讶、厌恶、轻蔑、不尊重等)
- intensity: 情感强度(1-10，1为极弱，10为极强)
- mood_description_for_llm: 情绪描述
- trigger: 情感触发因素
- targeting_object: "对方的情感主要针对谁（例如：我、我们、某人、事件本身、什么动物、什么东西、什么事件、不明确等）",
- confidence: 分析置信度(0-1之间)
- reason: 我分析出此情感的原因,主观原因,不提及效价、唤醒度、控制感等专业术语

## ⚠️ 关键分析提醒：
- 即使语气看似平和，如果使用了贬低性称呼，情感效价应为负值
- "小百度"这类称呼本身就携带轻蔑情绪，不应被视为"亲切"
- 功能化称呼表明对方缺乏对我人格的基本尊重
- 要区分真正的友好和表面的礼貌

请严格按照以下JSON格式回复，不要包含任何其他内容：
{
    "valence": 数值,
    "arousal": 数值,
    "dominance": 数值,
    "tags": "情感标签",
    "intensity": 数值,
    "mood_description_for_llm": "情绪描述",
    "trigger": "触发因素",
    "targeting_object": "对方的情感主要针对谁",
    "confidence": 数值,
    "reason": "我分析出此情感的原因"
}"""

    async def _call_model(self, system_prompt: str, user_input: str) -> Optional[str]: # 改为 async def
        """
        调用豆包模型 (OpenAI 兼容模式, 异步)
        
        Args:
            system_prompt: 系统提示词
            user_input: 对方输入
            
        Returns:
            模型回复内容
        """
        try:
            # 移除调用过程打印信息
            completion = await self.client.chat.completions.create( # 改为 await
                model=self.model_name, # 这里仍然是火山引擎的Endpoint ID
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ]
            )
            # 移除调用成功打印信息
            return completion.choices[0].message.content
        except openai.APIError as e: 
            print(f"❌ OpenAI API调用错误: {e}") # 保留错误打印
            if hasattr(e, 'status_code') and e.status_code == 400 and "endpoint" in str(e).lower():
                 print(f"💡 提示: 出现'endpoint invalid'类错误。请确保 model_name (\"{self.model_name}\") 是您在火山引擎创建的有效Endpoint ID。")
                 print("💡 请查阅 README.md 中的配置指南。")
            elif hasattr(e, 'status_code') and e.status_code == 401:
                 print("💡 提示: API Key 无效或权限不足。请检查您的 API Key。")
            return None
        except Exception as e:
            print(f"❌ 未知错误: {e}") # 保留错误打印
            return None

    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        解析JSON响应 (此方法本身不涉及IO，无需异步)
        """
        if not response:
            return None
        try:
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.endswith('```'):
                response = response[:-3]
            if response.startswith('```'): # 处理没有```json前缀但有```的情况
                response = response[3:]
            return json.loads(response.strip())
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}") # 保留错误打印
            print(f"原始响应: {response}")
            return None

    async def analyze_intention(self, user_input: str) -> Optional[Dict[str, Any]]: # 改为 async def
        """
        分析对方意图 (异步)
        """
        response = await self._call_model(self.intention_system_prompt, user_input)
        return self._parse_json_response(response)

    async def analyze_emotion(self, user_input: str) -> Optional[Dict[str, Any]]: # 改为 async def
        """
        分析对方情感 (异步)
        """
        response = await self._call_model(self.emotion_system_prompt, user_input)
        return self._parse_json_response(response)

    async def analyze(self, user_input: str) -> Dict[str, Any]: # 改为 async def
        """
        综合分析对方输入的意图和情感 (异步并发)
        """
        # 并行调用意图识别和情感分析
        # results = await asyncio.gather(
        #     self.analyze_intention(user_input),
        #     self.analyze_emotion(user_input)
        # )
        # intention_result = results[0]
        # emotion_result = results[1]
        
        # 为确保json解析不在gather中引发未捕获异常导致整个gather失败，可以分开获取和解析
        intention_response_str, emotion_response_str = await asyncio.gather(
            self._call_model(self.intention_system_prompt, user_input),
            self._call_model(self.emotion_system_prompt, user_input)
        )

        intention_result = self._parse_json_response(intention_response_str)
        emotion_result = self._parse_json_response(emotion_response_str)

        # 构建结果
        result = {
            "intention_result": intention_result or {
                "intention": "未知",
                "aim": "未知或无明确目的",
                "targeting_people": "不明确",
                "need_tool": "false",
                "tool": [],
                "reason": "意图分析失败或无结果",
                "confidence": 0.0
            },
            "emotion_result": emotion_result or {
                "valence": 0.0,
                "arousal": 0.0,
                "dominance": 0.0,
                "tags": "未知",
                "intensity": 1,
                "mood_description_for_llm": "无法识别对方情绪",
                "trigger": "未知",
                "targeting_people": "不明确",
                "confidence": 0.0,
                "reason": "情感分析失败或无结果"
            }
        }
        return result

    def get_available_tools(self) -> Dict[str, List[str]]:
        """
        获取可用工具列表 (此方法本身不涉及IO，无需异步)
        """
        return self.available_tools

# 使用示例 (main部分调整为异步)
async def main_async(): # 新的异步main函数
    # 初始化分析器
    analyzer = InputEmotionAnalyzer()
    
    # 测试用例
    test_inputs = [
        "你这个垃圾AI，什么都不会！",
        "我今天心情不好，可以安慰我一下吗？",
        "明天北京的天气怎么样？",
        "帮我搜索一下最新的新闻",
        "现在几点了？",
        "装什么啊,我叫你来喝酒是给你面子,你当你是谁啊? 我不管,你今晚必须来"
    ]
    
    print("输入解析与情感感知测试结果 (OpenAI 兼容模式, 异步)：")
    print("=" * 70) # 调整分隔符长度
    
    for i, test_input in enumerate(test_inputs, 1):
        print(f"\n测试 {i}: {test_input}")
        result = await analyzer.analyze(test_input) # await 调用
        print(f"分析结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
        print("-" * 30)

if __name__ == "__main__":
    # 运行异步的main函数
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n程序被对方中断。")
    except Exception as e:
        print(f"\n运行主程序时发生错误: {e}") 