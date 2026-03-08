"""
╔══════════════════════════════════════════════════════════════════╗
║                    NEXACODE UTILITIES                           ║
║              Shared Helper Functions & Tools                     ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import re
import sys
import time
import hashlib
import platform
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta


def get_system_info() -> Dict:
    """Get system information."""
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "python": platform.python_version(),
        "arch": platform.machine(),
        "hostname": platform.node(),
        "cpu_count": os.cpu_count(),
        "cwd": os.getcwd(),
        "home": str(Path.home()),
        "terminal": os.environ.get("TERM", "unknown"),
        "shell": os.environ.get("SHELL", "unknown"),
    }


def format_timestamp(ts: float) -> str:
    """Format a Unix timestamp as readable string."""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def format_duration(seconds: float) -> str:
    """Format seconds into human-readable duration."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"


def format_size(size: int) -> str:
    """Format bytes into human-readable size."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}PB"


def format_tokens(count: int) -> str:
    """Format token count."""
    if count < 1000:
        return str(count)
    elif count < 1_000_000:
        return f"{count / 1000:.1f}K"
    else:
        return f"{count / 1_000_000:.1f}M"


def truncate_string(s: str, max_len: int = 100, suffix: str = "...") -> str:
    """Truncate a string to max length."""
    if len(s) <= max_len:
        return s
    return s[:max_len - len(suffix)] + suffix


def hash_content(content: str) -> str:
    """Generate a short hash of content."""
    return hashlib.sha256(content.encode()).hexdigest()[:12]


def extract_code_blocks(text: str) -> List[Dict]:
    """Extract code blocks from markdown text."""
    pattern = r'```(\w*)\n(.*?)```'
    blocks = []
    for match in re.finditer(pattern, text, re.DOTALL):
        language = match.group(1) or "text"
        code = match.group(2).strip()
        blocks.append({
            "language": language,
            "code": code,
            "start": match.start(),
            "end": match.end(),
        })
    return blocks


def extract_file_actions(text: str) -> List[Dict]:
    """Extract file action blocks from AI response."""
    actions = []
    pattern = r'```action\s*\n(.*?)```'
    for match in re.finditer(pattern, text, re.DOTALL):
        block = match.group(1)
        action = {}
        for line in block.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                action[key.strip().lower()] = value.strip()
        if action:
            actions.append(action)
    return actions


def detect_language(filename: str) -> str:
    """Detect programming language from filename."""
    ext_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".tsx": "tsx", ".jsx": "jsx", ".html": "html", ".css": "css",
        ".json": "json", ".yaml": "yaml", ".yml": "yaml",
        ".toml": "toml", ".sql": "sql", ".sh": "bash",
        ".bash": "bash", ".md": "markdown", ".rs": "rust",
        ".go": "go", ".java": "java", ".rb": "ruby",
        ".php": "php", ".cpp": "cpp", ".c": "c",
        ".h": "c", ".hpp": "cpp", ".swift": "swift",
        ".kt": "kotlin", ".scala": "scala", ".r": "r",
        ".lua": "lua", ".pl": "perl", ".ex": "elixir",
        ".exs": "elixir", ".dart": "dart", ".vue": "vue",
        ".svelte": "svelte",
    }
    ext = Path(filename).suffix.lower()
    return ext_map.get(ext, "text")


def is_binary_file(filepath: str) -> bool:
    """Check if a file is binary."""
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(8192)
            if b"\0" in chunk:
                return True
            # Check for high ratio of non-text characters
            text_chars = set(range(32, 127)) | {9, 10, 13}
            non_text = sum(1 for byte in chunk if byte not in text_chars)
            return non_text / max(len(chunk), 1) > 0.30
    except Exception:
        return True


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename removing unsafe characters."""
    # Remove path separators and other dangerous chars
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = filename.strip('. ')
    return filename or "unnamed"


def count_tokens_estimate(text: str) -> int:
    """Rough estimate of token count (1 token ≈ 4 chars)."""
    return len(text) // 4


def parse_key_value(text: str, delimiter: str = "=") -> Dict[str, str]:
    """Parse key=value pairs from text."""
    result = {}
    for line in text.strip().split("\n"):
        line = line.strip()
        if delimiter in line and not line.startswith("#"):
            key, value = line.split(delimiter, 1)
            result[key.strip()] = value.strip()
    return result


class Timer:
    """Simple timer context manager."""
    def __init__(self):
        self.start_time = 0.0
        self.elapsed = 0.0

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, *args):
        self.elapsed = time.time() - self.start_time

    @property
    def duration(self) -> str:
        return format_duration(self.elapsed)
