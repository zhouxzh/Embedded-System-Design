#include "mpu6050.h"
#include "i2c.h"
#include <math.h>

/* Accelerometer scale: ±2g, LSB sensitivity = 16384 LSB/g */
#define ACCEL_SCALE_FACTOR      (9.81f / 16384.0f)

/* Gyroscope scale: ±250 deg/s, LSB sensitivity = 131 LSB/(deg/s) */
#define GYRO_SCALE_FACTOR       (1.0f / 131.0f)

/* Temperature formula: Temp_C = (raw / 340.0) + 36.53 */
#define TEMP_SCALE_FACTOR       (1.0f / 340.0f)
#define TEMP_OFFSET             36.53f

/* Global I2C error flag: set by read/write helpers when HAL fails */
uint8_t g_mpu6050_i2c_error = 0;

/* ==================== Low-Level I2C Helpers ==================== */

static int MPU6050_WriteReg(uint8_t reg, uint8_t data) {
    HAL_StatusTypeDef status = HAL_I2C_Mem_Write(&hi2c2, MPU6050_ADDR << 1, reg,
                                                  I2C_MEMADD_SIZE_8BIT, &data, 1, 100);
    if (status != HAL_OK) {
        g_mpu6050_i2c_error = 1;
        return -1;
    }
    return 0;
}

static int MPU6050_ReadRegs(uint8_t reg, uint8_t *data, uint8_t len) {
    HAL_StatusTypeDef status = HAL_I2C_Mem_Read(&hi2c2, MPU6050_ADDR << 1, reg,
                                                 I2C_MEMADD_SIZE_8BIT, data, len, 100);
    if (status != HAL_OK) {
        g_mpu6050_i2c_error = 1;
        return -1;
    }
    return 0;
}

/* ==================== Init ==================== */

int MPU6050_Init(void) {
    g_mpu6050_i2c_error = 0;

    uint8_t whoami = MPU6050_WhoAmI();
    if (whoami != 0x68) {
        return -1;  /* Device not found or wrong address */
    }

    /* Wake up MPU6050 (clear sleep bit) */
    if (MPU6050_WriteReg(MPU6050_REG_PWR_MGMT_1, 0x00) != 0) return -1;
    HAL_Delay(10);

    /* Sample rate divider: 4 → 1kHz / (1+4) = 200Hz */
    if (MPU6050_WriteReg(MPU6050_REG_SMPLRT_DIV, 0x04) != 0) return -1;

    /* DLPF: bandwidth 42Hz (bits 0-2 = 0x03) */
    if (MPU6050_WriteReg(MPU6050_REG_CONFIG, 0x03) != 0) return -1;

    /* Gyro range: ±250 deg/s (bits 3-4 = 0x00) */
    if (MPU6050_WriteReg(MPU6050_REG_GYRO_CONFIG, 0x00) != 0) return -1;

    /* Accel range: ±2g (bits 3-4 = 0x00) */
    if (MPU6050_WriteReg(MPU6050_REG_ACCEL_CONFIG, 0x00) != 0) return -1;

    return 0;
}

/* ==================== Connection Check ==================== */

int MPU6050_CheckConnection(void) {
    uint8_t whoami = MPU6050_WhoAmI();
    if (whoami != 0x68) {
        return -1;
    }
    return 0;
}

/* ==================== WHO_AM_I ==================== */

uint8_t MPU6050_WhoAmI(void) {
    uint8_t data = 0;
    if (MPU6050_ReadRegs(MPU6050_REG_WHO_AM_I, &data, 1) != 0) {
        return 0x00;  /* I2C error → return invalid value */
    }
    return data;
}

/* ==================== Sensor Read ==================== */

int MPU6050_ReadAccel(MPU6050_Accel_t *accel) {
    uint8_t raw[6];
    if (MPU6050_ReadRegs(MPU6050_REG_ACCEL_XOUT_H, raw, 6) != 0) {
        return -1;
    }

    int16_t ax_raw = (int16_t)((raw[0] << 8) | raw[1]);
    int16_t ay_raw = (int16_t)((raw[2] << 8) | raw[3]);
    int16_t az_raw = (int16_t)((raw[4] << 8) | raw[5]);

    accel->ax = ax_raw * ACCEL_SCALE_FACTOR;
    accel->ay = ay_raw * ACCEL_SCALE_FACTOR;
    accel->az = az_raw * ACCEL_SCALE_FACTOR;
    return 0;
}

int MPU6050_ReadGyro(MPU6050_Gyro_t *gyro) {
    uint8_t raw[6];
    if (MPU6050_ReadRegs(MPU6050_REG_GYRO_XOUT_H, raw, 6) != 0) {
        return -1;
    }

    int16_t gx_raw = (int16_t)((raw[0] << 8) | raw[1]);
    int16_t gy_raw = (int16_t)((raw[2] << 8) | raw[3]);
    int16_t gz_raw = (int16_t)((raw[4] << 8) | raw[5]);

    gyro->gx = gx_raw * GYRO_SCALE_FACTOR;
    gyro->gy = gy_raw * GYRO_SCALE_FACTOR;
    gyro->gz = gz_raw * GYRO_SCALE_FACTOR;
    return 0;
}

float MPU6050_ReadTemp(void) {
    uint8_t raw[2];
    if (MPU6050_ReadRegs(MPU6050_REG_TEMP_OUT_H, raw, 2) != 0) {
        return -273.0f;  /* I2C error sentinel */
    }

    int16_t temp_raw = (int16_t)((raw[0] << 8) | raw[1]);
    return (float)temp_raw * TEMP_SCALE_FACTOR + TEMP_OFFSET;
}

/* ==================== Angle Calculation ==================== */

void MPU6050_CalcAngle(MPU6050_Accel_t *accel, MPU6050_Angle_t *angle) {
    angle->pitch = atan2f(accel->ay, sqrtf(accel->ax * accel->ax + accel->az * accel->az)) * 57.29578f;
    angle->roll  = atan2f(-accel->ax, accel->az) * 57.29578f;
}
