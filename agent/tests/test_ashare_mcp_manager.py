"""a-share-mcp 管理器測試。"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ashare_mcp_manager import AShareMcpManager, ashare_mcp_manager


class TestAShareMcpManager:
    """a-share-mcp 子進程管理器測試。"""

    def test_initial_state(self):
        """初始狀態：未運行。"""
        mgr = AShareMcpManager()
        assert mgr.is_running is False
        assert mgr._process is None

    def test_is_running_with_active_process(self):
        """有活躍進程時 is_running 為 True。"""
        mgr = AShareMcpManager()
        mock_proc = MagicMock()
        mock_proc.returncode = None  # 進程仍在運行
        mgr._process = mock_proc
        assert mgr.is_running is True

    def test_is_running_with_exited_process(self):
        """進程已退出時 is_running 為 False。"""
        mgr = AShareMcpManager()
        mock_proc = MagicMock()
        mock_proc.returncode = 0  # 進程已退出
        mgr._process = mock_proc
        assert mgr.is_running is False

    @pytest.mark.asyncio
    async def test_start_skips_if_already_running(self):
        """已在運行時跳過啟動。"""
        mgr = AShareMcpManager()
        mock_proc = MagicMock()
        mock_proc.returncode = None
        mgr._process = mock_proc

        result = await mgr.start()
        assert result is True

    @pytest.mark.asyncio
    async def test_start_returns_false_if_dir_not_exists(self):
        """a-share-mcp 目錄不存在時返回 False。"""
        mgr = AShareMcpManager()
        with patch.object(Path, "exists", return_value=False):
            result = await mgr.start()
            assert result is False

    @pytest.mark.asyncio
    async def test_stop_with_no_process(self):
        """無進程時 stop 不報錯。"""
        mgr = AShareMcpManager()
        await mgr.stop()  # 不應拋異常

    @pytest.mark.asyncio
    async def test_stop_with_already_exited_process(self):
        """進程已退出時 stop 清理引用。"""
        mgr = AShareMcpManager()
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mgr._process = mock_proc
        await mgr.stop()
        assert mgr._process is None

    def test_global_instance_exists(self):
        """全局實例存在。"""
        assert ashare_mcp_manager is not None
        assert isinstance(ashare_mcp_manager, AShareMcpManager)
