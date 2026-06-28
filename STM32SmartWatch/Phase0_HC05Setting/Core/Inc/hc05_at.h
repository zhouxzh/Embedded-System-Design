#ifndef __HC05_AT_H
#define __HC05_AT_H

#ifdef __cplusplus
extern "C" {
#endif

#include "main.h"
#include <stdint.h>

#define HC05_AT_PC_BAUD_DEFAULT     115200U
#define HC05_AT_MODULE_BAUD_DEFAULT 38400U

void HC05_AT_Init(void);
void HC05_AT_Process(void);
void HC05_AT_OnPcRxByte(uint8_t byte);
void HC05_AT_OnModuleRxByte(uint8_t byte);
uint32_t HC05_AT_GetModuleBaud(void);

#ifdef __cplusplus
}
#endif

#endif /* __HC05_AT_H */
