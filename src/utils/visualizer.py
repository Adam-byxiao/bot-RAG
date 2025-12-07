import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import base64
from io import BytesIO

def create_radar_chart(df):
    """生成雷达图"""
    categories = ['faithfulness_score', 'completeness_score', 'relevance_score']
    labels = ['忠实度', '完整性', '相关性']
    
    values = df[categories].mean().values.flatten().tolist()
    values += values[:1] # 闭合
    
    angles = [n / float(len(categories)) * 2 * np.pi for n in range(len(categories))]
    angles += angles[:1]
    
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    
    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'Microsoft YaHei', 'SimSun']
    plt.rcParams['axes.unicode_minus'] = False
    
    ax.plot(angles, values, linewidth=2, linestyle='solid', color='#1f77b4')
    ax.fill(angles, values, '#1f77b4', alpha=0.25)
    
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, size=12)
    ax.set_ylim(0, 5)
    
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close()
    return base64.b64encode(buf.getvalue()).decode('utf-8')

def create_bar_chart(df):
    """生成柱状图"""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    questions = [q[:10] + "..." for q in df['question']]
    x = np.arange(len(questions))
    width = 0.25
    
    rects1 = ax.bar(x - width, df['faithfulness_score'], width, label='忠实度')
    rects2 = ax.bar(x, df['completeness_score'], width, label='完整性')
    rects3 = ax.bar(x + width, df['relevance_score'], width, label='相关性')
    
    ax.set_ylabel('得分 (1-5)')
    ax.set_title('各测试用例详细得分')
    ax.set_xticks(x)
    ax.set_xticklabels(questions, rotation=45, ha='right')
    ax.legend()
    ax.set_ylim(0, 6)
    
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close()
    return base64.b64encode(buf.getvalue()).decode('utf-8')

def generate_html_report(df, output_file, timestamp):
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
                            忠实度: {row.get('faithfulness_reason','')}<br/>
                            完整性: {row.get('completeness_reason','')}<br/>
                            相关性: {row.get('relevance_reason','')}
                        </td>
                        <td>
                            忠: <span class="score">{row.get('faithfulness_score',0)}</span><br/>
                            完: <span class="score">{row.get('completeness_score',0)}</span><br/>
                            相: <span class="score">{row.get('relevance_score',0)}</span>
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
