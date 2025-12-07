import os
import shutil

# 1. 定义目录结构
dirs = [
    "outputs/datasets",
    "outputs/responses",
    "outputs/reports",
    "src/gui",
    "src/core",
    "src/utils",
    "docs"
]

for d in dirs:
    os.makedirs(d, exist_ok=True)
    print(f"Created: {d}")

# 2. 移动文档
docs_to_move = ["EVALUATION_SPEC.md", "DATASET_RECOMMENDATION.md"]
for doc in docs_to_move:
    if os.path.exists(doc):
        shutil.move(doc, f"docs/{doc}")
        print(f"Moved {doc} to docs/")

# 3. 创建空 __init__.py
init_files = [
    "src/__init__.py",
    "src/gui/__init__.py",
    "src/core/__init__.py",
    "src/utils/__init__.py"
]
for f in init_files:
    with open(f, 'w') as fp:
        pass
    print(f"Created {f}")

print("Directory structure initialized.")
