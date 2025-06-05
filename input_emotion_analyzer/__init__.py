"""
输入解析与情感初步感知模块

这是一个基于豆包大模型的输入解析与情感感知模块，
提供用户意图识别和情感分析功能。

主要功能：
- 用户意图识别（挑衅、强迫、寻求安慰等）
- 工具需求判断和推荐
- 多维度情感分析（效价、唤醒度、控制感等）
- 情感标签识别和强度评估

使用示例：
    from input_emotion_analyzer import InputEmotionAnalyzer
    
    analyzer = InputEmotionAnalyzer()
    result = analyzer.analyze("我今天心情不好")
    print(result)
"""

from .analyzer import InputEmotionAnalyzer
from .config import Config

__version__ = "1.0.0"
__author__ = "AI Assistant"
__email__ = "assistant@example.com"

__all__ = [
    "InputEmotionAnalyzer",
    "Config"
] 