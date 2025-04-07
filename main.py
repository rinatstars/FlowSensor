# main.py
"""Основной модуль приложения"""

import time
from device_controller import DeviceController
from gui import DeviceGUI


def main():
    """Точка входа в приложение"""
    max_attempts = 5
    controller = DeviceController("10.11.13.241", port=502, device_id=0x03)

    for attempt in range(1, max_attempts + 1):
        if controller.connect():
            app = DeviceGUI(controller)
            controller.start_polling()
            app.run()
            break
        print(f"Попытка {attempt} из {max_attempts} не удалась")
        if attempt < max_attempts:
            time.sleep(2)
    else:
        print("Не удалось подключиться к устройству после нескольких попыток")


if __name__ == "__main__":
    main()