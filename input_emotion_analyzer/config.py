# 配置文件
class Config:
    """配置类"""
    
    # 豆包API配置
    DOUBAO_API_KEY = ""
    DOUBAO_API_BASE = "https://ark.cn-beijing.volces.com/api/v3"
    DOUBAO_MODEL_NAME = "doubao-1.5-pro-32k-250115"
    
    # 工具配置
    AVAILABLE_TOOLS = {
        "搜索工具": ["bocha_web_search", "bocha_ai_search"],
        "天气工具": ["get_weather_forecast", "maps_weather"],
        "地图工具": ["maps系列"],
        "日期时间工具": ["get_current_date", "get_date_weekday", "get_beijing_time"]
    }
    
    # 情感分析配置
    EMOTION_DIMENSIONS = {
        "valence": {"range": (-1, 1), "description": "情感效价"},
        "arousal": {"range": (0, 1), "description": "唤醒度"},
        "dominance": {"range": (0, 1), "description": "控制感"},
        "intensity": {"range": (1, 10), "description": "情感强度"},
        "confidence": {"range": (0, 1), "description": "置信度"}
    }
    
    # 常见意图类型
    INTENTION_TYPES = [
        "挑衅", "强迫", "寻求安慰", "询问信息", "闲聊",
        "求助", "抱怨", "赞美", "请求", "威胁"
    ]
    
    # 常见情感标签
    EMOTION_TAGS = [
        "愤怒", "快乐", "悲伤", "恐惧", "惊讶", "厌恶",
        "焦虑", "兴奋", "平静", "失望", "满足", "困惑"
    ] 