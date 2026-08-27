# fix-java21-system.ps1
# 將系統級 Java 環境切換為 JDK 21
# 需要以管理員身份運行：右鍵 PowerShell → 以管理員身份運行 → 執行此腳本
#
# 用法：
#   Set-ExecutionPolicy Bypass -Scope Process -Force
#   .\fix-java21-system.ps1

$jdk21Path = "C:\Users\13026\.jdks\ms-21.0.9"

Write-Host "===== Java 21 系統環境修復腳本 =====" -ForegroundColor Cyan
Write-Host ""

# 1. 設置 System 級 JAVA_HOME
Write-Host "[1/3] 設置 System JAVA_HOME → $jdk21Path" -ForegroundColor Yellow
[System.Environment]::SetEnvironmentVariable("JAVA_HOME", $jdk21Path, "Machine")
Write-Host "  完成" -ForegroundColor Green

# 2. 清理 System PATH 中的舊 Java 路徑，確保 JDK 21 優先
Write-Host "[2/3] 清理 System PATH 中的舊 Java 路徑" -ForegroundColor Yellow
$sysPath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
$pathList = $sysPath -split ";" | Where-Object { $_ -ne "" }

Write-Host "  原始 System PATH 中的 Java 相關路徑：" -ForegroundColor Gray
$pathList | Where-Object { $_ -match "java|jdk|jre" } | ForEach-Object { Write-Host "    - $_" -ForegroundColor Gray }

# 移除所有舊 Java 路徑
$cleanedPath = $pathList | Where-Object {
    $_ -notmatch "Oracle\\Java\\javapath" -and
    $_ -notmatch "java8path" -and
    $_ -notmatch "javapath" -and
    $_ -notmatch "jdk-17" -and
    $_ -notmatch "jre1\.8" -and
    $_ -notmatch "\.jdks\\ms-21" -and        # 避免重複
    $_ -notmatch "%JAVA_HOME%\\bin"            # 避免重複
}

# 在 PATH 最前面加入 %JAVA_HOME%\bin（最高優先級）
$cleanedPath = @("%JAVA_HOME%\bin") + $cleanedPath

$newSysPath = $cleanedPath -join ";"
[System.Environment]::SetEnvironmentVariable("Path", $newSysPath, "Machine")
Write-Host "  已清理並將 %JAVA_HOME%\bin 置於 System PATH 最前面" -ForegroundColor Green

# 3. 驗證
Write-Host "[3/3] 驗證" -ForegroundColor Yellow
$verifyJavaHome = [System.Environment]::GetEnvironmentVariable("JAVA_HOME", "Machine")
Write-Host "  System JAVA_HOME = $verifyJavaHome" -ForegroundColor Gray

$verifyPath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
$javaPaths = ($verifyPath -split ";") | Where-Object { $_ -match "java|jdk|jre|JAVA_HOME" }
Write-Host "  System PATH 中的 Java 相關路徑：" -ForegroundColor Gray
$javaPaths | ForEach-Object { Write-Host "    - $_" -ForegroundColor Gray }

Write-Host ""
Write-Host "===== 完成 =====" -ForegroundColor Cyan
Write-Host "請關閉所有終端窗口，重新打開新的終端，然後運行：" -ForegroundColor White
Write-Host "  java -version" -ForegroundColor White
Write-Host "  echo `$env:JAVA_HOME" -ForegroundColor White
Write-Host "確認顯示 Java 21。" -ForegroundColor White
Write-Host ""
Write-Host "注意：Oracle javapath 已從 PATH 移除。如果其他軟件依賴它，" -ForegroundColor DarkGray
Write-Host "      可重新安裝對應的 JRE 或手動加回。" -ForegroundColor DarkGray
