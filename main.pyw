"""Основной модуль приложения"""

import time
import json
from pathlib import Path
from device_controller import DeviceController
from gui import DeviceGUI


def load_config(config_path="config.json"):
    """Загрузка настроек устройства из JSON-файла"""
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Файл конфигурации не найден: {config_path}")
    with open(config_file, "r") as f:
        return json.load(f)


def main():
    """Точка входа в приложение"""
    config = load_config()
    max_attempts = config.get("max_attempts", 5)
    poll_interval = config.get("poll_interval_sec", 2)

    controller = DeviceController(
        config["ip"],
        port=config.get("port", 502),
        device_id=config.get("device_id", 0x03)
    )

    for attempt in range(1, max_attempts + 1):
        if controller.connect():
            app = DeviceGUI(controller)
            controller.start_polling()
            app.run()
            break
        print(f"Попытка {attempt} из {max_attempts} не удалась")
        if attempt < max_attempts:
            time.sleep(poll_interval)
    else:
        print("Не удалось подключиться к устройству после нескольких попыток")


if __name__ == "__main__":
    main()