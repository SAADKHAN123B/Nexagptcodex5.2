"""
╔══════════════════════════════════════════════════════════════════╗
║                  NEXACODE FILE MANAGER                          ║
║        Read, Write, Edit, Glob, Grep — Full File Operations     ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import re
import fnmatch
import difflib
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from pygments import highlight
from pygments.lexers import get_lexer_for_filename, TextLexer
from pygments.formatters import TerminalTrueColorFormatter


class FileManager:
    """Full-featured file manager with read, write, edit, search capabilities."""

    def __init__(self, workspace: str = "."):
        self.workspace = Path(workspace).resolve()
        self.file_history: List[Dict] = []  # Track all file operations
        self.clipboard: str = ""
        self._ignore_patterns = self._load_ignore_patterns()

    def _load_ignore_patterns(self) -> List[str]:
        """Load .gitignore patterns."""
        patterns = [
            "node_modules", ".git", "__pycache__", ".venv", "venv",
            ".env", "*.pyc", ".DS_Store", "dist", "build", ".next",
            ".wrangler", "*.egg-info",
        ]
        gitignore = self.workspace / ".gitignore"
        if gitignore.exists():
            try:
                for line in gitignore.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        patterns.append(line)
            except Exception:
                pass
        return patterns

    def _should_ignore(self, path: Path) -> bool:
        """Check if path should be ignored."""
        rel = str(path.relative_to(self.workspace)) if path.is_relative_to(self.workspace) else str(path)
        for pattern in self._ignore_patterns:
            if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(path.name, pattern):
                return True
            if any(fnmatch.fnmatch(part, pattern) for part in Path(rel).parts):
                return True
        return False

    # ─────────────────────────────────────────────────
    # READ OPERATIONS
    # ─────────────────────────────────────────────────
    def read_file(self, path: str, line_start: int = None, line_end: int = None) -> Dict:
        """Read a file with optional line range."""
        filepath = self._resolve_path(path)
        if not filepath.exists():
            return {"success": False, "error": f"File not found: {path}"}
        if not filepath.is_file():
            return {"success": False, "error": f"Not a file: {path}"}

        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            total_lines = len(lines)

            if line_start is not None or line_end is not None:
                start = max(0, (line_start or 1) - 1)
                end = min(total_lines, line_end or total_lines)
                lines = lines[start:end]
                content = "\n".join(lines)

            return {
                "success": True,
                "path": str(filepath),
                "content": content,
                "lines": lines,
                "total_lines": total_lines,
                "size": filepath.stat().st_size,
                "modified": datetime.fromtimestamp(filepath.stat().st_mtime).isoformat(),
                "extension": filepath.suffix,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def read_file_highlighted(self, path: str) -> str:
        """Read file with syntax highlighting."""
        result = self.read_file(path)
        if not result["success"]:
            return result["error"]

        try:
            lexer = get_lexer_for_filename(path)
        except Exception:
            lexer = TextLexer()

        formatter = TerminalTrueColorFormatter(style="monokai")
        return highlight(result["content"], lexer, formatter)

    # ─────────────────────────────────────────────────
    # WRITE OPERATIONS
    # ─────────────────────────────────────────────────
    def write_file(self, path: str, content: str, create_dirs: bool = True) -> Dict:
        """Write content to a file."""
        filepath = self._resolve_path(path)

        if create_dirs:
            filepath.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Backup existing file
            if filepath.exists():
                self._backup_file(filepath)

            filepath.write_text(content, encoding="utf-8")

            self._log_operation("write", str(filepath), len(content))
            return {
                "success": True,
                "path": str(filepath),
                "size": len(content),
                "lines": content.count("\n") + 1,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def append_file(self, path: str, content: str) -> Dict:
        """Append content to a file."""
        filepath = self._resolve_path(path)
        try:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(content)
            self._log_operation("append", str(filepath), len(content))
            return {"success": True, "path": str(filepath)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─────────────────────────────────────────────────
    # EDIT OPERATIONS
    # ─────────────────────────────────────────────────
    def edit_file(self, path: str, old_text: str, new_text: str, replace_all: bool = False) -> Dict:
        """Edit a file by replacing text."""
        result = self.read_file(path)
        if not result["success"]:
            return result

        content = result["content"]
        count = content.count(old_text)

        if count == 0:
            return {"success": False, "error": "Text not found in file"}
        if count > 1 and not replace_all:
            return {
                "success": False,
                "error": f"Text found {count} times. Use replace_all=True or provide more context.",
            }

        if replace_all:
            new_content = content.replace(old_text, new_text)
        else:
            new_content = content.replace(old_text, new_text, 1)

        return self.write_file(path, new_content)

    def multi_edit(self, path: str, edits: List[Tuple[str, str]]) -> Dict:
        """Apply multiple edits to a file in sequence."""
        result = self.read_file(path)
        if not result["success"]:
            return result

        content = result["content"]
        for old_text, new_text in edits:
            if old_text not in content:
                return {"success": False, "error": f"Text not found: {old_text[:50]}..."}
            content = content.replace(old_text, new_text, 1)

        return self.write_file(path, content)

    def insert_at_line(self, path: str, line_number: int, content: str) -> Dict:
        """Insert content at a specific line number."""
        result = self.read_file(path)
        if not result["success"]:
            return result

        lines = result["content"].split("\n")
        idx = max(0, min(line_number - 1, len(lines)))
        lines.insert(idx, content)
        return self.write_file(path, "\n".join(lines))

    def delete_lines(self, path: str, start: int, end: int) -> Dict:
        """Delete lines from a file."""
        result = self.read_file(path)
        if not result["success"]:
            return result

        lines = result["content"].split("\n")
        del lines[start - 1:end]
        return self.write_file(path, "\n".join(lines))

    def get_diff(self, path: str, new_content: str) -> str:
        """Get a unified diff between current file and new content."""
        result = self.read_file(path)
        if not result["success"]:
            return ""

        old_lines = result["content"].splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"a/{path}", tofile=f"b/{path}",
        )
        return "".join(diff)

    # ─────────────────────────────────────────────────
    # SEARCH OPERATIONS
    # ─────────────────────────────────────────────────
    def glob_search(self, pattern: str, path: str = None) -> List[Dict]:
        """Search for files matching a glob pattern."""
        search_path = self._resolve_path(path) if path else self.workspace
        results = []

        for filepath in search_path.rglob(pattern):
            if self._should_ignore(filepath):
                continue
            try:
                stat = filepath.stat()
                results.append({
                    "path": str(filepath),
                    "relative": str(filepath.relative_to(self.workspace)),
                    "name": filepath.name,
                    "size": stat.st_size,
                    "is_dir": filepath.is_dir(),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
            except Exception:
                continue

        results.sort(key=lambda x: x["modified"], reverse=True)
        return results

    def grep_search(
        self,
        pattern: str,
        path: str = None,
        include: str = None,
        max_results: int = 100,
        context_lines: int = 2,
    ) -> List[Dict]:
        """Search file contents using regex pattern."""
        search_path = self._resolve_path(path) if path else self.workspace
        results = []
        regex = re.compile(pattern, re.IGNORECASE)

        glob_pattern = include or "*"
        for filepath in search_path.rglob(glob_pattern):
            if not filepath.is_file() or self._should_ignore(filepath):
                continue
            if filepath.stat().st_size > 1_000_000:  # Skip files > 1MB
                continue

            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
                lines = content.split("\n")

                for i, line in enumerate(lines):
                    if regex.search(line):
                        start = max(0, i - context_lines)
                        end = min(len(lines), i + context_lines + 1)
                        context = "\n".join(
                            f"{'>' if j == i else ' '} {j+1}: {lines[j]}"
                            for j in range(start, end)
                        )
                        results.append({
                            "file": str(filepath.relative_to(self.workspace)),
                            "line": i + 1,
                            "match": line.strip(),
                            "context": context,
                        })
                        if len(results) >= max_results:
                            return results
            except Exception:
                continue

        return results

    # ─────────────────────────────────────────────────
    # DIRECTORY OPERATIONS
    # ─────────────────────────────────────────────────
    def list_dir(self, path: str = None, recursive: bool = False, max_depth: int = 3) -> Dict:
        """List directory contents as a tree."""
        dir_path = self._resolve_path(path) if path else self.workspace
        if not dir_path.is_dir():
            return {"success": False, "error": f"Not a directory: {path}"}

        tree = self._build_tree(dir_path, max_depth=max_depth if recursive else 1)
        return {"success": True, "path": str(dir_path), "tree": tree}

    def _build_tree(self, path: Path, depth: int = 0, max_depth: int = 3) -> List[Dict]:
        """Build directory tree structure."""
        if depth >= max_depth:
            return []

        items = []
        try:
            entries = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            for entry in entries:
                if self._should_ignore(entry):
                    continue
                item = {
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "path": str(entry.relative_to(self.workspace)),
                }
                if entry.is_file():
                    item["size"] = entry.stat().st_size
                    item["extension"] = entry.suffix
                elif entry.is_dir() and depth < max_depth - 1:
                    item["children"] = self._build_tree(entry, depth + 1, max_depth)
                items.append(item)
        except PermissionError:
            pass
        return items

    def create_dir(self, path: str) -> Dict:
        """Create a directory."""
        dir_path = self._resolve_path(path)
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            return {"success": True, "path": str(dir_path)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_path(self, path: str) -> Dict:
        """Delete a file or directory."""
        filepath = self._resolve_path(path)
        try:
            if filepath.is_dir():
                shutil.rmtree(filepath)
            elif filepath.is_file():
                self._backup_file(filepath)
                filepath.unlink()
            else:
                return {"success": False, "error": "Path not found"}
            self._log_operation("delete", str(filepath))
            return {"success": True, "path": str(filepath)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def move_path(self, src: str, dst: str) -> Dict:
        """Move/rename a file or directory."""
        src_path = self._resolve_path(src)
        dst_path = self._resolve_path(dst)
        try:
            shutil.move(str(src_path), str(dst_path))
            self._log_operation("move", f"{src_path} → {dst_path}")
            return {"success": True, "from": str(src_path), "to": str(dst_path)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def copy_path(self, src: str, dst: str) -> Dict:
        """Copy a file or directory."""
        src_path = self._resolve_path(src)
        dst_path = self._resolve_path(dst)
        try:
            if src_path.is_dir():
                shutil.copytree(str(src_path), str(dst_path))
            else:
                shutil.copy2(str(src_path), str(dst_path))
            self._log_operation("copy", f"{src_path} → {dst_path}")
            return {"success": True, "from": str(src_path), "to": str(dst_path)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_project_stats(self) -> Dict:
        """Get project statistics."""
        stats = {
            "total_files": 0, "total_dirs": 0,
            "total_size": 0, "by_extension": {},
            "largest_files": [],
        }
        files_list = []

        for filepath in self.workspace.rglob("*"):
            if self._should_ignore(filepath):
                continue
            if filepath.is_file():
                stats["total_files"] += 1
                size = filepath.stat().st_size
                stats["total_size"] += size
                ext = filepath.suffix or "no_ext"
                stats["by_extension"][ext] = stats["by_extension"].get(ext, 0) + 1
                files_list.append((str(filepath.relative_to(self.workspace)), size))
            elif filepath.is_dir():
                stats["total_dirs"] += 1

        files_list.sort(key=lambda x: x[1], reverse=True)
        stats["largest_files"] = files_list[:10]
        return stats

    # ─────────────────────────────────────────────────
    # UTILITY METHODS
    # ─────────────────────────────────────────────────
    def _resolve_path(self, path: str = None) -> Path:
        """Resolve a path relative to workspace."""
        if path is None:
            return self.workspace
        p = Path(path)
        if p.is_absolute():
            return p
        return (self.workspace / p).resolve()

    def _backup_file(self, filepath: Path):
        """Create a backup of a file before modifying."""
        from nexacode.config.settings import NEXACODE_DIR
        backup_dir = NEXACODE_DIR / "backups"
        backup_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{filepath.name}.{ts}.bak"
        try:
            shutil.copy2(str(filepath), str(backup_dir / backup_name))
        except Exception:
            pass

    def _log_operation(self, op: str, path: str, size: int = 0):
        """Log a file operation."""
        self.file_history.append({
            "operation": op,
            "path": path,
            "size": size,
            "timestamp": datetime.now().isoformat(),
        })

    def render_tree_string(self, tree: List[Dict], prefix: str = "", is_last: bool = True) -> str:
        """Render tree as a formatted string."""
        lines = []
        for i, item in enumerate(tree):
            is_last_item = (i == len(tree) - 1)
            connector = "└── " if is_last_item else "├── "

            icon = "📁 " if item["is_dir"] else self._get_file_icon(item.get("extension", ""))
            size_str = ""
            if not item["is_dir"] and "size" in item:
                size_str = f" ({self._format_size(item['size'])})"

            lines.append(f"{prefix}{connector}{icon}{item['name']}{size_str}")

            if item["is_dir"] and "children" in item:
                child_prefix = prefix + ("    " if is_last_item else "│   ")
                lines.append(self.render_tree_string(item["children"], child_prefix, is_last_item))

        return "\n".join(lines)

    def _get_file_icon(self, ext: str) -> str:
        icons = {
            ".py": "🐍 ", ".js": "📜 ", ".ts": "📘 ", ".tsx": "⚛️ ",
            ".jsx": "⚛️ ", ".html": "🌐 ", ".css": "🎨 ", ".json": "📋 ",
            ".md": "📝 ", ".yml": "⚙️ ", ".yaml": "⚙️ ", ".toml": "⚙️ ",
            ".sql": "🗄️ ", ".sh": "🔧 ", ".bash": "🔧 ", ".go": "🔷 ",
            ".rs": "🦀 ", ".java": "☕ ", ".cpp": "⚡ ", ".c": "⚡ ",
            ".rb": "💎 ", ".php": "🐘 ", ".swift": "🍎 ", ".kt": "🟣 ",
            ".r": "📊 ", ".ipynb": "📓 ", ".lock": "🔒 ", ".env": "🔐 ",
            ".dockerfile": "🐳 ", ".docker": "🐳 ", ".gitignore": "🙈 ",
        }
        return icons.get(ext, "📄 ")

    def _format_size(self, size: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
