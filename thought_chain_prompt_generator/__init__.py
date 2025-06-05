"""
内心os思维链prompt生成模块

用于接收意图识别和情感分析结果，生成思维链prompt指导我的大脑决策
"""

from .thought_chain_generator import ThoughtChainPromptGenerator
from .config import Config

__version__ = "1.0.0"
__author__ = "AI Assistant"
__description__ = "内心os思维链prompt生成模块，用于指导我的大脑进行情绪和意图相关的决策"

__all__ = [
    "ThoughtChainPromptGenerator",
    "Config"
] 