# config.py
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv
import json

@dataclass
class Config:
    OPENROUTER_API_KEY: str
    SITE_URL: Optional[str]
    APP_NAME: Optional[str]
    MODEL: str = "anthropic/claude-3.5-sonnet"
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0

def load_config(config_source: str = "env") -> Config:
    """從指定來源加載配置
    
    Args:
        config_source (str): 配置來源，可以是 "env" 或 "json"
    
    Returns:
        Config: 配置對象
    """
    if config_source == "env":
        # 嘗試加載.env文件
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        load_dotenv(env_path)
        
        # 如果找不到API金鑰，提供指引
        api_key = os.getenv('OPENROUTER_API_KEY')
        if not api_key:
            print("未找到 OPENROUTER_API_KEY，請選擇設置方式：")
            print("1. 直接輸入API金鑰")
            print("2. 創建.env文件")
            choice = input("請選擇 (1/2): ")
            
            if choice == "1":
                api_key = input("請輸入你的 OPENROUTER_API_KEY: ")
                # 可以選擇是否保存到.env文件
                save = input("是否保存到.env文件？(y/n): ")
                if save.lower() == 'y':
                    with open(env_path, 'w', encoding='utf-8') as f:
                        f.write(f"OPENROUTER_API_KEY={api_key}\n")
                        f.write(f"SITE_URL=http://localhost:3000\n")
                        f.write(f"APP_NAME=ThinkingChain\n")
            else:
                print("\n請創建.env文件，內容如下：")
                print("OPENROUTER_API_KEY=your_api_key_here")
                print("SITE_URL=http://localhost:3000")
                print("APP_NAME=ThinkingChain")
                raise ValueError("請設置配置後重試")
        
        return Config(
            OPENROUTER_API_KEY=api_key,
            SITE_URL=os.getenv('SITE_URL', 'http://localhost:3000'),
            APP_NAME=os.getenv('APP_NAME', 'ThinkingChain'),
        )
    
    elif config_source == "json":
        # 從 config.json 加載配置
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                return Config(**config_data)
        except FileNotFoundError:
            print("未找到 config.json，將創建範例文件")
            example_config = {
                "OPENROUTER_API_KEY": "your_api_key_here",
                "SITE_URL": "http://localhost:3000",
                "APP_NAME": "ThinkingChain"
            }
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(example_config, f, indent=2)
            raise ValueError("請在 config.json 中設置配置後重試")
    
    else:
        raise ValueError("不支援的配置來源")

# 使用示例
if __name__ == "__main__":
    try:
        # 可以選擇從env或json加載配置
        config = load_config("env")  # 或 load_config("json")
        print("配置加載成功:")
        print(f"Model: {config.MODEL}")
        print(f"Max retries: {config.MAX_RETRIES}")
        print(f"Site URL: {config.SITE_URL}")
        print(f"App name: {config.APP_NAME}")
    except ValueError as e:
        print(f"配置加載失敗: {e}")