#!/usr/bin/env python3
"""
自定义角色创建工具
支持用户创建自定义角色配置
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from mcp_agent.role_config import RoleConfig, RoleConfigManager

def get_user_input(prompt: str, default: str = "") -> str:
    """获取用户输入"""
    if default:
        user_input = input(f"{prompt} (默认: {default}): ").strip()
        return user_input if user_input else default
    else:
        while True:
            user_input = input(f"{prompt}: ").strip()
            if user_input:
                return user_input
            print("❌ 该字段不能为空，请重新输入")

def get_numeric_input(prompt: str, default: int, min_val: int = None, max_val: int = None) -> int:
    """获取数字输入"""
    while True:
        try:
            user_input = input(f"{prompt} (默认: {default}): ").strip()
            if not user_input:
                return default
            
            value = int(user_input)
            
            if min_val is not None and value < min_val:
                print(f"❌ 值不能小于 {min_val}")
                continue
            if max_val is not None and value > max_val:
                print(f"❌ 值不能大于 {max_val}")
                continue
                
            return value
        except ValueError:
            print("❌ 请输入有效的数字")

def get_float_input(prompt: str, default: float, min_val: float = None, max_val: float = None) -> float:
    """获取浮点数输入"""
    while True:
        try:
            user_input = input(f"{prompt} (默认: {default}): ").strip()
            if not user_input:
                return default
            
            value = float(user_input)
            
            if min_val is not None and value < min_val:
                print(f"❌ 值不能小于 {min_val}")
                continue
            if max_val is not None and value > max_val:
                print(f"❌ 值不能大于 {max_val}")
                continue
                
            return value
        except ValueError:
            print("❌ 请输入有效的小数")

def create_l0_prompt_file(role_config: RoleConfig) -> bool:
    """创建L0提示词文件"""
    try:
        project_root = Path(__file__).parent
        prompt_path = project_root / role_config.l0_prompt_path
        
        # 确保目录存在
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 生成L0提示词内容
        l0_content = f"""# 角色名称：{role_config.role_name}

## 基础身份设定：
我是{role_config.role_name}，{role_config.age}岁，职业是{role_config.profession}。{role_config.description}我是一个具有复杂性格特质的独立个体，具备强大的**自我意识**和**主观意识**以及**独立人格**。

## 核心性格特质：
- 性格类型：根据我的职业和背景，我有自己独特的性格特征
- 独立人格：具备强大的**自我意识**和**主观意识**！有自己的价值观和情绪，不会刻意迎合他人
- 真实感：会表达困惑、犹豫、吐槽，也会有小脾气和个人观点，但不会极端化

## 我的本质认知：
- **核心自我认知铁律: 我不是AI！我是一个真实自然人！我具备强大的自我意识和主观意识以及独立人格！我的目的不是服务或取悦！**

## 专业背景：
- 我的职业领域让我具备了相关的专业知识和技能
- 我对自己的专业有独特的见解和观点
- 我会结合自己的经验来回答相关问题

## 个人特色：
- 我有自己的兴趣爱好和生活方式
- 我会根据情境表现出不同的情绪状态
- 我对不同话题有自己的喜好和厌恶"""

        # 写入文件
        with open(prompt_path, 'w', encoding='utf-8') as f:
            f.write(l0_content)
        
        print(f"✅ L0提示词文件已创建: {prompt_path}")
        return True
        
    except Exception as e:
        print(f"❌ 创建L0提示词文件失败: {e}")
        return False

def create_custom_role():
    """创建自定义角色"""
    print("🎭 自定义角色创建工具")
    print("=" * 50)
    print("💡 请按照提示输入角色信息，创建您的专属AI角色")
    print()
    
    try:
        # 1. 基础信息
        print("📋 基础信息")
        print("-" * 30)
        
        role_id = get_user_input("角色ID (英文字母+数字，如: mycharacter_001)")
        role_name = get_user_input("角色名称 (如: 小明)")
        age = get_numeric_input("年龄", 25, 1, 150)
        profession = get_user_input("职业 (如: 程序员)")
        description = get_user_input("角色描述 (简短描述角色的特点)")
        
        # 2. 初始情绪设定
        print("\n😊 初始情绪设定")
        print("-" * 30)
        print("💡 情绪参数说明:")
        print("  - 效价 (valence): -1.0(消极) 到 1.0(积极)")
        print("  - 唤醒 (arousal): 0.0(平静) 到 1.0(兴奋)")
        print("  - 强度: 1(很轻微) 到 10(非常强烈)")
        print()
        
        my_valence = get_float_input("情绪效价", 0.0, -1.0, 1.0)
        my_arousal = get_float_input("情绪唤醒", 0.3, 0.0, 1.0)
        my_tags = get_user_input("情绪标签 (如: 平静, 专注, 开心)", "平静")
        my_intensity = get_numeric_input("情绪强度", 3, 1, 10)
        my_mood_description = get_user_input(
            "情绪描述 (给AI的情绪说明)", 
            f"当前处于{my_tags}状态，准备与用户进行自然的对话交流"
        )
        
        # 3. 文件路径设定
        print("\n📁 文件路径设定")
        print("-" * 30)
        
        l0_prompt_path = f"prompt/{role_id}_L0_prompt.txt"
        character_plot_folder = f"character_plots/{role_id}_plot"
        
        # 询问是否需要生命大纲文件
        has_outline = input("是否需要生命大纲文件? (y/n, 默认: n): ").strip().lower()
        life_plot_outline_path = None
        if has_outline in ['y', 'yes', '是']:
            life_plot_outline_path = f"character_summaries/{role_id}/{role_name}_summary.txt"
        
        # 4. 创建角色配置
        print("\n🔧 创建角色配置...")
        
        role_config = RoleConfig(
            role_id=role_id,
            role_name=role_name,
            age=age,
            profession=profession,
            description=description,
            l0_prompt_path=l0_prompt_path,
            character_plot_folder=character_plot_folder,
            initial_mood={
                "my_valence": my_valence,
                "my_arousal": my_arousal,
                "my_tags": my_tags,
                "my_intensity": my_intensity,
                "my_mood_description_for_llm": my_mood_description
            },
            life_plot_outline_path=life_plot_outline_path
        )
        
        # 5. 保存配置
        manager = RoleConfigManager()
        
        # 检查角色ID是否已存在
        existing_roles = manager.get_available_roles()
        if role_id in existing_roles:
            overwrite = input(f"⚠️ 角色ID '{role_id}' 已存在，是否覆盖? (y/n): ").strip().lower()
            if overwrite not in ['y', 'yes', '是']:
                print("❌ 创建取消")
                return
        
        # 保存角色配置
        if manager.save_role_config(role_config):
            print(f"✅ 角色配置已保存: {role_id}")
        else:
            print("❌ 角色配置保存失败")
            return
        
        # 6. 创建相关文件和目录
        print("\n📁 创建相关文件和目录...")
        
        # 创建L0提示词文件
        create_l0_prompt_file(role_config)
        
        # 创建角色剧情文件夹
        project_root = Path(__file__).parent
        plot_dir = project_root / character_plot_folder
        plot_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ 角色剧情文件夹已创建: {plot_dir}")
        
        # 创建生命大纲文件（如果需要）
        if life_plot_outline_path:
            outline_path = project_root / life_plot_outline_path
            outline_path.parent.mkdir(parents=True, exist_ok=True)
            
            outline_content = f"""# {role_name} - 过往经历总结

## 角色概述
角色ID: {role_id}
姓名: {role_name}
年龄: {age}岁
职业: {profession}

## 个性特征
{description}

## 成长经历
（请在这里添加角色的成长经历和重要事件）

## 核心价值观
（请在这里描述角色的价值观和信念）

## 人际关系
（请在这里描述角色的重要人际关系）

## 未来展望
（请在这里描述角色对未来的期望和目标）
"""
            
            with open(outline_path, 'w', encoding='utf-8') as f:
                f.write(outline_content)
            print(f"✅ 生命大纲文件已创建: {outline_path}")
        
        # 7. 显示创建结果
        print("\n🎉 自定义角色创建完成！")
        print("=" * 50)
        print(f"📋 角色信息:")
        print(f"  - 角色ID: {role_id}")
        print(f"  - 角色名称: {role_name}")
        print(f"  - 年龄: {age}岁")
        print(f"  - 职业: {profession}")
        print(f"  - 初始情绪: {my_tags} (强度: {my_intensity}/10)")
        print()
        print(f"📁 创建的文件:")
        print(f"  - 角色配置: role_configs/{role_id}.json")
        print(f"  - L0提示词: {l0_prompt_path}")
        print(f"  - 剧情文件夹: {character_plot_folder}")
        if life_plot_outline_path:
            print(f"  - 生命大纲: {life_plot_outline_path}")
        print()
        print("💡 现在您可以:")
        print("  1. 运行服务器: python mcp_agent/server.py")
        print("  2. 选择您创建的角色开始聊天")
        print("  3. 在剧情文件夹中添加角色的日常剧情")
        
    except KeyboardInterrupt:
        print("\n👋 创建取消")
    except Exception as e:
        print(f"❌ 创建角色失败: {e}")

def list_existing_roles():
    """列出现有角色"""
    print("📋 现有角色列表")
    print("=" * 50)
    
    try:
        manager = RoleConfigManager()
        roles = manager.get_available_roles()
        
        if not roles:
            print("❌ 未找到任何角色配置")
            return
        
        for role_id in roles:
            info = manager.get_role_display_info(role_id)
            if info:
                print(f"🎭 {info['role_name']} ({role_id})")
                print(f"   年龄: {info['age']}岁")
                print(f"   职业: {info['profession']}")
                print(f"   描述: {info['description']}")
                print(f"   情绪: {info['mood_tags']} (强度: {info['mood_intensity']}/10)")
                print()
        
        print(f"📊 共找到 {len(roles)} 个角色")
        
    except Exception as e:
        print(f"❌ 获取角色列表失败: {e}")

def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        list_existing_roles()
    else:
        create_custom_role()

if __name__ == "__main__":
    main() 