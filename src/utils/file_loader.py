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
            
        # 智能分配每个文件的字符配额，确保多文件时能覆盖更多文档
        total_limit = 500000
        num_files = len(file_list)
        # 基础配额：总限制除以文件数，但单文件最少给 10k (除非总限制不够)，最多不限制
        # 如果文件很多，优先保证前面的文件能读入，但限制单个文件大小，避免一个文件占满
        per_file_limit = int(total_limit / max(1, num_files))
        # 修正配额：如果文件很少，允许单个文件更大；如果文件很多，限制每个文件大小
        # 这里采用一个策略：单文件最大允许 500k (即 total_limit)，但如果有多个文件，
        # 我们希望至少能读入前 N 个文件。
        # 简单策略：如果文件数 > 1，强制限制每个文件最大占用 total_limit / 2 或 total_limit / num_files 的较大者
        # 这样至少能读入 2 个文件。
        # 更优策略：动态配额。
        
        if num_files > 1:
            per_file_limit = max(int(total_limit / num_files), 20000) # 至少给20k，除非...
            # 但如果 per_file_limit * num_files > total_limit，后面的文件还是进不来。
            # 关键是防止前面的文件太大。
            # 让我们设定一个硬限制：单个文件最多占用 50% 的总配额 (如果有 >1 个文件)
            # 或者更简单：max_per_file = 500000
            pass 

        current_total = 0
        
        for file_path in file_list:
            content = read_file_content(file_path)
            if content:
                # 计算该文件允许的最大长度
                # 策略：如果有多个文件，限制单个文件不能超过剩余空间的 80% (为了给后面留点？不，这会导致太小)
                # 策略：限制单个文件最大 100k (如果有多个文件)
                
                limit_for_this_file = len(content)
                if num_files > 1:
                    # 动态调整：总配额 50w。如果有 5 个文件，平均 10w。
                    # 强制限制：单个文件不超过 20w (为了至少容纳 2.5 个大文件)
                    # 或者不超过 total_limit / num_files * 2
                    avg_quota = int(total_limit / num_files)
                    limit_for_this_file = min(len(content), max(avg_quota * 2, 50000))
                
                if len(content) > limit_for_this_file:
                     content = content[:limit_for_this_file] + "...(部分截断)"
                
                # 检查加入后是否超总限
                if current_total + len(content) > total_limit:
                    remaining = total_limit - current_total
                    if remaining > 100: # 如果还能塞点东西
                        content = content[:remaining] + "...(总长截断)"
                        doc_content += f"\n\n--- 文档: {os.path.basename(file_path)} ---\n{content}"
                    break
                
                doc_content += f"\n\n--- 文档: {os.path.basename(file_path)} ---\n{content}"
                current_total += len(content)
                
    else:
        doc_content = read_file_content(kb_path)
        
    # 简单截断保护 (从 50k 增加到 500k)
    if len(doc_content) > 500000:
        doc_content = doc_content[:500000] + "...(截断)..."
    return doc_content
