"""
环境配置文件
管理API密钥和其他配置信息
"""

import os
from model_config import get_model_config, setup_environment

# 使用统一模型配置设置环境变量
setup_environment()

# 高德地图API配置
AMAP_MAPS_API_KEY = "81d4e0e5baf967c6d632e83d6b332dcf"

# Bocha搜索API配置
BOCHA_API_KEY = "sk-af4f2db4236a4168ad7759e8c8823748"

# 设置环境变量
os.environ["AMAP_MAPS_API_KEY"] = AMAP_MAPS_API_KEY
os.environ["BOCHA_API_KEY"] = BOCHA_API_KEY

def get_config():
    """获取配置信息"""
    model_config = get_model_config()
    return {
        "google_api_key": model_config.api_key,
        "amap_api_key": AMAP_MAPS_API_KEY,
        "bocha_api_key": BOCHA_API_KEY,
        "model_provider": model_config.provider.value,
        "model_name": model_config.model_name
    } 