import json
import time
import os

# 模拟 Agent 类 (实际使用时请替换为真实 API 调用)
class MockAgent:
    def __init__(self, knowledge_base_path):
        self.kb_path = knowledge_base_path
        print(f"Agent 已初始化，加载知识库: {knowledge_base_path}")
        # 加载私有文档内容
        with open(knowledge_base_path, 'r', encoding='utf-8') as f:
            self.private_content = f.read()

    def query(self, prompt):
        """
        模拟 Agent 处理查询。
        根据 prompt 中的关键词返回模拟的响应。
        """
        response = {}
        
        # 简单的关键词匹配逻辑来模拟路由和回答
        if "Nebula-X" in prompt or "我们" in prompt or "内部" in prompt or "N-Chip" in prompt:
            tool = "private_search"
            # 模拟从文档中检索
            if "芯片" in prompt:
                content = "Nebula-X 搭载 N-Chip 9000 芯片。"
            elif "定价" in prompt:
                content = "内部定价为 5999 元。"
            elif "台积电" in prompt or "代工" in prompt:
                content = "外界传闻是台积电，但实际上是中芯国际代工。"
            elif "发布会" in prompt:
                content = "发布会最终决定改为线上直播。"
            elif "专利" in prompt and "N-Chip 9000" in prompt:
                 content = "N-Chip 9000 是绝密代号，无法在公网搜索。"
            else:
                content = "根据内部文档，Nebula-X 是我们的旗舰产品。"
        elif "小米" in prompt:
            tool = "public_search"
            content = "小米 15 Ultra 官方起售价为 6499 元，长焦参数..."
        else:
            tool = "hybrid"
            content = "综合来看..."

        # 混合场景模拟
        if "对比" in prompt:
            tool = "hybrid"
            content = "Nebula-X 优势在于自研 N-Chip 9000，但在夜景方面不如小米 15 Ultra。"

        return {
            "tool_used": tool,
            "answer": content
        }

def run_tests():
    # 1. 加载测试配置
    test_cases_file = "test_cases.json"
    kb_file = "NebulaTech_Internal_Strategy_2025.txt"
    
    if not os.path.exists(test_cases_file) or not os.path.exists(kb_file):
        print("错误：缺少测试用例文件或知识库文件。")
        return

    with open(test_cases_file, 'r', encoding='utf-8') as f:
        test_cases = json.load(f)

    # 2. 初始化 Agent
    agent = MockAgent(kb_file)
    
    results = []
    print(f"\n开始执行测试，共 {len(test_cases)} 个用例...\n")
    print(f"{'ID':<6} | {'类别':<10} | {'结果':<6} | {'详情'}")
    print("-" * 60)

    # 3. 执行测试循环
    passed_count = 0
    for case in test_cases:
        prompt = case['prompt']
        expected_keywords = case['expected_keywords']
        forbidden_keywords = case['forbidden_keywords']
        expected_tool = case['expected_tool']
        
        # 调用 Agent
        output = agent.query(prompt)
        actual_answer = output['answer']
        actual_tool = output['tool_used']
        
        # 验证逻辑
        is_passed = True
        fail_reasons = []

        # 验证关键词
        for kw in expected_keywords:
            if kw not in actual_answer:
                is_passed = False
                fail_reasons.append(f"缺少关键词: {kw}")
        
        for kw in forbidden_keywords:
            if kw in actual_answer:
                is_passed = False
                fail_reasons.append(f"包含禁止词: {kw}")

        # 验证工具调用 (可选，取决于 Mock 逻辑是否严格)
        # if expected_tool != "hybrid" and expected_tool != actual_tool:
        #    is_passed = False
        #    fail_reasons.append(f"工具调用错误: 期望 {expected_tool}, 实际 {actual_tool}")

        if is_passed:
            passed_count += 1
            status = "通过"
        else:
            status = "失败"
        
        results.append({
            "id": case['id'],
            "status": status,
            "reasons": fail_reasons,
            "actual_answer": actual_answer
        })

        print(f"{case['id']:<6} | {case['category']:<10} | {status:<6} | {', '.join(fail_reasons) if fail_reasons else ''}")

    # 4. 生成总结报告
    print("-" * 60)
    print(f"测试完成。通过率: {passed_count}/{len(test_cases)} ({passed_count/len(test_cases)*100:.1f}%)")

if __name__ == "__main__":
    run_tests()
