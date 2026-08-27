package com.quantization.common.api;

import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.List;

/**
 * 分页响应封装，包含当前页数据列表及分页元信息。
 *
 * @param <T> 列表元素类型
 */
@Getter
@AllArgsConstructor
public class PageResponse<T> {
    /** 当前页数据列表 */
    private final List<T> items;
    /** 总记录数 */
    private final int total;
    /** 当前页码 */
    private final int page;
    /** 每页大小 */
    private final int size;

    /**
     * 构建分页响应。
     *
     * @param items 当前页数据
     * @param total 总记录数
     * @param page  当前页码
     * @param size  每页大小
     * @param <T>   元素类型
     * @return 分页响应对象
     */
    public static <T> PageResponse<T> of(List<T> items, int total, int page, int size) {
        return new PageResponse<>(items, total, page, size);
    }
}
