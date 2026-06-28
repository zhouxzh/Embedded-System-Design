# Phase 3：接入 HC-05 蓝牙模块

## 目标

在 Phase 2（OLED + MPU6050 可用）的基础上新增 HC-05 蓝牙数据链路。STM32 通过 `USART2` 向 HC-05 发送传感器数据，上位机通过蓝牙串口接收并显示曲线。

HC-05 的 AT 模式、改名、从机模式、数据模式波特率等配置统一参考 [Phase0_HC05Setting/README.md](../Phase0_HC05Setting/README.md)，本阶段不重复编写 AT 配置流程。

## 接线速查

| STM32F103C8T6 | HC-05 | 说明 |
|---|---|---|
| `5V` | `VCC` | HC-05 模块供电建议接 5 V，可从 ST-LINK 的 5V 引脚取电 |
| `GND` | `GND` | 必须共地 |
| `PA2` (`USART2_TX`) | `RXD` | 交叉连接：STM32 发送 -> HC-05 接收 |
| `PA3` (`USART2_RX`) | `TXD` | 交叉连接：HC-05 发送 -> STM32 接收 |
| `PB0` (`GPIO_Input`) | `STATE` | 连接状态检测，高电平表示已连接 |
| 不接 | `KEY/EN` | Phase3 正常数据模式不接；AT 配置见 Phase0 |

连接要点：

- HC-05 的 `TXD/RXD/STATE` 逻辑电平按 3.3 V 使用，可直接接 STM32F103。
- HC-05 的 `VCC` 需要稳定 5 V 供电；如果只接 3.3 V，可能会出现搜不到、广播名异常或连接不稳定。
- `TXD/RXD` 必须交叉连接，不要 TX 对 TX。
- `STATE` 接 `PB0`，固件实时读取该引脚，并在 OLED 状态栏和蓝牙页面显示连接状态。
- Phase3 固件默认串口为 `38400 8N1`，请确保 Phase0 中配置后的 HC-05 数据模式串口参数与此一致。

## STM32CubeMX 配置

在 Phase 2 的 `.ioc` 基础上新增以下配置。本工程当前已经按此配置修改为 `USART2 + PA2/PA3 + PB0`。

### USART2

Pinout View：

| 引脚 | 配置 |
|---|---|
| `PA2` | `USART2_TX` |
| `PA3` | `USART2_RX` |

Parameter Settings：

| 配置项 | 值 |
|---|---|
| Mode | `Asynchronous` |
| Baud Rate | `38400` |
| Word Length | `8 Bits` |
| Parity | `None` |
| Stop Bits | `1` |
| Hardware Flow Control | `Disable` |
| Over Sampling | `16 Samples` |

### USART2 DMA

在 `USART2 -> DMA Settings` 中添加两条 DMA：

| 通道 | Request | Direction | Mode | 用途 |
|---|---|---|---|---|
| `DMA1 Channel 7` | `USART2_TX` | Memory To Peripheral | Normal | 蓝牙发送 |
| `DMA1 Channel 6` | `USART2_RX` | Peripheral To Memory | Circular | 蓝牙接收 |

RX 使用环形模式，适合不定长蓝牙数据帧。

### PB0 STATE 输入

在 Pinout View 中将 `PB0` 设为 `GPIO_Input`：

| 配置项 | 值 |
|---|---|
| GPIO Mode | `Input mode` |
| GPIO Pull-up/Pull-down | `Pull-down` |

### NVIC

| 中断 | 使能 | Preemption Priority |
|---|---|---|
| `USART2 global interrupt` | Enable | `5` |
| `DMA1 Channel6 global interrupt` | Enable | `0` |
| `DMA1 Channel7 global interrupt` | Enable | `0` |

Phase 4 引入 FreeRTOS 后可能需要重新整理中断优先级；Phase 3 裸机阶段保持当前配置即可。

## 本阶段外设总览

| 外设 | 引脚 | 功能 |
|---|---|---|
| `I2C1` | `PB6` SCL, `PB7` SDA | OLED SSD1306 `0x3C` |
| `I2C2` | `PB10` SCL, `PB11` SDA | MPU6050 `0x68` |
| `USART2` | `PA2` TX, `PA3` RX | HC-05 蓝牙串口 `38400 8N1` |
| `GPIO` | `PB0` Input Pull-down | HC-05 `STATE` |
| `SWD` | `PA13` SWDIO, `PA14` SWCLK | 下载和调试 |

## 数据帧格式

STM32 和上位机使用同一套二进制帧协议：

```text
[STX] [CMD] [LEN] [DATA...] [CHK] [ETX]
 0xAA  1B    1B    N bytes   1B    0x55

CHK = CMD ^ LEN ^ DATA[0] ^ ... ^ DATA[N-1]
```

命令：

| CMD | 方向 | DATA |
|---|---|---|
| `0x01` | STM32 -> 上位机 | 6 个 little-endian `float`：`ax ay az gx gy gz` |
| `0x02` | 上位机 -> STM32 | 7 字节时间：`hour min sec year_H year_L month day` |
| `0x03` | 预留 | ACK |

## 上位机

`smartwatch_bt_host/` 中提供两个上位机：

| 文件 | 场景 |
|---|---|
| `ble_host.py` | `hc05V2.3_le` 这类 BLE 模块，Windows 不生成虚拟 COM 口时使用 |
| `bt_host.py` | 传统经典蓝牙 HC-05/HC-06，Windows 能生成虚拟 COM 口时使用 |
| `web_host.py` | PC 蓝牙兼容性不好时，用 Linux/香橙派通过 BlueZ + RFCOMM 中转 |

### 安装依赖

```powershell
conda create -n stm32 python=3.13 -y
conda activate stm32
cd smartwatch_bt_host
pip install -r requirements.txt
```

### Windows BLE 上位机（适合 hc05V2.3_le）

如果 AT 日志中看到类似 `+VERSION:hc05V2.3_le`、`+PSWD:NO KEY OK`，说明模块更像 BLE 透传模块，不是传统 SPP 串口 HC-05。此时 Windows 通常不会生成 `COMx`，请使用 BLE 上位机：

```powershell
conda activate stm32
cd smartwatch_bt_host
python ble_host.py
```

使用流程：

1. 让 HC-05 正常数据模式上电。
2. 点击 `Scan` 开始持续扫描，设备列表会实时刷新，等待列表中出现 `SMARTWATCH`。
3. 扫描会一直进行，直到点击 `Stop Scan`。
4. 选择 `SMARTWATCH` 后点击 `Connect`。
5. 连接成功后右侧会显示 BLE Service/Characteristic。
6. 如果模块的 BLE 透传特征支持 notify，上位机会自动接收数据，并按现有 `0xAA ... 0x55` 帧协议解析。

BLE 上位机会把最近一次连接成功的设备保存到 `smartwatch_bt_host/.ble_last_device.json`。以后重新打开程序时，下拉框会自动出现 cached 设备，通常可直接点 `Connect`，不必重新扫描；如果连接失败，再点 `Scan` 刷新一次即可。

如果能连接但 `Frames` 不增长，查看 `Raw Log` 和 `BLE Services`，需要根据实际可通知/可写特征继续适配。

### Windows 经典蓝牙串口上位机

```powershell
conda activate stm32
cd smartwatch_bt_host
python bt_host.py
```

使用流程：

1. Windows 设置中先与 HC-05 配对。
2. 系统一般会生成两个虚拟 COM 口，一个传入、一个传出。
3. 在上位机中选择 HC-05 对应 COM 口并点击 `Connect`。
4. 如果 `Frames` 增长、曲线滚动，说明选对了端口；如果一直为 0，换另一个 COM 口。
5. 需要同步时间时点击 `Send PC Time to Watch`。

### 香橙派 / Linux Web 上位机

详细配对、绑定和排查步骤见 [smartwatch_bt_host/README.md](smartwatch_bt_host/README.md)。

简要启动：

```bash
cd smartwatch_bt_host
python web_host.py
```

浏览器打开：

```text
http://<设备IP>:5000
```

常用环境变量：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `BT_DEVICE` | `/dev/rfcomm0` | 蓝牙串口设备 |
| `BT_BAUDRATE` | `38400` | 串口波特率 |
| `WEB_PORT` | `5000` | Web 服务端口 |

## 验证标准

- 手机或 PC 能搜索并连接自己的 HC-05 设备。
- HC-05 连接后 `STATE` 输出高电平，OLED 状态栏显示 `BT`。
- OLED 蓝牙页面显示 `CONNECTED`。
- 上位机连接后 `Frames` 持续增长，曲线和数值刷新。
- OLED 和 MPU6050 功能不受蓝牙发送影响。

## 常见问题

| 问题 | 检查项 |
|---|---|
| 搜不到 HC-05 | 优先检查 HC-05 `VCC` 是否接 5 V（可从 ST-LINK 取 5V），再检查 LED 状态和是否处于正常数据模式 |
| 搜到多个同名设备 | 先用 Phase0 给模块改唯一名称，或只保留自己的模块上电配对 |
| 连上后无数据 | 检查 `PA2 -> RXD`、`PA3 <- TXD` 是否交叉，检查 HC-05 数据模式是否为 `38400 8N1` |
| OLED 不显示 BT | 检查 `STATE -> PB0`，以及 PB0 是否下拉输入 |
| 数据乱码 | HC-05 数据模式串口参数与固件不一致，回到 Phase0 检查配置 |
| 重新 Generate Code 后配置丢失 | 确认 `.ioc` 中仍为 `USART2`、`PA2/PA3`、`PB0`、`DMA1 Channel6/7` |
