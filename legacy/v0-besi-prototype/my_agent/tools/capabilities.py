import os
from pathlib import Path

import docx


def get_default_capabilities() -> str:
    """Loads the default BESI capability document from the data directory."""
    try:
        # Define path relative to this file
        # This file is in my_agent/tools/capabilities.py
        # We need to go up to my_agent/ and then to data/
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.dirname(os.path.dirname(current_dir))  # my_agent/
        data_dir = os.path.join(base_dir, "my_agent", "data")

        # Target specific file
        target_file = "capabilities.txt"
        file_path = os.path.join(data_dir, target_file)

        if os.path.exists(file_path):
            return load_capabilities(file_path)

        return ""
    except Exception as e:
        print(f"Error loading default capabilities: {e}")
        return ""


def load_capabilities(file_path: str) -> str:
    """Loads company capabilities from a file (supports .txt and .docx)."""
    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: File not found at {file_path}"

        if path.suffix.lower() == ".docx":
            doc = docx.Document(file_path)
            return "\n".join([para.text for para in doc.paragraphs])
        else:
            # Try UTF-8 first
            try:
                return path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Fallback to Latin-1
                print(f"⚠️ UTF-8 decode failed for {file_path}, trying Latin-1")
                return path.read_text(encoding="latin-1")
    except Exception as e:
        return f"Error loading capabilities: {e!s}"


def read_capabilities_doc(file_path: str) -> str:
    """Reads a company capabilities document (txt or docx) and returns the content.

    Args:
        file_path: Absolute path to the capabilities document.
    """
    return load_capabilities(file_path)
