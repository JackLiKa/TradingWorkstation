package com.quantization.module.sync;

import com.quantization.common.exception.BusinessException;
import com.quantization.common.api.ErrorCode;
import com.quantization.config.properties.AppProperties;
import com.quantization.module.sync.dto.SyncRequestDto;
import com.quantization.module.sync.dto.SyncStatusDto;
import jakarta.annotation.PreDestroy;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.concurrent.atomic.AtomicReference;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 数据同步服务：编排 Python Baostock 摄取脚本。
 * 通过 ProcessBuilder 启动 ingestion/baostock_ingest.py，解析 stdout 进度行维护任务状态。
 */
@Slf4j
@Service
public class SyncService {

    private static final Pattern WRITTEN_PATTERN = Pattern.compile("已寫入\\s*(\\d+)\\s*條");
    private static final Pattern DONE_PATTERN = Pattern.compile("共寫入\\s*(\\d+)\\s*條");
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final AppProperties properties;
    private final AtomicReference<SyncStatusDto> statusRef = new AtomicReference<>(SyncStatusDto.idle());
    private volatile Process runningProcess;

    public SyncService(AppProperties properties) {
        this.properties = properties;
    }

    /**
     * 获取当前同步任务状态。
     *
     * @return 同步状态 DTO
     */
    public SyncStatusDto currentStatus() {
        return statusRef.get();
    }

    /**
     * 启动同步任务：构建命令行参数并通过 ProcessBuilder 启动 Python 脚本，
     * 后台线程解析 stdout 进度行维护任务状态。
     *
     * @param request 同步请求参数
     * @return 初始同步状态
     * @throws BusinessException 已有任务运行中时抛出 BAD_REQUEST
     */
    public synchronized SyncStatusDto start(SyncRequestDto request) {
        if ("RUNNING".equals(statusRef.get().state())) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "已有同步任务正在运行");
        }
        String scriptPath = resolveScriptPath();
        ProcessBuilder pb = new ProcessBuilder(
                properties.getSync().getPythonExecutable(),
                scriptPath,
                "--mode", request.effectiveMode(),
                "--adjustflags", request.effectiveAdjustflags(),
                "--batch-size", String.valueOf(properties.getSync().getBatchSize())
        );
        // 日期參數：range 模式必須提供，incremental 模式可省略（腳本自動用資料庫最新日期）
        String startDate = request.startDate() == null ? properties.getSync().getDefaultStartDate() : request.startDate().toString();
        String endDate = request.endDate() == null ? java.time.LocalDate.now().toString() : request.endDate().toString();
        pb.command().add("--start");
        pb.command().add(startDate);
        pb.command().add("--end");
        pb.command().add(endDate);
        if (request.codes() != null && !request.codes().isBlank()) {
            pb.command().add("--codes");
            pb.command().add(request.codes());
        }
        if (request.effectiveSyncIndex()) {
            pb.command().add("--index");
        }
        if (request.effectiveSyncIndustry()) {
            pb.command().add("--industry");
        }
        pb.redirectErrorStream(true);
        pb.directory(new File(System.getProperty("user.dir")));
        // Windows 上 Python stdout 默認用系統碼頁（GBK/CP936），需強制 UTF-8 以便正則正確匹配中文進度行
        pb.environment().put("PYTHONIOENCODING", "utf-8");
        pb.environment().put("PYTHONUTF8", "1");

        String startedAt = LocalDateTime.now().format(TS);
        SyncStatusDto initial = new SyncStatusDto("RUNNING", 0, "任务已启动", 0, startedAt, null, null);
        statusRef.set(initial);

        Thread worker = new Thread(() -> runProcess(pb, startedAt), "baostock-sync");
        worker.setDaemon(true);
        worker.start();

        return initial;
    }

    private void runProcess(ProcessBuilder pb, String startedAt) {
        int written = 0;
        try {
            runningProcess = pb.start();
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(runningProcess.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    log.info("[sync] {}", line);
                    Matcher m = WRITTEN_PATTERN.matcher(line);
                    if (m.find()) {
                        written = Integer.parseInt(m.group(1));
                        statusRef.set(new SyncStatusDto("RUNNING", 50, "已写入 " + written + " 条",
                                written, startedAt, null, null));
                    }
                    Matcher done = DONE_PATTERN.matcher(line);
                    if (done.find()) {
                        written = Integer.parseInt(done.group(1));
                    }
                }
            }
            int code = runningProcess.waitFor();
            String finishedAt = LocalDateTime.now().format(TS);
            if (code == 0) {
                statusRef.set(new SyncStatusDto("SUCCESS", 100, "同步完成，共写入 " + written + " 条",
                        written, startedAt, finishedAt, null));
            } else {
                statusRef.set(new SyncStatusDto("FAILED", 0, "同步失败，退出码 " + code,
                        written, startedAt, finishedAt, "进程退出码 " + code));
            }
        } catch (IOException | InterruptedException e) {
            String finishedAt = LocalDateTime.now().format(TS);
            statusRef.set(new SyncStatusDto("FAILED", 0, "同步异常：" + e.getMessage(),
                    written, startedAt, finishedAt, e.toString()));
            log.error("[sync] 异常", e);
            Thread.currentThread().interrupt();
        } finally {
            runningProcess = null;
        }
    }

    /**
     * 取消正在运行的同步任务，销毁子进程。
     *
     * @return 取消后的同步状态
     */
    public synchronized SyncStatusDto cancel() {
        if (runningProcess != null && runningProcess.isAlive()) {
            runningProcess.destroy();
            statusRef.set(new SyncStatusDto("CANCELLED", 0, "任务已取消",
                    0, statusRef.get().startedAt(), LocalDateTime.now().format(TS), "用户取消"));
        }
        return statusRef.get();
    }

    private String resolveScriptPath() {
        String configured = properties.getSync().getIngestionScript();
        File file = new File(configured);
        if (!file.isAbsolute()) {
            File workspaceRoot = new File(System.getProperty("user.dir")).getParentFile();
            file = new File(workspaceRoot, configured);
        }
        if (!file.exists()) {
            throw new BusinessException(ErrorCode.SYNC_ERROR, "未找到同步脚本：" + file.getAbsolutePath());
        }
        return file.getAbsolutePath();
    }

    /**
     * 应用关闭时强制销毁正在运行的同步子进程。
     */
    @PreDestroy
    public void shutdown() {
        if (runningProcess != null && runningProcess.isAlive()) {
            runningProcess.destroyForcibly();
        }
    }
}
