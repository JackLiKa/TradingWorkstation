# ===== Next.js 前端啟動腳本 =====
# 用法: .\start.ps1
# 功能: 檢查依賴、啟動 Next.js 開發服務器（端口 3010）

$ErrorActionPreference = "Stop"

# 1. 檢查 Node.js
try {
    $nodeVer = node --version 2>&1
    Write-Host "[OK] Node.js $nodeVer" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] 未找到 Node.js，請安裝 Node.js 18+" -ForegroundColor Red
    exit 1
}

# 2. 檢查 node_modules
$NodeModules = Join-Path $PSScriptRoot "node_modules"
if (-not (Test-Path $NodeModules)) {
    Write-Host "[INFO] 首次運行，安裝依賴中..." -ForegroundColor Cyan
    Set-Location $PSScriptRoot
    npm install --legacy-peer-deps
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] npm install 失敗" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] 依賴安裝完成" -ForegroundColor Green
}

# 3. 檢查端口 3010 是否被佔用（去重 PID，處理多個連接和已退出進程）
$portConns = Get-NetTCPConnection -LocalPort 3010 -State Listen -ErrorAction SilentlyContinue
if ($portConns) {
    $portPids = $portConns.OwningProcess | Sort-Object -Unique | Where-Object { $_ -ne 0 }
    if ($portPids) {
        $procNames = @()
        foreach ($p in $portPids) {
            $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
            if ($proc) { $procNames += "$p ($($proc.ProcessName))" }
            else { $procNames += "$p (已退出)" }
        }
        Write-Host "[WARN] 端口 3010 已被佔用: $($procNames -join ', ')" -ForegroundColor Yellow
        $choice = Read-Host "是否終止該進程並重啟？(y/N)"
        if ($choice -eq 'y' -or $choice -eq 'Y') {
            foreach ($p in $portPids) {
                try {
                    $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
                    if ($proc) {
                        Stop-Process -Id $p -Force -ErrorAction Stop
                        Write-Host "[OK] 已終止 PID=$p ($($proc.ProcessName))" -ForegroundColor Green
                    } else {
                        Write-Host "[OK] PID=$p 已自行退出，跳過" -ForegroundColor Gray
                    }
                } catch {
                    Write-Host "[WARN] 終止 PID=$p 失敗: $($_.Exception.Message)" -ForegroundColor Yellow
                }
            }
            Start-Sleep -Seconds 2
        } else {
            Write-Host "[INFO] 用戶取消，退出" -ForegroundColor Gray
            exit 0
        }
    }
}

# 4. 啟動 Next.js
Write-Host "[INFO] 啟動 Next.js 前端（端口 3010）..." -ForegroundColor Cyan
Set-Location $PSScriptRoot
npm run dev
