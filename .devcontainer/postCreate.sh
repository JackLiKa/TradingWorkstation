#!/usr/bin/env bash
# DevContainer 創建後初始化腳本
set -e

echo "===== Trading Workstation DevContainer 初始化 ====="

# 安裝 Python 依賴
echo ">>> 安裝 Agent 依賴..."
cd /workspace/agent
pip install -r requirements.txt -r requirements-dev.txt

# 安裝前端依賴
echo ">>> 安裝前端依賴..."
cd /workspace/next
npm install --legacy-peer-deps

# 安裝 pre-commit hooks
echo ">>> 安裝 pre-commit hooks..."
cd /workspace
pip install pre-commit
pre-commit install

echo "===== 初始化完成 ====="
echo "啟動順序: MySQL → Java(8090) → Next(3010) → Agent(8100)"
