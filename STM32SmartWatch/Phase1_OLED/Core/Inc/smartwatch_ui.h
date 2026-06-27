#ifndef __SMARTWATCH_UI_H
#define __SMARTWATCH_UI_H

#include "main.h"
#include <stdint.h>

/* UI Pages */
typedef enum {
    PAGE_WATCH_FACE = 0,
    PAGE_HEART_RATE,
    PAGE_STEPS,
    PAGE_WEATHER,
    PAGE_DEVICE_INFO,
    PAGE_MAX
} UIPage_t;

/* Demo data (simulated sensor data) */
typedef struct {
    uint8_t  hour;
    uint8_t  minute;
    uint8_t  second;
    uint16_t year;
    uint8_t  month;
    uint8_t  day;
    uint8_t  weekday;       /* 0=Sun, 1=Mon ... 6=Sat */
    uint8_t  heart_rate;
    uint8_t  hr_min;
    uint8_t  hr_max;
    uint32_t steps;
    float    distance_km;
    uint16_t calories_kcal;
    uint8_t  temp_celsius;
    uint8_t  humidity_pct;
    uint16_t pressure_hpa;
    uint8_t  battery_pct;
} SmartWatchData_t;

/* ==================== UI Framework API ==================== */

/* Initialize demo data with default values */
void UI_InitData(SmartWatchData_t *data);

/* Draw a single page (does NOT call OLED_Update) */
void UI_DrawPage(UIPage_t page, SmartWatchData_t *data);

/* Draw status bar (top 10px: battery, Bluetooth, time) */
void UI_DrawStatusBar(SmartWatchData_t *data);

/* Draw page indicator dots at bottom */
void UI_DrawPageIndicator(uint8_t current, uint8_t total);

/* Scroll transition effect (simple) */
void UI_ScrollEffect(UIPage_t from, UIPage_t to, SmartWatchData_t *data);

#endif /* __SMARTWATCH_UI_H */
