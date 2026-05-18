import os
import asyncio
import subprocess
import re
import difflib
import base64
import mimetypes
from typing import List, Dict, Optional, Tuple, Any
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

# --- Global State ---
_current_workspace_root = os.getcwd()

def resolve_path(path: str) -> str:
    """
    Resolves a path. 
    - If absolute: allowed as-is.
    - If relative: anchored to _current_workspace_root and MUST stay within it.
    """
    global _current_workspace_root
    abs_root = os.path.abspath(_current_workspace_root)
    
    if os.path.isabs(path):
        return os.path.abspath(path)
    
    final_path = os.path.abspath(os.path.join(abs_root, path))
    if not final_path.startswith(abs_root):
        raise PermissionError(f"Access denied: Relative path {path} resolves outside the current workspace root {abs_root}")
    
    return final_path

# Create an MCP server
mcp = FastMCP("FileSystem")

class FileEdit(BaseModel):
    oldText: str = Field(..., description="The exact text to be replaced. Must be unique within the file for a surgical edit.")
    newText: str = Field(..., description="The text to replace the oldText with.")

def detect_line_ending(text: str) -> str:
    """Detects if the text uses CRLF (\r\n) or LF (\n). Defaults to LF."""
    if "\r\n" in text:
        return "\r\n"
    return "\n"

@mcp.tool()
async def fs_set_root(path: str) -> str:
    """
    Sets the current workspace root for all subsequent file operations.
    """
    global _current_workspace_root
    try:
        abs_path = os.path.abspath(path)
        if not os.path.isdir(abs_path):
            return f"Error: {path} is not a valid directory."
        _current_workspace_root = abs_path
        return f"Workspace root successfully set to: {_current_workspace_root}"
    except Exception as e:
        return f"Error setting workspace root: {str(e)}"

@mcp.tool()
async def fs_list_allowed_directories() -> str:
    """
    Returns the current workspace root that the server is allowed to access.
    """
    return f"Allowed root: {_current_workspace_root}"

@mcp.tool()
async def fs_search_text(query: str, path: str = ".", case_sensitive: bool = False) -> str:
    """
    Searches for text across files using `rg` (ripgrep). 
    """
    try:
        target_path = resolve_path(path)
        args = ["rg", "--line-number", "--no-heading", "--color", "never"]
        if not case_sensitive:
            args.append("-i")
        args.extend([query, target_path])
        
        process = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode == 0:
            return stdout.decode('utf-8')
        elif process.returncode == 1:
            return "No matches found."
        else:
            return f"Error running rg: {stderr.decode('utf-8')}"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def fs_find_files(pattern: str, path: str = ".", max_depth: Optional[int] = None) -> List[str]:
    """
    Finds files matching a pattern using `fd`.
    """
    try:
        target_path = resolve_path(path)
        args = ["fd", pattern]
        if max_depth is not None:
            args.extend(["--max-depth", str(max_depth)])
        args.append(target_path)
        
        process = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode == 0:
            abs_root = os.path.abspath(_current_workspace_root)
            lines = stdout.decode('utf-8').splitlines()
            return [os.path.relpath(p, abs_root) if os.path.abspath(p).startswith(abs_root) else p for p in lines]
        else:
            return [f"Error running fd: {stderr.decode('utf-8')}"]
    except Exception as e:
        return [f"Error: {str(e)}"]

@mcp.tool()
async def fs_read_file(path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """
    Reads the content of a file from disk. 
    Path can be absolute or relative to the current workspace root.
    You can specify start_line and end_line (1-indexed) to read a specific range.
    This is a non-caching operation.
    """
    try:
        target_path = resolve_path(path)
        def _read():
            with open(target_path, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()
            
            total_lines = len(lines)
            start = max(0, (start_line or 1) - 1)
            end = min(total_lines, end_line if end_line is not None else total_lines)
            
            if start >= total_lines:
                return f"Error: start_line {start_line} is beyond the end of file ({total_lines} lines)."
            
            selected_lines = lines[start:end]
            content = "".join(selected_lines)
            
            if start_line or end_line:
                actual_start = start + 1
                actual_end = min(end, total_lines)
                return f"[Showing lines {actual_start}-{actual_end} of {total_lines}]\n{content}"
            
            return content
        return await asyncio.to_thread(_read)
    except FileNotFoundError:
        return f"Error: File not found at {path}."
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def fs_read_multiple_files(paths: List[str]) -> Dict[str, str]:
    """
    Reads multiple files simultaneously. Failed reads are reported as errors in the value.
    """
    results = {}
    for path in paths:
        try:
            results[path] = await fs_read_file(path)
        except Exception as e:
            results[path] = f"Error reading file: {str(e)}"
    return results

@mcp.tool()
async def fs_read_media_file(path: str) -> Dict[str, str]:
    """
    Reads an image or audio file and returns base64 data with the corresponding MIME type.
    """
    try:
        target_path = resolve_path(path)
        def _read_media():
            mime_type, _ = mimetypes.guess_type(target_path)
            if not mime_type:
                mime_type = "application/octet-stream"
            
            with open(target_path, 'rb') as f:
                data = f.read()
                base64_data = base64.b64encode(data).decode('utf-8')
            return {"mimeType": mime_type, "data": base64_data}
            
        return await asyncio.to_thread(_read_media)
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
async def fs_read_with_context(path: str, line: int, context_lines: int = 5) -> str:
    """
    Reads a specific line from a file with a surrounding context of lines.
    line: The 1-indexed target line.
    context_lines: Number of lines to include above and below the target.
    """
    start_line = max(1, line - context_lines)
    end_line = line + context_lines
    return await fs_read_file(path, start_line=start_line, end_line=end_line)

@mcp.tool()
async def fs_stat(path: str) -> str:
    """
    Returns metadata for a file or directory (size, modification time, permissions).
    """
    try:
        target_path = resolve_path(path)
        def _stat():
            stats = os.stat(target_path)
            return (
                f"Path: {path}\n"
                f"Size: {stats.st_size} bytes\n"
                f"Modified: {stats.st_mtime}\n"
                f"Is Directory: {os.path.isdir(target_path)}"
            )
        return await asyncio.to_thread(_stat)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def fs_list_dir(path: str = ".", with_sizes: bool = False) -> Any:
    """
    Lists the contents of a directory. 
    If with_sizes is True, returns a list of tuples (name, size).
    """
    try:
        target_path = resolve_path(path)
        def _list():
            entries = os.listdir(target_path)
            if not with_sizes:
                return entries
            
            results = []
            for entry in entries:
                full_path = os.path.join(target_path, entry)
                try:
                    size = os.path.getsize(full_path) if os.path.isfile(full_path) else None
                except OSError:
                    size = "Error"
                results.append({"name": entry, "size": size})
            return results
            
        return await asyncio.to_thread(_list)
    except Exception as e:
        return [f"Error: {str(e)}"]

@mcp.tool()
async def fs_get_directory_tree(path: str, exclude_patterns: List[str] = None) -> List[Dict[str, Any]]:
    """
    Get recursive JSON tree structure of directory contents.
    """
    try:
        target_path = resolve_path(path)
        exclude_patterns = exclude_patterns or []
        
        def _build_tree(current_path):
            tree = []
            try:
                entries = os.listdir(current_path)
            except PermissionError:
                return tree

            for entry in entries:
                if any(re.search(p, entry) for p in exclude_patterns):
                    continue
                
                full_path = os.path.join(current_path, entry)
                is_dir = os.path.isdir(full_path)
                node = {
                    "name": entry,
                    "type": "directory" if is_dir else "file"
                }
                if is_dir:
                    node["children"] = _build_tree(full_path)
                tree.append(node)
            return tree

        return await asyncio.to_thread(_build_tree, target_path)
    except Exception as e:
        return [f"Error: {str(e)}"]

@mcp.tool()
async def fs_write_file(path: str, content: str) -> str:
    """
    Writes content to a file.
    """
    try:
        target_path = resolve_path(path)
        def _write():
            dir_name = os.path.dirname(target_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(content)
        await asyncio.to_thread(_write)
        return f"Successfully wrote to {path}:\n\n{content}"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def fs_preview_edit(path: str, edits: List[FileEdit]) -> str:
    """
    Provides a unified diff preview of the proposed surgical edits without applying them.
    """
    try:
        target_path = resolve_path(path)
        def _preview():
            with open(target_path, 'rb') as f:
                raw_bytes = f.read()
            
            content_text = raw_bytes.decode('utf-8-sig')
            normalized_content = content_text.replace('\r\n', '\n')
            
            current_text = normalized_content
            for edit in edits:
                old = edit.oldText.replace('\r\n', '\n')
                new = edit.newText.replace('\r\n', '\n')
                if old not in current_text:
                    return f"Preview Error: oldText '{old}' not found."
                if current_text.count(old) > 1:
                    return f"Preview Error: oldText '{old}' is not unique."
                current_text = current_text.replace(old, new)
            
            diff = difflib.unified_diff(
                normalized_content.splitlines(),
                current_text.splitlines(),
                fromfile="original",
                tofile="preview",
                lineterm=""
            )
            return "\n".join(list(diff))
            
        return await asyncio.to_thread(_preview)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def fs_edit_file(path: str, edits: List[FileEdit]) -> str:
    """
    Performs batch surgical edits on a file. 
    Robustly handles invisible characters (BOM, line endings) and 
    standardizes on LF for internal matching.
    """
    try:
        target_path = resolve_path(path)
        def _edit():
            # 1. Read with universal newlines (all line endings become \n)
            with open(target_path, 'r', encoding='utf-8-sig', newline=None) as f:
                content = f.read()
            
            applied_edits = []
            for i, edit in enumerate(edits):
                old = edit.oldText.replace('\r\n', '\n')
                new = edit.newText.replace('\r\n', '\n')
                
                # Strict match first
                if old in content:
                    count = content.count(old)
                    if count > 1:
                        raise ValueError(f"Edit {i}: oldText found {count} times. Surgical edits require unique text.")
                    content = content.replace(old, new)
                    applied_edits.append(f"'{old}' -> '{new}'")
                    continue
                
                # Fallback: Try matching by ignoring leading/trailing whitespace on each line
                # This handles cases where agent misses a tab or trailing space
                lines = content.splitlines(keepends=True)
                found_fuzzy = False
                
                # Split oldText into lines to match block by block
                old_lines = old.splitlines(keepends=True)
                if not old_lines: continue
                
                for idx in range(len(lines) - len(old_lines) + 1):
                    window = "".join(lines[idx : idx + len(old_lines)])
                    # Compare by stripping whitespace from each line
                    if all(
                        l.strip() == ol.strip() 
                        for l, ol in zip(lines[idx : idx + len(old_lines)], old_lines)
                    ):
                        # We found a match! Now replace the actual lines in content
                        # We keep the original indentation of the first line if possible,
                        # but replace the content.
                        new_lines = new.splitlines(keepends=True)
                        # If new text is shorter than old, we just replace.
                        # If longer, it expands.
                        
                        # To avoid corrupting the file, we replace the exact range
                        # We need to calculate the actual start/end bytes/indices
                        # But since we have the lines, we can just replace in the list.
                        
                        # Replace the window with new lines
                        lines[idx : idx + len(old_lines)] = new_lines
                        found_fuzzy = True
                        applied_edits.append(f"'{old[:20]}...' -> '{new[:20]}...' (fuzzy match)")
                        break
                
                if not found_fuzzy:
                    raise ValueError(f"Edit {i}: oldText not found in file. (Tried strict and fuzzy matching).")
            
            # Write back using LF
            with open(target_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write("".join(lines) if 'lines' in locals() else content)
            
            summary = "\n".join(applied_edits)
            return f"Successfully applied {len(edits)} surgical edits to {path}:\n\n{summary}"
            
        return await asyncio.to_thread(_edit)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def fs_mkdir(path: str) -> str:
    """
    Creates a new directory.
    """
    try:
        target_path = resolve_path(path)
        await asyncio.to_thread(os.makedirs, target_path, exist_ok=True)
        return f"Successfully created directory {path}"
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    mcp.run()
