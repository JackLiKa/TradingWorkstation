package com.quantization.module.news;

import com.quantization.common.api.ApiResponse;
import com.quantization.module.news.dto.FinancialNewsDto;
import com.quantization.module.news.dto.NewsBatchUpsertRequest;
import com.quantization.module.news.dto.NewsSyncResultDto;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.data.domain.Page;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;

/**
 * 财经新闻 Controller — 提供新闻查询和清理接口。
 * <p>
 * 新闻抓取由 Agent 服务的 /api/agent/news/sync 端点触发，
 * 本 Controller 负责已入库新闻的查询和管理。
 */
@Tag(name = "财经新闻 news")
@RestController
@RequestMapping("/api/news")
public class NewsController {

    private final NewsService newsService;

    public NewsController(NewsService newsService) {
        this.newsService = newsService;
    }

    @Operation(summary = "分页查询最新新闻")
    @GetMapping
    public ApiResponse<Page<FinancialNewsDto>> list(
            @Parameter(description = "页码（从0开始）") @RequestParam(defaultValue = "0") int page,
            @Parameter(description = "每页条数") @RequestParam(defaultValue = "20") int size
    ) {
        return ApiResponse.ok(newsService.listLatest(page, size));
    }

    @Operation(summary = "按频道查询新闻")
    @GetMapping("/channel/{channel}")
    public ApiResponse<Page<FinancialNewsDto>> listByChannel(
            @Parameter(description = "频道：global/a-stock/us-stock/hk-stock/forex/commodity")
            @RequestParam String channel,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size
    ) {
        return ApiResponse.ok(newsService.listByChannel(channel, page, size));
    }

    @Operation(summary = "清理过期新闻")
    @DeleteMapping("/expired")
    public ApiResponse<Integer> cleanupExpired(
            @Parameter(description = "保留天数（删除此天数之前的新闻）")
            @RequestParam(defaultValue = "30") int days
    ) {
        return ApiResponse.ok(newsService.cleanupExpired(days));
    }

    @Operation(summary = "获取新闻总数")
    @GetMapping("/count")
    public ApiResponse<Long> count() {
        return ApiResponse.ok(newsService.count());
    }

    @Operation(summary = "批量写入新闻（Agent 服务调用）")
    @PostMapping("/batch")
    public ApiResponse<NewsSyncResultDto> batchUpsert(@RequestBody NewsBatchUpsertRequest request) {
        return ApiResponse.ok(newsService.batchUpsert(request.items()));
    }

    @Operation(summary = "清空所有新闻（重建时调用）")
    @DeleteMapping("/all")
    public ApiResponse<Long> deleteAll() {
        long count = newsService.count();
        newsService.deleteAll();
        return ApiResponse.ok(count);
    }
}
