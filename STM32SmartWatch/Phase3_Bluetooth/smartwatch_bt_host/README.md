# SmartWatch BLE Host

本目录只保留已验证的 Windows BLE 上位机路径，用于连接 hc05V2.3_le 类 BLE 透传模块并接收 STM32 手表传感器数据。

已验证：

- Windows + Bleak
- BLE notify characteristic `0000ffe1`
- STM32 USART2 `38400 8N1`
- 帧格式 `aa 01 18 <24-byte sensor payload> <checksum> 55`

## 文件说明

| 文件 | 用途 |
|---|---|
| `ble_host.py` | Windows BLE 图形上位机 |
| `ble_probe.py` | BLE 扫描和服务探测辅助脚本 |
| `bt_protocol.py` | 帧协议编解码 |
| `requirements.txt` | Python 依赖 |

运行时文件：

| 文件 | 说明 |
|---|---|
| `.ble_last_device.json` | 最近一次连接成功的 BLE 设备缓存 |
| `ble_host.log` | 上位机日志 |

## 安装依赖

```powershell
conda create -n stm32 python=3.13 -y
conda activate stm32
cd smartwatch_bt_host
pip install -r requirements.txt
```

## 启动上位机

```powershell
conda activate stm32
cd smartwatch_bt_host
python ble_host.py
```

基本流程：

1. 蓝牙模块正常数据模式上电。
2. 首次连接时点击 `Scan`。
3. 选中 `SMARTWATCH` 或自己的模块名。
4. 点击 `Connect`。
5. 连接成功后观察 Raw Log。

正常 Raw Log 示例：

```text
rx 0000ffe1 aa 01 18 ... 55
```

其中：

- `aa` 是帧头。
- `01` 是传感器数据命令。
- `18` 表示 24 字节 payload，即 6 个 little-endian `float`。
- 最后 `55` 是帧尾。

## Windows 蓝牙注意事项

### 已配对设备不一定能 Scan 到

Windows 上 BLE 的 `Scan` 依赖广播包。设备一旦配对，或者模块当前不处于广播状态，Bleak 可能扫不到它。这不代表模块坏了。

处理方式：

- 如果下拉框里已有 cached 设备，直接选 cached 设备点 `Connect`。
- 上位机会先尝试短扫描刷新设备对象。
- 如果短扫描仍找不到，Windows 下会继续尝试按已配对设备地址连接。

### cached 设备

连接成功后，上位机会保存：

```text
.ble_last_device.json
```

下次启动时会自动加载为 cached 设备。这个缓存只保存最近一次成功连接的设备名和地址。

如果缓存错了设备，可以关闭程序后删除 `.ble_last_device.json`，再重新 Scan。

### Scan 和 Connect 不要抢占蓝牙适配器

程序在 Connect 前会停止 Scan。手动操作时也建议：

1. 先 `Stop Scan`。
2. 再点 `Connect`。

部分 Windows 蓝牙适配器无法一边扫描一边稳定连接。

### 只保留一个连接

同一时间只让一个客户端连接模块：

- 不要同时开两个 `ble_host.py`。
- 不要让手机蓝牙调试工具占用模块。
- Windows 设置页停留在设备详情页时也可能影响连接。

连接异常时，最稳的恢复顺序：

1. 关闭上位机。
2. 关闭 Windows 设置里的蓝牙设备页面。
3. 蓝牙模块重新上电。
4. 重新启动 `ble_host.py`。
5. 选 cached 设备连接。

### `00002a05` notify 失败可以忽略

日志中可能出现：

```text
notify failed 00002a05-0000-1000-8000-00805f9b34fb: Access Denied
```

这是 BLE Generic Attribute 的 Service Changed 特征，不是数据通道。只要后面出现：

```text
notify on 0000ffe1-0000-1000-8000-00805f9b34fb
```

并且 Raw Log 有 `aa 01 18 ... 55`，数据链路就是正常的。

## BLE 探测脚本

如果需要单独查看设备服务：

```powershell
conda activate stm32
cd smartwatch_bt_host
python ble_probe.py
```

注意：如果设备已经配对但不广播，`ble_probe.py` 也可能扫不到它。此时优先用 `ble_host.py` 的 cached Connect。

## 常见问题

| 现象 | 处理 |
|---|---|
| Scan 找不到设备 | 模块重新上电后马上 Scan；或使用 cached Connect |
| cached Connect 失败 | 确认 Windows 已配对、没有其他程序占用、模块已上电 |
| Raw Log 没有 `aa` | 检查 STM32 PA2/PA3 和模块 RXD/TXD 是否交叉 |
| Raw Log 是 `80 78 f8 ...` | STM32 与模块 UART 波特率不一致，应为 `38400 8N1` |
| 有 `aa 01 18 ... 55` 但 Frames 不动 | 检查是否修改过 `bt_protocol.py` 或帧校验逻辑 |
| 连接后无数据 | 确认固件已烧录新版，OLED 显示 `HC-05 USART2 38400` |
