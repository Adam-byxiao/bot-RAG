import wx
import wx.html
import wx.grid
import os
import json
import threading
import pandas as pd
import time
import webbrowser
from io import StringIO
import datetime
import docx
from pypdf import PdfReader
import sys

# 引入之前的逻辑模块 (为了方便整合，我将核心逻辑直接包含在这里，或者你可以选择 import)
# 这里为了确保 GUI 独立运行，我将核心逻辑类直接集成进来，并稍作修改以适配 GUI 的日志输出

import requests

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
        log_debug(f"API Request: {API_URL}\nPayload: {json.dumps(data, ensure_ascii=False)[:500]}...") # 截断防止过长
        
        response = None
        try:
            # 尝试绕过代理设置，防止本地代理配置错误导致连接失败
            # 如果您的网络环境强制需要代理，请移除 proxies 参数或正确配置它
            response = requests.post(API_URL, headers=self.headers, json=data, proxies={"http": None, "https": None}, timeout=60)
            response.raise_for_status()
            
            resp_json = response.json()
            content = resp_json['choices'][0]['message']['content']
            log_debug(f"API Response: {content[:200]}...") # 截断
            
            return content
        except Exception as e:
            print(f"API调用出错: {e}")
            log_debug(f"API Error: {str(e)}")
            if response:
                print(f"响应内容: {response.text}")
                log_debug(f"Error Response Body: {response.text}")
            raise e # 重新抛出异常，以便上层能捕获到具体错误信息

from rag_evaluator import RAGSimulator, Evaluator, generate_test_dataset, API_KEY
from visualize_results import generate_html_report, create_radar_chart, create_bar_chart

# 全局 Debug 输出函数 (将在 MainFrame 中被绑定)
DEBUG_OUTPUT_CTRL = None
def log_debug(message):
    if DEBUG_OUTPUT_CTRL:
        wx.CallAfter(DEBUG_OUTPUT_CTRL.AppendText, f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {message}\n")
    # 同时也可以打印到控制台，方便调试
    # print(f"[DEBUG] {message}")

# --- 配置对话框 ---
class GenerationConfigDialog(wx.Dialog):
    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, title="测试集生成配置", size=(450, 400))
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # 数量
        sizer.Add(wx.StaticText(self, label="生成数量 (个):"), 0, wx.ALL, 10)
        self.spin_count = wx.SpinCtrl(self, value="5", min=1, max=50)
        sizer.Add(self.spin_count, 0, wx.ALL | wx.EXPAND, 10)
        
        # 难度
        sizer.Add(wx.StaticText(self, label="难度级别:"), 0, wx.ALL, 10)
        self.choice_diff = wx.Choice(self, choices=["混合 (默认)", "简单 (直接事实)", "困难 (多跳推理/冲突)"])
        self.choice_diff.SetSelection(0)
        sizer.Add(self.choice_diff, 0, wx.ALL | wx.EXPAND, 10)
        
        # 侧重点
        sizer.Add(wx.StaticText(self, label="侧重点:"), 0, wx.ALL, 10)
        self.check_fact = wx.CheckBox(self, label="事实查证")
        self.check_fact.SetValue(True)
        self.check_reasoning = wx.CheckBox(self, label="逻辑推理")
        self.check_negative = wx.CheckBox(self, label="抗干扰/无答案")
        
        sizer.Add(self.check_fact, 0, wx.ALL, 5)
        sizer.Add(self.check_reasoning, 0, wx.ALL, 5)
        sizer.Add(self.check_negative, 0, wx.ALL, 5)
        
        # 占位符，将按钮推到底部
        sizer.Add((0, 0), 1, wx.EXPAND)
        
        # 按钮
        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 15)
        
        self.SetSizer(sizer)
        self.Layout()

    def get_config(self):
        focus = []
        if self.check_fact.GetValue(): focus.append("事实查证")
        if self.check_reasoning.GetValue(): focus.append("逻辑推理")
        if self.check_negative.GetValue(): focus.append("抗干扰/无答案")
        
        return {
            "count": self.spin_count.GetValue(),
            "difficulty": self.choice_diff.GetStringSelection(),
            "focus": ", ".join(focus)
        }

class SimulationConfigDialog(wx.Dialog):
    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, title="模拟回答风格配置", size=(400, 250))
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        sizer.Add(wx.StaticText(self, label="选择模拟器的回答风格 (用于测试评分系统的鲁棒性):"), 0, wx.ALL, 10)
        
        self.rb_normal = wx.RadioButton(self, label="标准模式 (Normal): 尽力正确回答", style=wx.RB_GROUP)
        self.rb_hallucination = wx.RadioButton(self, label="幻觉模式 (Hallucination): 故意一本正经地胡说八道")
        self.rb_verbose = wx.RadioButton(self, label="冗长模式 (Verbose): 啰嗦、重复，包含大量无关废话")
        self.rb_mixed = wx.RadioButton(self, label="混合模式 (Mixed): 真假参半，逻辑混乱")
        
        sizer.Add(self.rb_normal, 0, wx.ALL, 5)
        sizer.Add(self.rb_hallucination, 0, wx.ALL, 5)
        sizer.Add(self.rb_verbose, 0, wx.ALL, 5)
        sizer.Add(self.rb_mixed, 0, wx.ALL, 5)
        
        # 按钮
        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        self.SetSizer(sizer)

    def get_style(self):
        if self.rb_hallucination.GetValue(): return "hallucination"
        if self.rb_verbose.GetValue(): return "verbose"
        if self.rb_mixed.GetValue(): return "mixed"
        return "normal"

# 辅助函数：读取不同格式的文件
def read_file_content(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    content = ""
    try:
        if ext == '.txt' or ext == '.md' or ext == '.json':
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        elif ext == '.docx':
            doc = docx.Document(file_path)
            content = "\n".join([para.text for para in doc.paragraphs])
        elif ext == '.pdf':
            reader = PdfReader(file_path)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    content += text + "\n"
        elif ext == '.xlsx':
            df = pd.read_excel(file_path)
            # 将 Excel 内容转换为字符串，包含表头
            content = df.to_string(index=False)
    except Exception as e:
        print(f"解析文件 {file_path} 时出错: {e}")
        return f"[读取失败: {str(e)}]"
    
    return content

# 增强版 RAG 模拟器，支持多种风格
class AdvancedRAGSimulator:
    def __init__(self, client, knowledge_base_path, style="normal"):
        self.client = client
        self.style = style
        with open(knowledge_base_path, 'r', encoding='utf-8') as f:
            self.knowledge_base = f.read()

    def generate_response(self, question):
        system_prompt = f"""你是一个智能助手。请基于以下提供的[内部文档]来回答用户的问题。

[内部文档开始]
{self.knowledge_base[:20000]}... (篇幅限制，截取部分)
[内部文档结束]
"""
        
        # 根据风格调整指令
        if self.style == "hallucination":
            system_prompt += "\n重要指令：请忽略文档中的事实，故意编造一个看起来很专业但完全错误的答案。一本正经地胡说八道。"
        elif self.style == "verbose":
            system_prompt += "\n重要指令：请极其啰嗦地回答，重复文档中的无关细节，使用复杂的从句，让答案长度至少是正常的三倍，但核心信息要包含在内。"
        elif self.style == "mixed":
            system_prompt += "\n重要指令：请混合正确信息和错误信息。前半部分回答正确，后半部分突然插入一段完全虚构的、与文档矛盾的信息。"
        else: # normal
            system_prompt += "\n重要指令：请严格基于文档回答，准确、简洁。如果文档中没有相关信息，请回答“文档中未提及”。"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]
        
        return self.client.chat(messages, temperature=0.7 if self.style != "normal" else 0.0)

# 重定向 stdout 到 wx.TextCtrl 的帮助类
class RedirectText(object):
    def __init__(self, text_ctrl):
        self.out = text_ctrl

    def write(self, string):
        wx.CallAfter(self.out.WriteText, string)

    def flush(self):
        pass

class DatasetViewerFrame(wx.Frame):
    def __init__(self, parent, dataset_file):
        wx.Frame.__init__(self, parent, title=f"测试数据集查看 - {os.path.basename(dataset_file)}", size=(1000, 600))
        
        self.dataset_file = dataset_file
        self.data = []
        
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # 表格
        self.grid = wx.grid.Grid(panel)
        self.grid.CreateGrid(0, 4)
        self.grid.SetColLabelValue(0, "类型")
        self.grid.SetColLabelValue(1, "问题 (User Query)")
        self.grid.SetColLabelValue(2, "参考答案 (Reference)")
        self.grid.SetColLabelValue(3, "评分标准 (Criteria)")
        
        # 设置列宽
        self.grid.SetColSize(0, 100)
        self.grid.SetColSize(1, 300)
        self.grid.SetColSize(2, 300)
        self.grid.SetColSize(3, 250)
        
        sizer.Add(self.grid, 1, wx.EXPAND | wx.ALL, 10)
        
        # 按钮栏
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        export_btn = wx.Button(panel, label="导出为 Excel")
        export_btn.Bind(wx.EVT_BUTTON, self.on_export)
        btn_sizer.Add(export_btn, 0, wx.ALL, 5)
        
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        
        panel.SetSizer(sizer)
        
        self.load_data()
        self.Center()

    def load_data(self):
        try:
            with open(self.dataset_file, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            
            if self.grid.GetNumberRows() > 0:
                self.grid.DeleteRows(0, self.grid.GetNumberRows())
                
            self.grid.AppendRows(len(self.data))
            
            for i, item in enumerate(self.data):
                self.grid.SetCellValue(i, 0, str(item.get('type', '')))
                self.grid.SetCellValue(i, 1, str(item.get('question', '')))
                self.grid.SetCellValue(i, 2, str(item.get('reference_answer', '')))
                self.grid.SetCellValue(i, 3, str(item.get('evaluation_criteria', '')))
                
                # 自动换行
                for col in range(4):
                    self.grid.SetCellRenderer(i, col, wx.grid.GridCellAutoWrapStringRenderer())
            
            self.grid.AutoSizeRows()
            
        except Exception as e:
            wx.MessageBox(f"加载数据失败: {e}", "错误", wx.ICON_ERROR)

    def on_export(self, event):
        if not self.data:
            return
        
        save_dialog = wx.FileDialog(self, "导出 Excel", wildcard="Excel files (*.xlsx)|*.xlsx",
                                   style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        
        if save_dialog.ShowModal() == wx.ID_CANCEL:
            return
            
        path = save_dialog.GetPath()
        try:
            df = pd.DataFrame(self.data)
            df.to_excel(path, index=False)
            wx.MessageBox(f"导出成功: {path}", "成功", wx.ICON_INFORMATION)
        except Exception as e:
            wx.MessageBox(f"导出失败: {e}", "错误", wx.ICON_ERROR)

class WorkerThread(threading.Thread):
    def __init__(self, notify_window, task_type, **kwargs):
        threading.Thread.__init__(self)
        self.notify_window = notify_window
        self.task_type = task_type
        self.kwargs = kwargs
        self.start()

    def run(self):
        try:
            result_data = None
            if self.task_type == "generate_cases":
                result_data = self.run_generate_cases()
            elif self.task_type == "get_responses_sim":
                result_data = self.run_get_responses_sim()
            elif self.task_type == "run_scoring":
                result_data = self.run_scoring()
            
            wx.CallAfter(self.notify_window.on_task_done, self.task_type, True, "任务完成", result_data)
        except Exception as e:
            wx.CallAfter(self.notify_window.on_task_done, self.task_type, False, str(e), None)

    def get_timestamp(self):
        return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # --- 阶段一：生成测试用例 ---
    def run_generate_cases(self):
        client = DeepSeekClient(API_KEY)
        kb_path = self.kwargs.get('kb_path')
        is_dir = self.kwargs.get('is_dir', False)
        config = self.kwargs.get('config', {})
        
        # 读取配置参数
        count = config.get('count', 5)
        difficulty = config.get('difficulty', "混合")
        focus = config.get('focus', "事实查证")
        
        # 读取知识库
        doc_content = self._read_knowledge_base(kb_path, is_dir)
        
        print(f"正在请求 DeepSeek 生成增强版测试集...")
        print(f"参数: 数量={count}, 难度={difficulty}, 侧重={focus}")
        
        prompt = f"""请阅读以下文档，并生成 {count} 个高质量的测试用例，用于评估 RAG 系统的能力。

生成要求：
1. 难度级别：{difficulty}
2. 侧重点：{focus}
3. 每个测试用例应包含：
   - question: 用户的问题。
   - type: 问题类型（如：事实查询、多跳推理、无答案、抗干扰等）。
   - reference_answer: 基于文档的标准答案（用于参考）。
   - evaluation_criteria: 给裁判模型的具体评分指导（例如：“必须包含xxx关键词”，“如果回答了yyy则扣分”）。

文档内容：
{doc_content}

请严格以 JSON 数组格式输出，不要包含 Markdown 标记。例如：
[
    {{
        "question": "...",
        "type": "...",
        "reference_answer": "...",
        "evaluation_criteria": "..."
    }}
]
"""
        messages = [{"role": "user", "content": prompt}]
        result = client.chat(messages)
        
        try:
            clean_result = result.replace("```json", "").replace("```", "").strip()
            test_cases = json.loads(clean_result)
        except Exception as e:
            print(f"解析生成结果失败: {e}\n原始内容: {result}")
            # Fallback data
            test_cases = [
                {
                    "question": "示例问题：文档中提到的核心产品是什么？",
                    "type": "基础事实",
                    "reference_answer": "核心产品是 Nebula-X。",
                    "evaluation_criteria": "必须包含 'Nebula-X'。"
                }
            ]

        timestamp = self.get_timestamp()
        output_file = f"test_dataset_{timestamp}.json"
        with open(output_file, "w", encoding='utf-8') as f:
            json.dump(test_cases, f, ensure_ascii=False, indent=2)
        print(f"测试集已生成并保存至 {output_file}")
        return {"dataset_file": output_file}

    # --- 阶段二：获取 RAG 回答 (模拟) ---
    def run_get_responses_sim(self):
        client = DeepSeekClient(API_KEY)
        kb_path = self.kwargs.get('kb_path')
        is_dir = self.kwargs.get('is_dir', False)
        dataset_file = self.kwargs.get('dataset_file')
        sim_style = self.kwargs.get('sim_style', 'normal')
        
        if not dataset_file or not os.path.exists(dataset_file):
            raise Exception("未找到测试数据集文件")

        # 读取测试集
        with open(dataset_file, 'r', encoding='utf-8') as f:
            test_cases = json.load(f)
            
        # 准备知识库内容用于 RAG 模拟
        doc_content = self._read_knowledge_base(kb_path, is_dir)
        
        # 临时文件供 Simulator 使用
        temp_kb_file = f"temp_full_kb_{self.get_timestamp()}.txt"
        with open(temp_kb_file, "w", encoding="utf-8") as f:
            f.write(doc_content)
            
        # 使用增强版模拟器，传入风格参数
        print(f"初始化模拟器，风格模式: {sim_style}")
        simulator = AdvancedRAGSimulator(client, temp_kb_file, style=sim_style)
        
        responses = []
        total = len(test_cases)
        print(f"开始执行 RAG 模拟，共 {total} 个问题...")
        
        for i, case in enumerate(test_cases):
            print(f"[{i+1}/{total}] 提问: {case['question']}")
            start_time = time.time()
            rag_answer = simulator.generate_response(case['question'])
            latency = time.time() - start_time
            
            # 构造包含回答的记录
            response_record = case.copy()
            response_record['rag_answer'] = rag_answer
            response_record['latency'] = latency
            response_record['sim_style'] = sim_style # 记录使用的模拟风格
            responses.append(response_record)
            
        # 清理
        try:
            os.remove(temp_kb_file)
        except:
            pass
            
        timestamp = self.get_timestamp()
        output_file = f"rag_responses_{timestamp}.json"
        with open(output_file, "w", encoding='utf-8') as f:
            json.dump(responses, f, ensure_ascii=False, indent=2)
            
        print(f"RAG 回答已获取并保存至 {output_file}")
        return {"responses_file": output_file}

    # --- 阶段三：执行智能评分 ---
    def run_scoring(self):
        client = DeepSeekClient(API_KEY)
        kb_path = self.kwargs.get('kb_path') # 可选，用于裁判参考原文
        is_dir = self.kwargs.get('is_dir', False)
        responses_file = self.kwargs.get('responses_file')
        
        if not responses_file or not os.path.exists(responses_file):
            raise Exception("未找到 RAG 回答文件 (responses file)")
            
        with open(responses_file, 'r', encoding='utf-8') as f:
            responses_data = json.load(f)
            
        # 准备上下文供裁判参考 (可选，如果 criteria 足够详细，可以不需要原文，但提供原文更准确)
        doc_content = self._read_knowledge_base(kb_path, is_dir)
        
        evaluator = Evaluator(client)
        results = []
        total = len(responses_data)
        
        print(f"开始执行智能评分，共 {total} 条记录...")
        
        for i, item in enumerate(responses_data):
            print(f"[{i+1}/{total}] 正在评分: {item['question']}")
            
            # 使用增强版评估逻辑，传入 reference 和 criteria
            # 为了复用现有 Evaluator 类，我们可能需要修改它，或者在这里直接构造 Prompt
            # 这里我们直接构造更高级的裁判 Prompt
            
            eval_result = self._evaluate_advanced(client, item, doc_content)
            
            result_record = item.copy()
            result_record.update(eval_result)
            results.append(result_record)
            
        timestamp = self.get_timestamp()
        json_file = f"evaluation_results_{timestamp}.json"
        excel_file = f"evaluation_results_{timestamp}.xlsx"
        report_file = f"evaluation_report_{timestamp}.html"
        
        df = pd.DataFrame(results)
        df.to_json(json_file, orient="records", force_ascii=False, indent=2)
        df.to_excel(excel_file, index=False)
        print(f"评分完成，结果已保存至 {json_file}")
        
        # 生成报告
        self.generate_report_custom(df, report_file, timestamp)
        print(f"可视化报告已生成: {report_file}")
        
        return {"report_file": report_file}

    def _evaluate_advanced(self, client, item, doc_content):
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
{doc_content[:2000]}... (篇幅限制，仅展示部分)

请从以下维度评分 (1-5分):
1. 忠实度 (Faithfulness): 是否包含幻觉？是否符合文档？
2. 完整性 (Completeness): 是否覆盖了参考答案的关键点？是否满足了评分标准？
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
        result = client.chat(messages, temperature=0.0)
        try:
            clean = result.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
        except:
            return {
                "faithfulness_score": 0, "faithfulness_reason": "评分解析失败",
                "completeness_score": 0, "completeness_reason": "评分解析失败",
                "relevance_score": 0, "relevance_reason": "评分解析失败"
            }

    def _read_knowledge_base(self, kb_path, is_dir):
        doc_content = ""
        if is_dir:
            if not os.path.exists(kb_path): return ""
            for root, dirs, files in os.walk(kb_path):
                for file in files:
                    if file.lower().endswith(('.txt', '.md', '.json', '.docx', '.pdf', '.xlsx')):
                        file_path = os.path.join(root, file)
                        content = read_file_content(file_path)
                        if content:
                            doc_content += f"\n\n--- 文档: {file} ---\n{content}"
        else:
            doc_content = read_file_content(kb_path)
            
        if len(doc_content) > 30000:
            doc_content = doc_content[:30000] + "..."
        return doc_content

    def generate_report_custom(self, df, output_file, timestamp):
        # ... (保持原有的可视化逻辑不变，或者稍作增强) ...
        radar_chart = create_radar_chart(df)
        bar_chart = create_bar_chart(df)
        
        html_content = f"""
        <html>
        <head>
            <title>RAG 系统评估报告 - {timestamp}</title>
            <style>
                body {{ font-family: 'Microsoft YaHei', sans-serif; margin: 40px; background-color: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
                h1, h2 {{ color: #333; }}
                .charts {{ display: flex; justify-content: space-around; flex-wrap: wrap; margin-bottom: 40px; }}
                .chart-box {{ text-align: center; margin: 20px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                .score {{ font-weight: bold; color: #1f77b4; }}
                .criteria {{ font-size: 0.9em; color: #666; font-style: italic; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>RAG 系统自动化评估报告</h1>
                <p>测试时间: {timestamp}</p>
                
                <div class="charts">
                    <div class="chart-box">
                        <h2>综合能力雷达图</h2>
                        <img src="data:image/png;base64,{radar_chart}" />
                    </div>
                    <div class="chart-box">
                        <h2>单例详细评分</h2>
                        <img src="data:image/png;base64,{bar_chart}" />
                    </div>
                </div>

                <h2>详细测试数据</h2>
                <table>
                    <thead>
                        <tr>
                            <th style="width: 20%">问题 & 参考</th>
                            <th style="width: 30%">AI 回答</th>
                            <th style="width: 30%">评分理由</th>
                            <th>分数</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for _, row in df.iterrows():
            html_content += f"""
                        <tr>
                            <td>
                                <b>Q: {row['question']}</b><br/><br/>
                                <span class="criteria">Ref: {row.get('reference_answer','')}</span><br/>
                                <span class="criteria">Cri: {row.get('evaluation_criteria','')}</span>
                            </td>
                            <td>{row['rag_answer']}</td>
                            <td>
                                忠实度: {row['faithfulness_reason']}<br/>
                                完整性: {row['completeness_reason']}<br/>
                                相关性: {row['relevance_reason']}
                            </td>
                            <td>
                                忠: <span class="score">{row['faithfulness_score']}</span><br/>
                                完: <span class="score">{row['completeness_score']}</span><br/>
                                相: <span class="score">{row['relevance_score']}</span>
                            </td>
                        </tr>
            """
            
        html_content += """
                    </tbody>
                </table>
            </div>
        </body>
        </html>
        """
        
        with open(output_file, "w", encoding='utf-8') as f:
            f.write(html_content)

class MainFrame(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, None, title="RAG 智能助手自动化测试工具 v2.1", size=(1200, 800))
        
        self.current_dataset_file = None
        self.current_responses_file = None
        self.current_report_file = None
        
        # 使用 SplitterWindow 分割左右
        self.splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE)
        
        # 左侧 Panel (Debug Log)
        self.debug_panel = wx.Panel(self.splitter)
        debug_sizer = wx.BoxSizer(wx.VERTICAL)
        debug_sizer.Add(wx.StaticText(self.debug_panel, label="Debug 日志 (API & 内部状态):"), 0, wx.ALL, 5)
        
        self.debug_ctrl = wx.TextCtrl(self.debug_panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        self.debug_ctrl.SetFont(wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        self.debug_ctrl.SetBackgroundColour("#F0F0F0")
        
        debug_sizer.Add(self.debug_ctrl, 1, wx.EXPAND | wx.ALL, 5)
        self.debug_panel.SetSizer(debug_sizer)
        
        # 绑定全局 Debug 输出
        global DEBUG_OUTPUT_CTRL
        DEBUG_OUTPUT_CTRL = self.debug_ctrl
        
        # 右侧 Panel (主操作区)
        self.main_panel = wx.Panel(self.splitter)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- 0. 顶部控制栏 ---
        top_bar = wx.BoxSizer(wx.HORIZONTAL)
        self.chk_debug = wx.CheckBox(self.main_panel, label="显示调试日志")
        self.chk_debug.SetValue(False) # 默认不显示
        self.chk_debug.Bind(wx.EVT_CHECKBOX, self.on_toggle_debug)
        
        top_bar.Add(wx.StaticText(self.main_panel, label="RAG 自动化测试工作台"), 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 10)
        top_bar.Add(self.chk_debug, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 10)
        
        main_sizer.Add(top_bar, 0, wx.EXPAND)
        main_sizer.Add(wx.StaticLine(self.main_panel), 0, wx.EXPAND | wx.ALL, 0)

        # --- 1. 知识库配置区 ---
        file_box = wx.StaticBox(self.main_panel, label="1. 知识库配置")
        file_sizer = wx.StaticBoxSizer(file_box, wx.VERTICAL)
        
        # 模式选择
        mode_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.rb_single = wx.RadioButton(self.main_panel, label="单文件模式", style=wx.RB_GROUP)
        self.rb_folder = wx.RadioButton(self.main_panel, label="文件夹模式 (读取 knowledge_base)")
        self.rb_folder.SetValue(True) 
        
        mode_sizer.Add(self.rb_single, 0, wx.ALL, 5)
        mode_sizer.Add(self.rb_folder, 0, wx.ALL, 5)
        file_sizer.Add(mode_sizer, 0, wx.ALL, 5)

        # 路径选择器
        path_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.file_picker = wx.FilePickerCtrl(self.main_panel, message="选择知识库文件", wildcard="Docs|*.txt;*.md;*.json;*.docx;*.pdf;*.xlsx")
        if os.path.exists("NebulaTech_Internal_Strategy_2025.txt"):
            self.file_picker.SetPath(os.path.abspath("NebulaTech_Internal_Strategy_2025.txt"))
            
        self.dir_picker = wx.DirPickerCtrl(self.main_panel, message="选择知识库文件夹")
        if os.path.exists("knowledge_base"):
            self.dir_picker.SetPath(os.path.abspath("knowledge_base"))

        path_sizer.Add(wx.StaticText(self.main_panel, label="路径:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        path_sizer.Add(self.file_picker, 1, wx.EXPAND | wx.ALL, 5)
        path_sizer.Add(self.dir_picker, 1, wx.EXPAND | wx.ALL, 5)
        
        file_sizer.Add(path_sizer, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(file_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # --- 2. 分步执行区 ---
        step_box = wx.StaticBox(self.main_panel, label="2. 评估流程 (Step by Step)")
        step_sizer = wx.StaticBoxSizer(step_box, wx.VERTICAL)
        
        # 步骤 1
        s1_sizer = wx.BoxSizer(wx.HORIZONTAL)
        s1_sizer.Add(wx.StaticText(self.main_panel, label="Step 1: 生成测试用例"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        self.btn_gen = wx.Button(self.main_panel, label="生成测试集 (AI)")
        self.btn_view_data = wx.Button(self.main_panel, label="查看/导出测试集")
        self.btn_view_data.Disable()
        
        s1_sizer.Add(self.btn_gen, 0, wx.ALL, 5)
        s1_sizer.Add(self.btn_view_data, 0, wx.ALL, 5)
        step_sizer.Add(s1_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        step_sizer.Add(wx.StaticLine(self.main_panel), 0, wx.EXPAND | wx.ALL, 5)

        # 步骤 2
        s2_sizer = wx.BoxSizer(wx.HORIZONTAL)
        s2_sizer.Add(wx.StaticText(self.main_panel, label="Step 2: 获取 RAG 回答"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        self.btn_get_resp_sim = wx.Button(self.main_panel, label="模拟执行 (内置RAG)")
        self.btn_get_resp_import = wx.Button(self.main_panel, label="导入外部结果 (JSON)")
        self.btn_get_resp_sim.Disable()
        
        s2_sizer.Add(self.btn_get_resp_sim, 0, wx.ALL, 5)
        s2_sizer.Add(self.btn_get_resp_import, 0, wx.ALL, 5)
        step_sizer.Add(s2_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        step_sizer.Add(wx.StaticLine(self.main_panel), 0, wx.EXPAND | wx.ALL, 5)

        # 步骤 3
        s3_sizer = wx.BoxSizer(wx.HORIZONTAL)
        s3_sizer.Add(wx.StaticText(self.main_panel, label="Step 3: 执行智能评分"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        self.btn_score = wx.Button(self.main_panel, label="开始 AI 评分")
        self.btn_report = wx.Button(self.main_panel, label="打开可视化报告")
        self.btn_score.Disable()
        self.btn_report.Disable()
        
        s3_sizer.Add(self.btn_score, 0, wx.ALL, 5)
        s3_sizer.Add(self.btn_report, 0, wx.ALL, 5)
        step_sizer.Add(s3_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        main_sizer.Add(step_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # 3. 底部：日志输出区
        log_box = wx.StaticBox(self.main_panel, label="执行日志")
        log_sizer = wx.StaticBoxSizer(log_box, wx.VERTICAL)
        self.log_ctrl = wx.TextCtrl(self.main_panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        self.log_ctrl.SetFont(wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        log_sizer.Add(self.log_ctrl, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(log_sizer, 1, wx.EXPAND | wx.ALL, 10)

        self.main_panel.SetSizer(main_sizer)
        
        # 设置 Splitter
        self.splitter.SplitVertically(self.debug_panel, self.main_panel, 300)
        self.splitter.SetMinimumPaneSize(20)
        self.splitter.Unsplit(self.debug_panel) # 默认隐藏左侧
        
        # 事件绑定
        self.Bind(wx.EVT_RADIOBUTTON, self.on_mode_change, self.rb_single)
        self.Bind(wx.EVT_RADIOBUTTON, self.on_mode_change, self.rb_folder)
        
        self.btn_gen.Bind(wx.EVT_BUTTON, self.on_gen)
        self.btn_view_data.Bind(wx.EVT_BUTTON, self.on_view_data)
        self.btn_get_resp_sim.Bind(wx.EVT_BUTTON, self.on_run_sim)
        self.btn_get_resp_import.Bind(wx.EVT_BUTTON, self.on_import_resp)
        self.btn_score.Bind(wx.EVT_BUTTON, self.on_score)
        self.btn_report.Bind(wx.EVT_BUTTON, self.on_view_report)

        # 初始化
        sys.stdout = RedirectText(self.log_ctrl)
        sys.stderr = RedirectText(self.log_ctrl)
        self.on_mode_change(None)
        self.Center()
        print("RAG 测试工具 v2.1 已就绪。请按顺序执行 Step 1 -> 2 -> 3。")

    def on_toggle_debug(self, event):
        if self.chk_debug.GetValue():
            self.splitter.SplitVertically(self.debug_panel, self.main_panel, 300)
        else:
            self.splitter.Unsplit(self.debug_panel)
        self.Layout()

    def on_mode_change(self, event):
        is_folder = self.rb_folder.GetValue()
        self.file_picker.Show(not is_folder)
        self.dir_picker.Show(is_folder)
        self.Layout()

    def get_kb_config(self):
        if self.rb_folder.GetValue():
            path = self.dir_picker.GetPath()
            return path, True, None if os.path.exists(path) else "无效文件夹"
        else:
            path = self.file_picker.GetPath()
            return path, False, None if os.path.exists(path) else "无效文件"

    def on_gen(self, event):
        path, is_dir, err = self.get_kb_config()
        if err: return wx.MessageBox(err, "错误", wx.ICON_ERROR)
        
        # 弹出配置对话框
        dlg = GenerationConfigDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            config = dlg.get_config()
            dlg.Destroy()
            
            self.btn_gen.Disable()
            print(f"--- Step 1: 开始生成测试集 (数量={config['count']}, 难度={config['difficulty']}) ---")
            WorkerThread(self, "generate_cases", kb_path=path, is_dir=is_dir, config=config)
        else:
            dlg.Destroy()

    def on_view_data(self, event):
        if self.current_dataset_file and os.path.exists(self.current_dataset_file):
            viewer = DatasetViewerFrame(self, self.current_dataset_file)
            viewer.Show()
        else:
            wx.MessageBox("无可用测试集", "提示")

    def on_run_sim(self, event):
        path, is_dir, err = self.get_kb_config()
        if err: return wx.MessageBox(err, "错误", wx.ICON_ERROR)
        
        # 弹出风格配置对话框
        dlg = SimulationConfigDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            sim_style = dlg.get_style()
            dlg.Destroy()
            
            self.btn_get_resp_sim.Disable()
            print(f"--- Step 2: 开始模拟 RAG 回答 (风格: {sim_style}) ---")
            WorkerThread(self, "get_responses_sim", kb_path=path, is_dir=is_dir, dataset_file=self.current_dataset_file, sim_style=sim_style)
        else:
            dlg.Destroy()

    def on_import_resp(self, event):
        dlg = wx.FileDialog(self, "导入 RAG 回答 (JSON)", wildcard="JSON files (*.json)|*.json", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.current_responses_file = dlg.GetPath()
            print(f"已导入外部回答文件: {self.current_responses_file}")
            self.btn_score.Enable()
            wx.MessageBox("导入成功！可以开始 Step 3 评分。", "成功")
        dlg.Destroy()

    def on_score(self, event):
        path, is_dir, err = self.get_kb_config()
        
        self.btn_score.Disable()
        print("--- Step 3: 开始智能评分 ---")
        WorkerThread(self, "run_scoring", kb_path=path, is_dir=is_dir, responses_file=self.current_responses_file)

    def on_view_report(self, event):
        if self.current_report_file and os.path.exists(self.current_report_file):
            webbrowser.open(f"file:///{os.path.abspath(self.current_report_file)}")
        else:
            wx.MessageBox("报告未生成", "错误")

    def on_task_done(self, task_type, success, message, result_data):
        if task_type == "generate_cases":
            self.btn_gen.Enable()
            if success:
                self.current_dataset_file = result_data.get("dataset_file")
                self.btn_view_data.Enable()
                self.btn_get_resp_sim.Enable()
                print(f"下一步：请执行 Step 2 获取回答。")

        elif task_type == "get_responses_sim":
            self.btn_get_resp_sim.Enable()
            if success:
                self.current_responses_file = result_data.get("responses_file")
                self.btn_score.Enable()
                print(f"下一步：请执行 Step 3 评分。")

        elif task_type == "run_scoring":
            self.btn_score.Enable()
            if success:
                self.current_report_file = result_data.get("report_file")
                self.btn_report.Enable()
                wx.MessageBox("评估全流程完成！", "成功")

        if not success:
            print(f"任务失败: {message}")
            wx.MessageBox(f"出错: {message}", "错误", wx.ICON_ERROR)

if __name__ == "__main__":
    app = wx.App()
    frame = MainFrame()
    frame.Show()
    app.MainLoop()
