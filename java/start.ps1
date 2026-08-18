# ===== Java 後端啟動腳本 =====
# 用法: .\start.ps1
# 功能: 自動加載根目錄 .env、設置 JDK 21、啟動 Spring Boot 後端（端口 8090）

$ErrorActionPreference = "Stop"
# java -version 輸出到 stderr，需要臨時放寬
$ErrorActionPreference = "SilentlyContinue"
$javaVer = & java -version 2>&1 | Out-String
$ErrorActionPreference = "Stop"
Write-Host $javaVer.Trim() -ForegroundColor Gray

# 項目根目錄（腳本所在目錄的上一級）
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $ProjectRoot ".env"

# 1. 設置 JDK 21
$Jdk21Path = "C:\Users\13026\.jdks\ms-21.0.9"
if (-not (Test-Path $Jdk21Path)) {
    # 嘗試常見路徑
    $candidates = @(
        "C:\Program Files\Eclipse Adoptium\jdk-21*",
        "C:\Program Files\Microsoft\jdk-21*",
        "C:\Program Files\Java\jdk-21*"
    )
    foreach ($pattern in $candidates) {
        $found = Get-ChildItem $pattern -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) { $Jdk21Path = $found.FullName; break }
    }
}
if (Test-Path $Jdk21Path) {
    $env:JAVA_HOME = $Jdk21Path
    $env:Path = "$Jdk21Path\bin;$env:Path"
    Write-Host "[OK] JAVA_HOME = $Jdk21Path" -ForegroundColor Green
} else {
    Write-Host "[WARN] 未找到 JDK 21，使用系統默認 Java" -ForegroundColor Yellow
}

# 2. 加載根目錄 .env
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line -match '^\s*([A-Z_]+)\s*=\s*(.+)$') {
            $key = $matches[1]
            $val = $matches[2].Trim('"').Trim("'")
            Set-Item -Path "env:$key" -Value $val
        }
    }
    Write-Host "[OK] 已加載 .env 環境變量" -ForegroundColor Green
    if ($env:DB_PASSWORD) {
        Write-Host "      DB_USER=$env:DB_USER, DB_HOST=$env:DB_HOST, DB_PORT=$env:DB_PORT, DB_NAME=$env:DB_NAME" -ForegroundColor Gray
    }
} else {
    Write-Host "[WARN] 未找到 .env 文件: $EnvFile" -ForegroundColor Yellow
    Write-Host "      數據庫密碼將為空，可能導致連接失敗" -ForegroundColor Yellow
}

# 3. 檢查端口 8090 是否被佔用（去重 PID，處理多個連接和已退出進程）
$portConns = Get-NetTCPConnection -LocalPort 8090 -State Listen -ErrorAction SilentlyContinue
if ($portConns) {
    $portPids = $portConns.OwningProcess | Sort-Object -Unique | Where-Object { $_ -ne 0 }
    if ($portPids) {
        $pidList = $portPids -join ", "
        $procNames = @()
        foreach ($p in $portPids) {
            $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
            if ($proc) { $procNames += "$p ($($proc.ProcessName))" }
            else { $procNames += "$p (已退出)" }
        }
        Write-Host "[WARN] 端口 8090 已被佔用: $($procNames -join ', ')" -ForegroundColor Yellow
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

# 4. 啟動 Spring Boot
Write-Host "[INFO] 啟動 Java 後端（端口 8090）..." -ForegroundColor Cyan
Set-Location $PSScriptRoot
mvn spring-boot:run
