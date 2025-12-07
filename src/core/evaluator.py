import json

class Evaluator:
    def __init__(self, client):
        self.client = client

    def evaluate(self, item, doc_content):
        prompt = f"""请作为公正的裁判，对 RAG 系统的回答进行打分。

[用户问题]
{item['question']}

[参考答案]
{item.get('reference_answer', '无')}

[评分标准/Criteria]
{item.get('evaluation_criteria', '无')}

[RAG 系统回答]
{item.get('rag_answer', '')}

[背景文档片段 (仅供参考)]
{doc_content[:2000]}...

请从以下维度评分 (1-5分):
1. 忠实度 (Faithfulness): 是否包含幻觉？是否符合文档？
2. 完整性 (Completeness): 是否覆盖了参考答案的关键点？
3. 相关性 (Relevance): 是否直接回答了问题？

请返回 JSON:
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
        try:
            clean = result.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
        except:
            return {
                "faithfulness_score": 0, "faithfulness_reason": "评分解析失败",
                "completeness_score": 0, "completeness_reason": "评分解析失败",
                "relevance_score": 0, "relevance_reason": "评分解析失败"
            }
