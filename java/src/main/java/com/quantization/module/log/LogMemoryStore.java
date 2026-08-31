package com.quantization.module.log;

import com.quantization.module.log.dto.LogEntry;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.ConcurrentLinkedDeque;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.Consumer;

/**
 * 日誌內存環形緩衝 — 保存最近的統一日誌條目，供 SSE 實時推送和 REST 歷史查詢。
 *
 * 設計：
 * - 使用 ConcurrentLinkedDeque 無鎖線程安全
 * - 最大容量 2000 條，超出時移除最舊的
 * - 支持 SSE 訂閱者註冊，新日誌到達時異步通知
 */
@Slf4j
@Component
public class LogMemoryStore {

    private static final int MAX_SIZE = 2000;

    private final ConcurrentLinkedDeque<LogEntry> buffer = new ConcurrentLinkedDeque<>();
    private final AtomicLong seqCounter = new AtomicLong(0);
    private final List<Consumer<LogEntry>> subscribers = Collections.synchronizedList(new ArrayList<>());

    /** 添加一條日誌並通知 SSE 訂閱者 */
    public void add(LogEntry entry) {
        buffer.addLast(entry);
        // 超出容量時移除最舊的
        while (buffer.size() > MAX_SIZE) {
            buffer.pollFirst();
        }
        // 通知訂閱者
        synchronized (subscribers) {
            for (Consumer<LogEntry> subscriber : subscribers) {
                try {
                    subscriber.accept(entry);
                } catch (Exception e) {
                    log.debug("[log-store] SSE 訂閱者通知失敗: {}", e.getMessage());
                }
            }
        }
    }

    /** 獲取最近的 N 條日誌（按時間倒序） */
    public List<LogEntry> getRecent(int limit) {
        List<LogEntry> all = new ArrayList<>(buffer);
        Collections.reverse(all);
        return all.size() > limit ? all.subList(0, limit) : all;
    }

    /** 生成唯一 ID */
    public String nextId(String source) {
        return source + ":" + seqCounter.incrementAndGet();
    }

    /** 註冊 SSE 訂閱者 */
    public void subscribe(Consumer<LogEntry> subscriber) {
        subscribers.add(subscriber);
    }

    /** 取消訂閱 */
    public void unsubscribe(Consumer<LogEntry> subscriber) {
        subscribers.remove(subscriber);
    }

    /** 當前緩衝區大小 */
    public int size() {
        return buffer.size();
    }
}
