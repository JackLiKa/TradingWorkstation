package com.quantization.module.system;

import com.quantization.common.exception.BusinessException;
import com.quantization.common.api.ErrorCode;
import com.quantization.config.properties.AppProperties;
import com.quantization.module.stock.StockService;
import com.quantization.module.system.dto.DatabaseConfigDto;
import com.quantization.module.system.dto.DatabaseConfigUpdateDto;
import com.quantization.module.system.dto.SystemHealthDto;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import jakarta.persistence.Query;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

/**
 * 系统服务：数据库连接/表结构校验，以及 .env 配置更新。
 * 注意：写入 .env 仅更新 DB_* 行，保留其它内容；密码不入日志。
 */
@Slf4j
@Service
@Transactional(readOnly = true)
public class SystemService {

    private static final Pattern ENV_LINE = Pattern.compile("^([A-Z_]+)=(.*)$");

    private final StockService stockService;
    private final Environment environment;
    private final AppProperties properties;
    @PersistenceContext
    private EntityManager em;

    public SystemService(StockService stockService, Environment environment, AppProperties properties) {
        this.stockService = stockService;
        this.environment = environment;
        this.properties = properties;
    }

    /**
     * 数据库健康检查：验证连接是否正常，并校验 stock_daily 表结构和唯一索引。
     *
     * @return 系统健康状态 DTO
     */
    public SystemHealthDto health() {
        boolean connected = stockService.ping();
        List<String> issues = new ArrayList<>();
        boolean schemaValid = false;
        if (connected) {
            schemaValid = validateSchema(issues);
        }
        String message = connected
                ? (schemaValid ? "数据库连接正常，stock_daily 表结构校验通过" : "数据库连接正常，但表结构存在异常")
                : "数据库连接失败";
        return new SystemHealthDto(connected, schemaValid,
                environment.getProperty("DB_NAME", "a_stock_baostock"),
                environment.getProperty("DB_HOST", "localhost"),
                Integer.parseInt(environment.getProperty("DB_PORT", "3306")),
                message, issues);
    }

    /**
     * 获取当前数据库配置（不含密码）。
     *
     * @return 数据库配置 DTO
     */
    public DatabaseConfigDto currentConfig() {
        return new DatabaseConfigDto(
                environment.getProperty("DB_HOST", "localhost"),
                Integer.parseInt(environment.getProperty("DB_PORT", "3306")),
                environment.getProperty("DB_NAME", "a_stock_baostock"),
                environment.getProperty("DB_USER", "root"),
                environment.getProperty("DB_CHARSET", "utf8mb4")
        );
    }

    /**
     * 更新数据库配置：将变更写入 .env 文件，重启后生效。
     * 仅更新 DB_* 行，保留其它内容；密码不入日志。
     *
     * @param update 配置更新请求
     * @return 更新后的数据库配置 DTO
     * @throws BusinessException 写入 .env 失败时抛出 DB_ERROR
     */
    @Transactional
    public DatabaseConfigDto updateConfig(DatabaseConfigUpdateDto update) {
        // 先校验新配置可用（不在此处真正切换 DataSource，仅写入 .env，重启后生效）
        Map<String, String> overrides = new LinkedHashMap<>();
        if (update.host() != null) overrides.put("DB_HOST", update.host());
        if (update.port() != null) overrides.put("DB_PORT", String.valueOf(update.port()));
        if (update.name() != null) overrides.put("DB_NAME", update.name());
        if (update.user() != null) overrides.put("DB_USER", update.user());
        if (update.password() != null && !update.password().isBlank()) overrides.put("DB_PASSWORD", update.password());
        if (update.charset() != null) overrides.put("DB_CHARSET", update.charset());

        try {
            Path envPath = resolveEnvPath();
            List<String> lines = Files.exists(envPath)
                    ? new ArrayList<>(Files.readAllLines(envPath))
                    : new ArrayList<>();
            Map<String, Integer> indexByKey = new LinkedHashMap<>();
            for (int i = 0; i < lines.size(); i++) {
                var m = ENV_LINE.matcher(lines.get(i));
                if (m.matches()) indexByKey.put(m.group(1), i);
            }
            for (var e : overrides.entrySet()) {
                String newline = e.getKey() + "=" + e.getValue();
                if (indexByKey.containsKey(e.getKey())) {
                    lines.set(indexByKey.get(e.getKey()), newline);
                } else {
                    lines.add(newline);
                }
            }
            Files.write(envPath, lines);
            log.info("[system] .env 已更新，键：{}", overrides.keySet());
        } catch (Exception e) {
            throw new BusinessException(ErrorCode.DB_ERROR, "更新 .env 失败：" + e.getMessage(), e);
        }
        return new DatabaseConfigDto(
                update.host() != null ? update.host() : environment.getProperty("DB_HOST", "localhost"),
                update.port() != null ? update.port() : Integer.parseInt(environment.getProperty("DB_PORT", "3306")),
                update.name() != null ? update.name() : environment.getProperty("DB_NAME", "a_stock_baostock"),
                update.user() != null ? update.user() : environment.getProperty("DB_USER", "root"),
                update.charset() != null ? update.charset() : environment.getProperty("DB_CHARSET", "utf8mb4")
        );
    }

    private boolean validateSchema(List<String> issues) {
        try {
            Query tableCheck = em.createNativeQuery(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'stock_daily'");
            Object result = tableCheck.getSingleResult();
            long count = ((Number) result).longValue();
            if (count == 0) {
                issues.add("stock_daily 表不存在");
                return false;
            }
            // 校验关键列存在
            Query columnCheck = em.createNativeQuery(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'stock_daily'");
            @SuppressWarnings("unchecked")
            List<String> columns = ((List<Object>) columnCheck.getResultList()).stream()
                    .map(Object::toString).toList();
            List<String> required = List.of("id", "code", "date", "open", "high", "low", "close",
                    "volume", "amount", "adjustflag", "turn", "tradestatus", "pctChg", "isST");
            for (String col : required) {
                if (!columns.contains(col)) issues.add("缺少列：" + col);
            }
            // 校验唯一索引
            Query indexCheck = em.createNativeQuery(
                    "SELECT index_name FROM information_schema.statistics WHERE table_schema = DATABASE() AND table_name = 'stock_daily' AND non_unique = 0");
            @SuppressWarnings("unchecked")
            List<Object> uniqueIndexes = indexCheck.getResultList();
            boolean hasCodeDateAdjust = uniqueIndexes.stream()
                    .map(Object::toString)
                    .anyMatch(name -> name.toLowerCase().contains("code") && name.toLowerCase().contains("date"));
            if (!hasCodeDateAdjust) {
                issues.add("缺少 (code, date, adjustflag) 唯一索引，可能导致不同复权数据互相覆盖");
            }
            return issues.isEmpty();
        } catch (Exception e) {
            issues.add("表结构校验异常：" + e.getMessage());
            return false;
        }
    }

    private Path resolveEnvPath() {
        String userDir = System.getProperty("user.dir");
        Path backendDir = Paths.get(userDir);
        Path workspaceRoot = backendDir.getParent();
        return workspaceRoot.resolve(".env");
    }
}
