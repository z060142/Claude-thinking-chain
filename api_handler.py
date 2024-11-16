# api_handler.py
import os
import requests
import json
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional, Union
from dataclasses import dataclass

# 創建logs目錄（如果不存在）
logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(logs_dir, exist_ok=True)

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(logs_dir, 'api.log')),
        logging.StreamHandler()
    ]
)

@dataclass
class TokenUsage:
    """Token使用記錄"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    timestamp: datetime

class TokenTracker:
    """Token使用追蹤器"""
    def __init__(self):
        self.history: List[TokenUsage] = []
    
    def add_usage(self, usage: TokenUsage):
        self.history.append(usage)
        logging.info(f"Token usage recorded: {usage.total_tokens} tokens")
    
    def get_total_usage(self) -> Dict[str, int]:
        return {
            "prompt_tokens": sum(usage.prompt_tokens for usage in self.history),
            "completion_tokens": sum(usage.completion_tokens for usage in self.history),
            "total_tokens": sum(usage.total_tokens for usage in self.history)
        }
    
    def estimate_cost(self, input_cost_per_1k: float = 0.0015, output_cost_per_1k: float = 0.015) -> float:
        usage = self.get_total_usage()
        input_cost = (usage["prompt_tokens"] / 1000) * input_cost_per_1k
        output_cost = (usage["completion_tokens"] / 1000) * output_cost_per_1k
        return input_cost + output_cost

class APIError(Exception):
    """API錯誤基類"""
    pass

class RateLimitError(APIError):
    """速率限制錯誤"""
    pass

class AuthenticationError(APIError):
    """認證錯誤"""
    pass

class APIHandler:
    """API處理器"""
    def __init__(self, config):
        self.config = config
        self.token_tracker = TokenTracker()
        self.session = requests.Session()
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 最小請求間隔(秒)
        
    def _build_headers(self) -> Dict[str, str]:
        """構建請求標頭"""
        headers = {
            "Authorization": f"Bearer {self.config.OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        
        if self.config.SITE_URL:
            headers["HTTP-Referer"] = self.config.SITE_URL
        if self.config.APP_NAME:
            headers["X-Title"] = self.config.APP_NAME
            
        return headers
    
    def _build_messages(self, prompt: str) -> List[Dict]:
        """構建消息體"""
        return [
            {
                "role": "user",
                "content": prompt
            }
        ]
    
    def _handle_error_response(self, response: requests.Response):
        """處理錯誤響應"""
        status_code = response.status_code
        error_detail = response.text
        
        if status_code == 429:
            raise RateLimitError("API請求超過速率限制")
        elif status_code == 401:
            raise AuthenticationError("API認證失敗")
        elif status_code == 400:
            raise APIError(f"無效的請求: {error_detail}")
        else:
            raise APIError(f"API請求失敗 ({status_code}): {error_detail}")
    
    def _handle_response(self, response: requests.Response) -> Dict:
        """處理API響應"""
        if response.status_code == 200:
            data = response.json()
            
            # 提取並記錄token使用情況
            usage = data.get('usage', {})
            token_usage = TokenUsage(
                prompt_tokens=usage.get('prompt_tokens', 0),
                completion_tokens=usage.get('completion_tokens', 0),
                total_tokens=usage.get('total_tokens', 0),
                timestamp=datetime.now()
            )
            self.token_tracker.add_usage(token_usage)
            
            # 提取回應內容
            response_content = self._extract_response_content(data)
            return {
                'content': response_content,
                'usage': usage,
                'raw_response': data
            }
        else:
            self._handle_error_response(response)
    
    def _extract_response_content(self, response_data: Dict) -> str:
        """從回應數據中提取內容"""
        try:
            # 適配OpenRouter的響應格式
            choices = response_data.get('choices', [])
            if choices:
                message = choices[0].get('message', {})
                return message.get('content', '')
            return ''
        except Exception as e:
            logging.error(f"提取響應內容時出錯: {e}")
            return ''
    
    def _wait_for_rate_limit(self):
        """等待以遵守速率限制"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last_request
            time.sleep(wait_time)
        self.last_request_time = time.time()
    
    def send_prompt(self, prompt: str, retry_count: int = 0) -> Dict:
        """發送prompt到API"""
        try:
            self._wait_for_rate_limit()
            
            logging.info(f"Sending prompt (attempt {retry_count + 1}/{self.config.MAX_RETRIES})")
            response = self.session.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers=self._build_headers(),
                data=json.dumps({
                    "model": self.config.MODEL,
                    "messages": self._build_messages(prompt)
                })
            )
            return self._handle_response(response)
            
        except (RateLimitError, APIError) as e:
            logging.error(f"API error: {str(e)}")
            if retry_count < self.config.MAX_RETRIES:
                wait_time = self.config.RETRY_DELAY * (2 ** retry_count)  # 指數退避
                logging.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                return self.send_prompt(prompt, retry_count + 1)
            else:
                logging.error(f"Max retries reached. Giving up.")
                raise
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            raise
    
    def get_usage_report(self) -> Dict:
        """獲取使用量報告"""
        usage = self.token_tracker.get_total_usage()
        cost = self.token_tracker.estimate_cost()
        return {
            "usage": usage,
            "estimated_cost": cost,
            "request_count": len(self.token_tracker.history),
            "latest_request": self.token_tracker.history[-1].timestamp if self.token_tracker.history else None
        }

# 使用示例
if __name__ == "__main__":
    from config import load_config
    
    try:
        config = load_config()
        api_handler = APIHandler(config)
        
        # 測試API調用
        response = api_handler.send_prompt("Hello, how are you?")
        print("\nAPI Response:")
        print(f"Content: {response['content']}")
        
        # 顯示使用量報告
        usage_report = api_handler.get_usage_report()
        print("\nUsage Report:")
        print(f"Total tokens: {usage_report['usage']['total_tokens']}")
        print(f"Estimated cost: ${usage_report['estimated_cost']:.4f}")
        
    except Exception as e:
        logging.error(f"Error in main: {str(e)}")