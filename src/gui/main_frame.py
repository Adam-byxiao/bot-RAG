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

# TODO: 建议移至环境变量
API_KEY = "sk-98201e2e39b840e3b73d9409b4a6425d"

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
        
        doc_content = read_knowledge_base(kb_path, is_dir)
        if not doc_content: raise Exception("知识库为空")
        
        print(f"正在生成测试集 (Count={config.get('count')})...")
        test_cases = generate_test_cases(client, doc_content, config)
        
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
            print(f"[{i+1}/{total}] Question: {case['question']}")
            start = time.time()
            ans = simulator.generate_response(case['question'])
            latency = time.time() - start
            
            rec = case.copy()
            rec['rag_answer'] = ans
            rec['latency'] = latency
            rec['sim_style'] = sim_style
            responses.append(rec)
            
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

class MainFrame(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, None, title="RAG 智能助手自动化测试工具 v1.0", size=(1200, 800))
        
        self.current_dataset_file = None
        self.current_responses_file = None
        self.current_report_file = None
        
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
        
        # 1. Config
        file_box = wx.StaticBox(self.main_panel, label="1. 知识库配置")
        file_sizer = wx.StaticBoxSizer(file_box, wx.VERTICAL)
        
        mode_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.rb_single = wx.RadioButton(self.main_panel, label="单文件", style=wx.RB_GROUP)
        self.rb_folder = wx.RadioButton(self.main_panel, label="文件夹")
        self.rb_folder.SetValue(True)
        mode_sizer.Add(self.rb_single, 0, wx.ALL, 5)
        mode_sizer.Add(self.rb_folder, 0, wx.ALL, 5)
        file_sizer.Add(mode_sizer, 0, wx.ALL, 5)
        
        path_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.file_picker = wx.FilePickerCtrl(self.main_panel, wildcard="Docs|*.txt;*.md;*.json;*.docx;*.pdf;*.xlsx")
        self.dir_picker = wx.DirPickerCtrl(self.main_panel)
        if os.path.exists("knowledge_base"): self.dir_picker.SetPath(os.path.abspath("knowledge_base"))
        
        path_sizer.Add(wx.StaticText(self.main_panel, label="路径:"), 0, wx.CENTER|wx.ALL, 5)
        path_sizer.Add(self.file_picker, 1, wx.EXPAND|wx.ALL, 5)
        path_sizer.Add(self.dir_picker, 1, wx.EXPAND|wx.ALL, 5)
        file_sizer.Add(path_sizer, 0, wx.EXPAND|wx.ALL, 5)
        main_sizer.Add(file_sizer, 0, wx.EXPAND|wx.ALL, 10)
        
        # 2. Steps
        step_box = wx.StaticBox(self.main_panel, label="2. 执行流程")
        step_sizer = wx.StaticBoxSizer(step_box, wx.VERTICAL)
        
        # Step 1
        s1 = wx.BoxSizer(wx.HORIZONTAL)
        s1.Add(wx.StaticText(self.main_panel, label="Step 1: 生成用例"), 0, wx.CENTER|wx.ALL, 5)
        self.btn_gen = wx.Button(self.main_panel, label="生成 (AI)")
        self.btn_view = wx.Button(self.main_panel, label="查看")
        self.btn_view.Disable()
        s1.Add(self.btn_gen, 0, wx.ALL, 5)
        s1.Add(self.btn_view, 0, wx.ALL, 5)
        step_sizer.Add(s1, 0, wx.EXPAND|wx.ALL, 5)
        step_sizer.Add(wx.StaticLine(self.main_panel), 0, wx.EXPAND)
        
        # Step 2
        s2 = wx.BoxSizer(wx.HORIZONTAL)
        s2.Add(wx.StaticText(self.main_panel, label="Step 2: 获取回答"), 0, wx.CENTER|wx.ALL, 5)
        self.btn_sim = wx.Button(self.main_panel, label="模拟")
        self.btn_imp = wx.Button(self.main_panel, label="导入")
        self.btn_sim.Disable()
        s2.Add(self.btn_sim, 0, wx.ALL, 5)
        s2.Add(self.btn_imp, 0, wx.ALL, 5)
        step_sizer.Add(s2, 0, wx.EXPAND|wx.ALL, 5)
        step_sizer.Add(wx.StaticLine(self.main_panel), 0, wx.EXPAND)
        
        # Step 3
        s3 = wx.BoxSizer(wx.HORIZONTAL)
        s3.Add(wx.StaticText(self.main_panel, label="Step 3: 智能评分"), 0, wx.CENTER|wx.ALL, 5)
        self.btn_score = wx.Button(self.main_panel, label="评分")
        self.btn_rpt = wx.Button(self.main_panel, label="报告")
        self.btn_score.Disable()
        self.btn_rpt.Disable()
        s3.Add(self.btn_score, 0, wx.ALL, 5)
        s3.Add(self.btn_rpt, 0, wx.ALL, 5)
        step_sizer.Add(s3, 0, wx.EXPAND|wx.ALL, 5)
        
        main_sizer.Add(step_sizer, 0, wx.EXPAND|wx.ALL, 10)
        
        # Log
        log_box = wx.StaticBox(self.main_panel, label="Log")
        log_sizer = wx.StaticBoxSizer(log_box, wx.VERTICAL)
        self.log_ctrl = wx.TextCtrl(self.main_panel, style=wx.TE_MULTILINE|wx.TE_READONLY)
        log_sizer.Add(self.log_ctrl, 1, wx.EXPAND|wx.ALL, 5)
        main_sizer.Add(log_sizer, 1, wx.EXPAND|wx.ALL, 10)
        
        self.main_panel.SetSizer(main_sizer)
        
        self.splitter.SplitVertically(self.debug_panel, self.main_panel, 300)
        self.splitter.Unsplit(self.debug_panel)
        
        # Bindings
        self.Bind(wx.EVT_RADIOBUTTON, self.on_mode, self.rb_single)
        self.Bind(wx.EVT_RADIOBUTTON, self.on_mode, self.rb_folder)
        self.btn_gen.Bind(wx.EVT_BUTTON, self.on_gen)
        self.btn_view.Bind(wx.EVT_BUTTON, self.on_view)
        self.btn_sim.Bind(wx.EVT_BUTTON, self.on_sim)
        self.btn_imp.Bind(wx.EVT_BUTTON, self.on_imp)
        self.btn_score.Bind(wx.EVT_BUTTON, self.on_score)
        self.btn_rpt.Bind(wx.EVT_BUTTON, self.on_rpt)
        
        # Redirect
        sys.stdout = RedirectText(self.log_ctrl)
        sys.stderr = RedirectText(self.log_ctrl)
        self.on_mode(None)
        self.Center()
        print("RAG Tool v1.0 Initialized.")

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
        self.Layout()

    def get_config(self):
        if self.rb_folder.GetValue():
            path = self.dir_picker.GetPath()
            return path, True, None if os.path.exists(path) else "Invalid Folder"
        else:
            path = self.file_picker.GetPath()
            return path, False, None if os.path.exists(path) else "Invalid File"

    def on_gen(self, evt):
        path, is_dir, err = self.get_config()
        if err: return wx.MessageBox(err)
        
        dlg = GenerationConfigDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            cfg = dlg.get_config()
            self.btn_gen.Disable()
            print("Generating Cases...")
            WorkerThread(self, "generate_cases", kb_path=path, is_dir=is_dir, config=cfg)
        dlg.Destroy()

    def on_view(self, evt):
        if self.current_dataset_file:
            DatasetViewerFrame(self, self.current_dataset_file).Show()

    def on_sim(self, evt):
        path, is_dir, err = self.get_config()
        if err: return wx.MessageBox(err)
        
        dlg = SimulationConfigDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            style = dlg.get_style()
            self.btn_sim.Disable()
            print(f"Simulating ({style})...")
            WorkerThread(self, "get_responses_sim", kb_path=path, is_dir=is_dir, dataset_file=self.current_dataset_file, sim_style=style)
        dlg.Destroy()

    def on_imp(self, evt):
        dlg = wx.FileDialog(self, "Import JSON", wildcard="JSON|*.json", style=wx.FD_OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.current_responses_file = dlg.GetPath()
            self.btn_score.Enable()
            print(f"Imported: {self.current_responses_file}")
        dlg.Destroy()

    def on_score(self, evt):
        path, is_dir, err = self.get_config()
        self.btn_score.Disable()
        print("Scoring...")
        WorkerThread(self, "run_scoring", kb_path=path, is_dir=is_dir, responses_file=self.current_responses_file)

    def on_rpt(self, evt):
        if self.current_report_file:
            webbrowser.open(f"file:///{os.path.abspath(self.current_report_file)}")

    def on_task_done(self, task, success, msg, res):
        if task == "generate_cases":
            self.btn_gen.Enable()
            if success:
                self.current_dataset_file = res['dataset_file']
                self.btn_view.Enable()
                self.btn_sim.Enable()
        elif task == "get_responses_sim":
            self.btn_sim.Enable()
            if success:
                self.current_responses_file = res['responses_file']
                self.btn_score.Enable()
        elif task == "run_scoring":
            self.btn_score.Enable()
            if success:
                self.current_report_file = res['report_file']
                self.btn_rpt.Enable()
                wx.MessageBox("Done!", "Success")
        
        if not success:
            print(f"Error: {msg}")
            wx.MessageBox(msg, "Error", wx.ICON_ERROR)
