package com.quantization.module.sync.dto;

/**
 * 同步状态 DTO，包含任务状态、进度、已写入条数和时间戳。
 *
 * @param state      任务状态（IDLE/RUNNING/SUCCESS/FAILED/CANCELLED）
 * @param progress   进度百分比（0-100）
 * @param message    状态描述消息
 * @param written    已写入条数
 * @param startedAt  启动时间
 * @param finishedAt 完成时间
 * @param error      错误信息（失败时）
 */
public record SyncStatusDto(
        String state,
        int progress,
        String message,
        int written,
        String startedAt,
        String finishedAt,
        String error
) {
    /**
     * 构建空闲状态（无任务运行）。
     *
     * @return 空闲状态 DTO
     */
    public static SyncStatusDto idle() {
        return new SyncStatusDto("IDLE", 0, "无任务", 0, null, null, null);
    }
}
