"""
模型配置使用示例
展示如何使用统一的模型配置管理器
"""

from model_config import (
    get_model_config, 
    get_langchain_llm, 
    get_genai_model,
    update_model_config,
    switch_model,
    ModelProvider
)

def example_usage():
    """使用示例"""
    
    print("=== 统一模型配置管理器使用示例 ===\n")
    
    # 1. 获取当前配置
    print("1. 获取当前模型配置:")
    config = get_model_config()
    print(f"   提供商: {config.provider.value}")
    print(f"   模型名称: {config.model_name}")
    print(f"   API密钥: {config.api_key[:10]}...")
    print(f"   温度: {config.temperature}")
    print()
    
    # 2. 获取LangChain LLM实例
    print("2. 获取LangChain LLM实例:")
    try:
        llm = get_langchain_llm()
        print(f"   ✅ 成功创建LangChain LLM: {type(llm).__name__}")
    except Exception as e:
        print(f"   ❌ 创建LangChain LLM失败: {e}")
    print()
    
    # 3. 获取Google GenerativeAI模型实例
    print("3. 获取Google GenerativeAI模型实例:")
    try:
        model = get_genai_model()
        print(f"   ✅ 成功创建GenAI模型: {type(model).__name__}")
    except Exception as e:
        print(f"   ❌ 创建GenAI模型失败: {e}")
    print()
    
    # 4. 更新配置
    print("4. 更新模型配置:")
    success = update_model_config(temperature=0.5)
    if success:
        updated_config = get_model_config()
        print(f"   ✅ 温度已更新为: {updated_config.temperature}")
    else:
        print("   ❌ 配置更新失败")
    print()
    
    # 5. 切换模型（示例 - 如果有其他模型配置）
    print("5. 模型切换示例:")
    print("   可用的模型切换:")
    print("   - switch_model('gemini', 'gemini-1.5-pro')")
    print("   - switch_model('openai', 'gpt-4')")
    print("   - switch_model('qwen', 'qwen-turbo')")
    print()
    
    # 6. 环境变量配置说明
    print("6. 环境变量配置说明:")
    print("   可以通过以下环境变量覆盖默认配置:")
    print("   - MODEL_PROVIDER: 模型提供商 (gemini/openai/claude/qwen/glm)")
    print("   - MODEL_NAME: 模型名称")
    print("   - GOOGLE_API_KEY: Google API密钥")
    print("   - OPENAI_API_KEY: OpenAI API密钥")
    print("   - MODEL_TEMPERATURE: 温度参数")
    print("   - MODEL_MAX_TOKENS: 最大token数")
    print()

def switch_to_openai_example():
    """切换到OpenAI的示例"""
    print("=== 切换到OpenAI模型示例 ===\n")
    
    # 注意：需要设置OPENAI_API_KEY环境变量
    success = switch_model("openai", "gpt-4")
    if success:
        config = get_model_config()
        print(f"✅ 已切换到OpenAI模型:")
        print(f"   提供商: {config.provider.value}")
        print(f"   模型: {config.model_name}")
        print(f"   Base URL: {config.base_url}")
    else:
        print("❌ 切换失败，请检查API密钥配置")

def switch_back_to_gemini():
    """切换回Gemini模型"""
    print("=== 切换回Gemini模型 ===\n")
    
    success = switch_model("gemini", "gemini-2.0-flash-exp")
    if success:
        config = get_model_config()
        print(f"✅ 已切换回Gemini模型:")
        print(f"   提供商: {config.provider.value}")
        print(f"   模型: {config.model_name}")
    else:
        print("❌ 切换失败")

if __name__ == "__main__":
    example_usage()
    
    # 如果需要测试模型切换，取消注释以下行
    # switch_to_openai_example()
    # switch_back_to_gemini() 