# SmartWatch Bluetooth Host

PC / 香橙派 / 昇腾 310B 蓝牙上位机，连接 HC-05 接收 STM32 手表传感器数据。

## 文件说明

| 文件 | 用途 |
|------|------|
| `bt_protocol.py` | 帧协议编解码（PC 和 Web 版共用） |
| `bt_host.py` | PC 桌面版上位机（tkinter + matplotlib） |
| `web_host.py` | Web 版上位机（Flask + Chart.js），跑在 Linux 上，PC 浏览器访问 |
| `templates/index.html` | Web 前端界面 |
| `requirements.txt` | Python 依赖 |

---

## 环境搭建（Anaconda）

所有平台统一用 Anaconda 管理 Python 环境。

```bash
# 新建虚拟环境（Python 3.13）
conda create -n stm32 python=3.13 -y

# 激活环境
conda activate stm32

# 安装依赖
pip install -r requirements.txt
```

---

## 方式一：PC 桌面版

### 启动

```bash
conda activate stm32
python bt_host.py
```

使用前需要 Windows 蓝牙配对 HC-05。如果 PC 蓝牙无法配对 HC-05（Intel 网卡通病），改用方式二。

---

## 方式二：Linux Web 版（香橙派 / 昇腾 310B）

### 1. 安装系统依赖

```bash
sudo apt update
sudo apt install -y bluez
```

`web_host.py` 通过 `/dev/rfcomm0` 读写 HC-05。普通用户需要能访问串口设备；一般加入 `dialout` 组即可：

```bash
sudo usermod -aG dialout $USER
newgrp dialout
```

> 如果你当前用户已经在 `dialout` 组里，可以跳过这一步。用 `groups` 查看。

### 2. 蓝牙配对 HC-05

配对前先确认 HC-05 的 `VCC` 接稳定 5 V，不能只接 3.3 V；可从 ST-LINK 的 5V 引脚给 HC-05 供电。供电不足时可能搜不到设备、广播名异常或连接不稳定。

**HC-05 重新上电**（LED 快闪后马上操作，太久会退出可发现状态）。

**第一步：扫描获取 MAC 地址**

```bash
bluetoothctl power on
bluetoothctl --timeout 10 scan on
```

`--timeout 10` 表示 10 秒后自动停止，不需要 `Ctrl+C`。扫描结果中找到 HC-05：

```
[NEW] Device 4B:63:DA:3A:2C:DB HC-05
```

记下 MAC 地址。

**第二步：配对（bluetoothctl 交互模式）**

建议进入交互模式完成扫描、配对和信任。`pair` 必须在当前 `bluetoothctl` 会话已经发现 HC-05 之后执行，否则容易报 `Device not available`。

```bash
bluetoothctl
```

进入 `[bluetooth]#` 提示符后：

```bash
power on
agent on
default-agent
scan on
# 等到出现：[NEW] Device 4B:63:DA:3A:2C:DB HC-05
pair 4B:63:DA:3A:2C:DB       # 弹 PIN 码直接回车（无需密码）
trust 4B:63:DA:3A:2C:DB      # 信任设备，之后自动重连
info 4B:63:DA:3A:2C:DB       # 确认 Paired: yes, Trusted: yes
scan off
exit
```

> 如果提示输入 PIN，优先试 `1234`，不行再试 `0000`；部分 HC-05 模块可以直接回车。

> HC-05 出厂默认名 "HC-05"。如果周围同名设备多，先断电扫一次记下列表，再上电扫一次——**新出现的 MAC 就是你的**。

### 3. 绑定 RFCOMM 串口

HC-05 是经典蓝牙 SPP/RFCOMM 设备，Linux 上最稳的做法是先把它绑定成串口：

```bash
# 如果已经有旧绑定，先释放；没有旧绑定时失败可以忽略
sudo rfcomm release /dev/rfcomm0 2>/dev/null || true

# 绑定 HC-05 到 /dev/rfcomm0，channel 通常是 1
sudo rfcomm bind /dev/rfcomm0 4B:63:DA:3A:2C:DB 1

# 检查绑定状态
rfcomm -a
ls -l /dev/rfcomm0
```

看到类似下面输出就说明绑定成功：

```text
rfcomm0: 4B:63:DA:3A:2C:DB channel 1 closed
crw-rw---- 1 root dialout ... /dev/rfcomm0
```

`closed` 表示当前没有程序打开这个串口，不是失败。启动 Web 上位机后，程序会打开 `/dev/rfcomm0`。

### 4. 启动 Web 上位机

程序使用 `pyserial` 打开 `/dev/rfcomm0`，不需要 `pybluez2`。

```bash
conda activate stm32

# 默认串口是 /dev/rfcomm0，波特率 38400
python web_host.py

# 如果你的绑定设备名不同，可以用环境变量指定
RFCOMM_DEVICE=/dev/rfcomm1 python web_host.py
```

在 PC 浏览器打开 `http://<设备IP>:5000`，点击 **Connect** 开始接收数据。如果自动连接失败，检查 `/dev/rfcomm0` 是否存在、当前用户是否在 `dialout` 组、HC-05 是否上电且没有被手机或其他设备占用。

> 默认绑定 MAC `4B:63:DA:3A:2C:DB`、channel `1`、串口 `/dev/rfcomm0`、波特率 `38400`。可通过 `BT_MAC`、`BT_CHANNEL`、`RFCOMM_DEVICE`、`BT_BAUDRATE` 环境变量覆盖。

---

## 蓝牙排查

```bash
# 查看已配对的设备
bluetoothctl devices

# 查看已连接的设备
bluetoothctl devices Connected

# 查看 rfcomm 绑定
rfcomm -a

# 查看串口权限
ls -l /dev/rfcomm0

# 删除配对（出问题时重来）
bluetoothctl remove 4B:63:DA:3A:2C:DB

# 查看蓝牙状态
bluetoothctl show
```
