package com.quantization.module.system.dto;

/**
 * 数据库配置更新 DTO（请求用，含可选密码）。
 * 所有字段可为 null，null 表示不更新该项。
 *
 * @param host     数据库主机
 * @param port     数据库端口
 * @param name     数据库名称
 * @param user     用户名
 * @param password 密码（空白表示不更新）
 * @param charset  字符集
 */
public record DatabaseConfigUpdateDto(
        String host,
        Integer port,
        String name,
        String user,
        String password,
        String charset
) {
}
