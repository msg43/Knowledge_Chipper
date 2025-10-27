import ast
import sys

try:
    with open("src/knowledge_system/services/file_generation.py") as f:
        code = f.read()
    ast.parse(code)
    print("No syntax errors found")
except SyntaxError as e:
    print(f"Syntax Error at line {e.lineno}")
    print(f"Message: {e.msg}")
    print(f"Text: {e.text}")
    print(f"Offset: {e.offset}")

    # Show context
    lines = code.split("\n")
    start = max(0, e.lineno - 10)
    end = min(len(lines), e.lineno + 5)

    print(f"\nContext (lines {start}-{end}):")
    for i in range(start, end):
        marker = " >>> " if i + 1 == e.lineno else "     "
        print(f"{marker}{i+1:4}: {lines[i]}")
