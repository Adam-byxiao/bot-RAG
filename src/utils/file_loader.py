import os
import pandas as pd
import docx
import random
from pypdf import PdfReader

def read_file_content(file_path):
    """
    读取不同格式的文件内容 (.txt, .md, .json, .docx, .pdf, .xlsx)
    """
    if not os.path.exists(file_path):
        return ""
        
    ext = os.path.splitext(file_path)[1].lower()
    content = ""
    try:
        if ext in ['.txt', '.md', '.json']:
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
            content = df.to_string(index=False)
    except Exception as e:
        print(f"解析文件 {file_path} 时出错: {e}")
        return f"[读取失败: {str(e)}]"
    
    return content

def read_knowledge_base(kb_path, is_dir, shuffle_files=False):
    """
    读取知识库（单文件或文件夹）
    """
    doc_content = ""
    if is_dir:
        if not os.path.exists(kb_path): return ""
        
        file_list = []
        for root, dirs, files in os.walk(kb_path):
            for file in files:
                if file.lower().endswith(('.txt', '.md', '.json', '.docx', '.pdf', '.xlsx')):
                    file_list.append(os.path.join(root, file))
        
        if shuffle_files:
            random.shuffle(file_list)
        else:
            file_list.sort()
            
        for file_path in file_list:
            content = read_file_content(file_path)
            if content:
                doc_content += f"\n\n--- 文档: {os.path.basename(file_path)} ---\n{content}"
                if len(doc_content) > 500000:
                    break
    else:
        doc_content = read_file_content(kb_path)
        
    # 简单截断保护 (从 50k 增加到 500k)
    if len(doc_content) > 500000:
        doc_content = doc_content[:500000] + "...(截断)..."
    return doc_content
