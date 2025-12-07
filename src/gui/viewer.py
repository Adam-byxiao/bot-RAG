import wx
import wx.grid
import json
import os
import pandas as pd

class DatasetViewerFrame(wx.Frame):
    def __init__(self, parent, dataset_file):
        wx.Frame.__init__(self, parent, title=f"测试数据集查看 - {os.path.basename(dataset_file)}", size=(1000, 600))
        
        self.dataset_file = dataset_file
        self.data = []
        
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        self.grid = wx.grid.Grid(panel)
        self.grid.CreateGrid(0, 4)
        self.grid.SetColLabelValue(0, "类型")
        self.grid.SetColLabelValue(1, "问题")
        self.grid.SetColLabelValue(2, "参考答案")
        self.grid.SetColLabelValue(3, "评分标准")
        
        self.grid.SetColSize(0, 100)
        self.grid.SetColSize(1, 300)
        self.grid.SetColSize(2, 300)
        self.grid.SetColSize(3, 250)
        
        sizer.Add(self.grid, 1, wx.EXPAND | wx.ALL, 10)
        
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
                for col in range(4):
                    self.grid.SetCellRenderer(i, col, wx.grid.GridCellAutoWrapStringRenderer())
            
            self.grid.AutoSizeRows()
        except Exception as e:
            wx.MessageBox(f"加载数据失败: {e}", "错误", wx.ICON_ERROR)

    def on_export(self, event):
        if not self.data: return
        
        save_dialog = wx.FileDialog(self, "导出 Excel", wildcard="Excel files (*.xlsx)|*.xlsx", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if save_dialog.ShowModal() == wx.ID_CANCEL: return
            
        path = save_dialog.GetPath()
        try:
            df = pd.DataFrame(self.data)
            df.to_excel(path, index=False)
            wx.MessageBox(f"导出成功: {path}", "成功", wx.ICON_INFORMATION)
        except Exception as e:
            wx.MessageBox(f"导出失败: {e}", "错误", wx.ICON_ERROR)
