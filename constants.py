"""Модуль с константами и настройками"""

# Константы для CRC7
CRC7_POLYNOMIAL = 0x89  # x^7 + x^3 + 1

# Настройки подключения
DEFAULT_PORT = 502
DEFAULT_DEVICE_ID = 0x03
RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY = 2
READ_TIMEOUT = 3.0
WRITE_TIMEOUT = 5.0

# Адреса регистров
REG_STATUS = 0x00
REG_MEASURED_PRESSURE = 0x01
REG_TEMPERATURE = 0x02
REG_POSITION = 0x03
REG_COMMAND = 0x08
REG_SET_PRESSURE = 0x09
REG_SET_POSITION = 0x0A

# Команды
CMD_START = 0x01
CMD_OPEN = 0x02
CMD_CLOSE = 0x03
CMD_STOP = 0x06
CMD_SAVE_FLASH = 0x07
CMD_MIDDLE_POSITION = 0x05