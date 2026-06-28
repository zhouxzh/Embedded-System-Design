# Phase0 HC-05 AT 配置工具

本工程用于给 HC-05 蓝牙模块做 AT 模式配置。PC 端不需要 USB 转 TTL，电脑直接连接 STM32F103C8T8 的 USB CDC 虚拟串口；STM32 再通过 `USART2` 把 AT 命令转发给 HC-05。

当前上位机采用 Flask Web 页面，定位是**手动 AT 控制台**：只保留串口连接、日志显示、手动命令输入、`Ping STM32` 和 `AT Test`。不再使用自动 Preset，避免不同 HC-05 固件命令差异导致误配置。

## 1. 硬件接线

| 功能 | STM32F103C8T8 | HC-05 / 外部设备 |
| --- | --- | --- |
| HC-05 RXD | `PA2 USART2_TX` | HC-05 `RXD` |
| HC-05 TXD | `PA3 USART2_RX` | HC-05 `TXD` |
| HC-05 STATE | `PB0 GPIO_Input` | HC-05 `STATE` |
| USB D- | `PA11 USB_DM` | 板载 USB |
| USB D+ | `PA12 USB_DP` | 板载 USB |
| 调试 SWDIO | `PA13` | ST-LINK SWDIO |
| 调试 SWCLK | `PA14` | ST-LINK SWCLK |
| 状态灯 | `PC13 GPIO_Output` | Blue Pill 板载 LED |
| 共地 | `GND` | HC-05 GND / ST-LINK GND |

注意：

- STM32F103 是 3.3 V 逻辑。
- HC-05 模块板的 `VCC` 通常可以接 5 V，但 `RXD/TXD/STATE/KEY` 逻辑脚建议按 3.3 V 使用。
- 必须共地：STM32、HC-05、ST-LINK 的 `GND` 要接在一起。
- STM32 的 USB CDC 虚拟串口只用于上位机通信；下载和调试仍然需要 ST-LINK/SWD。

## 2. HC-05 进入 AT 模式

如果你的 HC-05 模块板上有小按键，推荐使用按键方式：

1. 先断开 HC-05 电源。
2. 按住 HC-05 模块上的小按键不放。
3. 给 HC-05 上电。
4. 上电后松开按键。
5. 观察 LED，完整 AT 模式通常是慢闪，常见为约 2 秒闪一次。

如果使用 `KEY/EN` 引脚：

1. 先把 HC-05 的 `KEY/EN` 接到 `3.3V`。
2. 再给 HC-05 的 `VCC` 上电。
3. 进入 AT 模式后再使用上位机发送命令。

顺序很重要：很多 HC-05 只在上电瞬间检测 `KEY/EN` 是否为高电平。

## 3. STM32CubeMX 配置

### 3.1 基本配置

- MCU：`STM32F103C8Tx`
- Package：`LQFP48`
- Firmware Package：`STM32Cube FW_F1 V1.8.7`
- Toolchain：`CMake`
- `SYS -> Debug`：选择 `Serial Wire`
- 保留：
  - `PA13 = SWDIO`
  - `PA14 = SWCLK`

### 3.2 时钟配置

- HSE：按实际板子选择
  - 常见 Blue Pill 晶振：`Crystal/Ceramic Resonator`
  - 如果是外部时钟输入：`Bypass Clock Source`
- HSE Frequency：`8 MHz`
- PLL Source：`HSE`
- PLL MUL：`x9`
- SYSCLK：`72 MHz`
- HCLK：`72 MHz`
- APB1：`36 MHz`
- APB2：`72 MHz`
- USB Clock：`48 MHz`
- 如果 SYSCLK 为 `72 MHz`，USB prescaler 选择 `/1.5`

USB CDC 对 `48 MHz` USB 时钟比较敏感，这项必须正确。

### 3.3 USB CDC 虚拟串口

- `Connectivity -> USB`
  - Mode：`Device FS`
  - 引脚：
    - `PA11 = USB_DM`
    - `PA12 = USB_DP`
- `Middleware -> USB_DEVICE`
  - Class For FS IP：`Communication Device Class (CDC)`
- NVIC：
  - Enable `USB_LP_CAN1_RX0_IRQn`

电脑会把 STM32 识别成一个虚拟 COM 口，上位机连接的就是这个 COM 口。

### 3.4 HC-05 AT 串口

不要使用 `USART1`。`USART1` 的硬件流控脚会涉及 `PA11/PA12`，而 USB 正好占用 `PA11/PA12`，CubeMX 可能提示 `USART1 partially disabled conflict with USB`。

使用 `USART2`：

- `Connectivity -> USART2`
  - Mode：`Asynchronous`
  - Baud Rate：`38400`
  - Word Length：`8 Bits`
  - Parity：`None`
  - Stop Bits：`1`
  - Hardware Flow Control：`None`
- 引脚：
  - `PA2 = USART2_TX`
  - `PA3 = USART2_RX`
- NVIC：
  - Enable `USART2 global interrupt`
  - Priority：`5`

HC-05 完整 AT 模式常用 `38400 8N1`。如果你的模块不是这个速率，可以在上位机中手动发送 `/baud 9600`、`/baud 38400` 等命令切换 STM32 到 HC-05 侧的串口波特率。

### 3.5 HC-05 STATE 输入

- `PB0`
  - Mode：`GPIO_Input`
  - Pull：`Pull-down`
  - User Label：`HC05_STATE`

如果没有设置 `User Label`，代码中会找不到 `HC05_STATE_Pin` 和 `HC05_STATE_GPIO_Port`。

### 3.6 可选状态灯

- `PC13`
  - Mode：`GPIO_Output`
  - User Label：`LED_STATUS`

Blue Pill 的 PC13 LED 通常是低电平点亮。

## 4. 生成代码后的检查

CubeMX 生成代码后，确认以下内容存在：

`Core/Inc/main.h` 中应有：

```c
#define HC05_STATE_Pin GPIO_PIN_0
#define HC05_STATE_GPIO_Port GPIOB
```

`Core/Src/gpio.c` 中应启用 GPIOB 时钟，并初始化 PB0：

```c
__HAL_RCC_GPIOB_CLK_ENABLE();

GPIO_InitStruct.Pin = HC05_STATE_Pin;
GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
GPIO_InitStruct.Pull = GPIO_PULLDOWN;
HAL_GPIO_Init(HC05_STATE_GPIO_Port, &GPIO_InitStruct);
```

`Core/Src/main.c` 中应初始化：

```c
MX_GPIO_Init();
MX_USART2_UART_Init();
MX_USB_DEVICE_Init();
HC05_AT_Init();
```

主循环中应持续处理桥接逻辑：

```c
while (1)
{
  HC05_AT_Process();
}
```

如果 CMake 报 `usbd_cdc_if.h` 找不到，优先检查 CubeMX 是否启用了：

```text
Middleware -> USB_DEVICE -> Communication Device Class (CDC)
```

## 5. 下载和调试

使用 ST-LINK/SWD 下载，不是使用 USB CDC 下载。

ST-LINK 接线：

| ST-LINK | STM32F103C8T8 |
| --- | --- |
| SWDIO | PA13 |
| SWCLK | PA14 |
| GND | GND |
| 3.3V / VTref | 3.3V |
| NRST | NRST，可选但推荐 |

如果 VS Code 调试失败，先用 STM32CubeProgrammer 测试：

1. Interface 选择 `ST-LINK`。
2. Port 选择 `SWD`。
3. Frequency 先降到 `1000 kHz` 或 `400 kHz`。
4. Reset mode 可尝试 `Connect under reset`。
5. 点击 `Connect`。

CubeProgrammer 能连接成功后，VS Code 调试才有意义。

## 6. 启动 Flask 上位机

安装依赖：

```powershell
cd hc05_at_host
pip install -r requirements.txt
```

启动：

```powershell
python hc05_at_host.py
```

启动后会自动打开浏览器。如果没有自动打开，手动访问：

```text
http://127.0.0.1:5000
```

页面功能：

- 扫描并选择 STM32 USB VCP 对应的 COM 口。
- `Ping STM32`：发送 `/ping`，确认 STM32 固件在线。
- `AT Test`：发送 `AT`，确认 HC-05 AT 通信正常。
- 手动输入框：逐条发送 AT 命令。
- 日志窗口：显示上位机发送、STM32 转发、HC-05 返回的数据。

USB CDC 的物理传输不依赖传统串口波特率。上位机显示的 `115200` 只是 pyserial 打开 COM 口时使用的 line coding。

## 7. 基本联通测试

1. 让 HC-05 进入完整 AT 模式。
2. 烧录并复位 STM32。
3. 用 USB 线连接 STM32 和电脑。
4. 启动 Flask 上位机。
5. 选择 STM32 USB VCP 对应的 COM 口，例如 `COM15`。
6. 点击 `连接`。
7. 点击 `Ping STM32`。

正常应看到类似：

```text
[HOST] /ping
[STM32] pong
[STM32] USART2=38400  USB_CDC=VCP  STATE=LOW
```

8. 点击 `AT Test`。

正常应看到：

```text
[HOST] AT
[STM32->HC05] AT
OK
```

如果只看到 `[STM32->HC05] AT`，没有 `OK`，说明 STM32 到 HC-05 这一侧还没通。重点检查 HC-05 是否进入 AT 模式、TX/RX 是否交叉、GND 是否共地、波特率是否为 38400。

## 8. 手动配置建议流程

建议逐条发送，每条等返回后再发下一条。不要快速连续发送。

### 8.1 确认模块在线

```text
AT
```

期望返回：

```text
OK
```

### 8.2 查询当前信息

```text
AT+VERSION?
AT+NAME?
AT+ROLE?
AT+UART?
```

不同 HC-05 固件返回格式可能不同，这是正常的。

### 8.3 恢复默认值，可选

```text
AT+ORGL
```

如果返回 `OK`，建议等待 3 到 5 秒，再发送：

```text
AT
```

确认仍能返回 `OK` 后，再继续配置。

### 8.4 设置名称

```text
AT+NAME=SmartWatch
```

查询：

```text
AT+NAME?
```

期望看到类似：

```text
+NAME:SMARTWATCH
OK
```

有些固件会把名称自动转成大写。

### 8.5 设置角色

作为从机使用：

```text
AT+ROLE=0
```

查询：

```text
AT+ROLE?
```

期望：

```text
+ROLE:0
OK
```

### 8.6 设置数据模式串口

为了兼容 Phase3，建议把 HC-05 数据模式串口改成 `9600 8N1`：

```text
AT+UART=9600,0,0
```

查询：

```text
AT+UART?
```

期望类似：

```text
+UART:9600,0,0
OK
```

注意：这是 HC-05 退出 AT 模式后的数据模式串口参数，不是当前 AT 模式的 38400。

### 8.7 复位 HC-05

```text
AT+RESET
```

然后：

1. 断开 HC-05 电源。
2. 松开按键，或取消 `KEY/EN` 拉高。
3. 重新给 HC-05 上电。
4. 模块进入数据模式。
5. Phase3 中按 `9600 8N1` 使用。

## 9. 常见问题

### 9.1 `/ping` 有返回，但 `AT` 没有 `OK`

说明 PC 到 STM32 是通的，但 STM32 到 HC-05 不通。检查：

- HC-05 是否真的进入完整 AT 模式。
- `PA2 USART2_TX` 是否接到 HC-05 `RXD`。
- `PA3 USART2_RX` 是否接到 HC-05 `TXD`。
- GND 是否共地。
- HC-05 AT 波特率是否为 `38400`。

可以尝试：

```text
/baud 38400
AT
```

如果仍失败，再尝试：

```text
/baud 9600
AT
```

### 9.2 `AT+ORGL` 后下一条命令失败

`AT+ORGL` 后模块可能需要恢复时间。手动等待 3 到 5 秒，再发送：

```text
AT
```

确认返回 `OK` 后继续下一条。

### 9.3 Windows 11 配对建议

本项目实测的 HC-05 模块在 `AT+ORGL` 重置后，只需要设置名称和从机角色，就可以在 Windows 11 中被发现并配对，不需要执行 `AT+PSWD`。

推荐手动流程：

```text
AT+ORGL
AT+NAME=SmartWatch
AT+ROLE=0
AT+UART=9600,0,0
AT+RESET
```

如果你的模块对 `AT+PSWD=1234` 或 `AT+PSWD="1234"` 返回 `FAIL`，直接跳过密码设置即可。

### 9.4 电脑没有出现 STM32 虚拟 COM 口

检查：

- CubeMX 是否启用了 `USB Device CDC`。
- USB D+/D- 是否是 `PA12/PA11`。
- USB 时钟是否为 `48 MHz`。
- Blue Pill 的 USB 上拉电阻是否正常。
- Windows 设备管理器中是否出现未知 USB 设备。

### 9.5 VS Code 调试失败

优先用 STM32CubeProgrammer 连接 ST-LINK。常见检查项：

- ST-LINK 是否被电脑识别。
- SWDIO/SWCLK/GND 是否接对。
- 目标板是否供电。
- `BOOT0` 是否拉低。
- 尝试 `Connect under reset`。

## 10. 推荐最终配置

推荐最终 HC-05 配置为：

```text
AT+NAME=SmartWatch
AT+ROLE=0
AT+UART=9600,0,0
```

本项目当前不要求修改配对密码。实测流程是：`AT+ORGL` 重置后，设置名称 `SmartWatch`，设置为从机 `ROLE=0`，即可在 Windows 11 中搜索并配对。关键是确认：

- 名称按预期设置。
- 角色为从机 `ROLE=0`。
- 数据模式串口为 `9600,0,0`。
