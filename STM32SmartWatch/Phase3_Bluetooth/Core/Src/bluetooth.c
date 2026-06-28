#include "bluetooth.h"
#include "usart.h"
#include <string.h>
#include <stdio.h>

/* Ring buffer for DMA RX */
static uint8_t rx_buf[BT_RX_BUF_SIZE];
static uint8_t tx_buf[BT_TX_BUF_SIZE];
static uint16_t rx_old_pos = 0;

/* Frame parser state */
static uint8_t frame_buf[BT_RX_BUF_SIZE];
static uint8_t frame_idx = 0;
static uint8_t frame_expected_len = 0;

/* Received time sync data */
static BT_TimeSync_t rx_time_sync;
static volatile uint8_t time_sync_available = 0;

static void BT_ParseByte(uint8_t byte);

void BT_Init(void)
{
    /* Start DMA circular reception */
    HAL_UARTEx_ReceiveToIdle_DMA(&huart2, rx_buf, BT_RX_BUF_SIZE);
    __HAL_DMA_DISABLE_IT(&hdma_usart2_rx, DMA_IT_HT);
}

/* UART RX event callback (IDLE line or half-transfer) */
void HAL_UARTEx_RxEventCallback(UART_HandleTypeDef *huart, uint16_t Size)
{
    if (huart->Instance == USART2 && Size > 0)
    {
        BT_RxCpltCallback(Size);
    }
}

void BT_RxCpltCallback(uint16_t size)
{
    uint16_t new_pos = size;

    if (new_pos > BT_RX_BUF_SIZE)
    {
        new_pos = BT_RX_BUF_SIZE;
    }

    if (new_pos == rx_old_pos)
    {
        return;
    }

    if (new_pos > rx_old_pos)
    {
        for (uint16_t i = rx_old_pos; i < new_pos; i++)
        {
            BT_ParseByte(rx_buf[i]);
        }
    }
    else
    {
        for (uint16_t i = rx_old_pos; i < BT_RX_BUF_SIZE; i++)
        {
            BT_ParseByte(rx_buf[i]);
        }
        for (uint16_t i = 0; i < new_pos; i++)
        {
            BT_ParseByte(rx_buf[i]);
        }
    }

    rx_old_pos = new_pos;
}

static void BT_ParseByte(uint8_t byte)
{
    if (frame_idx == 0)
    {
        if (byte == BT_STX)
        {
            frame_buf[frame_idx++] = byte;
        }
        return;
    }

    if (frame_idx == 1)
    {
        frame_buf[frame_idx++] = byte; /* CMD */
        return;
    }

    if (frame_idx == 2)
    {
        frame_expected_len = byte;
        if (frame_expected_len > (BT_RX_BUF_SIZE - 5))
        {
            frame_idx = 0;
            frame_expected_len = 0;
            return;
        }
        frame_buf[frame_idx++] = byte; /* LEN */
        return;
    }

    if (frame_idx < 3 + frame_expected_len)
    {
        frame_buf[frame_idx++] = byte; /* DATA */
        return;
    }

    if (frame_idx == 3 + frame_expected_len)
    {
        frame_buf[frame_idx++] = byte; /* CHK */
        return;
    }

    if (frame_idx == 4 + frame_expected_len)
    {
        frame_buf[frame_idx] = byte; /* ETX */
        if (byte == BT_ETX)
        {
            uint8_t chk = frame_buf[1] ^ frame_buf[2];
            for (uint8_t j = 0; j < frame_expected_len; j++)
            {
                chk ^= frame_buf[3 + j];
            }
            if (chk == frame_buf[3 + frame_expected_len])
            {
                uint8_t cmd = frame_buf[1];
                if (cmd == BT_CMD_TIME_SYNC && frame_expected_len == 7)
                {
                    rx_time_sync.hour    = frame_buf[3];
                    rx_time_sync.minute  = frame_buf[4];
                    rx_time_sync.second  = frame_buf[5];
                    rx_time_sync.year    = ((uint16_t)frame_buf[6] << 8) | frame_buf[7];
                    rx_time_sync.month   = frame_buf[8];
                    rx_time_sync.day     = frame_buf[9];
                    rx_time_sync.weekday = 0;
                    time_sync_available = 1;
                }
            }
        }
        frame_idx = 0;
        frame_expected_len = 0;
    }
}

/* Send sensor data frame via BT */
void BT_SendSensorData(SmartWatchData_t *data)
{
    /* Build frame: STX + CMD + LEN + DATA + CHK + ETX */
    uint8_t len = 6 * 4; /* 6 floats = 24 bytes */
    tx_buf[0] = BT_STX;
    tx_buf[1] = BT_CMD_SENSOR_DATA;
    tx_buf[2] = len;

    /* Pack sensor data (little-endian float) */
    uint8_t *p = &tx_buf[3];
    memcpy(p, &data->accel.ax, 4); p += 4;
    memcpy(p, &data->accel.ay, 4); p += 4;
    memcpy(p, &data->accel.az, 4); p += 4;
    memcpy(p, &data->gyro.gx,  4); p += 4;
    memcpy(p, &data->gyro.gy,  4); p += 4;
    memcpy(p, &data->gyro.gz,  4); /* p += 4; */

    /* Checksum */
    uint8_t chk = tx_buf[1] ^ tx_buf[2];
    for (uint8_t i = 0; i < len; i++)
    {
        chk ^= tx_buf[3 + i];
    }
    tx_buf[3 + len] = chk;
    tx_buf[4 + len] = BT_ETX;

    /* Send via DMA (non-blocking) */
    HAL_UART_Transmit_DMA(&huart2, tx_buf, 5 + len);
}

/* Check and apply time sync from phone */
uint8_t BT_GetTimeSync(BT_TimeSync_t *ts)
{
    if (time_sync_available)
    {
        memcpy(ts, &rx_time_sync, sizeof(BT_TimeSync_t));
        time_sync_available = 0;
        return 1;
    }
    return 0;
}

uint8_t BT_Process(SmartWatchData_t *data)
{
    BT_TimeSync_t ts;
    if (BT_GetTimeSync(&ts))
    {
        if (data != NULL)
        {
            data->hour = ts.hour;
            data->minute = ts.minute;
            data->second = ts.second;
            data->year = ts.year;
            data->month = ts.month;
            data->day = ts.day;
            data->weekday = ts.weekday;
        }
        return 1;
    }
    return 0;
}

/* Read HC-05 STATE pin: returns 1 if connected, 0 if disconnected */
uint8_t BT_IsConnected(void)
{
    return (HAL_GPIO_ReadPin(BT_STATE_PORT, BT_STATE_PIN) == GPIO_PIN_SET) ? 1 : 0;
}
