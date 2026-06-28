# Phase 3: HC-05 BLE 数据链路

本阶段在 Phase 2（OLED + MPU6050 可用）的基础上接入蓝牙透传模块。当前只维护已验证路径：

- STM32F103C8T6 `USART2` -> hc05V2.3_le 类 BLE 透传模块
- Windows BLE 上位机 `smartwatch_bt_host/ble_host.py`
- BLE notify 特征 `0000ffe1`
- UART 参数 `38400 8N1`

## 接线速查

| STM32F103C8T6 | 蓝牙模块 | 说明 |
|---|---|---|
| `5V` | `VCC` | 建议接稳定 5 V，可从 ST-LINK 5V 取电 |
| `GND` | `GND` | 必须共地 |
| `PA2` (`USART2_TX`) | `RXD` | 交叉连接：STM32 发送到模块接收 |
| `PA3` (`USART2_RX`) | `TXD` | 交叉连接：模块发送到 STM32 接收 |
| `PB0` (`GPIO_Input`) | `STATE` | 连接状态检测，高电平表示已连接 |
| 不接 | `KEY/EN` | 正常数据模式不接；AT 配置见 Phase0 |

注意事项：

- `TXD/RXD` 必须交叉，不要 TX 对 TX。
- `VCC` 不建议只接 3.3 V；供电不足会导致搜不到、连接不稳定或数据异常。
- 模块数据模式 UART 必须配置成 `38400 8N1`，与固件一致。
- 如果收到 `80 78 f8 78 00 00 ...` 这类数据，而不是 `aa 01 18 ... 55`，通常是模块 UART 和 STM32 UART 波特率不一致。

## CubeMX 配置

工程当前配置为 `USART2 + DMA + PB0 STATE`。

### USART2

| 配置项 | 值 |
|---|---|
| Pins | `PA2 USART2_TX`, `PA3 USART2_RX` |
| Mode | `Asynchronous` |
| Baud Rate | `38400` |
| Word Length | `8 Bits` |
| Parity | `None` |
| Stop Bits | `1` |
| Hardware Flow Control | `Disable` |
| Over Sampling | `16 Samples` |

### USART2 DMA

| 通道 | Request | Direction | Mode | 用途 |
|---|---|---|---|---|
| `DMA1 Channel 7` | `USART2_TX` | Memory To Peripheral | Normal | 蓝牙发送 |
| `DMA1 Channel 6` | `USART2_RX` | Peripheral To Memory | Circular | 蓝牙接收 |

### PB0 STATE

| 配置项 | 值 |
|---|---|
| GPIO Mode | `Input mode` |
| GPIO Pull-up/Pull-down | `Pull-down` |

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

传感器帧长度固定为 29 字节：

```text
aa 01 18 <24-byte payload> <checksum> 55
```

## Windows BLE 上位机

上位机在 [smartwatch_bt_host](smartwatch_bt_host/) 目录中。

```powershell
conda create -n stm32 python=3.13 -y
conda activate stm32
cd smartwatch_bt_host
pip install -r requirements.txt
python ble_host.py
```

使用流程：

1. 让蓝牙模块正常数据模式上电。
2. 首次使用时点击 `Scan`，选中 `SMARTWATCH` 或自己的模块名。
3. 点击 `Connect`。
4. 连接成功后，右侧 BLE Services 中应看到 `0000ffe1` notify。
5. Raw Log 中应出现 `aa 01 18 ... 55`。
6. `Frames` 持续增长，说明 STM32 -> BLE -> PC 数据链路正常。

Windows 连接注意事项：

- 已配对的 BLE 设备不一定能再次被 `Scan` 扫到，这是 Windows/Bleak 的常见现象，不代表模块坏了。
- 上位机会缓存最近一次连接成功的设备到 `.ble_last_device.json`；重新打开程序后可以直接选择 cached 设备点 `Connect`。
- cached 连接时，如果设备不再广播，程序会尝试按 Windows 已配对设备地址连接。
- 如果连接失败，先关闭上位机，关闭 Windows 设置里的蓝牙页面，再给模块重新上电后重试。
- 同一时间只保留一个客户端连接模块；手机、系统设置页或旧的上位机进程占用连接时，新程序可能连不上。
- `notify failed 00002a05 ... Access Denied` 可以忽略；真正的数据通道是 `0000ffe1`。

## 验证标准

- OLED 蓝牙页显示 `HC-05 USART2 38400`。
- 上位机 Raw Log 出现 `aa 01 18 ... 55`。
- 上位机 `Frames` 持续增长。
- 姿态/加速度/陀螺仪数值持续刷新。
- OLED 和 MPU6050 功能不受蓝牙发送影响。

## 常见问题

| 问题 | 检查项 |
|---|---|
| Scan 找不到设备 | 已配对设备可能不广播；使用 cached Connect，或模块重新上电后马上 Scan |
| cached Connect 失败 | 确认 Windows 已配对该设备、没有其他程序占用、模块重新上电 |
| Raw Log 没有 `aa` | 检查 `PA2 -> RXD`、`PA3 <- TXD` 是否交叉 |
| Raw Log 是 `80 78 f8 ...` | STM32 和模块 UART 波特率不一致，确认都是 `38400 8N1` |
| Frames 不增长但有 rx | 检查是否为 `aa 01 18 ... 55` 完整帧，或查看 checksum/帧尾 |
| OLED 不显示 BT | 检查 `STATE -> PB0`，以及 PB0 下拉输入配置 |
| 重新 Generate Code 后配置丢失 | 确认 `.ioc` 中仍为 `USART2`、`PA2/PA3`、`PB0`、`DMA1 Channel6/7`、`38400` |
