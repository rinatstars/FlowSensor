"""Модуль для управления устройством через Modbus"""

import socket
import struct
import threading
import time
from queue import Queue

from constants import (
    DEFAULT_PORT, DEFAULT_DEVICE_ID, RECONNECT_ATTEMPTS, RECONNECT_DELAY,
    READ_TIMEOUT, WRITE_TIMEOUT, REG_STATUS, REG_MEASURED_PRESSURE,
    REG_TEMPERATURE, REG_POSITION_LO, REG_POSITION_HI, REG_COMMAND, REG_SET_PRESSURE, REG_SET_POSITION,
    CMD_START, CMD_OPEN, CMD_CLOSE, CMD_STOP, CMD_SAVE_FLASH, CMD_MIDDLE_POSITION
)
from crc import crc7_generate


class DeviceController:
    """Класс для управления устройством через TCP-соединение"""

    def __init__(self, ip, port=DEFAULT_PORT, device_id=DEFAULT_DEVICE_ID):
        """Инициализация контроллера устройства"""
        self.ip = ip
        self.port = port
        self.device_id = device_id & 0x07  # 3 бита (0-7)
        self.sock = None
        self.connection_lock = threading.Lock()
        self._init_queues()
        self.running = False
        self.reconnect_attempts = RECONNECT_ATTEMPTS
        self.reconnect_delay = RECONNECT_DELAY
        self.read_timeout = READ_TIMEOUT
        self.write_timeout = WRITE_TIMEOUT

    def _init_queues(self):
        """Инициализация очередей для данных"""
        self.status_queue = Queue(maxsize=100)
        self.temperature_queue = Queue(maxsize=100)
        self.position_queue = Queue(maxsize=100)
        self.measured_pressure_queue = Queue(maxsize=100)
        self.set_pressure_queue = Queue(maxsize=100)

    def _reconnect(self):
        """Пытается переподключиться к устройству"""
        with self.connection_lock:
            for attempt in range(self.reconnect_attempts):
                try:
                    self._close_socket()
                    self.sock = self._create_socket()
                    print("Успешное подключение")
                    return True
                except Exception as e:
                    print(f"Попытка {attempt + 1}/{self.reconnect_attempts}: {e}")
                    time.sleep(self.reconnect_delay)
            return False

    def _create_socket(self):
        """Создает и настраивает сокет"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.read_timeout)
        sock.connect((self.ip, self.port))
        return sock

    def _close_socket(self):
        """Закрывает сокет, если он открыт"""
        if self.sock:
            self.sock.close()
            self.sock = None

    def _ensure_connection(self):
        """Проверяет и восстанавливает соединение при необходимости"""
        if self.sock is None:
            return self._reconnect()

        try:
            self.sock.settimeout(1)
            self.sock.sendall(b'')  # Тестовый пустой пакет
            return True
        except Exception:
            return self._reconnect()

    def connect(self):
        """Устанавливает первоначальное соединение"""
        return self._reconnect()

    def _build_frame(self, address, write=False, data=0x0000):
        """Собирает кадр согласно протоколу."""
        byte1 = (
                0xC0 |
                (0x20 if write else 0x00) |
                ((data >> 15) & 0x01) << 4 |
                ((data >> 14) & 0x01) << 3 |
                self.device_id
        )
        byte2 = address & 0x7F
        byte3 = (data >> 7) & 0x7F
        byte4 = data & 0x7F

        frame = bytes([byte1, byte2, byte3, byte4])
        crc = crc7_generate(frame)
        return frame + bytes([crc & 0x7F])

    def _parse_response(self, response, expected_address):
        """Парсит ответное сообщение."""
        if len(response) != 5:
            return None
        if (response[0] & 0xC0) != 0xC0:
            return None
        if (response[0] & 0x07) != self.device_id:
            return None
        if (response[1] & 0x7F) != expected_address:
            return None
        if crc7_generate(response[:4]) != (response[4] & 0x7F):
            return None

        return (
                ((response[0] >> 4) & 0x03) << 14 |
                (response[2] & 0x7F) << 7 |
                response[3] & 0x7F
        )

    def read_register(self, address):
        """Чтение регистра с автоматическим переподключением"""
        for attempt in range(3):
            try:
                if not self._ensure_connection():
                    continue

                request = self._build_frame(address, write=False)
                self.sock.settimeout(self.read_timeout)
                self.sock.sendall(request)
                response = self.sock.recv(5)

                if not response:
                    raise socket.timeout("Пустой ответ")

                return self._parse_response(response, address)

            except (socket.timeout, socket.error, ConnectionError) as e:
                print(f"Ошибка связи (попытка {attempt + 1}): {e}")
                self.sock = None
                if not self._reconnect():
                    continue
            except Exception as e:
                print(f"Ошибка чтения регистра 0x{address:02X}: {e}")
                break

        return None

    def write_register(self, address, value):
        """Запись регистра с автоматическим переподключением"""
        for attempt in range(3):
            try:
                if not self._ensure_connection():
                    continue

                request = self._build_frame(address, write=True, data=value)
                self.sock.settimeout(self.write_timeout)
                self.sock.sendall(request)
                response = self.sock.recv(5)

                if not response:
                    raise socket.timeout("Пустой ответ")

                return self._parse_response(response, address) is not None

            except (socket.timeout, socket.error, ConnectionError) as e:
                print(f"Ошибка связи (попытка {attempt + 1}): {e}")
                self.sock = None
                if not self._reconnect():
                    continue
            except Exception as e:
                print(f"Ошибка записи регистра 0x{address:02X}: {e}")
                break

        return False

    def start_polling(self):
        """Запускает потоки для опроса данных"""
        if self.running:
            return

        self.running = True

        def polling_worker(address, queue, interval):
            """Поток для безопасного опроса регистров"""
            while self.running:
                try:
                    value = self.read_register(address)
                    if value is not None:
                        queue.put((address, value))
                    time.sleep(interval)
                except Exception as e:
                    print(f"Ошибка в потоке опроса: {e}")
                    time.sleep(1)

        # Конфигурация потоков опроса
        polling_config = [
            (REG_STATUS, self.status_queue, 0.1),  # Статус
            (REG_MEASURED_PRESSURE, self.measured_pressure_queue, 0.1),  # Давление
            (REG_TEMPERATURE, self.temperature_queue, 0.1),  # Температура
            (REG_POSITION_LO, self.position_queue, 0.1),     # Позиция
            (REG_POSITION_HI, self.position_queue, 0.1),  # Позиция
            (REG_SET_PRESSURE, self.set_pressure_queue, 2.0)  # Уставка давления
        ]

        for addr, queue, interval in polling_config:
            t = threading.Thread(
                target=polling_worker,
                args=(addr, queue, interval),
                daemon=True
            )
            t.start()

    def stop_polling(self):
        """Останавливает опрос данных"""
        self.running = False

    def disconnect(self):
        """Закрывает соединение"""
        self.stop_polling()
        with self.connection_lock:
            self._close_socket()