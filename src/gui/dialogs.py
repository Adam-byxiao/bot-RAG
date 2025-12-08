import wx

class GenerationConfigDialog(wx.Dialog):
    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, title="测试集生成配置", size=(500, 600))
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Scrolled Window
        self.scrolled_panel = wx.ScrolledWindow(self, -1, style=wx.TAB_TRAVERSAL)
        self.scrolled_panel.SetScrollRate(10, 10)
        
        content_sizer = wx.BoxSizer(wx.VERTICAL)
        
        content_sizer.Add(wx.StaticText(self.scrolled_panel, label="生成数量 (个):"), 0, wx.ALL, 10)
        self.spin_count = wx.SpinCtrl(self.scrolled_panel, value="5", min=1, max=50)
        content_sizer.Add(self.spin_count, 0, wx.ALL | wx.EXPAND, 10)
        
        content_sizer.Add(wx.StaticText(self.scrolled_panel, label="难度级别:"), 0, wx.ALL, 10)
        self.choice_diff = wx.Choice(self.scrolled_panel, choices=[
            "混合 (随机)",
            "L1: 简单 (单文档事实检索)",
            "L2: 中等 (跨段落/多文档整合)",
            "L3: 困难 (语义变体/隐含推理)",
            "L4: 极难 (干扰项/无答案/冲突)"
        ])
        self.choice_diff.SetSelection(0)
        content_sizer.Add(self.choice_diff, 0, wx.ALL | wx.EXPAND, 10)
        
        content_sizer.Add(wx.StaticText(self.scrolled_panel, label="侧重点:"), 0, wx.ALL, 10)
        self.check_fact = wx.CheckBox(self.scrolled_panel, label="事实查证 (Fact Checking)")
        self.check_fact.SetValue(True)
        self.check_multihop = wx.CheckBox(self.scrolled_panel, label="跨段落/多文档综合 (Multi-hop)")
        self.check_semantic = wx.CheckBox(self.scrolled_panel, label="语义变体与缩写 (Semantics)")
        self.check_hybrid = wx.CheckBox(self.scrolled_panel, label="常识混合与冲突 (Hybrid/Conflict)")
        self.check_negative = wx.CheckBox(self.scrolled_panel, label="抗干扰/无答案 (Negative)")
        
        content_sizer.Add(self.check_fact, 0, wx.ALL, 5)
        content_sizer.Add(self.check_multihop, 0, wx.ALL, 5)
        content_sizer.Add(self.check_semantic, 0, wx.ALL, 5)
        content_sizer.Add(self.check_hybrid, 0, wx.ALL, 5)
        content_sizer.Add(self.check_negative, 0, wx.ALL, 5)

        self.check_random = wx.CheckBox(self.scrolled_panel, label="随机截取长文档 (Random Sampling)")
        content_sizer.Add(self.check_random, 0, wx.ALL, 5)
        
        self.scrolled_panel.SetSizer(content_sizer)
        
        main_sizer.Add(self.scrolled_panel, 1, wx.EXPAND | wx.ALL, 5)
        
        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 15)
        
        self.SetSizer(main_sizer)
        self.Layout()

    def get_config(self):
        focus = []
        if self.check_fact.GetValue(): focus.append("事实查证")
        if self.check_multihop.GetValue(): focus.append("跨段落/多文档综合")
        if self.check_semantic.GetValue(): focus.append("语义变体与缩写")
        if self.check_hybrid.GetValue(): focus.append("常识混合与冲突")
        if self.check_negative.GetValue(): focus.append("抗干扰/无答案")
        
        return {
            "count": self.spin_count.GetValue(),
            "difficulty": self.choice_diff.GetStringSelection(),
            "focus": ", ".join(focus),
            "random_sampling": self.check_random.GetValue()
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
