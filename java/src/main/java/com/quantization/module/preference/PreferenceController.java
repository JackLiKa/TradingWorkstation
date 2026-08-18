package com.quantization.module.preference;

import com.quantization.common.api.ApiResponse;
import com.quantization.module.preference.dto.UserPreferenceDto;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 用户偏好 Controller，提供偏好的读取和保存接口。
 */
@Tag(name = "偏好 preference")
@RestController
@RequestMapping("/api/preference")
public class PreferenceController {

    private final PreferenceService preferenceService;

    public PreferenceController(PreferenceService preferenceService) {
        this.preferenceService = preferenceService;
    }

    /**
     * 读取用户偏好设置。
     *
     * @return 用户偏好 DTO
     */
    @Operation(summary = "读取用户偏好")
    @GetMapping
    public ApiResponse<UserPreferenceDto> load() {
        return ApiResponse.ok(preferenceService.load());
    }

    /**
     * 保存用户偏好设置。
     *
     * @param preference 用户偏好 DTO
     * @return 保存后的用户偏好 DTO
     */
    @Operation(summary = "保存用户偏好")
    @PutMapping
    public ApiResponse<UserPreferenceDto> save(@RequestBody UserPreferenceDto preference) {
        return ApiResponse.ok(preferenceService.save(preference));
    }
}
