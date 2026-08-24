# ===== Java 後端啟動腳本 =====
# 用法: .\start.ps1
# 功能: 自動加載 .env、設置 JDK 21、啟動 Spring Boot 後端（端口 8090）
# 環境變量加載順序：java/.env（優先）→ 根目錄 .env（降級兼容）

$ErrorActionPreference = "Stop"
# java -version 輸出到 stderr，需要臨時放寬
$ErrorActionPreference = "SilentlyContinue"
$javaVer = & java -version 2>&1 | Out-String
$ErrorActionPreference = "Stop"
Write-Host $javaVer.Trim() -ForegroundColor Gray

# 環境變量文件：優先 java/.env（自足模式），降級到根目錄 .env（向後兼容）
$LocalEnv = Join-Path $PSScriptRoot ".env"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RootEnv = Join-Path $ProjectRoot ".env"
$EnvFile = $null
$EnvSource = ""

if (Test-Path $LocalEnv) {
    $EnvFile = $LocalEnv
    $EnvSource = "java/.env"
} elseif (Test-Path $RootEnv) {
    $EnvFile = $RootEnv
    $EnvSource = "根目錄 .env（建議遷移到 java/.env 實現目錄自足）"
}

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

# 2. 加載 .env 環境變量
if ($EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line -match '^\s*([A-Z_]+)\s*=\s*(.+)$') {
            $key = $matches[1]
            $val = $matches[2].Trim('"').Trim("'")
            Set-Item -Path "env:$key" -Value $val
        }
    }
    Write-Host "[OK] 已加載 $EnvSource" -ForegroundColor Green
    if ($env:DB_PASSWORD) {
        Write-Host "      DB_USER=$env:DB_USER, DB_HOST=$env:DB_HOST, DB_PORT=$env:DB_PORT, DB_NAME=$env:DB_NAME" -ForegroundColor Gray
    }
} else {
    Write-Host "[WARN] 未找到 .env 文件" -ForegroundColor Yellow
    Write-Host "      已查找: $LocalEnv 和 $RootEnv" -ForegroundColor Gray
    Write-Host "      請從 java/.env.example 複製為 java/.env 並填寫數據庫密碼等" -ForegroundColor Yellow
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
# 設置 JVM 編碼為 UTF-8，解決 Windows 終端中文亂碼
$env:JAVA_TOOL_OPTIONS = "-Dfile.encoding=UTF-8 -Dsun.jnu.encoding=UTF-8"
# 同時設置 PowerShell 控制台輸出編碼為 UTF-8
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
try { chcp 65001 | Out-Null } catch {}

Write-Host "[INFO] 啟動 Java 後端（端口 8090，UTF-8 編碼）..." -ForegroundColor Cyan
Set-Location $PSScriptRoot
mvn spring-boot:run "-Dspring-boot.run.jvmArguments=-Dfile.encoding=UTF-8 -Dsun.jnu.encoding=UTF-8"
