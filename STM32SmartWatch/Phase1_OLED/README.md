# Phase 1：点亮 OLED 显示屏

## 目标

只连接 OLED（0.96 寸 MK993，4 管脚，SSD1306 控制器，I2C 接口），用裸机程序在屏幕上显示文字。

## 硬件：MK993 OLED 模块

| 参数 | 规格 |
|------|------|
| 型号 | MK993 |
| 尺寸 | 0.96 寸 |
| 分辨率 | 128 × 64 像素 |
| 控制器 | SSD1306 |
| 接口 | I2C（4 管脚） |
| 管脚 | VCC / GND / SCL / SDA |
| I2C 地址 | 0x3C（需验证，部分模块为 0x3D） |

> MK993 为 4 管脚模块，没有独立的 RESET 引脚。SSD1306 支持通过 I2C 命令进行软件复位，无需额外硬件复位。

## 硬件连接

| OLED 模块 | STM32F103C8T6 |
|-----------|---------------|
| VCC | 3.3V |
| GND | GND |
| SCL | PB6 |
| SDA | PB7 |

> SCL/SDA 需接 4.7kΩ 上拉电阻到 3.3V。MK993 模块通常已板载上拉电阻，建议用万用表确认：测 SCL 对 VCC、SDA 对 VCC 的阻值，约 4.7kΩ 则说明已有上拉。

## STM32CubeMX 配置

### 1. 新建工程

- **File → New Project** → 搜索 `STM32F103C8T6` → 双击 `STM32F103C8Tx`

### 2. System Core → SYS

| 配置项 | 选项 |
|--------|------|
| Debug | **Serial Wire** |
| Timebase Source | **SysTick** |

### 3. System Core → RCC

| 配置项 | 选项 |
|--------|------|
| High Speed Clock (HSE) | **Crystal/Ceramic Resonator** |

### 4. Clock Configuration（时钟树）

```
HSE (8MHz) → /1 → PLL Source Mux → ×9 → PLL (72MHz) → /1 → SYSCLK (72MHz)
                                                              ↓
                                              AHB /1 (72MHz) ──┬── APB1 /2 (36MHz)
                                                                └── APB2 /1 (72MHz)
```

逐步操作：

1. **PLL Source Mux** → HSE
2. **PLL Mul** → ×9
3. **System Clock Mux** → PLLCLK
4. **AHB Prescaler** → /1
5. **APB1 Prescaler** → /2
6. **APB2 Prescaler** → /1

确认 HCLK = 72MHz 后继续。

### 5. Pinout View → 配置 I2C1

- 将 **PB6** 设置为 **I2C1_SCL**
- 将 **PB7** 设置为 **I2C1_SDA**

点击 I2C1 进入配置面板，**Parameter Settings**：

| 配置项 | 值 |
|--------|-----|
| I2C Speed Mode | **Fast Mode** |
| Clock Speed | **400000** (Hz) |

其余参数保持默认。本阶段不需要使能 I2C 中断（裸机轮询方式即可）。

### 6. Project Manager

| 配置项 | 值 |
|--------|-----|
| Project Name | `SmartWatch_Phase1` |
| Toolchain/IDE | MDK-ARM 或 STM32CubeIDE |
| Code Generator → Copy only necessary library files | ✅ |
| Code Generator → Generate peripheral init as .c/.h pairs | ✅ |

### 7. GENERATE CODE

点击右上角 **GENERATE CODE**。

## 本阶段 CubeMX 配置总结

```
已启用外设：
  ✅ I2C1     — Fast Mode 400kHz  (PB6/PB7)
  ✅ SYS      — Serial Wire, SysTick 时基
  ✅ RCC      — HSE 8MHz 晶振
  ✅ 时钟树   — 72MHz

未启用的外设（后续 Phase 再加）：
  ❌ USART1   — Phase 3 加入
  ❌ TIM2     — Phase 4 加入
  ❌ TIM3     — Phase 4 加入
  ❌ FreeRTOS — Phase 4 加入
```

## SSD1306 控制器详解

MK993 模块搭载 **Solomon Systech SSD1306** —— 一款单芯片 CMOS OLED/PLED 驱动器，内嵌对比度控制、显示 RAM 和振荡器，专为 128×64 点阵 OLED 面板设计。

### 1. SSD1306 内部架构

```
┌──────────────────────────────────────────────────────┐
│                      SSD1306                         │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐ │
│  │ I2C/SPI  │  │   Clock  │  │   Graphic Display  │ │
│  │Interface │  │  Control │  │   RAM (GDDRAM)     │ │
│  │          │  │          │  │   128 × 64 bits    │ │
│  │ SA0 ─ I2C│  │ OSC ÷ D  │  │   = 1024 bytes    │ │
│  │ BS1,BS2  │  │ DCLK     │  │  organized as      │ │
│  │ for SPI  │  │          │  │  8 pages × 128 cols│ │
│  └────┬─────┘  └────┬─────┘  └─────────┬──────────┘ │
│       │             │                  │             │
│  ┌────┴─────────────┴──────────────────┴──────────┐  │
│  │              Command Decoder & Control           │  │
│  │  ┌──────┐ ┌─────────┐ ┌────────┐ ┌──────────┐  │  │
│  │  │Fundam│ │Address  │ │HW Conf │ │Timing &  │  │  │
│  │  │ental │ │Control  │ │(COM/HW)│ │Precharge │  │  │
│  │  └──────┘ └─────────┘ └────────┘ └──────────┘  │  │
│  └────────────────────┬────────────────────────────┘  │
│                       │                               │
│  ┌────────────────────┴────────────────────────────┐  │
│  │         Row Driver (COM0 ~ COM63)                │  │
│  │         Column Driver (SEG0 ~ SEG127)            │  │
│  │         Charge Pump (3.3V → 7.5V panel)          │  │
│  └─────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

**GDDRAM 组织方式：**

SSD1306 内部 **GDDRAM** (Graphic Display Data RAM) 为 **128×64 bits = 1024 bytes**，划分为 **8 个 Page (0~7)，每个 Page 128 列**。每个 Page 对应 OLED 面板上纵向 8 个像素（一个字节的 8 位从低到高分别对应 page 内的 8 行像素）。

```
     SEG0    SEG1    SEG2    ...    SEG127
COM0  Page0[col0 bit0]  Page0[col1 bit0]  ...  Page0[col127 bit0]     ── Y=0
COM1  Page0[col0 bit1]  Page0[col1 bit1]  ...  Page0[col127 bit1]     ── Y=1
 ...   ...
COM7  Page0[col0 bit7]  Page0[col1 bit7]  ...  Page0[col127 bit7]     ── Y=7
COM8  Page1[col0 bit0]  Page1[col1 bit0]  ...  Page1[col127 bit0]     ── Y=8
 ...   ...
COM63 Page7[col0 bit7]  Page7[col1 bit7]  ...  Page7[col127 bit7]     ── Y=63
```

> **关键理解：** GDDRAM 中的 1 bit 对应屏幕上 1 个像素。写入 `1` 点亮像素，`0` 熄灭。数据按 Page 组织：写 Page 0 的 128 bytes 就决定了屏幕顶部 8 行像素。

### 2. I2C 通信协议

#### 2.1 I2C 地址

| SA0 引脚状态 | 7-bit 地址 | 8-bit 写地址 | 备注 |
|-------------|-----------|-------------|------|
| 接地 (GND) | **0x3C** | 0x78 | MK993 模块默认 |
| 接 VCC | **0x3D** | 0x7A | 部分模块使用 |

MK993 模块 PCB 上 SA0 默认接地，地址为 **0x3C**。STM32 HAL 库中 `HAL_I2C_Mem_Write` 会自动左移 1 位，因此传入的地址参数为 `0x3C`（7-bit 形式）。

#### 2.2 控制字节：命令 vs 数据

I2C 传输 SSD1306 时，在地址字节之后必须跟一个 **控制字节 (Control Byte)**，用于区分后续字节是命令还是数据：

| 控制字节 | 含义 | 后续字节 |
|---------|------|---------|
| **0x00** | 命令模式 (Co=0, D/C#=0) | 下一个字节为命令 |
| **0x40** | 数据模式 (Co=0, D/C#=1) | 下一个字节写入 GDDRAM |
| 0x80 | 单命令模式 (Co=1, D/C#=0) | 仅发一个命令字节（不推荐，效率低） |

**实际代码中：**

```c
/* 写单个命令 — HAL_I2C_Mem_Write 自动处理地址+控制字节+数据 */
static void SSD1306_WriteCommand(uint8_t cmd) {
    HAL_I2C_Mem_Write(&hi2c1, SSD1306_ADDR << 1, 0x00,  // MemAddress=0x00 → 控制字节0x00
                      I2C_MEMADD_SIZE_8BIT, &cmd, 1, 100);
}

/* 批量写命令 — 一次 I2C 事务发送多个命令（高效） */
static void SSD1306_WriteCommands(const uint8_t *cmds, uint8_t len) {
    HAL_I2C_Mem_Write(&hi2c1, SSD1306_ADDR << 1, 0x00,
                      I2C_MEMADD_SIZE_8BIT, (uint8_t *)cmds, len, 100);
}

/* 写 GDDRAM 数据 — MemAddress=0x40 → 控制字节0x40 */
static void SSD1306_WriteData(const uint8_t *data, uint16_t len) {
    HAL_I2C_Mem_Write(&hi2c1, SSD1306_ADDR << 1, 0x40,
                      I2C_MEMADD_SIZE_8BIT, (uint8_t *)data, len, 200);
}
```

#### 2.3 I2C 时序要求

| 参数 | 符号 | 最小值 | 最大值 | 单位 |
|------|------|--------|--------|------|
| SCL 时钟频率 | f_SCL | — | **400** | kHz |
| 起始条件保持时间 | t_HD;STA | 0.6 | — | μs |
| 数据建立时间 | t_SU;DAT | 100 | — | ns |
| 停止条件建立时间 | t_SU;STO | 0.6 | — | μs |
| 总线空闲时间 | t_BUF | 1.3 | — | μs |

> 项目配置 I2C Fast Mode (400kHz)，在 72MHz SYSCLK、36MHz APB1 下完全满足时序要求。

### 3. SSD1306 命令集完整参考

#### 3.1 基础命令 (Fundamental Commands)

| 命令 | 代码 | 参数 | 说明 |
|------|------|------|------|
| **Display OFF** | `0xAE` | — | 关闭 OLED 面板，GDDRAM 内容保留 |
| **Display ON** | `0xAF` | — | 打开 OLED 面板，显示 GDDRAM 内容 |
| **Normal Display** | `0xA6` | — | GDDRAM `1` = 点亮（正常模式） |
| **Inverse Display** | `0xA7` | — | GDDRAM `0` = 点亮（反转模式） |
| **Entire Display ON** | `0xA5` | — | 忽略 GDDRAM，全部像素点亮 |
| **Entire Display ON from RAM** | `0xA4` | — | 按 GDDRAM 内容显示（正常工作模式） |
| **Set Contrast** | `0x81` | `contrast[7:0]` | 对比度控制，范围 0x00~0xFF（默认 0x7F） |

#### 3.2 寻址命令 (Addressing Commands)

| 命令 | 代码 | 参数 | 说明 |
|------|------|------|------|
| **Set Memory Addressing Mode** | `0x20` | `mode` | `0x00`=水平 / `0x01`=垂直 / `0x02`=页寻址 |
| **Set Column Address** | `0x21` | `start, end` | 水平/垂直模式下设定列范围 (0~127) |
| **Set Page Address** | `0x22` | `start, end` | 水平/垂直模式下设定页范围 (0~7) |
| **Set Page Start Address** | `0xB0~0xB7` | — | 页寻址模式下指定当前 Page |

> **本项目采用页寻址模式** (`0x20, 0x00` 即水平寻址) + 手动逐页刷新。这比全屏自动寻址更可靠——每页刷新前显式设定 Page 地址和列起始地址，避免 GDDRAM 写入错位。

#### 3.3 硬件配置命令 (Hardware Configuration)

| 命令 | 代码 | 参数 | 说明 |
|------|------|------|------|
| **Set Segment Remap** | `0xA0`/`0xA1` | — | `0xA0`=SEG0→col 0; **`0xA1`=SEG0→col 127**（本项目使用） |
| **Set COM Output Scan Dir** | `0xC0`/`0xC8` | — | `0xC0`=COM0→COM63; **`0xC8`=COM63→COM0**（本项目使用） |
| **Set COM Pins HW Config** | `0xDA` | `config` | `0x02`=顺序; `0x12`=交替（128×64 面板用 0x12） |
| **Set Multiplex Ratio** | `0xA8` | `ratio[5:0]` | MUX 比率，128×64 面板设 63 (`0x3F`) |
| **Set Display Offset** | `0xD3` | `offset[5:0]` | COM 起始行偏移，通常为 0 |
| **Set Display Start Line** | `0x40~0x7F` | — | GDDRAM 显示起始行，通常为 0 (`0x40`) |
| **Charge Pump Setting** | `0x8D` | `enable` | `0x10`=禁用; **`0x14`=启用**（3.3V 供电必须开启） |

#### 3.4 时序与驱动命令 (Timing & Driving)

| 命令 | 代码 | 参数 | 说明 |
|------|------|------|------|
| **Set Display Clock Divide** | `0xD5` | `ratio` | `[7:4]`=振荡频率; `[3:0]`=分频比。默认 `0x80` |
| **Set Pre-charge Period** | `0xD9` | `period` | `[7:4]`=Phase 1; `[3:0]`=Phase 2。推荐 `0xF1` |
| **Set VCOMH Deselect Level** | `0xDB` | `level` | `[6:4]`=VCOMH 电平。`0x40` 对应约 0.77×VCC |

#### 3.5 滚动命令 (Scrolling Commands)

| 命令 | 代码 | 说明 |
|------|------|------|
| **Continuous Horizontal Scroll Setup** | `0x26`/`0x27` | 水平滚动（右/左） |
| **Continuous Vertical + Horizontal** | `0x29`/`0x2A` | 对角滚动 |
| **Deactivate Scroll** | `0x2E` | **停止所有滚动**（初始化时必须调用） |
| **Activate Scroll** | `0x2F` | 启动已配置的滚动 |

> 本项目在初始化序列末尾执行 `0x2E`，确保滚动功能被禁用，画面静止。

### 4. 初始化序列详解

以下是 `OLED_Init()` 中每条命令的作用，按执行顺序解释：

```c
uint8_t init[] = {
    0xAE,       // ① Display OFF — 初始化前先关闭面板
    0x20, 0x00, // ② 寻址模式 = 水平寻址
    0x40,       // ③ 显示起始行 = 0（0x40 | 0）
    0xA1,       // ④ 段重映射: SEG0 对应列 127（左右镜像）
    0xC8,       // ⑤ COM 扫描方向: COM63→COM0（上下镜像）
    0xA8, 0x3F, // ⑥ MUX = 63（64 行，适配 128×64 面板）
    0xD3, 0x00, // ⑦ 显示偏移 = 0（不从中间行开始）
    0xD5, 0x80, // ⑧ 时钟分频: OSC=1000, DIV=0
    0xD9, 0xF1, // ⑨ 预充电周期: Phase1=15, Phase2=1
    0xDA, 0x12, // ⑩ COM 引脚配置 = 交替模式（128×64 标准）
    0xDB, 0x40, // ⑪ VCOMH 取消选择电平 ≈ 0.77×VCC
    0x81, 0xCF, // ⑫ 对比度 = 207（0xCF，亮度较高）
    0x8D, 0x14, // ⑬ 启用电荷泵（3.3V → 7.5V 面板驱动电压）
    0xA4,       // ⑭ 全屏显示跟随 GDDRAM
    0xA6,       // ⑮ 正常显示（非反转）
    0x2E,       // ⑯ 禁用滚动
    0xAF        // ⑰ Display ON — 初始化完成，点亮
};
```

**关键的硬件适配细节：**

- **`0xA1` + `0xC8`**：决定屏幕方向。这两个值配合实现 "左上角为原点、向右为+x、向下为+y" 的坐标系。如果修改其中一个，画面会翻转。
- **`0x8D, 0x14`**：**3.3V 供电下必须开启 Charge Pump**。SSD1306 内部电荷泵将 3.3V 升压至约 7.5V 以驱动 OLED 面板。如果忘记此条，屏幕完全不亮。
- **`0xDA, 0x12`**：COM 引脚交替配置。128×64 面板必须使用 `0x12`（alternative COM pin configuration），而非 `0x02`（sequential）。
- **初始化前后各加 `HAL_Delay(100)`**：上电后 SSD1306 需要约 100ms 完成内部复位和电荷泵稳定。

### 5. 软件 Framebuffer 架构

本项目采用 **全屏 Framebuffer** 方案：

```c
uint8_t OLED_Buffer[SSD1306_WIDTH * SSD1306_PAGES];  // 128 × 8 = 1024 bytes
```

**渲染流程：**

```
绘制操作（修改 framebuffer）          I2C 刷新（送 GDDRAM）
══════════════════════════            ══════════════════════
                                     Page 0 → 0xB0 + 0x00,0x10 + 128 bytes
OLED_DrawString6x8()  ─┐             Page 1 → 0xB1 + 0x00,0x10 + 128 bytes
OLED_DrawLine()       ─┤             Page 2 → 0xB2 + 0x00,0x10 + 128 bytes
OLED_DrawCircle()     ─┼─ OLED_Buffer    :      :
OLED_DrawBitmap()     ─┤   (1024B)    Page 7 → 0xB7 + 0x00,0x10 + 128 bytes
直接操作 OLED_Buffer[]─┘             ═══════════════════════════════════════
                                     I2C @ 400kHz: 1024B ≈ 25ms/帧
```

**为什么用 Page 寻址逐页刷新而不是一次性发送全部 1024 字节？**

1. **可靠性**：每页刷新前显式设定 Page 地址，即使某页 I2C 出错也只影响该页
2. **部分刷新**：`OLED_UpdateArea(0, 2)` 可以只刷新状态栏（Page 0~2），大幅减少 I2C 传输量
3. **HAL 库限制**：`HAL_I2C_Mem_Write` 单次传输长度受硬件 FIFO 限制，分批发送更安全

**Framebuffer 坐标系：**

```
(0,0) ────────────────────────────── x → (127,0)
  │    Page 0 (y=0~7)  ................
  │    Page 1 (y=8~15) ................
  │    Page 2 (y=16~23) ...............
  │    Page 3 (y=24~31) ...............
  │    Page 4 (y=32~39) ...............
  │    Page 5 (y=40~47) ...............
  │    Page 6 (y=48~55) ...............
  y    Page 7 (y=56~63) ...............
  ↓
(0,63)
```

### 6. 字体系统

项目内置三套字体，覆盖不同场景：

| 字体 | 尺寸 | 字符集 | 用途 | 适用 Page |
|------|------|--------|------|----------|
| **Font6x8** | 6×8 px | ASCII 0x20~0x7E (95字符) | 正文、状态栏、信息行 | 单 Page (page-aligned) |
| **Font8x16** | 8×16 px | 0-9, A-Z, `.`, `:`, `-`, `/` (42字符) | 标题、中等数字 | 双 Page (page-aligned) |
| **Font16x24** | 16×24 px | 0-9, `:` (11字符) | 大号时间显示 | 任意 y 坐标 (3 Page Span) |

**使用示例：**

```c
/* 6x8 字体 — 状态栏小字 */
OLED_DrawString6x8(0, 0, "85% 10:30");        // x=col, page=0

/* 8x16 字体 — 页面标题 */
OLED_DrawString8x16(4, 1, "HEART RATE");       // 占据 Page 1 和 Page 2

/* 16x24 字体 — 时钟大数字（支持非 page 对齐的 y 坐标） */
OLED_DrawTime16x24(20, 14, 10, 30);            // x=20, y=14, 显示 "10:30"

/* printf 风格 */
OLED_Printf6x8(4, 5, "STEPS: %lu", steps_count);
```

**为什么不包含完整 ASCII 8x16 字库？**

8x16 完整 ASCII (95 字符 × 16 bytes) = 1520 bytes，当前仅数字+大写字母 (42 字符) = 672 bytes。STM32F103C8T6 仅有 64KB Flash，精简字库节省 ~850 bytes，为后续 Phase 的 FreeRTOS 和应用逻辑预留空间。

### 7. 绘图 API 参考

| 函数 | 说明 | 坐标系 |
|------|------|--------|
| `OLED_SetPixel(x, y, color)` | 绘制单像素 | (x,y) 绝对坐标 |
| `OLED_DrawHLine(x, y, w)` | 水平线 | (x,y) 起点，w 宽度 |
| `OLED_DrawVLine(x, y, h)` | 竖直线 | (x,y) 起点，h 高度 |
| `OLED_DrawLine(x0,y0,x1,y1)` | 任意直线 (Bresenham) | 两端点坐标 |
| `OLED_DrawRect(x, y, w, h)` | 空心矩形 | (x,y) 左上角，w 宽度，h 高度 |
| `OLED_DrawFilledRect(x, y, w, h)` | 实心矩形 | 同上 |
| `OLED_DrawCircle(cx, cy, r)` | 空心圆 (Midpoint) | (cx,cy) 圆心，r 半径 |
| `OLED_DrawFilledCircle(cx, cy, r)` | 实心圆 | 同上 |
| `OLED_DrawBitmap(x, y, bmp, w, h)` | 位图绘制 | (x,y) 左上角 |

**关于 y 坐标：** 所有绘图函数的 (x,y) 使用绝对像素坐标 (0~127, 0~63)。而文本函数的 y 使用 **Page 编号** (0~7)，因为文本天然按 8-pixel 行对齐。

### 8. 功耗与低功耗

| 状态 | 典型电流 | 说明 |
|------|---------|------|
| 正常显示 (全白) | ~20 mA | 128×64 全亮，对比度 0xCF |
| 正常显示 (混合) | ~10 mA | 典型 UI 画面（本项目水平） |
| 睡眠模式 (Display OFF) | ~10 μA | `0xAE` 后关闭面板+振荡器 |
| 电荷泵关闭 | < 1 μA | 切回外部供电模式 |

**低功耗操作：**

```c
OLED_DisplayOff();                        // 发送 0xAE，关闭显示
HAL_I2C_MspDeInit(&hi2c1);               // 关闭 I2C 外设时钟
HAL_GPIO_WritePin(GPIOB, GPIO_PIN_6 | GPIO_PIN_7, GPIO_PIN_RESET);  // SDA/SCL 拉低
// → 此时 OLED 模块功耗降至 < 10μA

// 唤醒：
MX_I2C1_Init();                           // 重新初始化 I2C
OLED_DisplayOn();                         // 发送 0xAF，恢复显示
// GDDRAM 内容在睡眠期间保留，无需重绘
```

> SSD1306 的 Display OFF (`0xAE`) 并不清除 GDDRAM，仅关闭面板驱动。唤醒后立即显示之前的内容，无需重新传输 1024 字节。

## 验证标准

烧录测试程序后，OLED 屏幕显示 "Hello World!" 即通过。

### 常见问题

| 问题 | 检查项 |
|------|--------|
| OLED 不亮 | VCC/GND 接线、3.3V 供电 |
| 有背光无文字 | I2C 地址（0x3C 还是 0x3D）、SCL/SDA 是否接反 |
| 花屏 | 初始化序列顺序错误，对照 SSD1306 数据手册检查 |
| 无任何反应 | 万用表测 SCL/SDA 对 VCC 是否有上拉电阻（~4.7kΩ） |

## 关于中文显示

当前版本**不显示中文**。原因如下：

- STM32F103C8T6 仅有 **64KB Flash**，完整中文字库（GB2312 一级 3755 字，12×12 点阵）约需 90KB，远超 Flash 容量
- 12×12 点阵下汉字笔画复杂，渲染效果较差（一个 12×12 的汉字在 0.96 寸 OLED 上辨识度有限）
- 使用 Python + PIL 从系统字体（SimHei）自动生成字模的方案已测试，但在该分辨率下效果不理想

替代方案：
- **外挂 SPI Flash** 存储完整字库（如 W25Q64，8MB，成本约 2 元），可按需索引任意汉字
- **当前方案**：界面标签全部使用英文，ASCII 6×8 / 8×16 字体显示效果好、无额外存储开销
- 如需少量固定汉字（如菜单标题），可用 `python/gen_font_12x12.py` 脚本单独生成字模添加到 `oled.c`

## CMake 配置失败 / 工具链版本兼容性

初次配置时可能遇到 `cube-cmake` 崩溃（退出码 `3221226505`，对应 `STATUS_STACK_BUFFER_OVERRUN`）。

**原因**：STM32Cube VSCode 插件各组件版本不兼容。项目中使用的工具链版本：

| 组件 | 版本 | 说明 |
|------|------|------|
| STM32Cube IDE Build CMake 插件 | 1.45.0 | VSCode 扩展 |
| cube-cmake (CMake) | 4.2.3+st.1 | ST 定制版 CMake |
| GNU Tools for STM32 (ARM GCC) | 14.3.1+st.2 | 交叉编译工具链 |
| Ninja | 1.13.2+st.1 | 构建生成器 |
| STM32F1xx DFP | 1.2.0 | 固件包 |

**解决方案**：确保 VSCode 中所有 STM32Cube 相关插件均为**最新版本**（通过 VSCode Extensions 面板更新）。ST 的 cmake/工具链/Ninja 三件套由插件统一管理，旧版本之间可能存在 ABI 不兼容导致 `cube-cmake` 在编译器探测阶段崩溃。

如果更新后仍崩溃，可尝试：
1. 删除 `build/` 目录后重新配置
2. 检查 Windows Defender 是否拦截了 `arm-none-eabi-gcc.exe`
3. 改用 `Unix Makefiles` 生成器（`.vscode/settings.json` 中修改 `cmake.preferredGenerators`）
