"""
配置文件
用于管理API密钥和其他配置参数
"""
import os
import sys
from typing import Optional

# 导入统一模型配置管理器
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'mcp_agent'))
from model_config import get_model_config, model_manager

class Config:
    """配置类 - 使用统一的模型配置管理器"""
    
    # 日志配置
    LOG_LEVEL = "INFO"
    
    # 备用prompt配置
    USE_FALLBACK_ON_ERROR = True
    
    @classmethod
    def get_api_key(cls) -> str:
        """获取API密钥，使用统一配置"""
        config = get_model_config()
        return config.api_key
    
    @classmethod
    def get_model_name(cls) -> str:
        """获取模型名称，使用统一配置"""
        config = get_model_config()
        return config.model_name
    
    @classmethod
    def update_api_key(cls, new_key: str) -> None:
        """更新API密钥，使用统一配置管理器"""
        model_manager.update_config(api_key=new_key) 