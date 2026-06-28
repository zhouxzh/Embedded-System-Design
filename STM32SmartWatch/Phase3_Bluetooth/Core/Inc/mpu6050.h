#ifndef __MPU6050_H
#define __MPU6050_H

#include "main.h"

/* MPU6050 I2C2 address (7-bit: 0x68 when AD0 = GND) */
#define MPU6050_ADDR            0x68

/* ==================== Register Map ==================== */
#define MPU6050_REG_WHO_AM_I    0x75
#define MPU6050_REG_PWR_MGMT_1  0x6B
#define MPU6050_REG_SMPLRT_DIV  0x19
#define MPU6050_REG_CONFIG      0x1A
#define MPU6050_REG_GYRO_CONFIG 0x1B
#define MPU6050_REG_ACCEL_CONFIG 0x1C
#define MPU6050_REG_ACCEL_XOUT_H 0x3B
#define MPU6050_REG_ACCEL_YOUT_H 0x3D
#define MPU6050_REG_ACCEL_ZOUT_H 0x3F
#define MPU6050_REG_TEMP_OUT_H  0x41
#define MPU6050_REG_GYRO_XOUT_H 0x43
#define MPU6050_REG_GYRO_YOUT_H 0x45
#define MPU6050_REG_GYRO_ZOUT_H 0x47

/* ==================== Data Structures ==================== */

typedef struct {
    float ax;       /* m/s^2 */
    float ay;
    float az;
} MPU6050_Accel_t;

typedef struct {
    float gx;       /* deg/s */
    float gy;
    float gz;
} MPU6050_Gyro_t;

typedef struct {
    float pitch;    /* degrees */
    float roll;
} MPU6050_Angle_t;

/* ==================== API ==================== */

/* Initialize MPU6050, returns 0 on success (WHO_AM_I check) */
int MPU6050_Init(void);

/* Check if MPU6050 is still connected (returns 0 on success) */
int MPU6050_CheckConnection(void);

/* Read raw accelerometer data (converted to m/s^2), returns 0 on success */
int MPU6050_ReadAccel(MPU6050_Accel_t *accel);

/* Read raw gyroscope data (converted to deg/s), returns 0 on success */
int MPU6050_ReadGyro(MPU6050_Gyro_t *gyro);

/* Read temperature in Celsius */
float MPU6050_ReadTemp(void);

/* Calculate pitch and roll from accelerometer data */
void MPU6050_CalcAngle(MPU6050_Accel_t *accel, MPU6050_Angle_t *angle);

/* Read WHO_AM_I register */
uint8_t MPU6050_WhoAmI(void);

/* Last I2C communication error flag (read to clear) */
extern uint8_t g_mpu6050_i2c_error;

#endif /* __MPU6050_H */
