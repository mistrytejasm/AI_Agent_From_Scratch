import os
from tools.base import tool

# Establish the root folder of our project workspace as the safe directory boundary
WORKSPACE_DIR = os.path.abspath(".")

def is_safe_path(path: str) -> bool:
    """Verifies that the target path remains inside the workspace sandbox directory."""
    abs_path = os.path.abspath(path)
    return abs_path.startswith(WORKSPACE_DIR)

@tool
def list_directory(directory_path: str = ".") -> str:
    """Lists all files and directories in the specified path inside the workspace."""
    if not is_safe_path(directory_path):
        return "Error: Access denied. Target path lies outside sandbox directory."
    try:
        items = os.listdir(directory_path)
        if not items:
            return "Directory is empty."
        output = []
        for item in items:
            full_path = os.path.join(directory_path, item)
            item_type = "Folder" if os.path.isdir(full_path) else "File"
            size = os.path.getsize(full_path) if item_type == "File" else ""
            size_str = f" ({size} bytes)" if size != "" else ""
            output.append(f"[{item_type}] {item}{size_str}")
        return "\n".join(output)
    except Exception as e:
        return f"Error listing directory: {e}"

@tool
def read_file(file_path: str) -> str:
    """Reads and returns text contents from a file within the workspace."""
    if not is_safe_path(file_path):
        return "Error: Access denied. Target path lies outside sandbox directory."
    try:
        if not os.path.exists(file_path):
            return f"Error: File '{file_path}' does not exist."
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content
    except Exception as e:
        return f"Error reading file: {e}"

@tool
def write_file(file_path: str, content: str) -> str:
    """Writes content to a file inside the workspace sandbox, overwriting if it already exists."""
    if not is_safe_path(file_path):
        return "Error: Access denied. Target path lies outside sandbox directory."
    try:
        # Generate parent directory folders if they do not exist
        parent_dir = os.path.dirname(os.path.abspath(file_path))
        os.makedirs(parent_dir, exist_ok=True)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote content to '{file_path}'."
    except Exception as e:
        return f"Error writing to file: {e}"