#include "smartwatch_ui.h"
#include "oled.h"
#include <stdio.h>
#include <string.h>

/* Weekday strings */
static const char *weekdays_en[] = {"Sun","Mon","Tue","Wed","Thu","Fri","Sat"};

static void format_signed_fixed1(char *buf, size_t size, float value) {
    int32_t scaled = (int32_t)(value * 10.0f + (value >= 0.0f ? 0.5f : -0.5f));
    char sign = '+';

    if (scaled < 0) {
        sign = '-';
        scaled = -scaled;
    }

    snprintf(buf, size, "%c%ld.%ld", sign, (long)(scaled / 10), (long)(scaled % 10));
}

static void format_signed_int(char *buf, size_t size, float value) {
    int32_t rounded = (int32_t)(value + (value >= 0.0f ? 0.5f : -0.5f));
    char sign = '+';

    if (rounded < 0) {
        sign = '-';
        rounded = -rounded;
    }

    snprintf(buf, size, "%c%ld", sign, (long)rounded);
}

/* ==================== Data Init ==================== */

void UI_InitData(SmartWatchData_t *data) {
    data->hour = 10;
    data->minute = 30;
    data->second = 45;
    data->year = 2026;
    data->month = 6;
    data->day = 27;
    data->weekday = 6;       /* Saturday */
    data->battery_pct = 85;
    data->temp_celsius = 25;
    data->imu_status = 0;
    data->bt_connected = 0;
    data->accel.ax = 0.0f;
    data->accel.ay = 0.0f;
    data->accel.az = 9.81f;
    data->gyro.gx = 0.0f;
    data->gyro.gy = 0.0f;
    data->gyro.gz = 0.0f;
    data->angle.pitch = 0.0f;
    data->angle.roll = 0.0f;
}

/* ==================== Status Bar ==================== */

void UI_DrawStatusBar(SmartWatchData_t *data) {
    /* Clear page 0 */
    for (uint16_t i = 0; i < SSD1306_WIDTH; i++)
        OLED_Buffer[i] = 0x00;

    /* Battery icon (left side, x=0-14) */
    for (uint8_t x = 0; x < 14; x++) {
        if (x == 0 || x == 13)
            OLED_Buffer[x] = 0x7E;
        else if (x == 14)
            OLED_Buffer[x] = 0x18;
        else
            OLED_Buffer[x] = 0x42;
    }
    uint8_t fill_width = (data->battery_pct * 10) / 100;
    if (fill_width > 10) fill_width = 10;
    for (uint8_t x = 2; x < 2 + fill_width; x++)
        OLED_Buffer[x] = 0x5A;

    /* Battery percentage */
    char bat_str[5];
    snprintf(bat_str, sizeof(bat_str), "%d%%", data->battery_pct);
    OLED_DrawString6x8(18, 0, bat_str);

    /* Time in center */
    char time_str[9];
    snprintf(time_str, sizeof(time_str), "%02d:%02d", data->hour, data->minute);
    OLED_DrawString6x8(60, 0, time_str);

    /* Bluetooth status indicator */
    if (data->bt_connected) {
        OLED_DrawString6x8(102, 0, "BT");
    }

    /* IMU status dot (right side) */
    if (data->imu_status) {
        OLED_DrawFilledCircle(123, 3, 2);
    } else {
        OLED_DrawCircle(123, 3, 2);
    }

    /* Separator line at y=7 */
    for (uint8_t x = 0; x < SSD1306_WIDTH; x++)
        OLED_SetPixel(x, 7, 1);
}

/* ==================== Page Indicator ==================== */

void UI_DrawPageIndicator(uint8_t current, uint8_t total) {
    for (uint16_t i = 7 * SSD1306_WIDTH; i < SSD1306_WIDTH * SSD1306_PAGES; i++)
        OLED_Buffer[i] = 0x00;

    for (uint8_t x = 0; x < SSD1306_WIDTH; x++)
        OLED_SetPixel(x, 56, 1);

    uint8_t dot_spacing = 14;
    uint8_t total_width = (total - 1) * dot_spacing;
    uint8_t start_x = (SSD1306_WIDTH - total_width) / 2;

    for (uint8_t i = 0; i < total; i++) {
        uint8_t cx = start_x + i * dot_spacing;
        if (i == current) {
            OLED_DrawFilledCircle(cx, 60, 2);
        } else {
            OLED_DrawCircle(cx, 60, 2);
        }
    }
}

/* ==================== Page 0: Watch Face ==================== */

void UI_DrawWatchFace(SmartWatchData_t *data) {
    OLED_ClearBuffer();

    UI_DrawStatusBar(data);

    /* Large time display */
    uint8_t time_x = (128 - 88) / 2;
    OLED_DrawTime16x24(time_x, 14, data->hour, data->minute);

    /* Date line: page 5 */
    char date_str[32];
    snprintf(date_str, sizeof(date_str), "%04d-%02d-%02d %s",
             data->year, data->month, data->day,
             weekdays_en[data->weekday]);
    uint8_t date_len = strlen(date_str);
    uint8_t date_x = (128 - date_len * 6) / 2;
    OLED_DrawString6x8(date_x, 5, date_str);

    /* IMU quick status: page 6 */
    char imu_str[32];
    if (data->imu_status) {
        char pitch[8], roll[8];
        format_signed_int(pitch, sizeof(pitch), data->angle.pitch);
        format_signed_int(roll, sizeof(roll), data->angle.roll);
        snprintf(imu_str, sizeof(imu_str), "P:%s R:%s  T:%dC",
                 pitch, roll, data->temp_celsius);
    } else {
        snprintf(imu_str, sizeof(imu_str), "MPU6050: --");
    }
    uint8_t imu_len = strlen(imu_str);
    uint8_t imu_x = (128 - imu_len * 6) / 2;
    OLED_DrawString6x8(imu_x, 6, imu_str);

    UI_DrawPageIndicator(PAGE_WATCH_FACE, PAGE_MAX);
}

/* ==================== Page 1: IMU Sensor Detail ==================== */

void UI_DrawIMU(SmartWatchData_t *data) {
    OLED_ClearBuffer();

    UI_DrawStatusBar(data);

    OLED_DrawString8x16(4, 1, "IMU  MPU6050");

    for (uint8_t x = 0; x < SSD1306_WIDTH; x++)
        OLED_SetPixel(x, 24, 1);

    if (!data->imu_status) {
        OLED_DrawString6x8(4, 4, "MPU6050: NOT FOUND");
        OLED_DrawString6x8(4, 5, "PB10/PB11  I2C2");
        OLED_DrawString6x8(4, 6, "Auto-retry every 5s");
    } else {
        char buf[24];
        char ax[8], ay[8], az[8];
        char gx[8], gy[8], gz[8];
        char pitch[8], roll[8];

        format_signed_fixed1(ax, sizeof(ax), data->accel.ax);
        format_signed_fixed1(ay, sizeof(ay), data->accel.ay);
        format_signed_fixed1(az, sizeof(az), data->accel.az);
        format_signed_int(gx, sizeof(gx), data->gyro.gx);
        format_signed_int(gy, sizeof(gy), data->gyro.gy);
        format_signed_int(gz, sizeof(gz), data->gyro.gz);
        format_signed_int(pitch, sizeof(pitch), data->angle.pitch);
        format_signed_int(roll, sizeof(roll), data->angle.roll);

        /* Accel: "X+0.1 Y+0.3 Z+9.8" = 17 chars = 102px */
        snprintf(buf, sizeof(buf), "X%s Y%s Z%s", ax, ay, az);
        OLED_DrawString6x8(0, 3, buf);

        /* Gyro: "x+0 y+0 z+0 d/s" = 14 chars = 84px */
        snprintf(buf, sizeof(buf), "x%s y%s z%s d/s", gx, gy, gz);
        OLED_DrawString6x8(0, 4, buf);

        /* Pitch & Roll: "P+0 R+0 deg" = 12 chars = 72px */
        snprintf(buf, sizeof(buf), "P%s R%s deg", pitch, roll);
        OLED_DrawString6x8(0, 5, buf);

        /* Temperature + I2C status */
        snprintf(buf, sizeof(buf), "T:%dC %s",
                 data->temp_celsius,
                 g_mpu6050_i2c_error ? "ERR" : "OK");
        OLED_DrawString6x8(0, 6, buf);

        /* Attitude indicator (right side, away from text) */
        uint8_t cx = 114, cy = 40, r = 7;

        OLED_DrawCircle(cx, cy, r);
        OLED_DrawHLine(cx - r, cy, 2 * r + 1);
        OLED_DrawVLine(cx, cy - r, 2 * r + 1);

        int8_t dot_x = cx + (int8_t)(data->angle.roll * 0.12f);
        int8_t dot_y = cy + (int8_t)(data->angle.pitch * 0.12f);

        if (dot_x < cx - r + 2) dot_x = cx - r + 2;
        if (dot_x > cx + r - 2) dot_x = cx + r - 2;
        if (dot_y < cy - r + 2) dot_y = cy - r + 2;
        if (dot_y > cy + r - 2) dot_y = cy + r - 2;

        OLED_DrawFilledCircle(dot_x, dot_y, 2);
    }

    UI_DrawPageIndicator(PAGE_IMU, PAGE_MAX);
}

/* ==================== Page 2: Bluetooth ==================== */

void UI_DrawBluetooth(SmartWatchData_t *data) {
    OLED_ClearBuffer();

    UI_DrawStatusBar(data);

    OLED_DrawString8x16(4, 1, "BLUETOOTH");

    for (uint8_t x = 0; x < SSD1306_WIDTH; x++)
        OLED_SetPixel(x, 24, 1);

    OLED_DrawString6x8(4, 3, "HC-05 USART2 38400");
    OLED_DrawString6x8(4, 4, "TX: PA2  RX: PA3");

    if (data->bt_connected) {
        OLED_DrawString6x8(4, 6, "Status: CONNECTED");
    } else {
        OLED_DrawString6x8(4, 6, "Status: WAITING");
    }

    UI_DrawPageIndicator(PAGE_BLUETOOTH, PAGE_MAX);
}

/* ==================== Page 3: Device Info ==================== */

void UI_DrawDeviceInfo(SmartWatchData_t *data) {
    OLED_ClearBuffer();

    UI_DrawStatusBar(data);

    OLED_DrawString8x16(4, 1, "DEV INFO");

    for (uint8_t x = 0; x < SSD1306_WIDTH; x++)
        OLED_SetPixel(x, 24, 1);

    OLED_DrawString6x8(4, 3, "STM32F103C8T6  72MHz");
    OLED_DrawString6x8(4, 4, "OLED: I2C1 PB6/PB7");
    OLED_DrawString6x8(4, 5, "IMU:  I2C2 PB10/PB11");
    OLED_DrawString6x8(4, 6, "BT:   USART2 PA2/PA3");

    /* MPU6050 status */
    if (data->imu_status) {
        OLED_DrawString6x8(4, 7, "MPU6050: OK");
    } else {
        OLED_DrawString6x8(4, 7, "MPU6050: NOT FOUND");
    }

    UI_DrawPageIndicator(PAGE_DEVICE_INFO, PAGE_MAX);
}

/* ==================== Page Dispatcher ==================== */

void UI_DrawPage(UIPage_t page, SmartWatchData_t *data) {
    switch (page) {
        case PAGE_WATCH_FACE:  UI_DrawWatchFace(data);   break;
        case PAGE_IMU:         UI_DrawIMU(data);          break;
        case PAGE_BLUETOOTH:   UI_DrawBluetooth(data);    break;
        case PAGE_DEVICE_INFO: UI_DrawDeviceInfo(data);   break;
        default: break;
    }
    OLED_Update();
}
