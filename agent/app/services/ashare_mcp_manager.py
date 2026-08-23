"""a-share-mcp 子進程管理器 — Agent 啟動時自動拉起 a-share-mcp HTTP 服務。

a-share-mcp 是基於 Baostock 的 A 股 MCP 服務器，提供 23 個數據工具。
本模塊在 Agent 服務啟動時自動啟動 a-share-mcp 子進程，在 Agent 關閉時自動清理。

依賴：
- a-share-mcp 項目位於項目根目錄下的 a-share-mcp/ 子目錄
- 使用 uv 管理依賴（uv sync 已安裝 .venv）
- 默認監聽端口 8101（可通過 A_SHARE_MCP_PORT 環境變量配置）
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from pathlib import Path

logger = logging.getLogger("agent.services.ashare_mcp")

# a-share-mcp 項目目錄（相對於 agent 目錄的上兩級）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_ASHARE_MCP_DIR = _PROJECT_ROOT / "a-share-mcp"
_DEFAULT_PORT = 8101


class AShareMcpManager:
    """a-share-mcp 子進程生命週期管理器。"""

    def __init__(self):
        self._process: asyncio.subprocess.Process | None = None
        self._started = False

    @property
    def is_running(self) -> bool:
        """子進程是否正在運行。"""
        return self._process is not None and self._process.returncode is None

    async def start(self) -> bool:
        """啟動 a-share-mcp HTTP 服務。

        Returns:
            bool: True 表示成功啟動或已經在運行，False 表示啟動失敗
        """
        if self.is_running:
            logger.info("a-share-mcp 已在運行，跳過啟動")
            return True

        # 檢查 a-share-mcp 目錄是否存在
        if not _ASHARE_MCP_DIR.exists():
            logger.warning(
                f"a-share-mcp 目錄不存在: {_ASHARE_MCP_DIR}，跳過自動啟動。"
                f"如需 A 股歷史數據工具，請克隆 ashare-mcp 項目到此目錄。"
            )
            return False

        # 檢查 .venv 是否已安裝（uv sync 已執行）
        venv_dir = _ASHARE_MCP_DIR / ".venv"
        if not venv_dir.exists():
            logger.warning(
                f"a-share-mcp 的 .venv 不存在，請先在 {_ASHARE_MCP_DIR} 中執行 'uv sync'"
            )
            return False

        port = int(os.environ.get("A_SHARE_MCP_PORT", _DEFAULT_PORT))

        # 構建啟動命令：uv run python -m ashare_mcp --transport http --port <port>
        cmd = ["uv", "run", "python", "-m", "ashare_mcp", "--transport", "http", "--port", str(port)]

        logger.info(f"啟動 a-share-mcp（端口 {port}）: {' '.join(cmd)}")

        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(_ASHARE_MCP_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                # Windows 下創建新的進程組，方便整組終止
                creationflags=signal.CTRL_BREAK_EVENT if os.name == "nt" else 0,
            )
            self._started = True
            logger.info(f"a-share-mcp 子進程已啟動 (PID={self._process.pid})")

            # 等待服務就緒（最多等待 15 秒）
            ready = await self._wait_for_ready(port, timeout=15)
            if ready:
                logger.info(f"a-share-mcp 服務已就緒 (http://localhost:{port}/mcp)")
            else:
                logger.warning(
                    f"a-share-mcp 服務在 15 秒內未就緒，聊天工具可能無法連接。"
                    f"服務可能仍在啟動中（baostock 首次連接較慢）。"
                )
            return True

        except Exception as e:
            logger.error(f"啟動 a-share-mcp 失敗: {e}", exc_info=True)
            self._process = None
            self._started = False
            return False

    async def _wait_for_ready(self, port: int, timeout: float = 15.0) -> bool:
        """等待 a-share-mcp HTTP 服務就緒（輪詢健康檢查）。"""
        import httpx

        url = f"http://localhost:{port}/mcp"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        init_body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "agent-health-check", "version": "1.0"},
            },
        }

        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.post(url, headers=headers, json=init_body)
                    if resp.status_code == 200:
                        return True
            except (httpx.ConnectError, httpx.TimeoutException, OSError):
                pass
            await asyncio.sleep(1.0)

        return False

    async def stop(self):
        """停止 a-share-mcp 子進程。"""
        if self._process is None:
            return

        if self._process.returncode is not None:
            logger.info(f"a-share-mcp 進程已退出 (code={self._process.returncode})")
            self._process = None
            return

        logger.info("正在停止 a-share-mcp 子進程...")

        try:
            # 嘗試優雅終止
            if os.name == "nt":
                # Windows: 用 CTRL_BREAK_EVENT 發送信號到進程組
                self._process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                self._process.terminate()

            # 等待最多 5 秒
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
                logger.info("a-share-mcp 子進程已優雅停止")
            except asyncio.TimeoutError:
                # 強制終止
                logger.warning("a-share-mcp 未在 5 秒內停止，強制終止")
                self._process.kill()
                await self._process.wait()
                logger.info("a-share-mcp 子進程已強制終止")

        except Exception as e:
            logger.warning(f"停止 a-share-mcp 時異常: {e}")
        finally:
            self._process = None
            self._started = False


# 全局管理器實例
ashare_mcp_manager = AShareMcpManager()
