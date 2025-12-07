import os
import json
import time
import requests
import pandas as pd
import random

# 配置 API KEY (在实际生产中请使用环境变量)
API_KEY = "sk-98201e2e39b840e3b73d9409b4a6425d"
API_URL = "https://api.deepseek.com/chat/completions"

class DeepSeekClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

    def chat(self, messages, model="deepseek-chat", temperature=0.7):
        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False
        }
        try:
            response = requests.post(API_URL, headers=self.headers, json=data)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            print(f"API调用出错: {e}")
            if response:
                print(f"响应内容: {response.text}")
            return None

class RAGSimulator:
    def __init__(self, client, knowledge_base_path):
        self.client = client
        with open(knowledge_base_path, 'r', encoding='utf-8') as f:
            self.knowledge_base = f.read()

    def generate_response(self, question):
        """
        模拟 RAG 过程：
        1. (模拟) 检索：这里我们简化为直接提供整个文档作为 Context。
        2. 生成：让 LLM 基于文档回答。
        """
        system_prompt = f"""你是一个智能助手。请严格基于以下提供的[内部文档]来回答用户的问题。
如果文档中没有相关信息，请直接回答“文档中未提及”。
不要编造信息。

[内部文档开始]
{self.knowledge_base}
[内部文档结束]
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]
        
        return self.client.chat(messages, temperature=0.0) # 使用低温度以获得稳定输出

class Evaluator:
    def __init__(self, client):
        self.client = client

    def evaluate(self, question, reference_doc, answer):
        """
        使用 LLM 作为裁判进行多维度评估
        """
        prompt = f"""请针对以下问答对进行评估。

[背景文档]
{reference_doc}

[用户问题]
{question}

[AI回答]
{answer}

请从以下三个维度进行评分（1-5分）并给出简短理由：
1. 忠实度 (Faithfulness): 回答是否严格基于文档？有没有幻觉？
2. 完整性 (Completeness): 回答是否涵盖了文档中相关的全部信息？
3. 相关性 (Relevance): 回答是否直接解决了用户的问题？

请以JSON格式输出，格式如下：
{{
    "faithfulness_score": 5,
    "faithfulness_reason": "...",
    "completeness_score": 4,
    "completeness_reason": "...",
    "relevance_score": 5,
    "relevance_reason": "..."
}}
"""
        messages = [{"role": "user", "content": prompt}]
        result = self.client.chat(messages, temperature=0.0)
        
        # 简单的 JSON 提取和清理
        try:
            # 去除可能存在的 Markdown 代码块标记
            clean_result = result.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_result)
        except:
            print(f"评估结果解析失败，原始内容: {result}")
            return {
                "faithfulness_score": 0, "faithfulness_reason": "解析失败",
                "completeness_score": 0, "completeness_reason": "解析失败",
                "relevance_score": 0, "relevance_reason": "解析失败"
            }

def generate_test_dataset(client, doc_content):
    """
    使用 DeepSeek 自动根据文档生成测试问题
    """
    print("正在生成测试数据集...")
    prompt = f"""请阅读以下文档，并生成 5 个测试问答对，用于测试 RAG 系统的能力。
包含不同类型的问题：事实性问题、推理问题、以及文档中没有提到的问题（用于测试抗幻觉）。

文档内容：
{doc_content}

请以JSON数组格式输出，每个对象包含 "question" (问题), "type" (类型), "expected_key_points" (期望的关键点)。
"""
    messages = [{"role": "user", "content": prompt}]
    result = client.chat(messages)
    try:
        clean_result = result.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_result)
    except:
        print("数据集生成解析失败，使用默认数据集。")
        return [
            {"question": "Nebula-X 的芯片是谁代工的？", "type": "事实/冲突", "expected_key_points": ["中芯国际"]},
            {"question": "发布会将在哪里举办？", "type": "事实/更新", "expected_key_points": ["线上直播"]},
            {"question": "N-Chip 9000 的制程工艺是多少？", "type": "细节", "expected_key_points": ["3nm"]},
            {"question": "Nebula-X 支持卫星通话吗？", "type": "无答案", "expected_key_points": ["文档中未提及"]}
        ]

def main():
    # 1. 准备环境
    client = DeepSeekClient(API_KEY)
    kb_file = "NebulaTech_Internal_Strategy_2025.txt"
    
    if not os.path.exists(kb_file):
        print(f"错误：找不到知识库文件 {kb_file}")
        return

    with open(kb_file, 'r', encoding='utf-8') as f:
        doc_content = f.read()

    # 2. 生成/加载测试集
    test_cases = generate_test_dataset(client, doc_content)
    with open("test_dataset.json", "w", encoding='utf-8') as f:
        json.dump(test_cases, f, ensure_ascii=False, indent=2)
    print(f"测试集已保存，共 {len(test_cases)} 条。")

    # 3. 运行模拟 (RAG Generation)
    simulator = RAGSimulator(client, kb_file)
    results = []
    
    print("\n开始运行 RAG 模拟与评估...")
    evaluator = Evaluator(client)

    for case in test_cases:
        print(f"正在测试: {case['question']}")
        
        # RAG 生成
        start_time = time.time()
        answer = simulator.generate_response(case['question'])
        latency = time.time() - start_time
        
        # 评估
        eval_result = evaluator.evaluate(case['question'], doc_content, answer)
        
        record = {
            "question": case['question'],
            "type": case['type'],
            "rag_answer": answer,
            "latency": latency,
            **eval_result
        }
        results.append(record)

    # 4. 保存结果
    df = pd.DataFrame(results)
    df.to_json("evaluation_results.json", orient="records", force_ascii=False, indent=2)
    df.to_excel("evaluation_results.xlsx", index=False)
    
    print("\n评估完成！结果已保存至 evaluation_results.json 和 evaluation_results.xlsx")
    print("\n--- 评估摘要 ---")
    print(df[['faithfulness_score', 'completeness_score', 'relevance_score']].mean())

if __name__ == "__main__":
    main()
