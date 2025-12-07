import wx
import datetime

# 全局 Debug 输出函数 (将在 MainFrame 中被绑定)
DEBUG_OUTPUT_CTRL = None

def set_debug_ctrl(ctrl):
    global DEBUG_OUTPUT_CTRL
    DEBUG_OUTPUT_CTRL = ctrl

def log_debug(message):
    if DEBUG_OUTPUT_CTRL:
        # 确保在主线程更新 UI
        wx.CallAfter(DEBUG_OUTPUT_CTRL.AppendText, f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {message}\n")
    # 同时打印到控制台
    # print(f"[DEBUG] {message}")

class RedirectText(object):
    def __init__(self, text_ctrl):
        self.out = text_ctrl

    def write(self, string):
        wx.CallAfter(self.out.AppendText, string)

    def flush(self):
        pass
