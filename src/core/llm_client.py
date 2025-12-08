import requests
import json
from src.utils.logger import log_debug

API_URL = "https://api.deepseek.com/chat/completions"

import time

class DeepSeekClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

    def chat(self, messages, model="deepseek-chat", temperature=0.7, retries=3, timeout=90):
        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False
        }
        
        # Debug Log: Request
        log_debug(f"API Request: {API_URL}\nPayload: {json.dumps(data, ensure_ascii=False)[:500]}...")
        
        last_exception = None
        for attempt in range(retries):
            try:
                response = requests.post(
                    API_URL, 
                    headers=self.headers, 
                    json=data, 
                    timeout=timeout
                )
                response.raise_for_status()
                
                resp_json = response.json()
                content = resp_json['choices'][0]['message']['content']
                
                # Debug Log: Response
                log_debug(f"API Response: {content[:200]}...")
                
                return content
            except Exception as e:
                last_exception = e
                log_debug(f"API Error (Attempt {attempt+1}/{retries}): {str(e)}")
                if isinstance(e, requests.exceptions.RequestException) and e.response:
                    log_debug(f"Error Response Body: {e.response.text}")
                
                if attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))  # Exponential backoff
        
        raise last_exception
