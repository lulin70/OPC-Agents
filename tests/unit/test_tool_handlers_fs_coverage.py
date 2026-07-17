"""FileSystemHandlers 覆盖率补充测试

覆盖 `opc_manager/tool_handlers_fs.py` 中以下未覆盖路径：
- `_execute_file_read` 正常 / 路径拒绝 / 文件读取失败 分支
- `_execute_file_write` 新建 / 已存在拒绝 / overwrite / 自动建目录 / 路径拒绝 分支
- `_execute_file_list` 正常 / pattern 过滤 / 路径拒绝 / 目录不存在 分支
- `_read_file_sync` / `_write_file_sync` / `_list_files_sync` 静态方法
- `_validate_path` / `_ensure_allowed_dirs` / `_configure_allowed_dirs` 辅助函数

使用真实文件系统（tmp_path），不 Mock 文件操作。
"""

import os

import pytest

from opc_manager.tool_handlers_fs import (
    FileSystemHandlers,
    _ALLOWED_BASE_DIRS,
    _configure_allowed_dirs,
    _ensure_allowed_dirs,
    _validate_path,
)
from opc_manager.tool_audit_logger import AuditLogger


class _FsHandler(FileSystemHandlers):
    """FileSystemHandlers 是 Mixin，需要一个具体子类实例化后才能调用 self 方法。"""

    pass


@pytest.fixture
def fs_handler() -> _FsHandler:
    """提供独立的 FileSystemHandlers 实例。"""
    return _FsHandler()


@pytest.fixture(autouse=True)
def _isolate_allowed_dirs(tmp_path):
    """每个测试将白名单目录限定到 tmp_path，避免污染项目 data/output/logs。"""
    _configure_allowed_dirs([str(tmp_path)])
    yield
    # 恢复为"不限制"状态（仅拒绝 '..'），避免影响后续测试
    _configure_allowed_dirs([])


@pytest.fixture(autouse=True)
def _isolate_audit_log(tmp_path):
    """将 AuditLogger 重定向到 tmp_path，避免写入项目 logs/。"""
    AuditLogger.configure(str(tmp_path / "audit.jsonl"))
    AuditLogger._write_queue = None
    AuditLogger._writer_task = None
    AuditLogger._shutdown_event = None
    yield


# ─── 辅助函数: _validate_path / _ensure_allowed_dirs ──────────────


class TestValidatePath:
    """覆盖 _validate_path 与 _ensure_allowed_dirs。"""

    def test_dotdot_in_path_rejected(self):
        """路径分段中出现 '..'（normpath 后仍保留）应被拒绝，防止目录穿越。

        注意：os.path.normpath 会折叠 'a/../b'，因此必须使用以 '..' 开头的
        相对路径才能让 '..' 在校验时存活，覆盖 line 50 的拒绝分支。
        """
        with pytest.raises(ValueError) as ctx:
            _validate_path("../malicious.txt")
        assert "路径不允许包含 '..'" in str(ctx.value)

    def test_path_outside_allowed_dirs_rejected(self):
        """路径不在白名单目录下应被拒绝。"""
        with pytest.raises(ValueError) as ctx:
            _validate_path("/etc/passwd")
        assert "超出允许范围" in str(ctx.value)

    def test_path_within_allowed_dirs_returns_realpath(self, tmp_path):
        """白名单内的路径返回其 realpath。"""
        target = tmp_path / "file.txt"
        result = _validate_path(str(target))
        assert result == os.path.realpath(str(target))

    def test_ensure_allowed_dirs_idempotent(self):
        """_ensure_allowed_dirs 多次调用不会重置已配置的白名单。"""
        _ensure_allowed_dirs()
        first = list(_ALLOWED_BASE_DIRS)
        _ensure_allowed_dirs()
        second = list(_ALLOWED_BASE_DIRS)
        assert first == second


# ─── _execute_file_read ───────────────────────────────────────────


class TestExecuteFileRead:
    """覆盖 _execute_file_read 各分支。"""

    @pytest.mark.asyncio
    async def test_read_existing_file_success(self, fs_handler, tmp_path):
        """正常读取已存在文件应返回 content 与 safe_path。"""
        target = tmp_path / "read.txt"
        target.write_text("hello world", encoding="utf-8")

        result = await fs_handler._execute_file_read(str(target))

        assert result["content"] == "hello world"
        assert result["file_path"] == os.path.realpath(str(target))

    @pytest.mark.asyncio
    async def test_read_with_custom_encoding(self, fs_handler, tmp_path):
        """指定 encoding 参数应按该编码读取。"""
        target = tmp_path / "gbk.txt"
        target.write_text("你好", encoding="gbk")

        result = await fs_handler._execute_file_read(str(target), encoding="gbk")

        assert result["content"] == "你好"

    @pytest.mark.asyncio
    async def test_read_dotdot_path_rejected(self, fs_handler):
        """路径含 '..'（normpath 后仍保留）触发 PATH_REJECTED 并抛出 '路径校验失败'。

        注意：os.path.normpath 会折叠 'a/../b'，因此必须使用以 '..' 开头的
        相对路径才能让 '..' 在校验时存活。
        """
        bad_path = "../malicious_read.txt"

        with pytest.raises(Exception) as ctx:
            await fs_handler._execute_file_read(bad_path)

        assert "路径校验失败" in str(ctx.value)
        assert ".." in str(ctx.value)

    @pytest.mark.asyncio
    async def test_read_outside_allowed_rejected(self, fs_handler):
        """越界路径读取应被拒绝。"""
        with pytest.raises(Exception) as ctx:
            await fs_handler._execute_file_read("/etc/passwd")

        assert "路径校验失败" in str(ctx.value)

    @pytest.mark.asyncio
    async def test_read_nonexistent_file_raises(self, fs_handler, tmp_path):
        """读取不存在的文件应抛出 '文件读取失败'。"""
        missing = tmp_path / "no_such_file.txt"

        with pytest.raises(Exception) as ctx:
            await fs_handler._execute_file_read(str(missing))

        assert "文件读取失败" in str(ctx.value)

    @pytest.mark.asyncio
    async def test_read_input_too_long_rejected(self, fs_handler):
        """file_path 超长应被 _validate_input_length 拒绝（归入 ValueError 分支）。"""
        long_path = "x" * 501

        with pytest.raises(Exception) as ctx:
            await fs_handler._execute_file_read(long_path)

        assert "路径校验失败" in str(ctx.value)


# ─── _read_file_sync (static) ─────────────────────────────────────


class TestReadFileSync:
    """覆盖 _read_file_sync 静态方法。"""

    def test_read_file_sync_returns_content(self, tmp_path):
        target = tmp_path / "sync.txt"
        target.write_text("sync-content", encoding="utf-8")

        content = FileSystemHandlers._read_file_sync(str(target), "utf-8")

        assert content == "sync-content"


# ─── _execute_file_write ──────────────────────────────────────────


class TestExecuteFileWrite:
    """覆盖 _execute_file_write 各分支。"""

    @pytest.mark.asyncio
    async def test_write_new_file_success(self, fs_handler, tmp_path):
        """写入新文件成功，返回 success=True 与 safe_path。"""
        target = tmp_path / "new.txt"

        result = await fs_handler._execute_file_write(str(target), "data")

        assert result["success"] is True
        assert result["file_path"] == os.path.realpath(str(target))
        assert target.read_text(encoding="utf-8") == "data"

    @pytest.mark.asyncio
    async def test_write_existing_without_overwrite_raises(self, fs_handler, tmp_path):
        """目标已存在且 overwrite=False 时抛出 '文件已存在'。"""
        target = tmp_path / "exists.txt"
        target.write_text("old", encoding="utf-8")

        with pytest.raises(Exception) as ctx:
            await fs_handler._execute_file_write(str(target), "new")

        assert "文件已存在" in str(ctx.value)
        # 原文件未被覆盖
        assert target.read_text(encoding="utf-8") == "old"

    @pytest.mark.asyncio
    async def test_write_existing_with_overwrite_success(self, fs_handler, tmp_path):
        """overwrite=True 时覆盖已有文件。"""
        target = tmp_path / "overwrite.txt"
        target.write_text("old", encoding="utf-8")

        result = await fs_handler._execute_file_write(
            str(target), "new", overwrite=True
        )

        assert result["success"] is True
        assert target.read_text(encoding="utf-8") == "new"

    @pytest.mark.asyncio
    async def test_write_auto_creates_nested_directory(self, fs_handler, tmp_path):
        """写入时自动创建不存在的多级父目录。"""
        nested = tmp_path / "a" / "b" / "c" / "deep.txt"

        result = await fs_handler._execute_file_write(str(nested), "deep")

        assert result["success"] is True
        assert nested.read_text(encoding="utf-8") == "deep"

    @pytest.mark.asyncio
    async def test_write_dotdot_path_rejected(self, fs_handler):
        """路径含 '..'（normpath 后仍保留）应被拒绝。

        注意：os.path.normpath 会折叠 'a/../b'，因此必须使用以 '..' 开头的
        相对路径才能让 '..' 在校验时存活。
        """
        bad_path = "../malicious_write.txt"

        with pytest.raises(Exception) as ctx:
            await fs_handler._execute_file_write(bad_path, "x")

        assert "路径校验失败" in str(ctx.value)
        assert ".." in str(ctx.value)

    @pytest.mark.asyncio
    async def test_write_outside_allowed_rejected(self, fs_handler):
        """越界路径写入应被拒绝。"""
        with pytest.raises(Exception) as ctx:
            await fs_handler._execute_file_write("/etc/evil.txt", "x")

        assert "路径校验失败" in str(ctx.value)

    @pytest.mark.asyncio
    async def test_write_with_custom_encoding(self, fs_handler, tmp_path):
        """指定 encoding 写入后用相同编码读回。"""
        target = tmp_path / "enc.txt"

        await fs_handler._execute_file_write(str(target), "你好", encoding="utf-8")

        assert target.read_text(encoding="utf-8") == "你好"

    @pytest.mark.asyncio
    async def test_write_input_too_long_rejected(self, fs_handler):
        """file_path 超长应被拒绝。"""
        long_path = "x" * 501

        with pytest.raises(Exception) as ctx:
            await fs_handler._execute_file_write(long_path, "x")

        assert "路径校验失败" in str(ctx.value)

    @pytest.mark.asyncio
    async def test_write_to_readonly_dir_raises_write_failure(
        self, fs_handler, tmp_path
    ):
        """写入只读目录应触发 '文件写入失败' 异常（覆盖 except 分支）。

        通过将父目录 chmod 为只读来真实触发 OSError，不使用 Mock。
        """
        import stat

        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        target = readonly_dir / "file.txt"

        # 撤销父目录写权限，使 open(..., "w") 创建文件失败
        readonly_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)

        try:
            with pytest.raises(Exception) as ctx:
                await fs_handler._execute_file_write(str(target), "data")
            assert "文件写入失败" in str(ctx.value)
        finally:
            # 恢复权限以便 pytest 清理 tmp_path
            readonly_dir.chmod(stat.S_IRWXU)


# ─── _write_file_sync (static) ────────────────────────────────────


class TestWriteFileSync:
    """覆盖 _write_file_sync 静态方法。"""

    def test_write_file_sync_writes_content(self, tmp_path):
        target = tmp_path / "wfs.txt"

        FileSystemHandlers._write_file_sync(str(target), "static-write", "utf-8")

        assert target.read_text(encoding="utf-8") == "static-write"


# ─── _execute_file_list ───────────────────────────────────────────


class TestExecuteFileList:
    """覆盖 _execute_file_list 各分支。"""

    @pytest.mark.asyncio
    async def test_list_success_returns_files_and_dirs(self, fs_handler, tmp_path):
        """正常列出目录，区分文件/目录并返回 size 元数据。"""
        (tmp_path / "a.txt").write_text("aaa", encoding="utf-8")
        (tmp_path / "subdir").mkdir()

        result = await fs_handler._execute_file_list(str(tmp_path))

        names = {f["name"] for f in result["files"]}
        assert {"a.txt", "subdir"} <= names
        a_entry = next(f for f in result["files"] if f["name"] == "a.txt")
        assert a_entry["is_dir"] is False
        assert a_entry["size"] == 3
        sub_entry = next(f for f in result["files"] if f["name"] == "subdir")
        assert sub_entry["is_dir"] is True
        assert sub_entry["size"] == 0
        assert result["directory"] == os.path.realpath(str(tmp_path))

    @pytest.mark.asyncio
    async def test_list_with_pattern_filter(self, fs_handler, tmp_path):
        """pattern 参数应过滤返回的文件名。"""
        (tmp_path / "match.txt").write_text("m", encoding="utf-8")
        (tmp_path / "skip.log").write_text("s", encoding="utf-8")

        result = await fs_handler._execute_file_list(str(tmp_path), pattern="*.txt")

        names = {f["name"] for f in result["files"]}
        assert names == {"match.txt"}

    @pytest.mark.asyncio
    async def test_list_dotdot_path_rejected(self, fs_handler):
        """路径含 '..'（normpath 后仍保留）应被拒绝。

        注意：os.path.normpath 会折叠 'a/../b'，因此必须使用以 '..' 开头的
        相对路径才能让 '..' 在校验时存活。
        """
        bad_path = "../malicious_dir"

        with pytest.raises(Exception) as ctx:
            await fs_handler._execute_file_list(bad_path)

        assert "路径校验失败" in str(ctx.value)
        assert ".." in str(ctx.value)

    @pytest.mark.asyncio
    async def test_list_outside_allowed_rejected(self, fs_handler):
        """越界路径列出应被拒绝。"""
        with pytest.raises(Exception) as ctx:
            await fs_handler._execute_file_list("/etc")

        assert "路径校验失败" in str(ctx.value)

    @pytest.mark.asyncio
    async def test_list_nonexistent_dir_raises(self, fs_handler, tmp_path):
        """列出不存在的目录应抛出 '文件列表获取失败'。"""
        missing = tmp_path / "no_dir"

        with pytest.raises(Exception) as ctx:
            await fs_handler._execute_file_list(str(missing))

        assert "文件列表获取失败" in str(ctx.value)


# ─── _list_files_sync (static) ────────────────────────────────────


class TestListFilesSync:
    """覆盖 _list_files_sync 静态方法。"""

    def test_list_files_sync_without_pattern(self, tmp_path):
        (tmp_path / "x.txt").write_text("x", encoding="utf-8")

        files = FileSystemHandlers._list_files_sync(str(tmp_path))

        assert "x.txt" in {f["name"] for f in files}

    def test_list_files_sync_with_pattern(self, tmp_path):
        (tmp_path / "keep.txt").write_text("k", encoding="utf-8")
        (tmp_path / "drop.md").write_text("d", encoding="utf-8")

        files = FileSystemHandlers._list_files_sync(str(tmp_path), "*.txt")

        assert {f["name"] for f in files} == {"keep.txt"}

    def test_list_files_sync_includes_dir_with_zero_size(self, tmp_path):
        """目录条目 is_dir=True 且 size=0。"""
        (tmp_path / "subdir").mkdir()

        files = FileSystemHandlers._list_files_sync(str(tmp_path))

        sub = next(f for f in files if f["name"] == "subdir")
        assert sub["is_dir"] is True
        assert sub["size"] == 0
