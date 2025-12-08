import wx
import wx.html
import os
import json
import threading
import pandas as pd
import time
import webbrowser
import datetime
import sys

from src.core.llm_client import DeepSeekClient
from src.core.simulator import AdvancedRAGSimulator
from src.core.evaluator import Evaluator
from src.core.generator import generate_test_cases
from src.utils.logger import set_debug_ctrl, RedirectText
from src.utils.file_loader import read_knowledge_base
from src.utils.visualizer import generate_html_report
from src.gui.dialogs import GenerationConfigDialog, SimulationConfigDialog
from src.gui.viewer import DatasetViewerFrame

# 优先从环境变量获取，如果环境变量不存在则使用默认空字符串
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

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

    def run_generate_cases(self):
        client = DeepSeekClient(API_KEY)
        kb_path = self.kwargs.get('kb_path')
        is_dir = self.kwargs.get('is_dir', False)
        config = self.kwargs.get('config', {})
        
        # 如果启用了随机采样，同时打乱文件读取顺序，保证多文档时的随机性
        shuffle_files = config.get('random_sampling', False)
        doc_content = read_knowledge_base(kb_path, is_dir, shuffle_files=shuffle_files)
        if not doc_content: raise Exception("知识库为空")
        
        print(f"正在生成测试集 (Count={config.get('count')})...")
        
        # 定义进度回调
        def progress_callback(current, total):
            wx.CallAfter(self.notify_window.update_progress, f"正在生成 ({current}/{total})...")
            
        test_cases = generate_test_cases(client, doc_content, config, progress_callback)
        
        # 确保目录存在
        output_dir = "outputs/datasets"
        os.makedirs(output_dir, exist_ok=True)
        
        ts = self.get_timestamp()
        output_file = f"{output_dir}/test_dataset_{ts}.json"
        
        with open(output_file, "w", encoding='utf-8') as f:
            json.dump(test_cases, f, ensure_ascii=False, indent=2)
            
        print(f"测试集已保存至 {output_file}")
        return {"dataset_file": output_file}

    def run_get_responses_sim(self):
        client = DeepSeekClient(API_KEY)
        kb_path = self.kwargs.get('kb_path')
        is_dir = self.kwargs.get('is_dir', False)
        dataset_file = self.kwargs.get('dataset_file')
        sim_style = self.kwargs.get('sim_style', 'normal')
        
        doc_content = read_knowledge_base(kb_path, is_dir)
        
        with open(dataset_file, 'r', encoding='utf-8') as f:
            test_cases = json.load(f)
            
        simulator = AdvancedRAGSimulator(client, doc_content, style=sim_style)
        responses = []
        total = len(test_cases)
        
        print(f"开始模拟回答 (Style={sim_style})...")
        for i, case in enumerate(test_cases):
            msg = f"[{i+1}/{total}] Question: {case['question']}"
            print(msg)
            wx.CallAfter(self.notify_window.update_progress, f"正在模拟 ({i+1}/{total})...")
            
            rec = case.copy()
            rec['sim_style'] = sim_style
            
            try:
                start = time.time()
                ans = simulator.generate_response(case['question'])
                latency = time.time() - start
                
                rec['rag_answer'] = ans
                rec['latency'] = latency
                responses.append(rec)
            except Exception as e:
                print(f"Error simulating case {i+1}: {e}")
                # Skip adding failed simulations to avoid error bars in report
                continue
            
        # 确保目录存在
        output_dir = "outputs/responses"
        os.makedirs(output_dir, exist_ok=True)
        
        ts = self.get_timestamp()
        output_file = f"{output_dir}/rag_responses_{ts}.json"
        
        with open(output_file, "w", encoding='utf-8') as f:
            json.dump(responses, f, ensure_ascii=False, indent=2)
            
        print(f"回答已保存至 {output_file}")
        return {"responses_file": output_file}

    def run_scoring(self):
        client = DeepSeekClient(API_KEY)
        kb_path = self.kwargs.get('kb_path')
        is_dir = self.kwargs.get('is_dir', False)
        responses_file = self.kwargs.get('responses_file')
        
        doc_content = read_knowledge_base(kb_path, is_dir)
        with open(responses_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        evaluator = Evaluator(client)
        results = []
        total = len(data)
        
        print(f"开始评分...")
        for i, item in enumerate(data):
            print(f"[{i+1}/{total}] Scoring: {item['question']}")
            score = evaluator.evaluate(item, doc_content)
            rec = item.copy()
            rec.update(score)
            results.append(rec)
            
        # 确保目录存在
        output_dir = "outputs/reports"
        os.makedirs(output_dir, exist_ok=True)
        
        ts = self.get_timestamp()
        json_file = f"{output_dir}/evaluation_results_{ts}.json"
        excel_file = f"{output_dir}/evaluation_results_{ts}.xlsx"
        report_file = f"{output_dir}/evaluation_report_{ts}.html"
        
        df = pd.DataFrame(results)
        df.to_json(json_file, orient="records", force_ascii=False, indent=2)
        df.to_excel(excel_file, index=False)
        generate_html_report(df, report_file, ts)
        
        print(f"评分完成，报告已生成: {report_file}")
        return {"report_file": report_file}

class GeneratorPanel(wx.Panel):
    def __init__(self, parent, get_kb_config):
        wx.Panel.__init__(self, parent)
        self.get_kb_config = get_kb_config
        self.current_dataset_file = None
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Controls
        ctrl_box = wx.StaticBox(self, label="操作区")
        ctrl_sizer = wx.StaticBoxSizer(ctrl_box, wx.HORIZONTAL)
        
        self.btn_gen = wx.Button(self, label="生成测试用例 (AI)")
        self.btn_view = wx.Button(self, label="预览/编辑")
        self.btn_export = wx.Button(self, label="导出 JSON...")
        
        self.btn_view.Disable()
        self.btn_export.Disable()
        
        ctrl_sizer.Add(self.btn_gen, 0, wx.ALL, 5)
        ctrl_sizer.Add(self.btn_view, 0, wx.ALL, 5)
        ctrl_sizer.Add(self.btn_export, 0, wx.ALL, 5)
        
        sizer.Add(ctrl_sizer, 0, wx.EXPAND|wx.ALL, 10)
        
        # Info
        self.info_txt = wx.StaticText(self, label="请点击生成按钮开始...")
        sizer.Add(self.info_txt, 0, wx.ALL, 15)
        
        self.SetSizer(sizer)
        
        # Bindings
        self.btn_gen.Bind(wx.EVT_BUTTON, self.on_gen)
        self.btn_view.Bind(wx.EVT_BUTTON, self.on_view)
        self.btn_export.Bind(wx.EVT_BUTTON, self.on_export)

    def update_progress(self, msg):
        self.info_txt.SetLabel(msg)

    def on_gen(self, evt):
        if not API_KEY:
            return wx.MessageBox("未找到 DEEPSEEK_API_KEY 环境变量！\n请设置环境变量 'DEEPSEEK_API_KEY' 后重启程序。", "错误", wx.ICON_ERROR)

        path, is_dir, err = self.get_kb_config()
        if err: return wx.MessageBox(err, "错误")
        
        dlg = GenerationConfigDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            cfg = dlg.get_config()
            self.btn_gen.Disable()
            self.info_txt.SetLabel("正在生成，请查看日志...")
            WorkerThread(self, "generate_cases", kb_path=path, is_dir=is_dir, config=cfg)
        dlg.Destroy()

    def on_view(self, evt):
        if self.current_dataset_file:
            DatasetViewerFrame(self, self.current_dataset_file).Show()

    def on_export(self, evt):
        if not self.current_dataset_file: return
        
        dlg = wx.FileDialog(self, "导出测试集", wildcard="JSON files (*.json)|*.json",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            try:
                import shutil
                shutil.copy2(self.current_dataset_file, path)
                wx.MessageBox(f"导出成功: {path}", "成功")
            except Exception as e:
                wx.MessageBox(f"导出失败: {e}", "错误")
        dlg.Destroy()

    def on_task_done(self, task, success, msg, res):
        self.btn_gen.Enable()
        if success:
            self.current_dataset_file = res['dataset_file']
            self.btn_view.Enable()
            self.btn_export.Enable()
            self.info_txt.SetLabel(f"生成完成: {os.path.basename(self.current_dataset_file)}")
        else:
            self.info_txt.SetLabel(f"生成失败: {msg}")
            wx.MessageBox(msg, "Error", wx.ICON_ERROR)

class SimulatorPanel(wx.Panel):
    def __init__(self, parent, get_kb_config):
        wx.Panel.__init__(self, parent)
        self.get_kb_config = get_kb_config
        self.current_responses_file = None
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Input: Dataset Selection
        input_box = wx.StaticBox(self, label="1. 输入: 测试用例集")
        input_sizer = wx.StaticBoxSizer(input_box, wx.HORIZONTAL)
        
        self.dataset_picker = wx.FilePickerCtrl(self, message="选择测试集JSON", wildcard="JSON|*.json")
        input_sizer.Add(wx.StaticText(self, label="文件:"), 0, wx.CENTER|wx.ALL, 5)
        input_sizer.Add(self.dataset_picker, 1, wx.EXPAND|wx.ALL, 5)
        
        sizer.Add(input_sizer, 0, wx.EXPAND|wx.ALL, 10)
        
        # Action
        act_box = wx.StaticBox(self, label="2. 执行模拟")
        act_sizer = wx.StaticBoxSizer(act_box, wx.HORIZONTAL)
        
        self.btn_sim = wx.Button(self, label="开始模拟 (AI)")
        self.btn_export = wx.Button(self, label="导出回答...")
        self.btn_export.Disable()
        
        act_sizer.Add(self.btn_sim, 0, wx.ALL, 5)
        act_sizer.Add(self.btn_export, 0, wx.ALL, 5)
        
        sizer.Add(act_sizer, 0, wx.EXPAND|wx.ALL, 10)
        
        # Info
        self.info_txt = wx.StaticText(self, label="准备就绪")
        sizer.Add(self.info_txt, 0, wx.ALL, 15)
        
        self.SetSizer(sizer)
        
        self.btn_sim.Bind(wx.EVT_BUTTON, self.on_sim)
        self.btn_export.Bind(wx.EVT_BUTTON, self.on_export)

    def update_progress(self, msg):
        self.info_txt.SetLabel(msg)

    def on_sim(self, evt):
        if not API_KEY:
            return wx.MessageBox("未找到 DEEPSEEK_API_KEY 环境变量！\n请设置环境变量 'DEEPSEEK_API_KEY' 后重启程序。", "错误", wx.ICON_ERROR)

        dataset_file = self.dataset_picker.GetPath()
        if not dataset_file or not os.path.exists(dataset_file):
            return wx.MessageBox("请先选择有效的测试用例集文件", "提示")
            
        path, is_dir, err = self.get_kb_config()
        if err: return wx.MessageBox(err, "错误")
        
        dlg = SimulationConfigDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            style = dlg.get_style()
            self.btn_sim.Disable()
            self.info_txt.SetLabel(f"正在模拟 ({style})...")
            WorkerThread(self, "get_responses_sim", kb_path=path, is_dir=is_dir, dataset_file=dataset_file, sim_style=style)
        dlg.Destroy()

    def on_export(self, evt):
        if not self.current_responses_file: return
        dlg = wx.FileDialog(self, "导出回答", wildcard="JSON files (*.json)|*.json",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            try:
                import shutil
                shutil.copy2(self.current_responses_file, path)
                wx.MessageBox(f"导出成功: {path}", "成功")
            except Exception as e:
                wx.MessageBox(f"导出失败: {e}", "错误")
        dlg.Destroy()

    def on_task_done(self, task, success, msg, res):
        self.btn_sim.Enable()
        if success:
            self.current_responses_file = res['responses_file']
            self.btn_export.Enable()
            self.info_txt.SetLabel(f"模拟完成: {os.path.basename(self.current_responses_file)}")
        else:
            self.info_txt.SetLabel(f"模拟失败: {msg}")
            wx.MessageBox(msg, "Error", wx.ICON_ERROR)

class EvaluatorPanel(wx.Panel):
    def __init__(self, parent, get_kb_config):
        wx.Panel.__init__(self, parent)
        self.get_kb_config = get_kb_config
        self.current_report_file = None
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Input
        input_box = wx.StaticBox(self, label="1. 输入: 回答结果")
        input_sizer = wx.StaticBoxSizer(input_box, wx.HORIZONTAL)
        
        self.resp_picker = wx.FilePickerCtrl(self, message="选择回答集JSON", wildcard="JSON|*.json")
        input_sizer.Add(wx.StaticText(self, label="文件:"), 0, wx.CENTER|wx.ALL, 5)
        input_sizer.Add(self.resp_picker, 1, wx.EXPAND|wx.ALL, 5)
        
        sizer.Add(input_sizer, 0, wx.EXPAND|wx.ALL, 10)
        
        # Action
        act_box = wx.StaticBox(self, label="2. 执行评分")
        act_sizer = wx.StaticBoxSizer(act_box, wx.HORIZONTAL)
        
        self.btn_score = wx.Button(self, label="开始评分 (AI)")
        self.btn_rpt = wx.Button(self, label="打开报告")
        self.btn_rpt.Disable()
        
        act_sizer.Add(self.btn_score, 0, wx.ALL, 5)
        act_sizer.Add(self.btn_rpt, 0, wx.ALL, 5)
        
        sizer.Add(act_sizer, 0, wx.EXPAND|wx.ALL, 10)
        
        # Info
        self.info_txt = wx.StaticText(self, label="准备就绪")
        sizer.Add(self.info_txt, 0, wx.ALL, 15)
        
        self.SetSizer(sizer)
        
        self.btn_score.Bind(wx.EVT_BUTTON, self.on_score)
        self.btn_rpt.Bind(wx.EVT_BUTTON, self.on_rpt)

    def on_score(self, evt):
        if not API_KEY:
            return wx.MessageBox("未找到 DEEPSEEK_API_KEY 环境变量！\n请设置环境变量 'DEEPSEEK_API_KEY' 后重启程序。", "错误", wx.ICON_ERROR)

        resp_file = self.resp_picker.GetPath()
        if not resp_file or not os.path.exists(resp_file):
            return wx.MessageBox("请先选择有效的回答集文件", "提示")
            
        path, is_dir, err = self.get_kb_config()
        # 评分阶段知识库非必须？但evaluator需要doc_content作为背景文档片段
        if err: return wx.MessageBox(err, "错误")
        
        self.btn_score.Disable()
        self.info_txt.SetLabel("正在评分...")
        WorkerThread(self, "run_scoring", kb_path=path, is_dir=is_dir, responses_file=resp_file)

    def on_rpt(self, evt):
        if self.current_report_file:
            webbrowser.open(f"file:///{os.path.abspath(self.current_report_file)}")

    def on_task_done(self, task, success, msg, res):
        self.btn_score.Enable()
        if success:
            self.current_report_file = res['report_file']
            self.btn_rpt.Enable()
            self.info_txt.SetLabel(f"评分完成，报告已生成")
            wx.MessageBox("评分完成！", "Success")
        else:
            self.info_txt.SetLabel(f"评分失败: {msg}")
            wx.MessageBox(msg, "Error", wx.ICON_ERROR)

class MainFrame(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, None, title="RAG 智能助手自动化测试工具 v2.0", size=(1200, 800))
        
        self.splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE)
        
        # Left Panel (Debug)
        self.debug_panel = wx.Panel(self.splitter)
        debug_sizer = wx.BoxSizer(wx.VERTICAL)
        debug_sizer.Add(wx.StaticText(self.debug_panel, label="Debug Log:"), 0, wx.ALL, 5)
        self.debug_ctrl = wx.TextCtrl(self.debug_panel, style=wx.TE_MULTILINE|wx.TE_READONLY)
        self.debug_ctrl.SetFont(wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        self.debug_ctrl.SetBackgroundColour("#F0F0F0")
        debug_sizer.Add(self.debug_ctrl, 1, wx.EXPAND|wx.ALL, 5)
        self.debug_panel.SetSizer(debug_sizer)
        
        set_debug_ctrl(self.debug_ctrl)
        
        # Right Panel (Main)
        self.main_panel = wx.Panel(self.splitter)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Top Bar
        top_bar = wx.BoxSizer(wx.HORIZONTAL)
        self.chk_debug = wx.CheckBox(self.main_panel, label="显示调试日志")
        self.chk_debug.Bind(wx.EVT_CHECKBOX, self.on_toggle_debug)
        top_bar.Add(wx.StaticText(self.main_panel, label="RAG 测试工作台"), 1, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 10)
        top_bar.Add(self.chk_debug, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 10)
        main_sizer.Add(top_bar, 0, wx.EXPAND)
        main_sizer.Add(wx.StaticLine(self.main_panel), 0, wx.EXPAND)
        
        # 1. Global Config (Knowledge Base)
        kb_box = wx.StaticBox(self.main_panel, label="全局设置：知识库路径")
        kb_sizer = wx.StaticBoxSizer(kb_box, wx.VERTICAL)
        
        mode_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.rb_single = wx.RadioButton(self.main_panel, label="单文件", style=wx.RB_GROUP)
        self.rb_folder = wx.RadioButton(self.main_panel, label="文件夹")
        self.rb_folder.SetValue(True)
        mode_sizer.Add(self.rb_single, 0, wx.ALL, 5)
        mode_sizer.Add(self.rb_folder, 0, wx.ALL, 5)
        kb_sizer.Add(mode_sizer, 0, wx.ALL, 5)
        
        path_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.file_picker = wx.FilePickerCtrl(self.main_panel, wildcard="Docs|*.txt;*.md;*.json;*.docx;*.pdf;*.xlsx")
        self.dir_picker = wx.DirPickerCtrl(self.main_panel)
        if os.path.exists("knowledge_base"): self.dir_picker.SetPath(os.path.abspath("knowledge_base"))
        
        path_sizer.Add(wx.StaticText(self.main_panel, label="路径:"), 0, wx.CENTER|wx.ALL, 5)
        path_sizer.Add(self.file_picker, 1, wx.EXPAND|wx.ALL, 5)
        path_sizer.Add(self.dir_picker, 1, wx.EXPAND|wx.ALL, 5)
        kb_sizer.Add(path_sizer, 0, wx.EXPAND|wx.ALL, 5)
        main_sizer.Add(kb_sizer, 0, wx.EXPAND|wx.ALL, 10)
        
        # 2. Tabs (Modular Workflow)
        self.notebook = wx.Notebook(self.main_panel)
        
        self.tab_gen = GeneratorPanel(self.notebook, self.get_config)
        self.tab_sim = SimulatorPanel(self.notebook, self.get_config)
        self.tab_eval = EvaluatorPanel(self.notebook, self.get_config)
        
        self.notebook.AddPage(self.tab_gen, "1. 生成测试集")
        self.notebook.AddPage(self.tab_sim, "2. 模拟回答")
        self.notebook.AddPage(self.tab_eval, "3. 评分报告")
        
        main_sizer.Add(self.notebook, 1, wx.EXPAND|wx.ALL, 10)
        
        # Log
        log_box = wx.StaticBox(self.main_panel, label="Log")
        log_sizer = wx.StaticBoxSizer(log_box, wx.VERTICAL)
        self.log_ctrl = wx.TextCtrl(self.main_panel, style=wx.TE_MULTILINE|wx.TE_READONLY, size=(-1, 100))
        log_sizer.Add(self.log_ctrl, 1, wx.EXPAND|wx.ALL, 5)
        main_sizer.Add(log_sizer, 0, wx.EXPAND|wx.ALL, 10)
        
        self.main_panel.SetSizer(main_sizer)
        
        self.splitter.SplitVertically(self.debug_panel, self.main_panel, 300)
        self.splitter.Unsplit(self.debug_panel)
        
        # Bindings
        self.Bind(wx.EVT_RADIOBUTTON, self.on_mode, self.rb_single)
        self.Bind(wx.EVT_RADIOBUTTON, self.on_mode, self.rb_folder)
        
        # Redirect
        sys.stdout = RedirectText(self.log_ctrl)
        sys.stderr = RedirectText(self.log_ctrl)
        self.on_mode(None)
        self.Center()
        print("RAG Tool v2.0 Initialized.")

    def on_toggle_debug(self, event):
        if self.chk_debug.GetValue():
            self.splitter.SplitVertically(self.debug_panel, self.main_panel, 300)
        else:
            self.splitter.Unsplit(self.debug_panel)
        self.Layout()

    def on_mode(self, event):
        is_folder = self.rb_folder.GetValue()
        self.file_picker.Show(not is_folder)
        self.dir_picker.Show(is_folder)
        self.main_panel.Layout()

    def get_config(self):
        if self.rb_folder.GetValue():
            path = self.dir_picker.GetPath()
            return path, True, None if os.path.exists(path) else "Invalid Folder"
        else:
            path = self.file_picker.GetPath()
            return path, False, None if os.path.exists(path) else "Invalid File"
