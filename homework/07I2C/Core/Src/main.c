/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <string.h>
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
#define SSD1306_ADDR     0x78   /* (7-bit 0x3D) << 1, if not working try 0x78 */
#define SSD1306_CMD       0x00
#define SSD1306_DATA      0x40

/* SSD1306 fundamental commands */
#define SSD1306_DISPLAYOFF        0xAE
#define SSD1306_DISPLAYON         0xAF
#define SSD1306_SETCONTRAST       0x81
#define SSD1306_DISPLAYALLON_RESUME 0xA4
#define SSD1306_DISPLAYALLON      0xA5
#define SSD1306_NORMALDISPLAY     0xA6
#define SSD1306_INVERTDISPLAY     0xA7

/* Scrolling */
#define SSD1306_RIGHT_HORIZONTAL_SCROLL  0x26
#define SSD1306_LEFT_HORIZONTAL_SCROLL   0x27
#define SSD1306_ACTIVATE_SCROLL          0x2F
#define SSD1306_DEACTIVATE_SCROLL        0x2E

/* Addressing */
#define SSD1306_MEMORYMODE        0x20
#define SSD1306_COLUMNADDR        0x21
#define SSD1306_PAGEADDR          0x22
#define SSD1306_SETLOWCOLUMN      0x00
#define SSD1306_SETHIGHCOLUMN     0x10
#define SSD1306_SETSTARTLINE      0x40

/* Hardware config */
#define SSD1306_SETMULTIPLEX      0xA8
#define SSD1306_SETDISPLAYOFFSET  0xD3
#define SSD1306_SETCOMPINS        0xDA
#define SSD1306_SETDISPLAYCLOCKDIV 0xD5
#define SSD1306_SETPRECHARGE      0xD9
#define SSD1306_SETVCOMDETECT     0xDB
#define SSD1306_CHARGEPUMP        0x8D
#define SSD1306_SEGREMAP          0xA1
#define SSD1306_COMSCANDEC        0xC8
/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
I2C_HandleTypeDef hi2c1;

/* USER CODE BEGIN PV */

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_I2C1_Init(void);
/* USER CODE BEGIN PFP */
void ssd1306_WriteCommand(uint8_t cmd);
void ssd1306_WriteData(uint8_t *data, uint16_t len);
void ssd1306_Init(void);
void ssd1306_SetCursor(uint8_t page, uint8_t col);
void ssd1306_WriteChar(char ch);
void ssd1306_WriteString(const char *str);
void ssd1306_ScrollRight(uint8_t start, uint8_t end, uint8_t speed);
void ssd1306_ScrollStop(void);
void ssd1306_Clear(void);
void ssd1306_ScrollMarquee(const char *str, uint8_t page, uint8_t delay_ms);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
/* 5x8 ASCII font for SSD1306, columns 0-4 (col 5 is spacer) */
static const uint8_t font5x8[][5] = {
    {0x00,0x00,0x00,0x00,0x00}, /* ' ' 32 */
    {0x00,0x00,0x5F,0x00,0x00}, /* '!' 33 */
    {0x00,0x07,0x00,0x07,0x00}, /* '"' 34 */
    {0x14,0x7F,0x14,0x7F,0x14}, /* '#' 35 */
    {0x24,0x2A,0x7F,0x2A,0x12}, /* '$' 36 */
    {0x23,0x13,0x08,0x64,0x62}, /* '%' 37 */
    {0x36,0x49,0x55,0x22,0x50}, /* '&' 38 */
    {0x00,0x05,0x03,0x00,0x00}, /* ''' 39 */
    {0x00,0x1C,0x22,0x41,0x00}, /* '(' 40 */
    {0x00,0x41,0x22,0x1C,0x00}, /* ')' 41 */
    {0x08,0x2A,0x1C,0x2A,0x08}, /* '*' 42 */
    {0x08,0x08,0x3E,0x08,0x08}, /* '+' 43 */
    {0x00,0x50,0x30,0x00,0x00}, /* ',' 44 */
    {0x08,0x08,0x08,0x08,0x08}, /* '-' 45 */
    {0x00,0x60,0x60,0x00,0x00}, /* '.' 46 */
    {0x20,0x10,0x08,0x04,0x02}, /* '/' 47 */
    {0x3E,0x51,0x49,0x45,0x3E}, /* '0' 48 */
    {0x00,0x42,0x7F,0x40,0x00}, /* '1' 49 */
    {0x42,0x61,0x51,0x49,0x46}, /* '2' 50 */
    {0x21,0x41,0x45,0x4B,0x31}, /* '3' 51 */
    {0x18,0x14,0x12,0x7F,0x10}, /* '4' 52 */
    {0x27,0x45,0x45,0x45,0x39}, /* '5' 53 */
    {0x3C,0x4A,0x49,0x49,0x30}, /* '6' 54 */
    {0x01,0x71,0x09,0x05,0x03}, /* '7' 55 */
    {0x36,0x49,0x49,0x49,0x36}, /* '8' 56 */
    {0x06,0x49,0x49,0x29,0x1E}, /* '9' 57 */
    {0x00,0x36,0x36,0x00,0x00}, /* ':' 58 */
    {0x00,0x56,0x36,0x00,0x00}, /* ';' 59 */
    {0x00,0x08,0x14,0x22,0x41}, /* '<' 60 */
    {0x14,0x14,0x14,0x14,0x14}, /* '=' 61 */
    {0x41,0x22,0x14,0x08,0x00}, /* '>' 62 */
    {0x02,0x01,0x51,0x09,0x06}, /* '?' 63 */
    {0x32,0x49,0x79,0x41,0x3E}, /* '@' 64 */
    {0x7E,0x11,0x11,0x11,0x7E}, /* 'A' 65 */
    {0x7F,0x49,0x49,0x49,0x36}, /* 'B' 66 */
    {0x3E,0x41,0x41,0x41,0x22}, /* 'C' 67 */
    {0x7F,0x41,0x41,0x22,0x1C}, /* 'D' 68 */
    {0x7F,0x49,0x49,0x49,0x41}, /* 'E' 69 */
    {0x7F,0x09,0x09,0x01,0x01}, /* 'F' 70 */
    {0x3E,0x41,0x41,0x51,0x32}, /* 'G' 71 */
    {0x7F,0x08,0x08,0x08,0x7F}, /* 'H' 72 */
    {0x00,0x41,0x7F,0x41,0x00}, /* 'I' 73 */
    {0x20,0x40,0x41,0x3F,0x01}, /* 'J' 74 */
    {0x7F,0x08,0x14,0x22,0x41}, /* 'K' 75 */
    {0x7F,0x40,0x40,0x40,0x40}, /* 'L' 76 */
    {0x7F,0x02,0x04,0x02,0x7F}, /* 'M' 77 */
    {0x7F,0x04,0x08,0x10,0x7F}, /* 'N' 78 */
    {0x3E,0x41,0x41,0x41,0x3E}, /* 'O' 79 */
    {0x7F,0x09,0x09,0x09,0x06}, /* 'P' 80 */
    {0x3E,0x41,0x51,0x21,0x5E}, /* 'Q' 81 */
    {0x7F,0x09,0x19,0x29,0x46}, /* 'R' 82 */
    {0x46,0x49,0x49,0x49,0x31}, /* 'S' 83 */
    {0x01,0x01,0x7F,0x01,0x01}, /* 'T' 84 */
    {0x3F,0x40,0x40,0x40,0x3F}, /* 'U' 85 */
    {0x1F,0x20,0x40,0x20,0x1F}, /* 'V' 86 */
    {0x7F,0x20,0x18,0x20,0x7F}, /* 'W' 87 */
    {0x63,0x14,0x08,0x14,0x63}, /* 'X' 88 */
    {0x03,0x04,0x78,0x04,0x03}, /* 'Y' 89 */
    {0x61,0x51,0x49,0x45,0x43}, /* 'Z' 90 */
    {0x00,0x00,0x7F,0x41,0x41}, /* '[' 91 */
    {0x02,0x04,0x08,0x10,0x20}, /* '\' 92 */
    {0x41,0x41,0x7F,0x00,0x00}, /* ']' 93 */
    {0x04,0x02,0x01,0x02,0x04}, /* '^' 94 */
    {0x40,0x40,0x40,0x40,0x40}, /* '_' 95 */
    {0x00,0x01,0x02,0x04,0x00}, /* '`' 96 */
    {0x20,0x54,0x54,0x54,0x78}, /* 'a' 97 */
    {0x7F,0x48,0x44,0x44,0x38}, /* 'b' 98 */
    {0x38,0x44,0x44,0x44,0x20}, /* 'c' 99 */
    {0x38,0x44,0x44,0x48,0x7F}, /* 'd' 100 */
    {0x38,0x54,0x54,0x54,0x18}, /* 'e' 101 */
    {0x08,0x7E,0x09,0x01,0x02}, /* 'f' 102 */
    {0x08,0x14,0x54,0x54,0x3C}, /* 'g' 103 */
    {0x7F,0x08,0x04,0x04,0x78}, /* 'h' 104 */
    {0x00,0x44,0x7D,0x40,0x00}, /* 'i' 105 */
    {0x20,0x40,0x44,0x3D,0x00}, /* 'j' 106 */
    {0x00,0x7F,0x10,0x28,0x44}, /* 'k' 107 */
    {0x00,0x41,0x7F,0x40,0x00}, /* 'l' 108 */
    {0x7C,0x04,0x18,0x04,0x78}, /* 'm' 109 */
    {0x7C,0x08,0x04,0x04,0x78}, /* 'n' 110 */
    {0x38,0x44,0x44,0x44,0x38}, /* 'o' 111 */
    {0x7C,0x14,0x14,0x14,0x08}, /* 'p' 112 */
    {0x08,0x14,0x14,0x18,0x7C}, /* 'q' 113 */
    {0x7C,0x08,0x04,0x04,0x08}, /* 'r' 114 */
    {0x48,0x54,0x54,0x54,0x20}, /* 's' 115 */
    {0x04,0x3F,0x44,0x40,0x20}, /* 't' 116 */
    {0x3C,0x40,0x40,0x20,0x7C}, /* 'u' 117 */
    {0x1C,0x20,0x40,0x20,0x1C}, /* 'v' 118 */
    {0x3C,0x40,0x30,0x40,0x3C}, /* 'w' 119 */
    {0x44,0x28,0x10,0x28,0x44}, /* 'x' 120 */
    {0x0C,0x50,0x50,0x50,0x3C}, /* 'y' 121 */
    {0x44,0x64,0x54,0x4C,0x44}, /* 'z' 122 */
    {0x00,0x08,0x36,0x41,0x00}, /* '{' 123 */
    {0x00,0x00,0x7F,0x00,0x00}, /* '|' 124 */
    {0x00,0x41,0x36,0x08,0x00}, /* '}' 125 */
    {0x08,0x08,0x2A,0x1C,0x08}, /* '~' 126 */
};
/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_I2C1_Init();
  /* USER CODE BEGIN 2 */
  ssd1306_Init();
  ssd1306_Clear();
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
    ssd1306_ScrollMarquee("Hello World!", 3, 30);
    HAL_Delay(500);
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.HSEPredivValue = RCC_HSE_PREDIV_DIV1;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLMUL = RCC_PLL_MUL9;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief I2C1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_I2C1_Init(void)
{

  /* USER CODE BEGIN I2C1_Init 0 */

  /* USER CODE END I2C1_Init 0 */

  /* USER CODE BEGIN I2C1_Init 1 */

  /* USER CODE END I2C1_Init 1 */
  hi2c1.Instance = I2C1;
  hi2c1.Init.ClockSpeed = 100000;
  hi2c1.Init.DutyCycle = I2C_DUTYCYCLE_2;
  hi2c1.Init.OwnAddress1 = 0;
  hi2c1.Init.AddressingMode = I2C_ADDRESSINGMODE_7BIT;
  hi2c1.Init.DualAddressMode = I2C_DUALADDRESS_DISABLE;
  hi2c1.Init.OwnAddress2 = 0;
  hi2c1.Init.GeneralCallMode = I2C_GENERALCALL_DISABLE;
  hi2c1.Init.NoStretchMode = I2C_NOSTRETCH_DISABLE;
  if (HAL_I2C_Init(&hi2c1) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN I2C1_Init 2 */

  /* USER CODE END I2C1_Init 2 */

}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  /* USER CODE BEGIN MX_GPIO_Init_1 */

  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOD_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */

/* ---- low-level I2C helpers ---- */
void ssd1306_WriteCommand(uint8_t cmd)
{
    uint8_t buf[2] = {SSD1306_CMD, cmd};
    HAL_I2C_Master_Transmit(&hi2c1, SSD1306_ADDR, buf, 2, HAL_MAX_DELAY);
}

void ssd1306_WriteData(uint8_t *data, uint16_t len)
{
    /* HAL_I2C_Mem_Write auto-prepends the control byte (0x40) */
    HAL_I2C_Mem_Write(&hi2c1, SSD1306_ADDR, SSD1306_DATA,
                      I2C_MEMADD_SIZE_8BIT, data, len, HAL_MAX_DELAY);
}

/* ---- init sequence ---- */
void ssd1306_Init(void)
{
    HAL_Delay(10); /* wait for VDD rise */

    ssd1306_WriteCommand(SSD1306_DISPLAYOFF);

    ssd1306_WriteCommand(SSD1306_SETDISPLAYCLOCKDIV);
    ssd1306_WriteCommand(0x80);

    ssd1306_WriteCommand(SSD1306_SETMULTIPLEX);
    ssd1306_WriteCommand(0x3F);  /* 64 lines */

    ssd1306_WriteCommand(SSD1306_SETDISPLAYOFFSET);
    ssd1306_WriteCommand(0x00);

    ssd1306_WriteCommand(SSD1306_SETSTARTLINE | 0x00);

    ssd1306_WriteCommand(SSD1306_CHARGEPUMP);
    ssd1306_WriteCommand(0x14);  /* enable charge pump (external VCC) */

    ssd1306_WriteCommand(SSD1306_MEMORYMODE);
    ssd1306_WriteCommand(0x00);  /* horizontal addressing */

    ssd1306_WriteCommand(SSD1306_SEGREMAP);
    ssd1306_WriteCommand(SSD1306_COMSCANDEC);

    ssd1306_WriteCommand(SSD1306_SETCOMPINS);
    ssd1306_WriteCommand(0x12);

    ssd1306_WriteCommand(SSD1306_SETCONTRAST);
    ssd1306_WriteCommand(0x7F);

    ssd1306_WriteCommand(SSD1306_SETPRECHARGE);
    ssd1306_WriteCommand(0x22);

    ssd1306_WriteCommand(SSD1306_SETVCOMDETECT);
    ssd1306_WriteCommand(0x20);

    ssd1306_WriteCommand(SSD1306_DISPLAYALLON_RESUME);
    ssd1306_WriteCommand(SSD1306_NORMALDISPLAY);

    ssd1306_WriteCommand(SSD1306_DEACTIVATE_SCROLL);
    ssd1306_WriteCommand(SSD1306_DISPLAYON);
}

/* ---- cursor / rendering ---- */
void ssd1306_SetCursor(uint8_t page, uint8_t col)
{
    ssd1306_WriteCommand(SSD1306_PAGEADDR);
    ssd1306_WriteCommand(page);
    ssd1306_WriteCommand(7);  /* last page (display has 8 pages, 0-7) */

    ssd1306_WriteCommand(SSD1306_COLUMNADDR);
    ssd1306_WriteCommand(col);
    ssd1306_WriteCommand(127);
}

void ssd1306_WriteChar(char ch)
{
    if (ch < ' ' || ch > '~') ch = ' ';
    uint8_t buf[6];
    buf[0] = 0x00; /* column spacer */
    memcpy(&buf[1], font5x8[ch - ' '], 5);
    ssd1306_WriteData(buf, 6);
}

void ssd1306_WriteString(const char *str)
{
    while (*str) {
        ssd1306_WriteChar(*str++);
    }
}

void ssd1306_Clear(void)
{
    for (uint8_t page = 0; page < 8; page++) {
        ssd1306_SetCursor(page, 0);
        uint8_t zero[128] = {0};
        ssd1306_WriteData(zero, 128);
    }
}

/* ---- hardware scrolling ---- */
void ssd1306_ScrollRight(uint8_t start, uint8_t end, uint8_t speed)
{
    ssd1306_WriteCommand(SSD1306_DEACTIVATE_SCROLL);
    ssd1306_WriteCommand(SSD1306_RIGHT_HORIZONTAL_SCROLL);
    ssd1306_WriteCommand(0x00);            /* dummy */
    ssd1306_WriteCommand(start);           /* start page */
    ssd1306_WriteCommand(speed & 0x07);    /* frame interval */
    ssd1306_WriteCommand(end);             /* end page */
    ssd1306_WriteCommand(0x00);            /* dummy */
    ssd1306_WriteCommand(0xFF);            /* dummy */
    ssd1306_WriteCommand(SSD1306_ACTIVATE_SCROLL);
}

void ssd1306_ScrollStop(void)
{
    ssd1306_WriteCommand(SSD1306_DEACTIVATE_SCROLL);
}

/* Draw a string into a 128-byte page buffer at pixel offset x_off */
static void ssd1306_DrawTextBuf(uint8_t *buf, const char *str, int x_off)
{
    int len = (int)strlen(str);
    for (int i = 0; i < len; i++) {
        int cx = x_off + i * 6;
        if (cx < -5 || cx > 127) continue;
        for (int col = 0; col < 6; col++) {
            int x = cx + col;
            if (x >= 0 && x < 128)
                buf[x] = (col == 0) ? 0 : font5x8[(int)(str[i] - ' ')][col - 1];
        }
    }
}

/* Smooth marquee scroll: text enters from right, exits left */
void ssd1306_ScrollMarquee(const char *str, uint8_t page, uint8_t delay_ms)
{
    int tw = (int)strlen(str) * 6;
    uint8_t buf[128];

    for (int off = 128; off > -tw; off--) {
        memset(buf, 0, sizeof(buf));
        ssd1306_DrawTextBuf(buf, str, off);
        ssd1306_SetCursor(page, 0);
        ssd1306_WriteData(buf, 128);
        HAL_Delay(delay_ms);
    }
}

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
