import asyncio
import os
import shutil
from fs_server import (
    fs_read_file, fs_write_file, fs_edit_file, 
    fs_list_dir, fs_mkdir, fs_search_text, fs_find_files, 
    fs_set_root, fs_stat, fs_preview_edit, fs_read_with_context
)

async def run_tests():
    base_test_dir = os.path.abspath("test_mcp_fs_final")
    root1 = os.path.join(base_test_dir, "root1")
    root2 = os.path.join(base_test_dir, "root2")
    file1 = "hello1.txt"
    file2 = "hello2.txt"
    
    print("Starting Final MCP FileSystem Server Tests...")

    try:
        # Setup
        if os.path.exists(base_test_dir):
            shutil.rmtree(base_test_dir)
        os.makedirs(root1)
        os.makedirs(root2)
        
        abs_file1_path = os.path.join(root1, file1)
        abs_file2_path = os.path.join(root2, file2)
        
        with open(abs_file1_path, 'w') as f: f.write("Content 1")
        with open(abs_file2_path, 'w') as f: f.write("Content 2")

        # 1. Root & Path Resolution
        print("Testing root and path resolution...", end=" ")
        await fs_set_root(root1)
        # Absolute access
        assert (await fs_read_file(abs_file2_path)) == "Content 2"
        # Relative isolation
        res_rel = await fs_read_file(f"../root2/{file2}")
        assert "Access denied" in res_rel
        # Relative inside
        assert (await fs_read_file(file1)) == "Content 1"
        print("OK")

        # 2. Stat
        print("Testing fs_stat...", end=" ")
        stat_res = await fs_stat(file1)
        assert "Size:" in stat_res
        print("OK")

        # 3. Range Reading
        print("Testing fs_read_file (ranges)...", end=" ")
        long_file = "long.txt"
        lines = [f"Line {i+1}" for i in range(20)]
        await fs_write_file(long_file, "\n".join(lines))
        res_range = await fs_read_file(long_file, start_line=5, end_line=7)
        assert "Line 5" in res_range and "Line 7" in res_range
        print("OK")

        # 4. Context Reading
        print("Testing fs_read_with_context...", end=" ")
        res_ctx = await fs_read_with_context(long_file, line=10, context_lines=2)
        assert "Line 8" in res_ctx and "Line 12" in res_ctx
        print("OK")

        # 5. Preview Edit
        print("Testing fs_preview_edit...", end=" ")
        from fs_server import FileEdit
        preview_file = "preview.txt"
        await fs_write_file(preview_file, "Original Text\nLine 2")
        edits = [FileEdit(oldText="Original Text", newText="Modified Text")]
        preview = await fs_preview_edit(preview_file, edits)
        assert "-Original Text" in preview and "+Modified Text" in preview
        print("OK")

        # 6. Robust Edit (Line Endings)
        print("Testing fs_edit_file robustness...", end=" ")
        endings_file = "endings.txt"
        with open(os.path.join(root1, endings_file), 'wb') as f:
            f.write(b"Line1\r\nLine2\r\nLine3")
        
        edit_res = await fs_edit_file(endings_file, [FileEdit(oldText="Line2", newText="UpdatedLine2")])
        assert "Successfully applied" in edit_res
        final_content = await fs_read_file(endings_file)
        assert "UpdatedLine2" in final_content
        print("OK")

        print("\nAll tests passed successfully!")

    except Exception as e:
        print(f"\nTest failed: {e}")
        raise e
    finally:
        if os.path.exists(base_test_dir):
            shutil.rmtree(base_test_dir)
            print("Cleaned up test directory.")

if __name__ == "__main__":
    asyncio.run(run_tests())
