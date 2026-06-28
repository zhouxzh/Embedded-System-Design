#ifndef __BLUETOOTH_H
#define __BLUETOOTH_H

#include "main.h"
#include "smartwatch_ui.h"
#include <stdint.h>

/* HC-05 frame constants */
#define BT_STX          0xAA
#define BT_ETX          0x55
#define BT_RX_BUF_SIZE  256
#define BT_TX_BUF_SIZE  256

/* HC-05 STATE pin (PB0): HIGH = connected, LOW = disconnected */
#define BT_STATE_PORT   GPIOB
#define BT_STATE_PIN    GPIO_PIN_0

/* Command IDs */
#define BT_CMD_SENSOR_DATA  0x01
#define BT_CMD_TIME_SYNC    0x02
#define BT_CMD_ACK          0x03

/* Time sync data structure */
typedef struct {
    uint8_t  hour;
    uint8_t  minute;
    uint8_t  second;
    uint16_t year;
    uint8_t  month;
    uint8_t  day;
    uint8_t  weekday;
} BT_TimeSync_t;

void BT_Init(void);
void BT_SendSensorData(SmartWatchData_t *data);
uint8_t BT_Process(SmartWatchData_t *data);
uint8_t BT_GetTimeSync(BT_TimeSync_t *ts);
void BT_RxCpltCallback(uint16_t size);
uint8_t BT_IsConnected(void);

#endif /* __BLUETOOTH_H */
