import pandas as pd

try:
    # Read all sheets
    excel_file = pd.ExcelFile(r"f:\python\bot-RAG\testcase.xlsx")
    
    print(f"Sheet names: {excel_file.sheet_names}")
    
    for sheet_name in excel_file.sheet_names:
        print(f"\n--- Sheet: {sheet_name} ---")
        df = pd.read_excel(excel_file, sheet_name=sheet_name)
        print(df.head().to_markdown(index=False))
        
except Exception as e:
    print(f"Error reading excel: {e}")
