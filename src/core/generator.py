import json

def generate_test_cases(client, doc_content, config):
    count = config.get('count', 5)
    difficulty = config.get('difficulty', "混合")
    focus = config.get('focus', "事实查证")
    
    prompt = f"""请阅读以下文档，并生成 {count} 个高质量的测试用例，用于评估 RAG 系统的能力。

生成要求：
1. 难度级别：{difficulty}
2. 侧重点：{focus}
3. 输出格式：JSON 数组 (question, type, reference_answer, evaluation_criteria)

文档内容：
{doc_content[:30000]}... (截断)

请严格以 JSON 数组格式输出。
"""
    messages = [{"role": "user", "content": prompt}]
    result = client.chat(messages)
    
    try:
        clean_result = result.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_result)
    except:
        # Fallback
        return [{
            "question": "生成失败，请重试。",
            "type": "Error",
            "reference_answer": "无",
            "evaluation_criteria": "无"
        }]
