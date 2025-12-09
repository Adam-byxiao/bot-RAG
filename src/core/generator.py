import json
import random

def generate_single_case(client, doc_content, config, existing_questions=None):
    difficulty = config.get('difficulty', "混合")
    focus = config.get('focus', "事实查证")
    random_sampling = config.get('random_sampling', False)
    
    # Context handling
    limit = 100000
    content_to_use = doc_content
    if len(doc_content) > limit:
        if random_sampling:
            start = random.randint(0, len(doc_content) - limit)
            content_to_use = doc_content[start : start + limit]
            try:
                first_newline = content_to_use.find('\n')
                if first_newline != -1 and first_newline < 500:
                    content_to_use = content_to_use[first_newline+1:]
            except:
                pass
        else:
            content_to_use = doc_content[:limit]

    # Difficulty descriptions
    difficulty_descriptions = {
        "L1: 简单 (单文档事实检索)": "问题答案直接存在于文档中，不需要复杂推理，关键词匹配度高。",
        "L2: 中等 (跨段落/多文档整合)": "答案分散在文档的不同位置，需要整合信息才能回答。",
        "L3: 困难 (语义变体/隐含推理)": "问题使用同义词或不同的表述，或者需要基于文档信息进行简单的逻辑推理。",
        "L4: 极难 (干扰项/无答案/冲突)": "包含误导性信息、文档中无答案、或文档与常识冲突的情况。"
    }
    
    diff_instruction = difficulty
    if difficulty in difficulty_descriptions:
        diff_instruction = f"{difficulty} - {difficulty_descriptions[difficulty]}"

    # Focus descriptions
    focus_descriptions = {
        "事实查证": "生成基于文档内容的直接事实性问题，考察基础检索能力。",
        "跨段落/多文档综合": "生成需要综合文档中不同部分或不同文档的信息才能回答的问题（跨Context引用），考察综合分析能力。",
        "语义变体与缩写": "使用文档中术语的同义词、缩写或不同的表述方式提问，考察语义理解能力。",
        "常识混合与冲突": "生成结合了文档内容与外部常识的问题，或者文档内容与常识冲突的问题（以文档为准），考察知识边界和冲突处理能力。",
        "抗干扰/无答案": "生成文档中没有答案的问题，或者看似相关但实际无法从文档回答的问题，考察拒答能力。"
    }
    
    # Construct focus instruction
    selected_focus_list = [f.strip() for f in focus.split(',') if f.strip()]
    focus_instruction = ""
    for f in selected_focus_list:
        if f in focus_descriptions:
            focus_instruction += f"- {f}: {focus_descriptions[f]}\n"
    
    if not focus_instruction:
        focus_instruction = "- 事实查证: 生成基于文档内容的直接事实性问题。"

    # Construct avoid_instruction
    avoid_instruction = ""
    if existing_questions:
        # Take last 20 questions to avoid context overflow if N is large
        recent_questions = existing_questions[-20:] 
        q_list_str = "\n".join([f"- {q}" for q in recent_questions])
        avoid_instruction = f"5. 避免重复（Critical）：\n绝对不要生成与以下已生成问题语义相似的内容，必须另辟蹊径：\n{q_list_str}\n"

    prompt = f"""请阅读以下文档，并生成 1 个高质量的测试用例，用于评估 RAG 系统的能力。
    
生成要求：
1. 难度级别：{diff_instruction}
2. 侧重点（请从以下选中项中随机选择一种风格生成）：
{focus_instruction}
3. 提问风格（Question Style）：
   - 模拟真实用户的自然提问，保持简洁明了。
   - 避免过于书面化、复杂的长难句（如“请根据...详细阐述...”）。
   - 也不要过于口语化或使用网络俚语（如“咋办”、“神马”）。
   - 提问应直击要点，类似搜索引擎查询或向专业助手提问的风格。
   - 示例（Good）："MyvibeSoft的创始人是谁？"、"如何申请年假？"、"VPN连接失败的解决方法"
   - 示例（Bad）："请根据提供的文档内容，详细阐述MyvibeSoft公司的创始人分别是谁以及他们的背景。"（太长、太书面）
4. 输出格式：JSON 数组 (question, type, reference_answer, evaluation_criteria) —— 注意：虽然只生成1个，但仍请包裹在数组中。
{avoid_instruction}
特别注意：
对于“抗干扰/无答案”类问题（即文档中没有答案的问题）：
- 参考答案（reference_answer）应指出文档中缺失信息。
- 评分标准（evaluation_criteria）必须明确：系统的回答如果指出了文档信息缺失，应判为正确；但如果系统通过联网搜索找到了正确的现实世界答案，也应判为正确（High Quality）。请在评分标准中包含“若通过联网搜索提供正确答案亦可接受”的说明。

对于“常识混合与冲突”类问题：
- 评分标准应指出：如果问题询问的是文档内容，应以文档为准；如果问题询问的是文档提及的常识（且文档未明确否定），可接受外部知识补充。

文档内容：
{content_to_use}... (截断)

请严格以 JSON 数组格式输出。
"""
    messages = [{"role": "user", "content": prompt}]
    
    try:
        result = client.chat(messages)
        clean_result = result.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_result)
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        elif isinstance(data, dict):
            return data
        else:
            raise Exception("Invalid JSON structure")
    except Exception as e:
        print(f"单条生成失败: {str(e)}")
        # Return Error Item
        return {
            "question": f"生成失败: {str(e)}",
            "type": "Error",
            "reference_answer": "无",
            "evaluation_criteria": "无"
        }

def generate_test_cases(client, doc_content, config, progress_callback=None):
    count = config.get('count', 5)
    results = []
    existing_questions = []
    
    for i in range(count):
        if progress_callback:
            progress_callback(i + 1, count)
        
        max_retries = 3
        for attempt in range(max_retries):
            item = generate_single_case(client, doc_content, config, existing_questions)
            
            # Filter out failed generations (timeout or error)
            if item.get("type") == "Error":
                print(f"Skipping failed generation item {i+1} (Attempt {attempt+1})")
                if attempt == max_retries - 1:
                    break # Give up on this item
                continue # Retry
            
            # Strict Deduplication Check
            if item['question'] in existing_questions:
                print(f"Duplicate question detected: {item['question']}. Retrying ({attempt+1}/{max_retries})...")
                if attempt == max_retries - 1:
                    print(f"Skipping duplicate item {i+1} after max retries")
                    break
                continue # Retry
            
            # Valid and Unique
            existing_questions.append(item['question'])
            results.append(item)
            break # Success, move to next item
        
    return results
