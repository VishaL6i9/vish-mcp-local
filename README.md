# vish-mcp-local

[![MCP Server](https://img.shields.io/badge/MCP-Server-blue.svg)](https://modelcontextprotocol.io)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A professional-grade, high-performance Filesystem MCP (Model Context Protocol) server designed specifically for AI Coding Agents. This server eliminates common friction points in agentic workflows, such as aggressive caching, imprecise file edits, and rigid workspace roots.

## Design Goals

Modern AI agents often struggle with filesystem interactions due to three main issues:
1. Caching Stale Data: Agents often read cached versions of files, missing local changes.
2. Imprecise Edits: Simple "replace" operations often cause accidental corruption or "whole-file" rewrites.
3. Rigid Context: Fixed workspace roots hinder the ability to switch projects dynamically.

`vish-mcp-local` solves these by implementing strictly non-caching reads, surgical batch edits, and a mutable workspace root.

## Key Features

### High Performance
- Discovery: Leverages `rg` (ripgrep) for blazing-fast text search and `fd` for rapid file discovery.
- Async I/O: Built on `FastMCP` and `asyncio` to ensure the agent remains responsive during heavy I/O.

### Surgical Precision
- Unique Matching: `fs_edit_file` requires `oldText` to be unique within the file, preventing accidental corruption of similar code blocks.
- Batching: Apply multiple disjoint edits in a single tool call to reduce latency and token usage.
- Diff Previews: Integrated `fs_preview_edit` allows agents to verify changes via unified diffs before committing to disk.

### Robustness & Compatibility
- Universal Line Endings: Automatically handles BOM (Byte Order Mark) and normalizes CRLF/LF line endings to ensure matches always succeed regardless of OS.
- Surgical Reading: Supports reading specific line ranges and surrounding context to minimize context window bloat.
- Dynamic Rooting: Shift the project context on-the-fly using `fs_set_root` while maintaining strict isolation for relative paths.

## Installation

### Prerequisites
- Python 3.12+ (Managed via `uv` recommended)
- ripgrep (`rg`): Installed and available in system PATH.
- fd: Installed and available in system PATH.

### Setup
```bash
# Clone the repository
git clone https://github.com/VishaL6i9/vish-mcp-local.git
cd vish-mcp-local

# Create and activate virtual environment using uv
uv venv
# Windows
.\venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# Install dependencies
uv pip install mcp tree-sitter-language-pack
```

## Configuration

Add the server to your MCP settings (e.g., `.pi/agent/mcp.json`):

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "C:/path/to/venv/Scripts/python.exe",
      "args": ["C:/path/to/fs-mcp-server/fs_server.py"]
    }
  }
}
```

## API Reference

### Tools

| Tool | Description | Key Arguments | ReadOnly | Idempotent | Destructive |
| :--- | :--- | :--- | :---: | :---: | :---: |
| `fs_set_root` | Sets the active workspace root. | `path` | No | Yes | No |
| `fs_read_file` | Non-caching read. Supports ranges. | `path`, `start_line`, `end_line` | Yes | - | - |
| `fs_read_with_context` | Reads a line + surrounding buffer. | `path`, `line`, `context_lines` | Yes | - | - |
| `fs_write_file` | Overwrites file with new content. | `path`, `content` | No | Yes | Yes |
| `fs_edit_file` | Performs surgical batch replacements. | `path`, `edits: [{oldText, newText}]` | No | No | Yes |
| `fs_preview_edit` | Returns a diff of proposed edits. | `path`, `edits: [{oldText, newText}]` | Yes | - | - |
| `fs_search_text` | High-speed text search via `rg`. | `query`, `path`, `case_sensitive` | Yes | - | - |
| `fs_find_files` | High-speed file find via `fd`. | `pattern`, `path`, `max_depth` | Yes | - | - |
| `fs_list_dir` | Lists directory contents. | `path` | Yes | - | - |
| `fs_stat` | Returns file/folder metadata. | `path` | Yes | - | - |
| `fs_mkdir` | Creates directories recursively. | `path` | No | Yes | No |

## Testing

Run the comprehensive test suite to verify installation and tool logic:

```bash
python fs-mcp-server/tests.py
```

## License
Distributed under the MIT License. See `LICENSE` for more information.
