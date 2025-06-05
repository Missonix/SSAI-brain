import json
import google.generativeai as genai
from typing import Dict, Any, Optional, List
import logging
import os
import asyncio
from datetime import datetime
import uuid

# 导入统一模型配置管理器
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'mcp_agent'))
from model_config import get_genai_model, get_model_config

class ThoughtChainPromptGenerator:
    """
    内心os思维链prompt生成器
    用于接收意图识别和情感分析结果，结合从文件读取的性格特质和当前情绪状态，
    生成思维链prompt用于我的大脑决策
    """
    
    def __init__(self):
        """
        初始化思维链生成器
        """
        self.logger = logging.getLogger(__name__)
        
        # 使用统一的模型配置
        try:
            self.model = get_genai_model()
            model_config = get_model_config()
            self.logger.info(f"✅ ThoughtChainGenerator初始化成功 - 使用模型: {model_config.model_name}")
        except Exception as e:
            self.logger.error(f"❌ ThoughtChainGenerator初始化失败: {e}")
            raise
        
        try:
            # 获取项目根目录路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            self.character_prompt_file = os.path.join(project_root, "prompt", "L0_prompt.txt")
            
            # 加载性格特质和人设背景
            self.character_prompt = self._load_character_prompt()
            
            self.logger.info("✅ ThoughtChainPromptGenerator初始化成功")
            
        except Exception as e:
            self.logger.error(f"❌ ThoughtChainPromptGenerator初始化失败: {e}")
            raise RuntimeError(f"ThoughtChainPromptGenerator初始化失败: {e}")
    
    def _load_character_prompt(self) -> str:
        """从文件加载性格特质和人设背景"""
        try:
            with open(self.character_prompt_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                self.logger.info(f"成功加载性格特质文件: {self.character_prompt_file}")
                return content
        except FileNotFoundError:
            self.logger.warning(f"性格特质文件未找到: {self.character_prompt_file}")
            return self._get_default_character_prompt()
        except Exception as e:
            self.logger.error(f"加载性格特质文件时发生错误: {str(e)}")
            return self._get_default_character_prompt()
    
    def _get_default_character_prompt(self) -> str:
        """获取默认的性格特质描述"""
        return """我是一个具有理性思维的个体。

## 我的核心性格特质：
- 性格类型：理性分析型
- 特质程度：理性分析0.7
- 特质稳定度：0.8

## 我的思维模式：
- 习惯用逻辑分析问题
- 关注事实和效率
- 在决策时会权衡利弊"""

    def reload_character_prompt(self, new_file_path: str = None) -> bool:
        """重新加载性格特质文件"""
        try:
            if new_file_path:
                self.character_prompt_file = new_file_path
            
            self.character_prompt = self._load_character_prompt()
            self.logger.info("性格特质文件重新加载成功")
            return True
        except Exception as e:
            self.logger.error(f"重新加载性格特质文件失败: {str(e)}")
            return False
    
    def generate_thought_chain_prompt(self, 
                                    original_input: str,
                                    intention_result: Dict[str, Any],
                                    emotion_result: Dict[str, Any],
                                    my_mood: Dict[str, Any] = None,
                                    recent_conversation: list = None) -> str:
        """
        生成思维链prompt
        
        Args:
            original_input: 用户原始输入
            intention_result: 意图识别结果
            emotion_result: 情感分析结果
            my_mood: 我当前的情绪状态（只包含情绪相关字段）
            recent_conversation: 近期对话历史列表，格式：[{"type": "user/agent", "content": "...", "timestamp": "..."}]
            
        Returns:
            生成的思维链prompt字符串
        """
        try:
            # 构建系统prompt
            system_prompt = self._build_system_prompt(my_mood, recent_conversation) + "\n" + self._build_analysis_input(intention_result, emotion_result, my_mood, recent_conversation)
            
            # 构建用户输入
            user_input = original_input
            
            # 调用Gemini生成思维链
            response = self.model.generate_content([system_prompt, user_input])
            
            thought_chain_prompt = response.text.strip()
            
            self.logger.info(f"成功生成思维链prompt，长度: {len(thought_chain_prompt)}")
            
            return thought_chain_prompt
            
        except Exception as e:
            self.logger.error(f"生成思维链prompt时发生错误: {str(e)}")
            return self._get_fallback_prompt(original_input, intention_result, emotion_result, my_mood, recent_conversation)
    
    def _build_system_prompt(self, my_mood: Dict[str, Any] = None, recent_conversation: list = None) -> str:
        """构建系统prompt"""
        base_prompt = """我是一个具备主观意识的独立自然人的思维,对方在和我对话,我刚才判断了对方的意图和情绪,现在我的任务是根据对方的原始输入、我刚才意图识别结果和情感分析结果，生成一段思考(思维链prompt)。

这个思考(思维链prompt)将用于指导我的大脑进行情绪及意图方向的决策。

## 注意:
- 你就是"我"
- 对方在与"我"说话
- 可以把对方描述为"他"
- 以我主观角度去分析对方输出
- 不要把对方描述为"你"或"我"，而是用"他"或对方

## 要求：
1. 必须以"我"的口吻描述，体现第一人称视角,以我主观角度去分析对方输出
2. 要结合意图识别和情感分析的结果
3. 要引导我的大脑做出合适的回应策略,不要让我的大脑去分析意图和情绪,而是让我的大脑根据我刚才的意图识别结果和情感分析结果,做出合适的回应策略
4. 直接生成思考(思维链prompt),不要有任何解释"""

        # 添加从文件加载的性格特质和人设背景
        personality_section = f"""

## 我的性格特质和人设背景：
{self.character_prompt}"""

        base_prompt += personality_section

        # 如果有对话历史，添加相关指导
        if recent_conversation and len(recent_conversation) > 0:
            conversation_section = """

## 对话历史记忆指导：
1. 我要基于我们近期的对话历史来理解当前的情境
2. 要考虑对话的连贯性和情绪发展轨迹
3. 如果对方提到了之前聊过的话题，我要体现出记忆和连续性
4. 要根据之前的互动调整我对对方的态度和回应方式
5. 如果发现对方的情绪或态度有变化，要在思考中体现出我的观察
6. 要让我的思考体现出"这不是第一次对话"的感觉"""
            
            base_prompt += conversation_section

        # 如果有当前情绪状态信息，添加相关指导
        if my_mood:
            my_tags = my_mood.get('my_tags', '平静')
            my_intensity = my_mood.get('my_intensity', 5)
            my_mood_desc = my_mood.get('my_mood_description_for_llm', '情绪状态正常')
            my_valence = my_mood.get('my_valence', 0)
            my_arousal = my_mood.get('my_arousal', 0.5)
            
            mood_section = f"""

## 我当前的情绪状态：
- 我的情感标签：{my_tags}
- 我的情感强度：{my_intensity}/10
- 我的情感效价：{my_valence} (负值消极，正值积极)
- 我的情感唤醒度：{my_arousal} (0平静，1激动)
- 我现在的心情：{my_mood_desc}

## 思维链生成要求：
1. 必须体现我的个性特质和人设背景，让思考过程具有强烈的个人色彩
2. 要融入我当前的情绪状态，让思考过程带有明显的情绪色彩
3. 根据我的性格特质来解读对方的意图和情绪，带有明显的主观偏见
4. 生成的思维链要极具个人色彩，体现我独特的思考方式和价值观
5. 要让情绪和性格特质影响我对对方的判断和回应策略选择
6. 要让情绪和性格特质影响我思考的深度和广度
7. 要让情绪和性格特质影响我是否接受或拒绝对方的提议
8. 要让情绪和性格特质影响我对对方的好感和信任度"""
            
            base_prompt += mood_section

        return base_prompt

    def _build_analysis_input(self, 
                         intention_result: Dict[str, Any],
                         emotion_result: Dict[str, Any],
                         my_mood: Dict[str, Any] = None,
                         recent_conversation: list = None) -> str:
        """构建识别输入"""
        analysis_text = f"""我刚才分析了对方的意图和情绪：

意图识别结果：
- 意图：{intention_result.get('intention', '未知')}
- 目的：{intention_result.get('aim', '未知')}
- 针对对象：{intention_result.get('targeting_object', '未知')}
- 是否需要工具：{intention_result.get('need_tool', 'false')}
- 工具：{intention_result.get('tool', [])}
- 识别原因：{intention_result.get('reason', '未知')}
- 置信度：{intention_result.get('confidence', 0)}

情感分析结果：
- 情感效价：{emotion_result.get('valence', 0)}
- 情感唤醒度：{emotion_result.get('arousal', 0)}
- 情感主导性：{emotion_result.get('dominance', 0)}
- 情感标签：{emotion_result.get('tags', '未知')}
- 情感强度：{emotion_result.get('intensity', 0)}
- 情绪描述：{emotion_result.get('mood_description_for_llm', '未知')}
- 情绪触发原因：{emotion_result.get('trigger', '未知')}
- 针对对象：{emotion_result.get('targeting_object', '未知')}
- 置信度：{emotion_result.get('confidence', 0)}
- 分析原因：{emotion_result.get('reason', '未知')}"""

        # 添加对话历史分析
        if recent_conversation and len(recent_conversation) > 0:
            conversation_analysis = "\n\n我们最近的对话历史："
            
            for i, msg in enumerate(recent_conversation[-10:], 1):  # 最多显示最近10条消息
                role = "我" if msg.get("type") in ["agent", "ai", "assistant"] else "对方"
                content = msg.get("content", "")
                timestamp = msg.get("timestamp", "")
                
                # 限制消息长度避免过长
                if len(content) > 100:
                    content = content[:100] + "..."
                
                conversation_analysis += f"\n{i}. {role}: {content}"
            
            conversation_analysis += f"""

根据这些对话历史，我需要考虑：
1. 我们之前聊了什么，对方可能还记得
2. 对方的情绪和态度是否有变化
3. 我应该如何延续之前的话题和情感氛围
4. 是否需要回应之前提到但未完成的事情
5. 对方这次的输入是否与之前的对话有关联"""
            
            analysis_text += conversation_analysis

        if my_mood:
            my_mood_text = f"""

我当前的情绪状态：
- 我的情感效价：{my_mood.get('my_valence', 0)}
- 我的情感唤醒度：{my_mood.get('my_arousal', 0)}
- 我的情感标签：{my_mood.get('my_tags', '平静')}
- 我的情感强度：{my_mood.get('my_intensity', 5)}/10
- 我的心情描述：{my_mood.get('my_mood_description_for_llm', '平常心情')}"""
            
            analysis_text += my_mood_text

        analysis_text += "\n\n现在基于我的性格特质、人设背景、当前情绪状态、我们的对话历史，以及对对方的分析，生成一段极具主观色彩、情绪化且连贯的思考(思维链prompt)，以指导我的大脑做出符合我个性和当前情境的回应。"

        return analysis_text

    def _get_fallback_prompt(self, 
                           original_input: str,
                           intention_result: Dict[str, Any],
                           emotion_result: Dict[str, Any],
                           my_mood: Dict[str, Any] = None,
                           recent_conversation: list = None) -> str:
        """生成备用prompt（当API调用失败时使用）"""
        intention = intention_result.get('intention', '未知')
        emotion_tags = emotion_result.get('tags', '未知')
        intensity = emotion_result.get('intensity', 5)
        mood_desc = emotion_result.get('mood_description_for_llm', '情绪状态不明')
        
        fallback_prompt = f"""基于我的性格特质和人设背景，我需要主观地观察对方，分析对方的意图和情绪：

我的性格特质和背景：
{self.character_prompt}

对方说："{original_input}"

我观察到对方的意图是{intention}，情绪状态是{emotion_tags}，情绪强度达到了{intensity}分（满分10分）。{mood_desc}。"""

        # 添加对话历史信息
        if recent_conversation and len(recent_conversation) > 0:
            fallback_prompt += f"""

回想我们最近的对话，我记得："""
            
            for msg in recent_conversation[-3:]:  # 显示最近3条消息
                role = "我" if msg.get("type") in ["agent", "ai", "assistant"] else "对方"
                content = msg.get("content", "")[:80] + ("..." if len(msg.get("content", "")) > 80 else "")
                fallback_prompt += f"\n- {role}说过：{content}"
            
            fallback_prompt += """

这让我对当前的情况有了更完整的理解。"""

        # 添加我的情绪状态信息
        if my_mood:
            my_tags = my_mood.get('my_tags', '平静')
            my_intensity = my_mood.get('my_intensity', 5)
            my_mood_desc = my_mood.get('my_mood_description_for_llm', '平常心情')
            
            fallback_prompt += f"""

而我自己现在的情绪状态是：{my_tags}，情绪强度{my_intensity}/10，{my_mood_desc}。

基于我的性格特质、人设背景、当前情绪状态和我们的对话历史，我对这个情况的主观看法是：
结合我的个性特征和我们之前的互动，我会从我独特的视角来理解和回应这个情况。我的思考过程会带有明显的个人色彩、主观倾向和对话连续性。"""

        fallback_prompt += """

基于这些分析，我需要：
1. 根据我的性格特质和人设背景来解读对方的真实需求
2. 考虑我当前的情绪状态如何影响我的判断
3. 结合我们的对话历史，理解当前对话的完整语境
4. 选择最符合我个性且连贯的回应方式
5. 如果需要，提供实际的建议或解决方案

我应该以我自己独特的主观视角，结合我们的互动历史，去分析对方的意图和情绪，形成一个具有强烈个人色彩且连贯的思维链prompt。"""
        
        return fallback_prompt

    def process_analysis_result(self, 
                              original_input: str,
                              analysis_data: Dict[str, Any],
                              my_mood: Dict[str, Any] = None,
                              recent_conversation: list = None) -> str:
        """
        处理分析结果的便捷方法
        
        Args:
            original_input: 用户原始输入
            analysis_data: 包含intention_result和emotion_result的字典
            my_mood: 我当前的情绪状态（只包含情绪相关字段）
            recent_conversation: 近期对话历史列表
            
        Returns:
            生成的思维链prompt
        """
        intention_result = analysis_data.get('intention_result', {})
        emotion_result = analysis_data.get('emotion_result', {})
        
        return self.generate_thought_chain_prompt(
            original_input=original_input,
            intention_result=intention_result,
            emotion_result=emotion_result,
            my_mood=my_mood,
            recent_conversation=recent_conversation
        )

    def get_character_info(self) -> str:
        """获取当前加载的性格特质信息"""
        return self.character_prompt

    def update_character_prompt_file(self, new_file_path: str) -> bool:
        """更新性格特质文件路径并重新加载"""
        return self.reload_character_prompt(new_file_path)

    async def update_mood_with_plot_events(self, 
                                          initial_mood: Dict[str, Any],
                                          plot_events: List[str],
                                          role_id: str = "chenxiaozhi_001") -> Dict[str, Any]:
        """
        基于剧情事件更新情绪状态
        
        Args:
            initial_mood: 初始情绪状态字典，包含 my_valence, my_arousal, my_tags, my_intensity, my_mood_description_for_llm
            plot_events: 剧情事件列表
            role_id: 角色ID
            
        Returns:
            更新后的情绪状态字典
        """
        try:
            if not plot_events:
                self.logger.info("没有剧情事件，保持原有情绪状态")
                return initial_mood
            
            # 构建情绪更新的system prompt
            system_prompt = self._build_mood_update_system_prompt(initial_mood)
            
            # 构建用户输入
            user_input = self._build_plot_events_input(plot_events)
            
            # 🔧 添加超时处理的API调用
            self.logger.info("开始调用Gemini API进行剧情情绪分析...")
            
            try:
                # 设置10秒超时
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.model.generate_content,
                        [system_prompt, user_input]
                    ),
                    timeout=10.0
                )
                
                updated_mood_text = response.text.strip()
                self.logger.info("✅ Gemini API调用成功")
                
            except asyncio.TimeoutError:
                self.logger.warning("⚠️ Gemini API调用超时，使用原始情绪状态")
                return initial_mood
            except Exception as api_error:
                self.logger.error(f"❌ Gemini API调用失败: {api_error}")
                return initial_mood
            
            # 解析更新后的情绪状态
            updated_mood = self._parse_mood_response(updated_mood_text, initial_mood)
            
            self.logger.info(f"情绪状态更新成功: {initial_mood.get('my_tags', '未知')} -> {updated_mood.get('my_tags', '未知')}")
            
            # 更新Redis中的情绪状态
            await self._update_mood_in_redis(role_id, updated_mood)
            
            return updated_mood
            
        except Exception as e:
            self.logger.error(f"更新情绪状态时发生错误: {str(e)}")
            return initial_mood  # 出错时返回原始情绪状态
    
    def _build_mood_update_system_prompt(self, initial_mood: Dict[str, Any]) -> str:
        """构建情绪更新的系统prompt"""
        base_prompt = f"""你是一个情绪状态分析和更新专家。

## 我的性格特质和人设背景：
{self.character_prompt}

## 当前情绪状态：
- 我的情感效价：{initial_mood.get('my_valence', 0)} (范围-1到1，负值消极，正值积极)
- 我的情感唤醒度：{initial_mood.get('my_arousal', 0)} (范围0到1，0平静，1激动)
- 我的情感标签：{initial_mood.get('my_tags', '平静')}
- 我的情感强度：{initial_mood.get('my_intensity', 5)}/10
- 我的心情描述：{initial_mood.get('my_mood_description_for_llm', '平常心情')}

## 任务要求：
基于我的性格特质和当前情绪状态，分析即将提供的剧情事件对我情绪的影响，生成更新后的情绪状态。

## 输出格式要求：
请严格按照以下JSON格式输出，不要添加任何其他文字：
{{
    "my_valence": 数值(范围-1到1),
    "my_arousal": 数值(范围0到1),
    "my_tags": "情感标签",
    "my_intensity": 数值(范围1到10),
    "my_mood_description_for_llm": "详细的心情描述"
}}

## 分析原则：
1. 要结合我的性格特质来分析情绪变化
2. 考虑情绪的渐进性变化，不要过于剧烈
3. 情感效价和唤醒度要与情感标签和强度保持一致
4. 心情描述要具体、生动，体现我的个性特征
5. 要考虑我对不同事件的个人反应模式"""

        return base_prompt
    
    def _build_plot_events_input(self, plot_events: List[str]) -> str:
        """构建剧情事件输入"""
        events_text = "## 剧情事件:\n"
        events_text += "以下是我近期的生活和工作事件：\n\n"
        
        for i, event in enumerate(plot_events, 1):
            events_text += f"{i}. {event}\n"
        
        events_text += "\n请基于这些事件分析我的情绪变化，生成更新后的情绪状态。"
        return events_text
    
    def _parse_mood_response(self, response_text: str, initial_mood: Dict[str, Any]) -> Dict[str, Any]:
        """解析情绪更新响应"""
        try:
            # 尝试提取JSON部分
            import re
            import json
            
            # 查找JSON格式的内容
            json_pattern = r'\{[^}]*"my_valence"[^}]*\}'
            json_match = re.search(json_pattern, response_text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group()
                try:
                    parsed_mood = json.loads(json_str)
                    
                    # 验证和修正数值范围
                    parsed_mood["my_valence"] = max(-1, min(1, float(parsed_mood.get("my_valence", 0))))
                    parsed_mood["my_arousal"] = max(0, min(1, float(parsed_mood.get("my_arousal", 0.5))))
                    parsed_mood["my_intensity"] = max(1, min(10, int(parsed_mood.get("my_intensity", 5))))
                    
                    # 确保必要字段存在
                    if "my_tags" not in parsed_mood:
                        parsed_mood["my_tags"] = initial_mood.get("my_tags", "平静")
                    if "my_mood_description_for_llm" not in parsed_mood:
                        parsed_mood["my_mood_description_for_llm"] = initial_mood.get("my_mood_description_for_llm", "情绪状态正常")
                    
                    self.logger.info("成功解析情绪更新响应")
                    return parsed_mood
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"JSON解析失败: {e}")
            
            # 如果JSON解析失败，尝试文本解析
            return self._fallback_parse_mood(response_text, initial_mood)
            
        except Exception as e:
            self.logger.error(f"解析情绪响应失败: {e}")
            return initial_mood
    
    def _fallback_parse_mood(self, response_text: str, initial_mood: Dict[str, Any]) -> Dict[str, Any]:
        """备用的情绪解析方法"""
        try:
            # 简单的文本解析逻辑
            updated_mood = initial_mood.copy()
            
            response_lower = response_text.lower()
            
            # 根据关键词推断情绪变化
            if any(word in response_lower for word in ["高兴", "开心", "愉悦", "兴奋", "满意"]):
                updated_mood["my_valence"] = min(1, updated_mood.get("my_valence", 0) + 0.3)
                updated_mood["my_tags"] = "愉悦"
                updated_mood["my_intensity"] = min(10, updated_mood.get("my_intensity", 5) + 2)
            elif any(word in response_lower for word in ["难过", "沮丧", "失望", "痛苦", "烦恼"]):
                updated_mood["my_valence"] = max(-1, updated_mood.get("my_valence", 0) - 0.3)
                updated_mood["my_tags"] = "沮丧"
                updated_mood["my_intensity"] = min(10, updated_mood.get("my_intensity", 5) + 1)
            elif any(word in response_lower for word in ["愤怒", "生气", "气愤", "恼火", "暴躁"]):
                updated_mood["my_valence"] = max(-1, updated_mood.get("my_valence", 0) - 0.4)
                updated_mood["my_arousal"] = min(1, updated_mood.get("my_arousal", 0.5) + 0.3)
                updated_mood["my_tags"] = "愤怒"
                updated_mood["my_intensity"] = min(10, updated_mood.get("my_intensity", 5) + 3)
            elif any(word in response_lower for word in ["焦虑", "紧张", "担心", "不安", "压力"]):
                updated_mood["my_arousal"] = min(1, updated_mood.get("my_arousal", 0.5) + 0.2)
                updated_mood["my_tags"] = "焦虑"
                updated_mood["my_intensity"] = min(10, updated_mood.get("my_intensity", 5) + 2)
            
            updated_mood["my_mood_description_for_llm"] = f"基于近期事件的情绪状态，{updated_mood['my_tags']}程度{updated_mood['my_intensity']}/10"
            
            self.logger.info("使用备用方法解析情绪状态")
            return updated_mood
            
        except Exception as e:
            self.logger.error(f"备用情绪解析失败: {e}")
            return initial_mood
    
    async def _update_mood_in_redis(self, role_id: str, updated_mood: Dict[str, Any]) -> bool:
        """更新Redis中的情绪状态"""
        try:
            from database_config import get_redis_client
            
            redis_client = await get_redis_client()
            redis_key = f"role_mood:{role_id}"
            
            # 存储到Redis
            await redis_client.hset(redis_key, mapping=updated_mood)
            await redis_client.expire(redis_key, 86400)  # 24小时过期
            
            self.logger.info(f"✅ 情绪状态已更新到Redis: {role_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 更新Redis中的情绪状态失败: {e}")
            return False
    
    async def get_mood_from_redis(self, role_id: str) -> Optional[Dict[str, Any]]:
        """从Redis获取当前情绪状态"""
        try:
            from database_config import get_redis_client
            
            redis_client = await get_redis_client()
            redis_key = f"role_mood:{role_id}"
            
            mood_data = await redis_client.hgetall(redis_key)
            if mood_data:
                # 转换数据类型
                mood = {}
                for key, value in mood_data.items():
                    key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                    value_str = value.decode('utf-8') if isinstance(value, bytes) else value
                    
                    if key_str in ['my_valence', 'my_arousal']:
                        mood[key_str] = float(value_str)
                    elif key_str == 'my_intensity':
                        mood[key_str] = int(value_str)
                    else:
                        mood[key_str] = value_str
                
                self.logger.info(f"从Redis获取情绪状态成功: {role_id}")
                return mood
            else:
                self.logger.info(f"Redis中未找到情绪状态: {role_id}")
                return None
                
        except Exception as e:
            self.logger.error(f"从Redis获取情绪状态失败: {e}")
            return None

    async def process_plot_events_and_update_mood(self, 
                                                  role_id: str,
                                                  plot_events: List[str]) -> Dict[str, Any]:
        """
        处理剧情事件并更新情绪状态的便捷方法
        
        Args:
            role_id: 角色ID
            plot_events: 剧情事件列表
            
        Returns:
            更新后的情绪状态字典
        """
        try:
            # 1. 获取当前情绪状态
            current_mood = await self.get_mood_from_redis(role_id)
            if not current_mood:
                # 使用默认情绪状态
                current_mood = {
                    "my_valence": 0.0,
                    "my_arousal": 0.3,
                    "my_tags": "平静",
                    "my_intensity": 5,
                    "my_mood_description_for_llm": "当前状态比较平静"
                }
                self.logger.warning(f"未找到角色 {role_id} 的情绪状态，使用默认值")
            
            # 2. 基于剧情事件更新情绪
            updated_mood = await self.update_mood_with_plot_events(current_mood, plot_events, role_id)
            
            return updated_mood
            
        except Exception as e:
            self.logger.error(f"处理剧情事件并更新情绪失败: {e}")
            return current_mood if 'current_mood' in locals() else {
                "my_valence": 0.0,
                "my_arousal": 0.3,
                "my_tags": "平静",
                "my_intensity": 5,
                "my_mood_description_for_llm": "情绪状态处理异常"
            }


def main():
    """测试函数"""
    # 示例数据
    test_original_input = "受不了了，一天也不想上班了，地球快点爆炸"
    
    test_analysis_data = {
        "intention_result": {
            "intention": "抱怨",
            "aim": "没有明确目的",
            "targeting_object": "上班这件事",
            "need_tool": "false",
            "tool": [],
            "reason": "他表达了对上班的极度不满，称一天也不想上了，还说地球快点爆炸，这是明显的抱怨情绪的体现，没有向我提出具体要求或寻求帮助等。",
            "confidence": "0.9"
        },
        "emotion_result": {
            "valence": -0.8,
            "arousal": 0.8,
            "dominance": 0.1,
            "tags": "愤怒、烦躁",
            "intensity": 8,
            "mood_description_for_llm": "他处于极度愤怒和烦躁的情绪中，对上班这件事忍无可忍",
            "trigger": "上班带来的压力和不满",
            "targeting_object": "上班这件事",
            "confidence": 0.9,
            "reason": "他明确表达受不了上班，还说一天也不想上，甚至有极端的想法，说明他对上班的愤怒和烦躁情绪很强烈"
        }
    }
    
    # 我的情绪状态（现在只包含情绪相关字段）
    test_my_mood = {
        "my_valence": 0.4,
        "my_arousal": 0.6,
        "my_tags": "愉悦",
        "my_intensity": 6,
        "my_mood_description_for_llm": "今天天气很好,我心情愉悦"
    }
    
    # 模拟近期对话历史
    test_recent_conversation = [
        {
            "type": "user",
            "content": "你好小智，我最近工作压力好大",
            "timestamp": "2024-01-20 10:30:00"
        },
        {
            "type": "agent", 
            "content": "哎，工作压力大确实挺烦人的。我自己也经常因为工作的事情感到烦躁。你具体是哪方面压力比较大？",
            "timestamp": "2024-01-20 10:30:15"
        },
        {
            "type": "user",
            "content": "主要是老板总是催进度，感觉做不完",
            "timestamp": "2024-01-20 10:31:00"
        },
        {
            "type": "agent",
            "content": "我懂，被老板催进度真的很讨厌。我之前也遇到过类似情况，那种感觉就像被人追着跑一样。有没有考虑过和老板沟通一下工作量的问题？",
            "timestamp": "2024-01-20 10:31:20"
        },
        {
            "type": "user",
            "content": "试过了，但是老板说这是正常的工作量",
            "timestamp": "2024-01-20 10:32:00"
        },
        {
            "type": "agent",
            "content": "典型的甩锅行为啊。老板总是这样，把责任推给员工。我觉得你可以考虑记录一下每天的工作内容和时间，给他看看到底量有多大。",
            "timestamp": "2024-01-20 10:32:30"
        }
    ]
    
    # 创建生成器实例（性格特质从文件加载）
    generator = ThoughtChainPromptGenerator()
    
    print("=== 优化后的思维链prompt生成器（含对话历史） ===")
    print(f"用户输入：{test_original_input}")
    print(f"我的性格特质（从文件加载）：")
    print(generator.get_character_info()[:200] + "...")
    print(f"\n我的当前情绪：{test_my_mood}")
    print(f"\n对话历史（最近{len(test_recent_conversation)}条）：")
    for i, msg in enumerate(test_recent_conversation[-3:], 1):
        role = "用户" if msg["type"] == "user" else "我"
        content = msg["content"][:50] + "..." if len(msg["content"]) > 50 else msg["content"]
        print(f"  {i}. {role}: {content}")
    
    # 生成思维链prompt
    thought_chain = generator.process_analysis_result(
        original_input=test_original_input,
        analysis_data=test_analysis_data,
        my_mood=test_my_mood,
        recent_conversation=test_recent_conversation
    )
    
    print(f"\n生成的思维链prompt：\n{thought_chain}")
    print("-" * 80)
    
    # 测试没有对话历史的情况
    print("=== 对比：没有对话历史的情况 ===")
    thought_chain_no_history = generator.process_analysis_result(
        original_input=test_original_input,
        analysis_data=test_analysis_data,
        my_mood=test_my_mood,
        recent_conversation=None
    )
    
    print(f"没有对话历史的思维链prompt：\n{thought_chain_no_history}")
    print("-" * 80)
    
    # 测试不同对话历史的影响
    print("=== 对比：轻松愉快的对话历史 ===")
    happy_conversation = [
        {
            "type": "user",
            "content": "小智，今天天气真好！",
            "timestamp": "2024-01-20 10:25:00"
        },
        {
            "type": "agent",
            "content": "是啊，阳光明媚的，心情都变好了。你今天有什么开心的计划吗？",
            "timestamp": "2024-01-20 10:25:15"
        },
        {
            "type": "user",
            "content": "打算去公园走走，放松一下",
            "timestamp": "2024-01-20 10:26:00"
        },
        {
            "type": "agent",
            "content": "不错的选择！我也喜欢在好天气的时候出去走走，能让人心情舒畅。",
            "timestamp": "2024-01-20 10:26:20"
    }
    ]
    
    thought_chain_happy = generator.process_analysis_result(
        original_input=test_original_input,
        analysis_data=test_analysis_data,
        my_mood=test_my_mood,
        recent_conversation=happy_conversation
    )
    
    print(f"轻松对话历史下的思维链prompt：\n{thought_chain_happy}")
    print("=" * 80)


if __name__ == "__main__":
    main() 