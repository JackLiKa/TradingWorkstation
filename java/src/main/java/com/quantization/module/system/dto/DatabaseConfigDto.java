package com.quantization.module.system.dto;

/**
 * 数据库配置 DTO（响应用，不含密码）。
 *
 * @param host    数据库主机
 * @param port    数据库端口
 * @param name    数据库名称
 * @param user    用户名
 * @param charset 字符集
 */
public record DatabaseConfigDto(
        String host,
        int port,
        String name,
        String user,
        String charset
) {
}
