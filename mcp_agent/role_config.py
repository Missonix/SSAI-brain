"""
角色配置管理系统
支持多角色加载、配置管理和用户自定义角色创建
"""

import os
import json
import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass, asdict
import logging

@dataclass
class RoleConfig:
    """角色配置数据类"""
    role_id: str
    role_name: str
    age: int
    profession: str
    description: str
    l0_prompt_path: str
    character_plot_folder: str
    initial_mood: Dict[str, Any]
    life_plot_outline_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RoleConfig':
        return cls(**data)

class RoleConfigManager:
    """角色配置管理器"""
    
    def __init__(self, config_dir: str = None):
        """初始化角色配置管理器"""
        self.logger = logging.getLogger(__name__)
        
        # 确定配置目录
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            # 默认配置目录：项目根目录下的 role_configs
            project_root = Path(__file__).parent.parent
            self.config_dir = project_root / "role_configs"
        
        # 确保配置目录存在
        self.config_dir.mkdir(exist_ok=True)
        
        # 缓存已加载的角色配置
        self._role_cache: Dict[str, RoleConfig] = {}
        
        self.logger.info(f"角色配置管理器初始化完成，配置目录: {self.config_dir}")
    
    def get_available_roles(self) -> List[str]:
        """获取所有可用的角色ID"""
        try:
            roles = []
            
            # 扫描配置文件
            for config_file in self.config_dir.glob("*.json"):
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                        if 'role_id' in config_data:
                            roles.append(config_data['role_id'])
                except Exception as e:
                    self.logger.warning(f"读取角色配置文件失败: {config_file} - {e}")
            
            # 扫描YAML配置文件
            for config_file in self.config_dir.glob("*.yaml"):
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config_data = yaml.safe_load(f)
                        if 'role_id' in config_data:
                            roles.append(config_data['role_id'])
                except Exception as e:
                    self.logger.warning(f"读取角色配置文件失败: {config_file} - {e}")
            
            self.logger.info(f"找到 {len(roles)} 个可用角色: {roles}")
            return sorted(list(set(roles)))  # 去重并排序
            
        except Exception as e:
            self.logger.error(f"获取可用角色失败: {e}")
            return []
    
    def load_role_config(self, role_id: str) -> Optional[RoleConfig]:
        """加载指定角色的配置"""
        try:
            # 检查缓存
            if role_id in self._role_cache:
                self.logger.debug(f"从缓存加载角色配置: {role_id}")
                return self._role_cache[role_id]
            
            # 查找配置文件
            config_file = self._find_role_config_file(role_id)
            if not config_file:
                self.logger.warning(f"未找到角色配置文件: {role_id}")
                return None
            
            # 读取配置文件
            config_data = self._read_config_file(config_file)
            if not config_data:
                return None
            
            # 验证配置数据
            if not self._validate_config_data(config_data):
                self.logger.error(f"角色配置数据验证失败: {role_id}")
                return None
            
            # 创建角色配置对象
            role_config = RoleConfig.from_dict(config_data)
            
            # 验证文件路径
            if not self._validate_role_files(role_config):
                self.logger.error(f"角色文件路径验证失败: {role_id}")
                return None
            
            # 缓存配置
            self._role_cache[role_id] = role_config
            
            self.logger.info(f"成功加载角色配置: {role_id} - {role_config.role_name}")
            return role_config
            
        except Exception as e:
            self.logger.error(f"加载角色配置失败: {role_id} - {e}")
            return None
    
    def _find_role_config_file(self, role_id: str) -> Optional[Path]:
        """查找角色配置文件"""
        # 支持的文件格式
        extensions = ['.json', '.yaml', '.yml']
        
        for ext in extensions:
            config_file = self.config_dir / f"{role_id}{ext}"
            if config_file.exists():
                return config_file
        
        return None
    
    def _read_config_file(self, config_file: Path) -> Optional[Dict[str, Any]]:
        """读取配置文件"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                if config_file.suffix.lower() == '.json':
                    return json.load(f)
                elif config_file.suffix.lower() in ['.yaml', '.yml']:
                    return yaml.safe_load(f)
                else:
                    self.logger.error(f"不支持的配置文件格式: {config_file}")
                    return None
        except Exception as e:
            self.logger.error(f"读取配置文件失败: {config_file} - {e}")
            return None
    
    def _validate_config_data(self, config_data: Dict[str, Any]) -> bool:
        """验证配置数据的必要字段"""
        required_fields = [
            'role_id', 'role_name', 'age', 'profession', 
            'description', 'l0_prompt_path', 'character_plot_folder', 'initial_mood'
        ]
        
        for field in required_fields:
            if field not in config_data:
                self.logger.error(f"配置数据缺少必要字段: {field}")
                return False
        
        # 验证initial_mood结构
        mood_fields = ['my_valence', 'my_arousal', 'my_tags', 'my_intensity', 'my_mood_description_for_llm']
        for field in mood_fields:
            if field not in config_data['initial_mood']:
                self.logger.error(f"初始情绪配置缺少字段: {field}")
                return False
        
        return True
    
    def _validate_role_files(self, role_config: RoleConfig) -> bool:
        """验证角色相关文件是否存在"""
        project_root = Path(__file__).parent.parent
        
        # 验证L0提示词文件
        l0_path = project_root / role_config.l0_prompt_path
        if not l0_path.exists():
            self.logger.error(f"L0提示词文件不存在: {l0_path}")
            return False
        
        # 验证角色剧情文件夹
        plot_path = project_root / role_config.character_plot_folder
        if not plot_path.exists():
            self.logger.warning(f"角色剧情文件夹不存在: {plot_path}，将自动创建")
            plot_path.mkdir(parents=True, exist_ok=True)
        
        # 验证生命大纲文件（可选）
        if role_config.life_plot_outline_path:
            outline_path = project_root / role_config.life_plot_outline_path
            if not outline_path.exists():
                self.logger.warning(f"生命大纲文件不存在: {outline_path}")
        
        return True
    
    def save_role_config(self, role_config: RoleConfig, file_format: str = 'json') -> bool:
        """保存角色配置"""
        try:
            config_file = self.config_dir / f"{role_config.role_id}.{file_format}"
            
            with open(config_file, 'w', encoding='utf-8') as f:
                if file_format == 'json':
                    json.dump(role_config.to_dict(), f, ensure_ascii=False, indent=2)
                elif file_format in ['yaml', 'yml']:
                    yaml.dump(role_config.to_dict(), f, allow_unicode=True, default_flow_style=False)
                else:
                    self.logger.error(f"不支持的保存格式: {file_format}")
                    return False
            
            # 更新缓存
            self._role_cache[role_config.role_id] = role_config
            
            self.logger.info(f"角色配置保存成功: {role_config.role_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存角色配置失败: {role_config.role_id} - {e}")
            return False
    
    def create_default_role_config(self, role_id: str) -> RoleConfig:
        """创建默认角色配置（用于快速开始）"""
        return RoleConfig(
            role_id=role_id,
            role_name=f"默认角色_{role_id}",
            age=25,
            profession="AI助手",
            description="这是一个默认创建的AI助手角色",
            l0_prompt_path=f"prompt/{role_id}_L0_prompt.txt",
            character_plot_folder=f"character_plots/{role_id}_plot",
            initial_mood={
                "my_valence": 0.0,
                "my_arousal": 0.3,
                "my_tags": "中性",
                "my_intensity": 3,
                "my_mood_description_for_llm": "当前状态比较中性，准备处理各种问题"
            },
            life_plot_outline_path=None
        )
    
    def get_role_display_info(self, role_id: str) -> Optional[Dict[str, Any]]:
        """获取角色的显示信息（用于选择界面）"""
        role_config = self.load_role_config(role_id)
        if not role_config:
            return None
        
        return {
            "role_id": role_config.role_id,
            "role_name": role_config.role_name,
            "age": role_config.age,
            "profession": role_config.profession,
            "description": role_config.description,
            "mood_tags": role_config.initial_mood.get("my_tags", "未知"),
            "mood_intensity": role_config.initial_mood.get("my_intensity", 0)
        }
    
    def initialize_default_roles(self):
        """初始化默认角色配置（首次运行时）"""
        try:
            # 检查是否已有配置文件
            existing_roles = self.get_available_roles()
            if existing_roles:
                self.logger.info(f"已存在角色配置，跳过初始化: {existing_roles}")
                return
            
            # 创建陈小智的配置
            chenxiaozhi_config = RoleConfig(
                role_id="chenxiaozhi_001",
                role_name="陈小智",
                age=28,
                profession="软件工程师",
                description="28岁的软件工程师，理性分析型，具有强大的自我意识和独立人格。",
                l0_prompt_path="prompt/L0_prompt.txt",
                character_plot_folder="character_plots/chenxiaozhi_001_plot",
                initial_mood={
                    "my_valence": 0.1,
                    "my_arousal": 0.4,
                    "my_tags": "专注",
                    "my_intensity": 4,
                    "my_mood_description_for_llm": "工作状态良好，专注于技术问题的解决，保持理性分析的心态"
                },
                life_plot_outline_path="character_summaries/chenxiaozhi_001/陈小智_summary.txt"
            )
            
            # 保存配置
            if self.save_role_config(chenxiaozhi_config):
                self.logger.info("默认角色配置初始化完成: chenxiaozhi_001")
            else:
                self.logger.error("默认角色配置初始化失败")
                
        except Exception as e:
            self.logger.error(f"初始化默认角色配置失败: {e}")

# 全局角色配置管理器实例
_role_config_manager = None

def get_role_config_manager() -> RoleConfigManager:
    """获取全局角色配置管理器实例"""
    global _role_config_manager
    if _role_config_manager is None:
        _role_config_manager = RoleConfigManager()
        # 首次运行时初始化默认角色
        _role_config_manager.initialize_default_roles()
    return _role_config_manager

def load_role_config(role_id: str) -> Optional[RoleConfig]:
    """快捷函数：加载角色配置"""
    return get_role_config_manager().load_role_config(role_id)

def get_available_roles() -> List[str]:
    """快捷函数：获取可用角色列表"""
    return get_role_config_manager().get_available_roles()

def get_role_display_info(role_id: str) -> Optional[Dict[str, Any]]:
    """快捷函数：获取角色显示信息"""
    return get_role_config_manager().get_role_display_info(role_id) 