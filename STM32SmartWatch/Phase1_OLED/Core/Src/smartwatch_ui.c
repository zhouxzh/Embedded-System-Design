#include "smartwatch_ui.h"
#include "oled.h"
#include <stdio.h>
#include <string.h>

/* Weekday strings */
static const char *weekdays_en[] = {"Sun","Mon","Tue","Wed","Thu","Fri","Sat"};

/* ==================== Data Init ==================== */

void UI_InitData(SmartWatchData_t *data) {
    data->hour = 10;
    data->minute = 30;
    data->second = 45;
    data->year = 2026;
    data->month = 6;
    data->day = 26;
    data->weekday = 5;       /* Friday */
    data->heart_rate = 78;
    data->hr_min = 62;
    data->hr_max = 95;
    data->steps = 8532;
    data->distance_km = 6.8f;
    data->calories_kcal = 320;
    data->temp_celsius = 36;
    data->humidity_pct = 58;
    data->pressure_hpa = 1013;
    data->battery_pct = 85;
}

/* ==================== Status Bar ==================== */

void UI_DrawStatusBar(SmartWatchData_t *data) {
    /* Clear page 0 */
    for (uint16_t i = 0; i < SSD1306_WIDTH; i++)
        OLED_Buffer[i] = 0x00;

    /* Battery icon (left side) */
    /* Draw battery outline at x=0-13, y in page 0 */
    for (uint8_t x = 0; x < 14; x++) {
        if (x == 0 || x == 13)
            OLED_Buffer[x] = 0x7E;  /* vertical edges: 01111110 */
        else if (x == 14)
            OLED_Buffer[x] = 0x18;  /* battery tip: 00011000 */
        else
            OLED_Buffer[x] = 0x42;  /* horizontal edges: 01000010 */
    }
    /* Fill battery based on percentage */
    uint8_t fill_width = (data->battery_pct * 10) / 100;
    if (fill_width > 10) fill_width = 10;
    for (uint8_t x = 2; x < 2 + fill_width; x++)
        OLED_Buffer[x] = 0x5A;  /* filled: 01011010 */

    /* Battery percentage text */
    char bat_str[5];
    snprintf(bat_str, sizeof(bat_str), "%d%%", data->battery_pct);
    OLED_DrawString6x8(18, 0, bat_str);

    /* Time in the center of status bar */
    char time_str[9];
    snprintf(time_str, sizeof(time_str), "%02d:%02d", data->hour, data->minute);
    OLED_DrawString6x8(60, 0, time_str);

    /* Bluetooth icon (right side) */
    OLED_DrawBitmap(120, 0, IconBT, 8, 8);

    /* Separator line at bottom of page 0 (y=7) */
    for (uint8_t x = 0; x < SSD1306_WIDTH; x++)
        OLED_SetPixel(x, 7, 1);
}

/* ==================== Page Indicator ==================== */

void UI_DrawPageIndicator(uint8_t current, uint8_t total) {
    /* Clear page 7 */
    for (uint16_t i = 7 * SSD1306_WIDTH; i < SSD1306_WIDTH * SSD1306_PAGES; i++)
        OLED_Buffer[i] = 0x00;

    /* Separator line at top of page 7 (y=56) */
    for (uint8_t x = 0; x < SSD1306_WIDTH; x++)
        OLED_SetPixel(x, 56, 1);

    /* Center the dots */
    uint8_t dot_spacing = 12;
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

    /* Status bar */
    UI_DrawStatusBar(data);

    /* Large time display centered (88px total width) */
    uint8_t time_x = (128 - 88) / 2;  /* = 20 */
    OLED_DrawTime16x24(time_x, 14, data->hour, data->minute);

    /* Date line: page 5+6, y~40 */
    char date_str[32];
    snprintf(date_str, sizeof(date_str), "%04d-%02d-%02d %s",
             data->year, data->month, data->day,
             weekdays_en[data->weekday]);
    uint8_t date_len = strlen(date_str);
    uint8_t date_x = (128 - date_len * 6) / 2;
    OLED_DrawString6x8(date_x, 5, date_str);

    /* Temperature & humidity hint at page 6 */
    char env_str[24];
    snprintf(env_str, sizeof(env_str), "%dC %d%%RH", data->temp_celsius, data->humidity_pct);
    uint8_t env_len = strlen(env_str);
    uint8_t env_x = (128 - env_len * 6) / 2;
    OLED_DrawString6x8(env_x, 6, env_str);

    /* Page indicator */
    UI_DrawPageIndicator(0, PAGE_MAX);
}

/* ==================== Page 1: Heart Rate Monitor ==================== */

void UI_DrawHeartRate(SmartWatchData_t *data) {
    OLED_ClearBuffer();

    /* Status bar */
    UI_DrawStatusBar(data);

    /* Title */
    OLED_DrawString8x16(4, 1, "HEART RATE");

    /* Separator line */
    for (uint8_t x = 0; x < SSD1306_WIDTH; x++)
        OLED_SetPixel(x, 24, 1);

    /* Heart icon (simplified, drawn with primitives) */
    /* Small heart shape at left */
    OLED_DrawFilledCircle(30, 32, 3);
    OLED_DrawFilledCircle(38, 32, 3);
    OLED_DrawFilledRect(28, 32, 14, 5);

    /* HR value - large */
    char hr_str[10];
    snprintf(hr_str, sizeof(hr_str), "%d", data->heart_rate);
    OLED_DrawString8x16(48, 3, hr_str);
    OLED_DrawString8x16(72, 3, "BPM");

    /* Min/Max on page 5 */
    char min_str[16], max_str[16];
    snprintf(min_str, sizeof(min_str), "MIN:%d", data->hr_min);
    snprintf(max_str, sizeof(max_str), "MAX:%d", data->hr_max);
    OLED_DrawString6x8(4, 5, min_str);
    OLED_DrawString6x8(70, 5, max_str);

    /* HR graph - simple bar on page 6 */
    /* Draw a simple pulse waveform */
    uint8_t wave_y[32] = {50,50,50,50,52,55,60,63,62,58,52,48,46,46,48,52,
                          56,62,64,60,54,50,47,47,49,52,56,60,62,58,52,50};
    for (uint8_t i = 1; i < 32; i++) {
        OLED_DrawLine(i * 4 - 4, wave_y[i-1], i * 4, wave_y[i]);
    }

    UI_DrawPageIndicator(1, PAGE_MAX);
}

/* ==================== Page 2: Step Counter ==================== */

void UI_DrawSteps(SmartWatchData_t *data) {
    OLED_ClearBuffer();

    /* Status bar */
    UI_DrawStatusBar(data);

    /* Title */
    OLED_DrawString8x16(4, 1, "STEP COUNT");

    for (uint8_t x = 0; x < SSD1306_WIDTH; x++)
        OLED_SetPixel(x, 24, 1);

    /* Step icon + count */
    /* Simple foot icon at (10, 28) */
    OLED_DrawFilledCircle(16, 30, 4);
    OLED_DrawFilledCircle(16, 40, 3);

    char steps_str[16];
    snprintf(steps_str, sizeof(steps_str), "%lu", data->steps);
    OLED_DrawString8x16(28, 3, steps_str);
    OLED_DrawString6x8(84, 3, "STEPS");

    /* Distance */
    char dist_str[16];
    snprintf(dist_str, sizeof(dist_str), "DIST:%.1fkm", data->distance_km);
    OLED_DrawString6x8(28, 5, dist_str);

    /* Calories */
    char cal_str[16];
    snprintf(cal_str, sizeof(cal_str), "CAL:%dkcal", data->calories_kcal);
    OLED_DrawString6x8(28, 6, cal_str);

    UI_DrawPageIndicator(2, PAGE_MAX);
}

/* ==================== Page 3: Weather ==================== */

void UI_DrawWeather(SmartWatchData_t *data) {
    OLED_ClearBuffer();

    /* Status bar */
    UI_DrawStatusBar(data);

    /* Title */
    OLED_DrawString8x16(4, 1, "WEATHER");

    for (uint8_t x = 0; x < SSD1306_WIDTH; x++)
        OLED_SetPixel(x, 24, 1);

    /* Sun icon centered */
    OLED_DrawCircle(24, 36, 10);
    /* Sun rays (8 directions, precomputed) */
    static const int8_t ray_dirs[8][2] = {
        {12, 0}, {8, 8}, {0, 12}, {-8, 8},
        {-12, 0}, {-8, -8}, {0, -12}, {8, -8}
    };
    for (uint8_t i = 0; i < 8; i++) {
        OLED_DrawLine(24, 36,
            24 + ray_dirs[i][0], 36 + ray_dirs[i][1]);
    }

    /* Temperature - large */
    char temp_str[8];
    snprintf(temp_str, sizeof(temp_str), "%dC", data->temp_celsius);
    OLED_DrawString8x16(42, 3, temp_str);

    /* Humidity */
    char hum_str[16];
    snprintf(hum_str, sizeof(hum_str), "HUM:%d%%", data->humidity_pct);
    OLED_DrawString6x8(42, 5, hum_str);

    /* Pressure */
    char pres_str[16];
    snprintf(pres_str, sizeof(pres_str), "PRS:%dhPa", data->pressure_hpa);
    OLED_DrawString6x8(42, 6, pres_str);

    UI_DrawPageIndicator(3, PAGE_MAX);
}

/* ==================== Page 4: Device Info ==================== */

void UI_DrawDeviceInfo(SmartWatchData_t *data) {
    (void)data; /* unused */
    OLED_ClearBuffer();

    /* Status bar */
    UI_DrawStatusBar(data);

    /* Title */
    OLED_DrawString8x16(4, 1, "DEV INFO");

    for (uint8_t x = 0; x < SSD1306_WIDTH; x++)
        OLED_SetPixel(x, 24, 1);

    /* Device info lines */
    OLED_DrawString6x8(4, 4, "SmartWatch V1.0");
    OLED_DrawString6x8(4, 5, "STM32F103C8T6");
    OLED_DrawString6x8(4, 6, "OLED: SSD1306 128x64");

    /* Separator */
    OLED_DrawHLine(0, 55, 128);

    /* Bottom info line */
    OLED_DrawString6x8(4, 7, "I2C1 400kHz PB6/PB7");

    UI_DrawPageIndicator(4, PAGE_MAX);
}

/* ==================== Page Dispatcher ==================== */

void UI_DrawPage(UIPage_t page, SmartWatchData_t *data) {
    switch (page) {
        case PAGE_WATCH_FACE:  UI_DrawWatchFace(data);  break;
        case PAGE_HEART_RATE:  UI_DrawHeartRate(data);  break;
        case PAGE_STEPS:       UI_DrawSteps(data);       break;
        case PAGE_WEATHER:     UI_DrawWeather(data);     break;
        case PAGE_DEVICE_INFO: UI_DrawDeviceInfo(data);  break;
        default: break;
    }
    OLED_Update();
}

/* ==================== Scroll Effect ==================== */

void UI_ScrollEffect(UIPage_t from, UIPage_t to, SmartWatchData_t *data) {
    (void)from;
    /* Simple fade: clear, draw new page, update */
    OLED_ClearBuffer();
    UI_DrawPage(to, data);
}
