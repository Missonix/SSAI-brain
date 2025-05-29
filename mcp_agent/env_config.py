"""
环境配置文件
管理API密钥和其他配置信息
"""

import os

# Gemini API配置
GOOGLE_API_KEY = ""

# 高德地图API配置
AMAP_MAPS_API_KEY = ""

# Bocha搜索API配置
BOCHA_API_KEY = ""

# 设置环境变量
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
os.environ["AMAP_MAPS_API_KEY"] = AMAP_MAPS_API_KEY
os.environ["BOCHA_API_KEY"] = BOCHA_API_KEY

def get_config():
    """获取配置信息"""
    return {
        "google_api_key": GOOGLE_API_KEY,
        "amap_api_key": AMAP_MAPS_API_KEY,
        "bocha_api_key": BOCHA_API_KEY
    } 