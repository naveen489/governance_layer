import os

ignore = {'.git', 'node_modules', 'venv', '__pycache__', 'dist', '.pytest_cache'}

def print_tree(directory, prefix=""):
    items = sorted([d for d in os.listdir(directory) if d not in ignore])
    for index, item in enumerate(items):
        path = os.path.join(directory, item)
        is_last = index == (len(items) - 1)
        connector = "\\-- " if is_last else "|-- "
        print(prefix + connector + item)
        if os.path.isdir(path):
            new_prefix = prefix + ("    " if is_last else "|   ")
            print_tree(path, new_prefix)

print("governance_layer/")
print_tree(".")
