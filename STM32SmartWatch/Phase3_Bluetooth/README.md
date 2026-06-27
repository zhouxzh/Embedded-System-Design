# Phase 3：接入 HC-05 蓝牙模块

## 目标

在 Phase 2（OLED + MPU6050 可用）的基础上新增 HC-05 蓝牙模块，通过蓝牙向手机发送传感器数据。

## 硬件连接（叠加在 Phase 2 之上）

蓝牙使用 UART 接口，与 I2C 总线完全独立：

| HC-05 模块 | STM32F103C8T6 |
|-----------|---------------|
| VCC | 3.3V（不要用 5V） |
| GND | GND |
| TXD | PA10 (USART1_RX) |
| RXD | PA9 (USART1_TX) |

> TXD → RX，RXD → TX，交叉连接。

## STM32CubeMX 配置

打开 Phase 2 的 `.ioc` 文件，在原有基础上新增以下配置。

### 新增：USART1

**Pinout View：**
- 将 **PA9** 设为 **USART1_TX**
- 将 **PA10** 设为 **USART1_RX**

**Parameter Settings：**

| 配置项 | 值 |
|--------|-----|
| Baud Rate | **115200** |
| Word Length | **8 Bits** |
| Parity | **None** |
| Stop Bits | **1** |
| Data Direction | **Receive and Transmit** |
| Over Sampling | **16 Samples** |

### 新增：USART1 DMA

进入 USART1 的 **DMA Settings** 标签页，点击 **Add** 添加两条 DMA 通道：

| 通道 | Direction | Mode | 用途 |
|------|-----------|------|------|
| DMA1 Channel 4 | Memory To Peripheral | Normal | TX 发送 |
| DMA1 Channel 5 | Peripheral To Memory | **Circular** | RX 环形接收 |

> RX 用环形模式：DMA 自动循环写入缓冲区，适合不定长的蓝牙数据帧。

### 新增：USART1 中断

进入 **NVIC Settings** 标签页：

| 中断 | 使能 | Preemption Priority |
|------|------|---------------------|
| USART1 global interrupt | ✅ | **5** |

> 注意：Phase 4 引入 FreeRTOS 后优先级可能需要调整，现阶段裸机设为 5 即可。

### GENERATE CODE

点击 **GENERATE CODE** 重新生成。

> 确保你在 `USER CODE BEGIN` / `USER CODE END` 之间的 Phase 1、Phase 2 代码未被覆盖。

## 本阶段 CubeMX 配置汇总

```
Phase 1 已有：
  ✅ I2C1     — Fast Mode 400kHz  (PB6/PB7)
  ✅ SYS      — Serial Wire, SysTick 时基
  ✅ RCC      — HSE 8MHz, 72MHz

Phase 3 新增：
  ✅ USART1   — 115200-8-N-1  (PA9/PA10)
  ✅ DMA1     — CH4 TX / CH5 RX (Circular)
  ✅ NVIC     — USART1 interrupt, Priority 5

尚未启用（Phase 4 加入）：
  ❌ TIM2     — 秒中断计时
  ❌ TIM3     — 编码器模式
  ❌ FreeRTOS — 多任务调度
```

## HC-05 AT 配置（首次使用必须做）

HC-05 默认波特率是 **9600**，需要改为 **115200** 才能与本项目配置匹配。

**方法一（推荐）：用 USB 转串口模块在电脑上配置**

1. HC-05 上电时按住按键 → LED 慢闪（进入 AT 模式）
2. 串口助手发送 `AT\r\n` → 回复 `OK`
3. 发送 `AT+UART=115200,0,0\r\n` → 回复 `OK`
4. 发送 `AT+NAME=SmartWatch\r\n` → 回复 `OK`
5. 重新上电（不按按键）→ 退出 AT 模式

**方法二：用 STM32 代码配置**

在 main 函数初始化阶段发送 AT 指令（代码需先以 9600 波特率与 HC-05 通信，配置完成后再切换为 115200）。

## 自定义数据帧格式

```
[STX] [CMD] [LEN] [DATA...] [CHK] [ETX]
 0xAA  1B    1B    N 字节    1B    0x55

CHK = CMD ^ LEN ^ DATA[0] ^ ... ^ DATA[N-1]
```

## 验证标准

- 手机蓝牙搜索到 HC-05（设备名 "SmartWatch" 或 "HC-05"）
- 手机蓝牙串口 APP 连接后持续收到传感器数据帧
- OLED 显示不受蓝牙影响（Phase 2 功能保持正常）
- 手机发送时间同步指令，STM32 能正确解析并响应

### 常见问题

| 问题 | 检查项 |
|------|--------|
| 搜索不到蓝牙 | HC-05 供电是否 3.3V、LED 是否闪烁 |
| 连上后无数据 | TX/RX 是否交叉连接、波特率是否 115200 |
| 数据乱码 | 波特率不匹配（HC-05 可能仍是 9600） |
| OLED 刷新变慢 | USART 中断优先级是否过高阻塞了主循环 |
