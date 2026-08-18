package com.quantization.module.system.dto;

/**
 * 系统健康状态 DTO，包含数据库连接状态、表结构校验结果和问题列表。
 *
 * @param connected     数据库是否连接正常
 * @param schemaValid   表结构是否校验通过
 * @param databaseName  数据库名称
 * @param host          数据库主机
 * @param port          数据库端口
 * @param message       状态描述消息
 * @param schemaIssues  表结构问题列表
 */
public record SystemHealthDto(
        boolean connected,
        boolean schemaValid,
        String databaseName,
        String host,
        int port,
        String message,
        java.util.List<String> schemaIssues
) {
}
