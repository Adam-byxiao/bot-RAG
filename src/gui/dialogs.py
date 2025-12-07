import wx

class GenerationConfigDialog(wx.Dialog):
    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, title="测试集生成配置", size=(450, 400))
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        sizer.Add(wx.StaticText(self, label="生成数量 (个):"), 0, wx.ALL, 10)
        self.spin_count = wx.SpinCtrl(self, value="5", min=1, max=50)
        sizer.Add(self.spin_count, 0, wx.ALL | wx.EXPAND, 10)
        
        sizer.Add(wx.StaticText(self, label="难度级别:"), 0, wx.ALL, 10)
        self.choice_diff = wx.Choice(self, choices=["混合 (默认)", "简单 (直接事实)", "困难 (多跳推理/冲突)"])
        self.choice_diff.SetSelection(0)
        sizer.Add(self.choice_diff, 0, wx.ALL | wx.EXPAND, 10)
        
        sizer.Add(wx.StaticText(self, label="侧重点:"), 0, wx.ALL, 10)
        self.check_fact = wx.CheckBox(self, label="事实查证")
        self.check_fact.SetValue(True)
        self.check_reasoning = wx.CheckBox(self, label="逻辑推理")
        self.check_negative = wx.CheckBox(self, label="抗干扰/无答案")
        
        sizer.Add(self.check_fact, 0, wx.ALL, 5)
        sizer.Add(self.check_reasoning, 0, wx.ALL, 5)
        sizer.Add(self.check_negative, 0, wx.ALL, 5)
        
        sizer.Add((0, 0), 1, wx.EXPAND)
        
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
        sizer.Add(wx.StaticText(self, label="选择模拟器的回答风格:"), 0, wx.ALL, 10)
        
        self.rb_normal = wx.RadioButton(self, label="标准模式 (Normal)", style=wx.RB_GROUP)
        self.rb_hallucination = wx.RadioButton(self, label="幻觉模式 (Hallucination)")
        self.rb_verbose = wx.RadioButton(self, label="冗长模式 (Verbose)")
        self.rb_mixed = wx.RadioButton(self, label="混合模式 (Mixed)")
        
        sizer.Add(self.rb_normal, 0, wx.ALL, 5)
        sizer.Add(self.rb_hallucination, 0, wx.ALL, 5)
        sizer.Add(self.rb_verbose, 0, wx.ALL, 5)
        sizer.Add(self.rb_mixed, 0, wx.ALL, 5)
        
        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        self.SetSizer(sizer)

    def get_style(self):
        if self.rb_hallucination.GetValue(): return "hallucination"
        if self.rb_verbose.GetValue(): return "verbose"
        if self.rb_mixed.GetValue(): return "mixed"
        return "normal"
