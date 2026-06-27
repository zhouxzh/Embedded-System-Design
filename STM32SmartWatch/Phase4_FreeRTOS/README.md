# Phase 4：FreeRTOS 多任务 + 旋转编码器

## 目标

将 Phase 3 的裸机程序迁移到 FreeRTOS，同时接入旋转编码器（EC11）实现菜单交互。

这是改动最大的一次——引入实时操作系统，将原来的 while(1) 大循环拆分成 5 个独立任务。

## 硬件连接（叠加在 Phase 3 之上）

| EC11 编码器 | STM32F103C8T6 |
|------------|---------------|
| A 相 | PA6 (TIM3_CH1) |
| B 相 | PA7 (TIM3_CH2) |
| SW (按键) | PB10 (EXTI10) |
| VCC | 3.3V |
| GND | GND |

> A/B 相与 GND 之间各接 100nF 电容有助于硬件去抖。TIM3 编码器模式本身具备一定软件去抖能力，但硬件电容更可靠。

## STM32CubeMX 配置

打开 Phase 3 的 `.ioc` 文件，依次完成以下改动。

### 1. 修改 SYS Timebase

**System Core → SYS：**

| 配置项 | 旧值 | 新值 |
|--------|------|------|
| Timebase Source | **SysTick** | **TIM1** |

> 原因：FreeRTOS 会占用 SysTick 作为系统节拍定时器，HAL 库的时基需要移到另一个定时器。TIM1 是最常用的替代。

### 2. 启用 FreeRTOS

**Pinout & Configuration → Middleware → FREERTOS：**

Interface 选择 **CMSIS_V1**。

**Config Parameters 标签页：**

| 配置项 | 值 | 说明 |
|--------|-----|------|
| TOTAL_HEAP_SIZE | **8192** | 8KB 堆 |
| Memory management scheme | **heap_4** | 最佳匹配，支持合并 |
| TICK_RATE_HZ | **1000** | 1ms 节拍 |
| MAX_PRIORITIES | **32** | |
| USE_PREEMPTION | **Enabled** | 抢占式 |
| USE_TIME_SLICING | **Enabled** | 同优先级轮转 |

### 3. 创建任务（Tasks 标签页）

点击 **Add** 依次添加 5 个任务：

| Task Name | Entry Function | Priority | Stack Size (words) |
|-----------|---------------|----------|---------------------|
| taskTimeKeep | vTask_TimeKeep | osPriorityHigh | 256 |
| taskSensor | vTask_Sensor | osPriorityAboveNormal | 512 |
| taskDisplay | vTask_Display | osPriorityNormal | 1024 |
| taskMenu | vTask_Menu | osPriorityNormal | 512 |
| taskBluetooth | vTask_Bluetooth | osPriorityBelowNormal | 512 |

实际 FreeRTOS 内部优先级（configMAX_PRIORITIES=32）：

| 任务 | 优先级 | 理由 |
|------|--------|------|
| taskTimeKeep | 4 | 最高：时间不可延迟 |
| taskSensor | 3 | 高：传感器实时性 |
| taskDisplay | 2 | 中：UI 刷新 |
| taskMenu | 1 | 中低：菜单交互 |
| taskBluetooth | 0 | 低：通信可延后 |

### 4. 创建队列（Queues 标签页）

| Queue Name | Item Size | Number of Items |
|------------|-----------|-----------------|
| queueSensorData | 24 | 4 |
| queueTimeUpdate | 8 | 2 |
| queueMenuMsg | 4 | 4 |
| queueBtCmd | 32 | 4 |

### 5. 创建互斥锁与信号量

**Mutexes 标签页：**

| Name |
|------|
| mutexI2C |

**Semaphores 标签页：**

| Name | Type |
|------|------|
| semDisplayUpdate | **Binary** |

### 6. 配置 TIM2（秒中断计时）

**Pinout & Configuration → Timers → TIM2：**

| 配置项 | 值 |
|--------|-----|
| Prescaler | **7199**（72MHz / 7200 = 10kHz） |
| Counter Period | **9999**（10kHz / 10000 = 1Hz） |
| Auto-reload preload | **Enable** |

> 不需要从 Pinout 分配引脚——TIM2 仅用作内部计时。

**NVIC Settings 标签页：** 勾选 ✅ TIM2 global interrupt，Preemption Priority = **5**。

### 7. 配置 TIM3（编码器模式）

**Pinout & Configuration → Timers → TIM3：**

| 配置项 | 值 |
|--------|-----|
| Combined Channels | **Encoder Mode** |
| Prescaler | **0**（不分频） |
| Counter Period | **65535**（16 位最大值） |

Pinout 自动分配：PA6 = TIM3_CH1，PA7 = TIM3_CH2。

> 不需要使能 TIM3 中断——编码器模式下直接读取 CNT 寄存器即可。

### 8. 配置 EXTI10（编码器按键）

**Pinout View：** 将 **PB10** 设为 **GPIO_EXTI10**。

**GPIO 配置面板：**

| 配置项 | 值 |
|--------|-----|
| GPIO mode | **External Interrupt Mode with Falling edge trigger** |
| GPIO Pull-up/Pull-down | **Pull-up** |

**NVIC 标签页：** 勾选 ✅ EXTI line[15:10] interrupts，Preemption Priority = **7**。

### 9. NVIC 全局优先级总览

进入 **System Core → NVIC → NVIC** 标签页，确认所有优先级：

| 中断源 | Preemption Priority | Sub Priority |
|--------|--------------------|------------|
| SysTick | **15** | 0 |
| TIM2 global | **5** | 0 |
| I2C1 event | **6** | 0 |
| I2C1 error | **6** | 0 |
| USART1 global | **7** | 0 |
| EXTI line[15:10] | **7** | 0 |

> 关键规则：在 ISR 中调用 FreeRTOS API（如 `xQueueSendFromISR`、`xSemaphoreGiveFromISR`）的中断，其抢占优先级必须 **≥ 5**（数值上 ≥ configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY）。SysTick 优先级 15（最低），TIM2=5 可以安全调用。

### 10. GENERATE CODE

点击 **GENERATE CODE**，重新生成工程。

> 生成后，你之前在 `USER CODE BEGIN` / `USER CODE END` 之间的 Phase 1~3 代码应被保留。检查 `ssd1306.c`、`mpu6050.c`、`bluetooth.c` 是否仍在工程中，如被移除则手动重新添加。

## 本阶段 CubeMX 配置汇总

```
Phase 1~3 已有：
  ✅ I2C1     — Fast Mode 400kHz  (PB6/PB7)
  ✅ USART1   — 115200-8-N-1  (PA9/PA10)
  ✅ DMA1     — CH4 TX, CH5 RX Circular
  ✅ SYS      — Serial Wire, TIM1 时基（改）
  ✅ RCC      — HSE 8MHz, 72MHz

Phase 4 新增/修改：
  ✅ SYS      — Timebase 从 SysTick 改为 TIM1（修改）
  ✅ FreeRTOS — CMSIS_V1, heap_4, 8KB, 1kHz
  ✅ Tasks    — 5 个任务
  ✅ Queues   — 4 个队列
  ✅ Mutex    — mutexI2C
  ✅ Semaphore — semDisplayUpdate (Binary)
  ✅ TIM2     — 1s 计时中断, Priority 5
  ✅ TIM3     — Encoder Mode  (PA6/PA7)
  ✅ EXTI10   — 编码器按键中断  (PB10)
  ✅ NVIC     — 全部中断优先级重整
```

## 引脚总览

| 引脚 | 功能 | 说明 |
|------|------|------|
| PA0 | ADC1_IN0 | 电池电压（Phase 5 启用） |
| PA6 | TIM3_CH1 | 编码器 A 相 |
| PA7 | TIM3_CH2 | 编码器 B 相 |
| PA9 | USART1_TX | 蓝牙 TXD |
| PA10 | USART1_RX | 蓝牙 RXD |
| PA13 | SWDIO | 调试接口 |
| PA14 | SWCLK | 调试接口 |
| PB6 | I2C1_SCL | OLED + MPU6050 |
| PB7 | I2C1_SDA | OLED + MPU6050 |
| PB10 | EXTI10 | 编码器按键 |
| PB12 | GPIO_Output | 电源保持（Phase 5 启用） |
| PB13 | GPIO_Output | 空闲（预留） |

## 验证标准

- OLED 每秒更新一次时间
- 旋转编码器可切换页面（时间 ↔ 传感器），短按确认
- 传感器数据实时刷新
- 蓝牙持续发送数据帧（手机 APP 确认）
- 旋转编码器时 OLED 不卡顿（任务调度正常）
- 连续运行 10 分钟无死机、无死锁

### 常见问题

| 问题 | 检查项 |
|------|--------|
| 编译报 SVC 相关错误 | FreeRTOS 中断优先级配置错误，检查 NVIC 表 |
| 某个任务不运行 | 堆栈溢出 → 用 `uxTaskGetStackHighWaterMark` 检查 |
| I2C 数据偶尔出错 | 多任务同时访问 I2C → 确保前后都加了 mutex |
| 编码器旋转无反应 | TIM3 编码器模式是否启用、PA6/PA7 引脚是否正确 |
| 按键触发两次 | 机械抖动 → 增加软件去抖（20ms 后再读取） |
