"""
统一模型配置管理
管理项目中所有LLM模型的配置，包括API key、base URL、模型名称等
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

class ModelProvider(Enum):
    """支持的模型提供商"""
    GEMINI = "gemini"
    OPENAI = "openai"
    CLAUDE = "claude"
    QWEN = "qwen"
    GLM = "glm"

@dataclass
class ModelConfig:
    """模型配置类"""
    provider: ModelProvider
    model_name: str
    api_key: str
    base_url: Optional[str] = None
    temperature: float = 0.0
    max_tokens: Optional[int] = None
    timeout: int = 30
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        config = {
            "provider": self.provider.value,
            "model_name": self.model_name,
            "api_key": self.api_key,
            "temperature": self.temperature,
            "timeout": self.timeout
        }
        if self.base_url:
            config["base_url"] = self.base_url
        if self.max_tokens:
            config["max_tokens"] = self.max_tokens
        return config

class UnifiedModelManager:
    """统一模型配置管理器"""
    
    # 默认配置 - 使用Gemini
    DEFAULT_CONFIG = {
        "provider": ModelProvider.GEMINI,
        "model_name": "gemini-2.0-flash-exp",
        "api_key": "",  # 默认key，可通过环境变量覆盖
        "base_url": None,
        "temperature": 0.0,
        "max_tokens": None,
        "timeout": 30
    }
    
    # 预定义的模型配置模板
    MODEL_TEMPLATES = {
        ModelProvider.GEMINI: {
            "gemini-2.0-flash-exp": {
                "provider": ModelProvider.GEMINI,
                "model_name": "gemini-2.0-flash-exp",
                "base_url": None,
                "temperature": 0.0,
                "timeout": 30
            },
            "gemini-1.5-pro": {
                "provider": ModelProvider.GEMINI,
                "model_name": "gemini-1.5-pro",
                "base_url": None,
                "temperature": 0.0,
                "timeout": 30
            }
        },
        ModelProvider.OPENAI: {
            "gpt-4": {
                "provider": ModelProvider.OPENAI,
                "model_name": "gpt-4",
                "base_url": "https://api.openai.com/v1",
                "temperature": 0.0,
                "timeout": 30
            },
            "gpt-3.5-turbo": {
                "provider": ModelProvider.OPENAI,
                "model_name": "gpt-3.5-turbo",
                "base_url": "https://api.openai.com/v1",
                "temperature": 0.0,
                "timeout": 30
            }
        },
        ModelProvider.QWEN: {
            "qwen-turbo": {
                "provider": ModelProvider.QWEN,
                "model_name": "qwen-turbo",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "temperature": 0.0,
                "timeout": 30
            }
        }
    }
    
    def __init__(self):
        """初始化模型管理器"""
        self._current_config = self._load_config_from_env()
    
    def _load_config_from_env(self) -> ModelConfig:
        """从环境变量加载配置"""
        # 获取当前配置的提供商
        provider_str = os.getenv('MODEL_PROVIDER', self.DEFAULT_CONFIG['provider'].value)
        try:
            provider = ModelProvider(provider_str)
        except ValueError:
            provider = self.DEFAULT_CONFIG['provider']
        
        # 获取模型名称
        model_name = os.getenv('MODEL_NAME', self.DEFAULT_CONFIG['model_name'])
        
        # 获取API密钥 - 根据提供商选择不同的环境变量
        api_key = self._get_api_key_by_provider(provider)
        
        # 获取其他配置
        base_url = os.getenv('MODEL_BASE_URL', self.DEFAULT_CONFIG['base_url'])
        temperature = float(os.getenv('MODEL_TEMPERATURE', str(self.DEFAULT_CONFIG['temperature'])))
        max_tokens = os.getenv('MODEL_MAX_TOKENS')
        if max_tokens:
            max_tokens = int(max_tokens)
        timeout = int(os.getenv('MODEL_TIMEOUT', str(self.DEFAULT_CONFIG['timeout'])))
        
        return ModelConfig(
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        )
    
    def _get_api_key_by_provider(self, provider: ModelProvider) -> str:
        """根据提供商获取对应的API密钥"""
        key_mapping = {
            ModelProvider.GEMINI: 'GOOGLE_API_KEY',
            ModelProvider.OPENAI: 'OPENAI_API_KEY', 
            ModelProvider.CLAUDE: 'ANTHROPIC_API_KEY',
            ModelProvider.QWEN: 'DASHSCOPE_API_KEY',
            ModelProvider.GLM: 'GLM_API_KEY'
        }
        
        env_key = key_mapping.get(provider, 'GOOGLE_API_KEY')
        return os.getenv(env_key, self.DEFAULT_CONFIG['api_key'])
    
    def get_current_config(self) -> ModelConfig:
        """获取当前模型配置"""
        return self._current_config
    
    def update_config(self, **kwargs) -> bool:
        """更新模型配置"""
        try:
            # 更新配置参数
            if 'provider' in kwargs:
                if isinstance(kwargs['provider'], str):
                    kwargs['provider'] = ModelProvider(kwargs['provider'])
            
            # 创建新配置
            current_dict = self._current_config.to_dict()
            current_dict.update(kwargs)
            
            # 验证配置
            self._current_config = ModelConfig(
                provider=current_dict['provider'] if isinstance(current_dict['provider'], ModelProvider) else ModelProvider(current_dict['provider']),
                model_name=current_dict['model_name'],
                api_key=current_dict['api_key'],
                base_url=current_dict.get('base_url'),
                temperature=current_dict['temperature'],
                max_tokens=current_dict.get('max_tokens'),
                timeout=current_dict['timeout']
            )
            
            return True
        except Exception as e:
            print(f"更新模型配置失败: {e}")
            return False
    
    def switch_to_template(self, provider: ModelProvider, model_name: str) -> bool:
        """切换到预定义的模型配置模板"""
        try:
            if provider not in self.MODEL_TEMPLATES:
                raise ValueError(f"不支持的提供商: {provider}")
            
            if model_name not in self.MODEL_TEMPLATES[provider]:
                raise ValueError(f"提供商 {provider.value} 不支持模型: {model_name}")
            
            template = self.MODEL_TEMPLATES[provider][model_name].copy()
            template['api_key'] = self._get_api_key_by_provider(provider)
            
            self._current_config = ModelConfig(**template)
            return True
            
        except Exception as e:
            print(f"切换模型配置失败: {e}")
            return False
    
    def get_langchain_config(self) -> Dict[str, Any]:
        """获取适用于LangChain的配置"""
        config = self._current_config
        
        if config.provider == ModelProvider.GEMINI:
            return {
                "model": config.model_name,
                "google_api_key": config.api_key,
                "temperature": config.temperature,
                "convert_system_message_to_human": False
            }
        elif config.provider == ModelProvider.OPENAI:
            langchain_config = {
                "model": config.model_name,
                "openai_api_key": config.api_key,
                "temperature": config.temperature
            }
            if config.base_url:
                langchain_config["base_url"] = config.base_url
            if config.max_tokens:
                langchain_config["max_tokens"] = config.max_tokens
            return langchain_config
        else:
            # 其他提供商的配置
            langchain_config = {
                "model": config.model_name,
                "api_key": config.api_key,
                "temperature": config.temperature
            }
            if config.base_url:
                langchain_config["base_url"] = config.base_url
            if config.max_tokens:
                langchain_config["max_tokens"] = config.max_tokens
            return langchain_config
    
    def get_genai_config(self) -> Dict[str, Any]:
        """获取适用于google.generativeai的配置"""
        if self._current_config.provider != ModelProvider.GEMINI:
            raise ValueError("genai配置仅适用于Gemini模型")
        
        return {
            "api_key": self._current_config.api_key,
            "model_name": self._current_config.model_name
        }
    
    def get_provider_info(self) -> Dict[str, Any]:
        """获取当前提供商信息"""
        config = self._current_config
        return {
            "provider": config.provider.value,
            "model_name": config.model_name,
            "has_api_key": bool(config.api_key),
            "base_url": config.base_url,
            "temperature": config.temperature,
            "timeout": config.timeout
        }

# 全局单例实例
model_manager = UnifiedModelManager()

def get_model_config() -> ModelConfig:
    """获取当前模型配置的全局函数"""
    return model_manager.get_current_config()

def get_langchain_llm():
    """获取配置好的LangChain LLM实例"""
    config = model_manager.get_current_config()
    
    if config.provider == ModelProvider.GEMINI:
        from langchain_google_genai import ChatGoogleGenerativeAI
        langchain_config = model_manager.get_langchain_config()
        return ChatGoogleGenerativeAI(**langchain_config)
    elif config.provider == ModelProvider.OPENAI:
        from langchain_openai import ChatOpenAI
        langchain_config = model_manager.get_langchain_config()
        return ChatOpenAI(**langchain_config)
    else:
        raise ValueError(f"暂不支持的LangChain提供商: {config.provider.value}")

def get_genai_model():
    """获取配置好的google.generativeai模型实例"""
    import google.generativeai as genai
    
    config = model_manager.get_current_config()
    if config.provider != ModelProvider.GEMINI:
        raise ValueError("genai模型仅支持Gemini提供商")
    
    genai.configure(api_key=config.api_key)
    return genai.GenerativeModel(config.model_name)

def update_model_config(**kwargs) -> bool:
    """更新全局模型配置"""
    return model_manager.update_config(**kwargs)

def switch_model(provider: str, model_name: str) -> bool:
    """切换模型配置"""
    try:
        provider_enum = ModelProvider(provider)
        return model_manager.switch_to_template(provider_enum, model_name)
    except ValueError as e:
        print(f"切换模型失败: {e}")
        return False

# 环境变量设置函数
def setup_environment():
    """设置环境变量"""
    config = model_manager.get_current_config()
    
    # 根据提供商设置对应的环境变量
    if config.provider == ModelProvider.GEMINI:
        os.environ["GOOGLE_API_KEY"] = config.api_key
    elif config.provider == ModelProvider.OPENAI:
        os.environ["OPENAI_API_KEY"] = config.api_key
    elif config.provider == ModelProvider.CLAUDE:
        os.environ["ANTHROPIC_API_KEY"] = config.api_key
    elif config.provider == ModelProvider.QWEN:
        os.environ["DASHSCOPE_API_KEY"] = config.api_key
    elif config.provider == ModelProvider.GLM:
        os.environ["GLM_API_KEY"] = config.api_key

# 初始化时设置环境变量
setup_environment() 