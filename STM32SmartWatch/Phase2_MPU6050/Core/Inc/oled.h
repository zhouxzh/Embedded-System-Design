#ifndef __OLED_H
#define __OLED_H

#include "main.h"

/* SSD1306 I2C address (7-bit: 0x3C, shifted: 0x78) */
#define SSD1306_ADDR        0x3C

/* Display dimensions */
#define SSD1306_WIDTH       128
#define SSD1306_HEIGHT      64
#define SSD1306_PAGES       8

/* Color constants */
#define OLED_BLACK          0
#define OLED_WHITE          1

/* Framebuffer - accessible for direct manipulation */
extern uint8_t OLED_Buffer[SSD1306_WIDTH * SSD1306_PAGES];

/* Icon / bitmap exports for UI layer */
extern const uint8_t IconHeart[20];
extern const uint8_t IconBattery[12];
extern const uint8_t IconBT[8];

/* Font dimensions */
#define FONT_6X8_WIDTH      6
#define FONT_6X8_HEIGHT     8
#define FONT_8X16_WIDTH     8
#define FONT_8X16_HEIGHT    16
#define FONT_16X24_WIDTH    16
#define FONT_16X24_HEIGHT   24

/* ==================== OLED Driver API ==================== */

void OLED_Init(void);
void OLED_Clear(void);
void OLED_ClearBuffer(void);
void OLED_Update(void);
void OLED_UpdateArea(uint8_t start_page, uint8_t end_page);
void OLED_SetContrast(uint8_t contrast);
void OLED_DisplayOn(void);
void OLED_DisplayOff(void);

/* Drawing primitives (operate on framebuffer) */
void OLED_SetPixel(uint8_t x, uint8_t y, uint8_t color);
void OLED_DrawLine(uint8_t x0, uint8_t y0, uint8_t x1, uint8_t y1);
void OLED_DrawHLine(uint8_t x, uint8_t y, uint8_t w);
void OLED_DrawVLine(uint8_t x, uint8_t y, uint8_t h);
void OLED_DrawRect(uint8_t x, uint8_t y, uint8_t w, uint8_t h);
void OLED_DrawFilledRect(uint8_t x, uint8_t y, uint8_t w, uint8_t h);
void OLED_DrawCircle(uint8_t cx, uint8_t cy, uint8_t r);
void OLED_DrawFilledCircle(uint8_t cx, uint8_t cy, uint8_t r);
void OLED_DrawBitmap(uint8_t x, uint8_t y, const uint8_t *bitmap, uint8_t w, uint8_t h);
void OLED_InvertDisplay(uint8_t invert);

/* Text rendering (6x8 font, page-aligned) */
void OLED_DrawChar6x8(uint8_t x, uint8_t page, char c);
void OLED_DrawString6x8(uint8_t x, uint8_t page, const char *str);

/* Text rendering (8x16 font, page-aligned) */
void OLED_DrawChar8x16(uint8_t x, uint8_t page, char c);
void OLED_DrawString8x16(uint8_t x, uint8_t page, const char *str);

/* Large number rendering (16x24 font) for clock display */
void OLED_DrawDigit16x24(uint8_t x, uint8_t y, uint8_t digit);
void OLED_DrawColon16x24(uint8_t x, uint8_t y);
void OLED_DrawTime16x24(uint8_t x, uint8_t y, uint8_t hour, uint8_t minute);

/* Convenience: printf-style output */
void OLED_Printf6x8(uint8_t x, uint8_t page, const char *fmt, ...);

#endif /* __OLED_H */
