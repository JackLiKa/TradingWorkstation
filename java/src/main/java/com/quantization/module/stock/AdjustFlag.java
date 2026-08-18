package com.quantization.module.stock;

/**
 * 复权方式枚举，与 baostock adjustflag 对齐。
 * <p>1=后复权、2=前复权、3=不复权</p>
 */
public enum AdjustFlag {
    POST_ADJUST(1, "后复权"),
    PRE_ADJUST(2, "前复权"),
    NONE(3, "不复权");

    private final int value;
    private final String label;

    AdjustFlag(int value, String label) {
        this.value = value;
        this.label = label;
    }

    /**
     * 获取复权方式的数值编码。
     *
     * @return 复权方式数值（1/2/3）
     */
    public int getValue() {
        return value;
    }

    /**
     * 获取复权方式的中文标签。
     *
     * @return 中文标签（如"后复权"）
     */
    public String getLabel() {
        return label;
    }

    /**
     * 根据数值编码获取枚举实例，未匹配时返回 {@link #NONE}。
     *
     * @param value 复权方式数值
     * @return 对应的枚举实例
     */
    public static AdjustFlag of(int value) {
        for (AdjustFlag flag : values()) {
            if (flag.value == value) return flag;
        }
        return NONE;
    }
}
