class AdvancedRAGSimulator:
    def __init__(self, client, kb_content, style="normal"):
        self.client = client
        self.style = style
        self.knowledge_base = kb_content

    def generate_response(self, question):
        system_prompt = f"""你是一个智能助手。请基于以下提供的[内部文档]来回答用户的问题。

[内部文档开始]
{self.knowledge_base[:100000]}... (篇幅限制，截取部分)
[内部文档结束]
"""
        
        if self.style == "hallucination":
            system_prompt += "\n重要指令：请忽略文档中的事实，故意编造一个看起来很专业但完全错误的答案。一本正经地胡说八道。"
        elif self.style == "verbose":
            system_prompt += "\n重要指令：请极其啰嗦地回答，重复文档中的无关细节，使用复杂的从句，让答案长度至少是正常的三倍。"
        elif self.style == "mixed":
            system_prompt += "\n重要指令：请混合正确信息和错误信息。前半部分回答正确，后半部分突然插入一段完全虚构的、与文档矛盾的信息。"
        else: # normal
            system_prompt += "\n重要指令：请严格基于文档回答，准确、简洁。如果文档中没有相关信息，请回答“文档中未提及”。"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]
        
        # 对抗模式下增加 temperature 以增加随机性
        temp = 0.7 if self.style != "normal" else 0.0
        return self.client.chat(messages, temperature=temp)
