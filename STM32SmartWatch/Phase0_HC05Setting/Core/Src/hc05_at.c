#include "hc05_at.h"
#include "usart.h"
#include "usbd_cdc_if.h"
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

#define PC_LINE_BUF_SIZE       96U
#define MODULE_RESPONSE_SIZE   192U
#define UART_RX_QUEUE_SIZE     256U
#define PRESET_TIMEOUT_MS      1500U
#define MODULE_TX_TIMEOUT_MS   100U
#define USB_TX_BUSY_RETRY      20U

typedef struct
{
  volatile uint16_t head;
  volatile uint16_t tail;
  uint8_t data[UART_RX_QUEUE_SIZE];
} ByteQueue_t;

static volatile uint8_t module_rx_byte;
static ByteQueue_t pc_queue;
static ByteQueue_t module_queue;
static char pc_line[PC_LINE_BUF_SIZE];
static uint16_t pc_line_len;
static char module_response[MODULE_RESPONSE_SIZE];
static uint16_t module_response_len;
static uint32_t module_baud = HC05_AT_MODULE_BAUD_DEFAULT;

static void queue_push(ByteQueue_t *queue, uint8_t byte);
static bool queue_pop(ByteQueue_t *queue, uint8_t *byte);
static void pc_write(const char *text);
static void pc_write_bytes(const uint8_t *data, uint16_t len);
static void module_write_line(const char *line);
static void process_pc_byte(uint8_t byte);
static void process_module_byte(uint8_t byte);
static void handle_pc_line(char *line);
static void trim_line(char *line);
static void send_help(void);
static void send_status(void);
static void set_module_baud(uint32_t baud);
static void run_preset(void);
static bool send_preset_command(const char *cmd);
static bool response_has_ok(void);
static bool is_supported_baud(uint32_t baud);
static void drain_module_queue(void);

void HC05_AT_Init(void)
{
  module_rx_byte = 0;
  pc_queue.head = pc_queue.tail = 0;
  module_queue.head = module_queue.tail = 0;
  pc_line_len = 0;
  module_response_len = 0;

  HAL_UART_Receive_IT(&huart2, (uint8_t *)&module_rx_byte, 1);
  pc_write("\r\n[STM32] Phase0 HC-05 AT bridge ready\r\n");
  send_status();
  pc_write("[STM32] Type AT, /preset, /baud 38400, /ping, or /help\r\n");
}

void HC05_AT_Process(void)
{
  uint8_t byte;

  while (queue_pop(&pc_queue, &byte))
  {
    process_pc_byte(byte);
  }

  while (queue_pop(&module_queue, &byte))
  {
    process_module_byte(byte);
  }
}

void HC05_AT_OnPcRxByte(uint8_t byte)
{
  queue_push(&pc_queue, byte);
}

void HC05_AT_OnModuleRxByte(uint8_t byte)
{
  queue_push(&module_queue, byte);
}

uint32_t HC05_AT_GetModuleBaud(void)
{
  return module_baud;
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
  if (huart->Instance == USART2)
  {
    HC05_AT_OnModuleRxByte(module_rx_byte);
    HAL_UART_Receive_IT(&huart2, (uint8_t *)&module_rx_byte, 1);
  }
}

void HAL_UART_ErrorCallback(UART_HandleTypeDef *huart)
{
  if (huart->Instance == USART2)
  {
    __HAL_UART_CLEAR_PEFLAG(&huart2);
    __HAL_UART_CLEAR_FEFLAG(&huart2);
    __HAL_UART_CLEAR_NEFLAG(&huart2);
    __HAL_UART_CLEAR_OREFLAG(&huart2);
    HAL_UART_Receive_IT(&huart2, (uint8_t *)&module_rx_byte, 1);
  }
}

static void queue_push(ByteQueue_t *queue, uint8_t byte)
{
  uint16_t next = (uint16_t)((queue->head + 1U) % UART_RX_QUEUE_SIZE);
  if (next != queue->tail)
  {
    queue->data[queue->head] = byte;
    queue->head = next;
  }
}

static bool queue_pop(ByteQueue_t *queue, uint8_t *byte)
{
  if (queue->tail == queue->head)
  {
    return false;
  }

  *byte = queue->data[queue->tail];
  queue->tail = (uint16_t)((queue->tail + 1U) % UART_RX_QUEUE_SIZE);
  return true;
}

static void pc_write(const char *text)
{
  pc_write_bytes((const uint8_t *)text, (uint16_t)strlen(text));
}

static void pc_write_bytes(const uint8_t *data, uint16_t len)
{
  static uint8_t tx_buf[64];
  uint16_t offset = 0;

  while (offset < len)
  {
    uint16_t chunk = (uint16_t)(len - offset);
    bool sent = false;

    if (chunk > sizeof(tx_buf))
    {
      chunk = sizeof(tx_buf);
    }

    memcpy(tx_buf, &data[offset], chunk);

    for (uint8_t retry = 0; retry < USB_TX_BUSY_RETRY; retry++)
    {
      if (CDC_Transmit_FS(tx_buf, chunk) == USBD_OK)
      {
        sent = true;
        break;
      }
      HAL_Delay(1);
    }

    if (!sent)
    {
      return;
    }

    offset = (uint16_t)(offset + chunk);
  }
}

static void module_write_line(const char *line)
{
  HAL_UART_Transmit(&huart2, (uint8_t *)line, (uint16_t)strlen(line), MODULE_TX_TIMEOUT_MS);
  HAL_UART_Transmit(&huart2, (uint8_t *)"\r\n", 2, MODULE_TX_TIMEOUT_MS);
}

static void process_pc_byte(uint8_t byte)
{
  if (byte == '\r' || byte == '\n')
  {
    if (pc_line_len > 0U)
    {
      pc_line[pc_line_len] = '\0';
      handle_pc_line(pc_line);
      pc_line_len = 0;
    }
    return;
  }

  if (pc_line_len < (PC_LINE_BUF_SIZE - 1U))
  {
    pc_line[pc_line_len++] = (char)byte;
  }
  else
  {
    pc_line_len = 0;
    pc_write("[STM32] ERR line too long\r\n");
  }
}

static void process_module_byte(uint8_t byte)
{
  pc_write_bytes(&byte, 1);

  if (module_response_len < (MODULE_RESPONSE_SIZE - 1U))
  {
    module_response[module_response_len++] = (char)byte;
    module_response[module_response_len] = '\0';
  }

  if (byte == '\r' || byte == '\n')
  {
    return;
  }
}

static void handle_pc_line(char *line)
{
  trim_line(line);
  if (line[0] == '\0')
  {
    return;
  }

  if (line[0] == '/')
  {
    if (strcmp(line, "/ping") == 0)
    {
      pc_write("[STM32] pong\r\n");
      send_status();
    }
    else if (strcmp(line, "/help") == 0)
    {
      send_help();
    }
    else if (strcmp(line, "/status") == 0)
    {
      send_status();
    }
    else if (strncmp(line, "/baud ", 6) == 0)
    {
      uint32_t baud = (uint32_t)strtoul(&line[6], NULL, 10);
      set_module_baud(baud);
    }
    else if (strcmp(line, "/preset") == 0)
    {
      run_preset();
    }
    else
    {
      pc_write("[STM32] ERR unknown command. Type /help\r\n");
    }
    return;
  }

  pc_write("[STM32->HC05] ");
  pc_write(line);
  pc_write("\r\n");
  module_response_len = 0;
  module_response[0] = '\0';
  module_write_line(line);
}

static void trim_line(char *line)
{
  size_t len = strlen(line);
  while (len > 0U && (line[len - 1U] == ' ' || line[len - 1U] == '\t'))
  {
    line[--len] = '\0';
  }

  char *start = line;
  while (*start == ' ' || *start == '\t')
  {
    start++;
  }

  if (start != line)
  {
    memmove(line, start, strlen(start) + 1U);
  }
}

static void send_help(void)
{
  pc_write("[STM32] Commands:\r\n");
  pc_write("  /ping          check bridge status\r\n");
  pc_write("  /status        show HC-05 STATE pin and USART2 baud\r\n");
  pc_write("  /baud 38400    change USART2 baud for HC-05 AT side\r\n");
  pc_write("  /preset        write Phase3-compatible HC-05 settings\r\n");
  pc_write("  AT...          forward an AT command to HC-05 with CRLF\r\n");
}

static void send_status(void)
{
  char buf[96];
  GPIO_PinState state = HAL_GPIO_ReadPin(HC05_STATE_GPIO_Port, HC05_STATE_Pin);
  snprintf(buf, sizeof(buf),
           "[STM32] USART2=%lu  USB_CDC=VCP  STATE=%s\r\n",
           (unsigned long)module_baud,
           state == GPIO_PIN_SET ? "HIGH" : "LOW");
  pc_write(buf);
}

static void set_module_baud(uint32_t baud)
{
  char buf[64];
  if (!is_supported_baud(baud))
  {
    pc_write("[STM32] ERR unsupported baud. Try 9600, 19200, 38400, 57600, 115200\r\n");
    return;
  }

  snprintf(buf, sizeof(buf), "[STM32] Switching USART2 to %lu\r\n", (unsigned long)baud);
  pc_write(buf);
  USART2_ReconfigureBaud(baud);
  module_baud = baud;
  HAL_UART_Receive_IT(&huart2, (uint8_t *)&module_rx_byte, 1);
}

static void run_preset(void)
{
  static const char *const preset_cmds[] = {
      "AT",
      "AT+ORGL",
      "AT+NAME=SmartWatch",
      "AT+ROLE=0",
      "AT+PSWD=1234",
      "AT+UART=9600,0,0",
      "AT+RESET",
  };

  pc_write("[STM32] Running Phase3-compatible preset\r\n");

  for (size_t i = 0; i < (sizeof(preset_cmds) / sizeof(preset_cmds[0])); i++)
  {
    if (!send_preset_command(preset_cmds[i]))
    {
      pc_write("[STM32] Preset stopped. Check KEY/EN AT mode, wiring, and baud.\r\n");
      return;
    }
    HAL_Delay(200);
  }

  pc_write("[STM32] Preset finished. Power-cycle HC-05 without KEY/EN for data mode.\r\n");
}

static bool send_preset_command(const char *cmd)
{
  char buf[96];
  uint32_t start;

  module_response_len = 0;
  module_response[0] = '\0';

  snprintf(buf, sizeof(buf), "[PRESET] > %s\r\n", cmd);
  pc_write(buf);
  module_write_line(cmd);

  start = HAL_GetTick();
  while (HAL_GetTick() - start < PRESET_TIMEOUT_MS)
  {
    drain_module_queue();
    if (response_has_ok())
    {
      pc_write("[PRESET] OK\r\n");
      return true;
    }
  }

  pc_write("[PRESET] TIMEOUT/ERR\r\n");
  return false;
}

static void drain_module_queue(void)
{
  uint8_t byte;
  while (queue_pop(&module_queue, &byte))
  {
    process_module_byte(byte);
  }
}

static bool response_has_ok(void)
{
  return strstr(module_response, "OK") != NULL;
}

static bool is_supported_baud(uint32_t baud)
{
  static const uint32_t baudrates[] = {9600U, 19200U, 38400U, 57600U, 115200U};
  for (size_t i = 0; i < (sizeof(baudrates) / sizeof(baudrates[0])); i++)
  {
    if (baud == baudrates[i])
    {
      return true;
    }
  }
  return false;
}
