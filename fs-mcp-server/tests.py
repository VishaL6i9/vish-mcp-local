import asyncio
import os
import shutil
import base64
from fs_server import (
    fs_read_file, fs_write_file, fs_edit_file, 
    fs_list_dir, fs_mkdir, fs_search_text, fs_find_files, 
    fs_set_root, fs_stat, fs_preview_edit, fs_read_with_context,
    fs_read_multiple_files, fs_read_media_file, fs_get_directory_tree, fs_list_allowed_directories
)

async def run_tests():
    base_test_dir = os.path.abspath("test_mcp_fs_full")
    root1 = os.path.join(base_test_dir, "root1")
    
    print("Starting Comprehensive MCP FileSystem Server Tests...")

    try:
        # Setup
        if os.path.exists(base_test_dir):
            shutil.rmtree(base_test_dir)
        os.makedirs(root1)
        await fs_set_root(root1)

        # 1. Root and Basic Stats
        print("Testing root and stat...", end=" ")
        allowed = await fs_list_allowed_directories()
        assert root1 in allowed
        
        test_file = "test.txt"
        await fs_write_file(test_file, "Hello World")
        stat_res = await fs_stat(test_file)
        assert "Size:" in stat_res
        print("OK")

        # 2. Multi-file read
        print("Testing fs_read_multiple_files...", end=" ")
        await fs_write_file("file1.txt", "Content 1")
        await fs_write_file("file2.txt", "Content 2")
        multi_res = await fs_read_multiple_files(["file1.txt", "file2.txt", "nonexistent.txt"])
        assert multi_res["file1.txt"] == "Content 1"
        assert multi_res["file2.txt"] == "Content 2"
        assert "Error" in multi_res["nonexistent.txt"]
        print("OK")

        # 3. Media file read
        print("Testing fs_read_media_file...", end=" ")
        img_file = "test.png"
        with open(os.path.join(root1, img_file), 'wb') as f:
            f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
        media_res = await fs_read_media_file(img_file)
        assert "mimeType" in media_res and "data" in media_res
        assert media_res["mimeType"] == "image/png"
        print("OK")

        # 4. Directory Tree
        print("Testing fs_get_directory_tree...", end=" ")
        os.makedirs(os.path.join(root1, "subdir"))
        await fs_write_file("subdir/inner.txt", "inner")
        tree = await fs_get_directory_tree(".")
        subdir_node = next((n for n in tree if n["name"] == "subdir"), None)
        assert subdir_node is not None and subdir_node["type"] == "directory"
        assert any(c["name"] == "inner.txt" for c in subdir_node["children"])
        print("OK")

        # 5. List Dir with Sizes
        print("Testing fs_list_dir with sizes...", end=" ")
        dir_res = await fs_list_dir(".", with_sizes=True)
        assert isinstance(dir_res, list)
        assert isinstance(dir_res[0], dict)
        assert "size" in dir_res[0]
        print("OK")

        # 6. Range Reading & Context
        print("Testing read ranges/context...", end=" ")
        long_file = "long.txt"
        lines = [f"L{i+1}" for i in range(10)]
        await fs_write_file(long_file, "\n".join(lines))
        # Read lines 2 to 3 (1-indexed)
        res_range = await fs_read_file(long_file, start_line=2, end_line=3)
        assert "L2" in res_range and "L3" in res_range
        res_ctx = await fs_read_with_context(long_file, line=5, context_lines=1)
        assert "L4" in res_ctx and "L6" in res_ctx
        print("OK")

        # 7. Surgical Edits & Previews
        print("Testing surgical edits...", end=" ")
        edit_file = "edit.txt"
        await fs_write_file(edit_file, "Line A\nLine B\nLine C")
        from fs_server import FileEdit
        edits = [FileEdit(oldText="Line B", newText="Line B-Modified")]
        preview = await fs_preview_edit(edit_file, edits)
        assert "-Line B" in preview and "+Line B-Modified" in preview
        
        edit_res = await fs_edit_file(edit_file, edits)
        assert "Successfully applied" in edit_res
        final = await fs_read_file(edit_file)
        assert "Line B-Modified" in final
        print("OK")

        print("\nAll comprehensive tests passed successfully!")

    except Exception as e:
        print(f"\nTest failed: {e}")
        raise e
    finally:
        if os.path.exists(base_test_dir):
            shutil.rmtree(base_test_dir)
            print("Cleaned up test directory.")

if __name__ == "__main__":
    asyncio.run(run_tests())
