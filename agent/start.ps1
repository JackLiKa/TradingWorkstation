# ===== Agent 服務啟動腳本 =====
# 用法: .\start.ps1
# 功能: 選擇正確的 Python（避免 Microsoft Store python3）、加載 agent/.env、啟動 FastAPI（端口 8100）

$ErrorActionPreference = "Stop"

# 1. 選擇 Python（優先 C:\Python314，避免 Microsoft Store python3）
$PythonExe = $null

# 優先級 1: C:\Python314\python.exe（已安裝 uvicorn）
$candidate = "C:\Python314\python.exe"
if (Test-Path $candidate) {
    $PythonExe = $candidate
}

# 優先級 2: where python 的第一個結果（跳過 WindowsApps）
if (-not $PythonExe) {
    $pythons = where.exe python 2>&1 | Where-Object { $_ -and -not $_.ToString().Contains("WindowsApps") }
    if ($pythons -and $pythons.Count -gt 0) {
        $PythonExe = $pythons[0].ToString().Trim()
    }
}

if (-not $PythonExe) {
    Write-Host "[ERROR] 未找到合適的 Python，請安裝 Python 3.10+ 並 pip install uvicorn fastapi" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Python = $PythonExe" -ForegroundColor Green
& $PythonExe --version

# 2. 檢查 uvicorn 和 fastapi
$checkResult = & $PythonExe -c "import uvicorn; import fastapi; print('OK')" 2>&1
if ($checkResult -ne "OK") {
    Write-Host "[INFO] 缺少依賴，安裝中..." -ForegroundColor Cyan
    Set-Location $PSScriptRoot
    & $PythonExe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] 依賴安裝失敗" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] 依賴安裝完成" -ForegroundColor Green
} else {
    Write-Host "[OK] uvicorn + fastapi 已安裝" -ForegroundColor Green
}

# 3. 加載 agent/.env
$AgentEnv = Join-Path $PSScriptRoot ".env"
if (Test-Path $AgentEnv) {
    Get-Content $AgentEnv | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line -match '^\s*([A-Z_]+)\s*=\s*(.+)$') {
            $key = $matches[1]
            $val = $matches[2].Trim('"').Trim("'")
            Set-Item -Path "env:$key" -Value $val
        }
    }
    Write-Host "[OK] 已加載 agent/.env" -ForegroundColor Green
} else {
    Write-Host "[WARN] 未找到 agent/.env，請從 agent/.env.example 複製" -ForegroundColor Yellow
}

# 4. 檢查端口 8100 是否被佔用（去重 PID，處理多個連接和已退出進程）
$portConns = Get-NetTCPConnection -LocalPort 8100 -State Listen -ErrorAction SilentlyContinue
if ($portConns) {
    $portPids = $portConns.OwningProcess | Sort-Object -Unique | Where-Object { $_ -ne 0 }
    if ($portPids) {
        $procNames = @()
        foreach ($p in $portPids) {
            $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
            if ($proc) { $procNames += "$p ($($proc.ProcessName))" }
            else { $procNames += "$p (已退出)" }
        }
        Write-Host "[WARN] 端口 8100 已被佔用: $($procNames -join ', ')" -ForegroundColor Yellow
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

# 5. 啟動 Agent 服務
Write-Host "[INFO] 啟動 Agent 服務（端口 8100）..." -ForegroundColor Cyan
Set-Location $PSScriptRoot
& $PythonExe -m uvicorn app.main:app --host 0.0.0.0 --port 8100
