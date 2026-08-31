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

# a-share-mcp 項目目錄：
# - 本地開發：相對於 agent 目錄的上兩級（項目根目錄 / a-share-mcp）
# - Docker 部署：通過 ASHARE_MCP_DIR 環境變量覆蓋（如 /opt/a-share-mcp）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_ASHARE_MCP_ENV = os.environ.get("ASHARE_MCP_DIR", "").strip()
_ASHARE_MCP_DIR = Path(_ASHARE_MCP_ENV) if _ASHARE_MCP_ENV else _PROJECT_ROOT / "a-share-mcp"
_DEFAULT_PORT = 8101
# baostock 首次連接較慢，需要較長的就緒等待時間
_READY_TIMEOUT = 30.0


class AShareMcpManager:
    """a-share-mcp 子進程生命週期管理器。"""

    def __init__(self):
        self._process: asyncio.subprocess.Process | None = None
        self._started = False
        self._port: int = int(os.environ.get("A_SHARE_MCP_PORT", _DEFAULT_PORT))
        # HTTP 服務是否已確認就緒（獨立於進程是否存活）
        self._ready: bool = False
        # 後台讀取 stdout/stderr 的任務（避免 pipe buffer 滿導致死鎖）
        self._pipe_tasks: list[asyncio.Task] = []

    @property
    def is_running(self) -> bool:
        """子進程是否正在運行。"""
        return self._process is not None and self._process.returncode is None

    async def ensure_running(self) -> bool:
        """確保 a-share-mcp 服務正在運行且 HTTP 已就緒。

        用於工具調用前的健康檢查：
        - 如果進程已死 → 自動重啟
        - 如果進程活著但 HTTP 未就緒 → 等待就緒
        - 如果進程活著且 HTTP 已就緒 → 立即返回
        """
        # 進程未運行 → 重啟
        if not self.is_running:
            logger.warning("a-share-mcp 進程未運行，嘗試自動重啟...")
            self._ready = False
            return await self.start()

        # 進程活著但 HTTP 未確認就緒 → 等待就緒
        if not self._ready:
            logger.info("a-share-mcp 進程運行中但 HTTP 尚未就緒，等待就緒...")
            self._ready = await self._wait_for_ready(self._port, timeout=_READY_TIMEOUT)
            if self._ready:
                logger.info(f"a-share-mcp 服務已就緒 (http://localhost:{self._port}/mcp)")
            else:
                logger.warning(
                    f"a-share-mcp 服務在 {_READY_TIMEOUT}s 內仍未就緒，"
                    f"可能是 baostock 初始化失敗或 pipe 死鎖。將殺死進程並重啟。"
                )
                # 進程活著但 HTTP 一直不就緒 → 可能是子進程崩潰，殺死重啟
                await self._kill_process()
                self._ready = False
                return await self.start()

        return True

    async def start(self) -> bool:
        """啟動 a-share-mcp HTTP 服務。

        Returns:
            bool: True 表示成功啟動或已經在運行，False 表示啟動失敗
        """
        if self.is_running:
            logger.info("a-share-mcp 已在運行，跳過啟動")
            return True

        # 如果之前的進程已退出，清理引用
        if self._process is not None and self._process.returncode is not None:
            logger.info(f"a-share-mcp 前一進程已退出 (code={self._process.returncode})，清理引用")
            self._process = None
        self._ready = False
        self._cancel_pipe_tasks()

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

        port = self._port

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

            # 啟動後台任務持續讀取 stdout/stderr，避免 pipe buffer 滿導致死鎖
            self._start_pipe_drainers()

            # 等待服務就緒（最多等待 30 秒，baostock 首次連接較慢）
            self._ready = await self._wait_for_ready(port, timeout=_READY_TIMEOUT)
            if self._ready:
                logger.info(f"a-share-mcp 服務已就緒 (http://localhost:{port}/mcp)")
            else:
                logger.warning(
                    f"a-share-mcp 服務在 {_READY_TIMEOUT}s 內未就緒。"
                    f"服務可能仍在啟動中（baostock 首次連接較慢）。"
                )
            return True

        except Exception as e:
            logger.error(f"啟動 a-share-mcp 失敗: {e}", exc_info=True)
            self._process = None
            self._started = False
            self._ready = False
            self._cancel_pipe_tasks()
            return False

    def _start_pipe_drainers(self):
        """啟動後台任務持續讀取子進程 stdout/stderr，避免 pipe buffer 滿導致死鎖。"""
        if self._process is None:
            return

        async def _drain_stream(stream, name: str, level: int = logging.INFO):
            try:
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    text = line.decode("utf-8", errors="replace").rstrip()
                    if text:
                        logger.log(level, f"[a-share-mcp {name}] {text}")
            except Exception as e:
                logger.debug(f"讀取 a-share-mcp {name} 結束: {e}")

        if self._process.stdout:
            self._pipe_tasks.append(asyncio.create_task(_drain_stream(self._process.stdout, "stdout")))
        if self._process.stderr:
            self._pipe_tasks.append(asyncio.create_task(_drain_stream(self._process.stderr, "stderr", logging.WARNING)))

    def _cancel_pipe_tasks(self):
        """取消並清理 pipe 讀取任務。"""
        for task in self._pipe_tasks:
            task.cancel()
        self._pipe_tasks.clear()

    async def _wait_for_ready(self, port: int, timeout: float = _READY_TIMEOUT) -> bool:
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
            # 先檢查進程是否已退出（避免對著死進程輪詢）
            if self._process and self._process.returncode is not None:
                logger.warning(f"a-share-mcp 進程已退出 (code={self._process.returncode})，停止等待就緒")
                return False
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.post(url, headers=headers, json=init_body)
                    if resp.status_code == 200:
                        return True
            except (httpx.ConnectError, httpx.TimeoutException, OSError):
                pass
            await asyncio.sleep(1.0)

        return False

    async def _kill_process(self):
        """強制殺死子進程（內部使用）。"""
        if self._process is None:
            return
        try:
            if os.name == "nt":
                self._process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()
        except Exception as e:
            logger.warning(f"殺死 a-share-mcp 進程時異常: {e}")
        finally:
            self._process = None
            self._ready = False
            self._cancel_pipe_tasks()

    async def stop(self):
        """停止 a-share-mcp 子進程。"""
        if self._process is None:
            self._ready = False
            self._cancel_pipe_tasks()
            return

        if self._process.returncode is not None:
            logger.info(f"a-share-mcp 進程已退出 (code={self._process.returncode})")
            self._process = None
            self._ready = False
            self._cancel_pipe_tasks()
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
            self._ready = False
            self._cancel_pipe_tasks()


# 全局管理器實例
ashare_mcp_manager = AShareMcpManager()
