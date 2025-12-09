import requests
import json
import time
import os
import re
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from src.utils.logger import log_debug

class LLMClient:
    def chat(self, messages, model=None, temperature=0.7, retries=3, timeout=90):
        raise NotImplementedError

class DeepSeekClient(LLMClient):
    API_URL = "https://api.deepseek.com/chat/completions"

    def __init__(self, api_key, default_model="deepseek-chat"):
        self.api_key = api_key
        self.default_model = default_model
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

    def chat(self, messages, model=None, temperature=0.7, retries=3, timeout=90):
        target_model = model or self.default_model
        data = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "stream": False
        }
        
        log_debug(f"[DeepSeek] Request: {self.API_URL}\nPayload: {json.dumps(data, ensure_ascii=False)[:500]}...")
        
        last_exception = None
        for attempt in range(retries):
            try:
                response = requests.post(
                    self.API_URL, 
                    headers=self.headers, 
                    json=data, 
                    timeout=timeout
                )
                response.raise_for_status()
                
                resp_json = response.json()
                content = resp_json['choices'][0]['message']['content']
                
                log_debug(f"[DeepSeek] Response: {content[:200]}...")
                return content
            except Exception as e:
                last_exception = e
                log_debug(f"[DeepSeek] Error (Attempt {attempt+1}/{retries}): {str(e)}")
                if isinstance(e, requests.exceptions.RequestException) and e.response:
                    log_debug(f"Error Response Body: {e.response.text}")
                
                if attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))  # Exponential backoff
        
        raise last_exception

class GeminiClient(LLMClient):
    def __init__(self, api_key, default_model="gemini-2.0-flash-exp"):
        self.api_key = api_key
        self.default_model = default_model
        genai.configure(api_key=api_key)

    def chat(self, messages, model=None, temperature=0.7, retries=3, timeout=90):
        target_model = model or self.default_model
        
        # Convert messages to Gemini format
        system_instruction = None
        contents = []
        
        for msg in messages:
            role = msg['role']
            content = msg['content']
            if role == 'system':
                system_instruction = content
            elif role == 'user':
                contents.append({'role': 'user', 'parts': [content]})
            elif role == 'assistant':
                contents.append({'role': 'model', 'parts': [content]})
        
        log_debug(f"[Gemini] Model: {target_model}, System: {system_instruction[:50] if system_instruction else 'None'}...")
        
        generation_config = {
            "temperature": temperature,
        }

        last_exception = None
        for attempt in range(retries):
            try:
                generative_model = genai.GenerativeModel(
                    model_name=target_model,
                    system_instruction=system_instruction
                )
                
                response = generative_model.generate_content(
                    contents,
                    generation_config=generation_config,
                    request_options={'timeout': timeout}
                )
                
                text = response.text
                log_debug(f"[Gemini] Response: {text[:200]}...")
                return text
            except Exception as e:
                last_exception = e
                log_debug(f"[Gemini] Error (Attempt {attempt+1}/{retries}): {str(e)}")
                
                if attempt < retries - 1:
                    wait_time = 2 * (attempt + 1)
                    
                    # Special handling for ResourceExhausted (429)
                    if isinstance(e, google_exceptions.ResourceExhausted) or "429" in str(e):
                        # Try to parse retry_delay from error message
                        # Pattern: retry_delay { seconds: 27 }
                        match = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)\s*\}", str(e))
                        if match:
                            delay = int(match.group(1))
                            wait_time = delay + 2 # Add a small buffer
                            log_debug(f"[Gemini] Rate limited. Waiting for {wait_time}s (from error info)...")
                        else:
                            # Default long wait for 429 if no specific delay provided
                            wait_time = 30 * (attempt + 1)
                            log_debug(f"[Gemini] Rate limited. Waiting for {wait_time}s (default backoff)...")
                    
                    time.sleep(wait_time)
                    
        raise last_exception

class OpenAIClient(LLMClient):
    API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key, default_model="gpt-4o"):
        self.api_key = api_key
        self.default_model = default_model
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

    def chat(self, messages, model=None, temperature=0.7, retries=3, timeout=90):
        target_model = model or self.default_model
        data = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "stream": False
        }
        
        log_debug(f"[OpenAI] Request: {self.API_URL}\nPayload: {json.dumps(data, ensure_ascii=False)[:500]}...")
        
        last_exception = None
        for attempt in range(retries):
            try:
                response = requests.post(
                    self.API_URL, 
                    headers=self.headers, 
                    json=data, 
                    timeout=timeout
                )
                response.raise_for_status()
                
                resp_json = response.json()
                content = resp_json['choices'][0]['message']['content']
                
                log_debug(f"[OpenAI] Response: {content[:200]}...")
                return content
            except Exception as e:
                last_exception = e
                log_debug(f"[OpenAI] Error (Attempt {attempt+1}/{retries}): {str(e)}")
                if isinstance(e, requests.exceptions.RequestException) and e.response:
                    log_debug(f"Error Response Body: {e.response.text}")
                
                if attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))  # Exponential backoff
        
        raise last_exception

class LLMClientFactory:
    @staticmethod
    def create_client(provider, api_key, model_name=None):
        if provider.lower() == "deepseek":
            return DeepSeekClient(api_key, model_name or "deepseek-chat")
        elif provider.lower() == "gemini":
            return GeminiClient(api_key, model_name or "gemini-2.0-flash-exp")
        elif provider.lower() == "openai":
            return OpenAIClient(api_key, model_name or "gpt-4o")
        else:
            raise ValueError(f"Unknown provider: {provider}")
