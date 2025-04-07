"""Модуль графического интерфейса"""

import time
from datetime import datetime
from tkinter import Tk, BooleanVar, StringVar, IntVar, Frame
from tkinter import ttk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import deque
from logger import DataLogger  # Добавляем импорт
from constants import (
    REG_STATUS, REG_TEMPERATURE, REG_MEASURED_PRESSURE,
    REG_POSITION, REG_COMMAND, REG_SET_PRESSURE, REG_SET_POSITION,
    CMD_START, CMD_STOP, CMD_SAVE_FLASH, CMD_OPEN, CMD_CLOSE, CMD_MIDDLE_POSITION
)

class DeviceGUI:
    """Класс графического интерфейса для управления устройством"""

    def __init__(self, controller):
        self.controller = controller
        self.window = Tk()
        self._setup_window()
        self._init_variables()
        self._init_graphs()
        self._setup_ui()
        self._start_background_tasks()
        self.logger = DataLogger(log_interval=60)  # Создаем экземпляр логгера

    def _setup_window(self):
        """Настройка основного окна"""
        self.window.title("Управление устройством")
        self.window.geometry("900x650")
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

    def _init_variables(self):
        """Инициализация переменных интерфейса"""
        self.status_vars = {
            'STAB': BooleanVar(),
            'OPEN': BooleanVar(),
            'CLOSE': BooleanVar(),
            'ERROR': BooleanVar()
        }
        self.measured_pressure_var = StringVar(value="--- Pa")
        self.set_pressure_var = StringVar(value="0")
        self.temperature_var = StringVar(value="--- °C")
        self.position_var = IntVar(value=0)
        self.position_text_var = StringVar(value="Позиция: 0")
        self.resive_new_pressure_data = False
        self.resive_new_temperature_data = False
        self.resive_new_position_data = False
        self.resive_new_status_data = False
        self.last_time_log = time.time()

    def _init_graphs(self):
        """Инициализация графиков с раздельными массивами данных"""
        self.temp_data = {'time': deque(maxlen=100), 'value': deque(maxlen=100)}
        self.pressure_data = {'time': deque(maxlen=100), 'value': deque(maxlen=100)}

    def _setup_ui(self):
        """Создание элементов интерфейса"""
        main_container = ttk.Frame(self.window, padding="10")
        main_container.pack(fill='both', expand=True)

        # Левая колонка (управление)
        left_frame = ttk.Frame(main_container)
        left_frame.pack(side='left', fill='both', expand=False)

        # Правая колонка (графики)
        right_frame = ttk.Frame(main_container)
        right_frame.pack(side='right', fill='both', expand=True)

        # Элементы управления
        self._create_status_frame(left_frame)
        self._create_temperature_frame(left_frame)
        self._create_position_frame(left_frame)
        self._create_pressure_frame(left_frame)
        self._create_command_frame(left_frame)

        # Графики
        self._create_graphs_frame(right_frame)

    def _create_graphs_frame(self, parent):
        """Создает фрейм с графиками"""
        frame = ttk.LabelFrame(parent, text="Графики в реальном времени", padding="5")
        frame.pack(fill='both', expand=True, pady=5)

        fig = Figure(figsize=(6, 5), dpi=80)
        fig.tight_layout()
        self.ax1 = fig.add_subplot(211)
        self.ax2 = fig.add_subplot(212)

        self.ax1.set_title('Температура (°C)')
        self.ax1.grid(True)
        self.ax2.set_title('Давление (Pa)')
        self.ax2.grid(True)

        self.canvas = FigureCanvasTkAgg(fig, master=frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill='both', expand=True)

    def _update_status(self):
        """Обновляет статусные флаги"""
        while not self.controller.status_queue.empty():
            address, value = self.controller.status_queue.get()
            self.resive_new_status_data = True
            if address == REG_STATUS:
                for i, (name, var) in enumerate(self.status_vars.items()):
                    var.set(bool(value & (1 << i)))

    def _update_position(self):
        """Обновляет позицию заслонки"""
        while not self.controller.position_queue.empty():
            address, value = self.controller.position_queue.get()
            self.resive_new_position_data = True
            if address == REG_POSITION:
                self.position_var.set(value)
                self.position_text_var.set(f"Позиция: {value}")

    def _update_graphs(self):
        """Обновляет графики с раздельными данными"""
        try:
            # Обновляем график температуры
            self.ax1.clear()
            if len(self.temp_data['value']) > 0:
                self.ax1.plot(
                    self.temp_data['value'],
                    'r-',
                    label='Температура'
                )
            self.ax1.set_title('Температура (°C)')
            self.ax1.grid(True)
            self.ax1.legend(loc='upper right')

            # Обновляем график давления
            self.ax2.clear()
            if len(self.pressure_data['value']) > 0:
                self.ax2.plot(
                    self.pressure_data['value'],
                    'b-',
                    label='Давление'
                )
            self.ax2.set_title('Давление (Pa)')
            self.ax2.grid(True)
            self.ax2.legend(loc='upper right')

            # # Форматирование времени на осях X
            # for ax in [self.ax1, self.ax2]:
            #     if len(ax.lines) > 0 and len(ax.lines[0].get_xdata()) > 0:
            #         #x_data = ax.lines[0].get_xdata()
            #         #time_labels = [datetime.fromtimestamp(t).strftime('%H:%M:%S') for t in x_data]
            #         #ax.set_xticks(x_data)
            #         #ax.set_xticklabels(time_labels, rotation=45)

            self.canvas.draw()
        except Exception as e:
            print(f"Ошибка обновления графиков: {e}")

    def _update_temperature(self):
        """Обновляет показания температуры и график"""
        while not self.controller.temperature_queue.empty():
            address, value = self.controller.temperature_queue.get()
            self.resive_new_temperature_data = True
            if address == REG_TEMPERATURE:
                temp_c = value / 10.0
                current_time = time.time()

                # Обновляем данные для графика температуры
                self.temp_data['time'].append(current_time)
                self.temp_data['value'].append(temp_c)

                # Обновляем текстовое поле
                self.temperature_var.set(f"{temp_c:.1f} °C")

                # Обновляем графики
                #self._update_graphs()

    def _update_pressure(self):
        """Обновляет показания давления и график"""
        while not self.controller.measured_pressure_queue.empty():
            address, value = self.controller.measured_pressure_queue.get()
            self.resive_new_pressure_data = True
            if address == REG_MEASURED_PRESSURE:
                pressure = value / 10.0
                current_time = time.time()

                # Обновляем данные для графика давления
                self.pressure_data['time'].append(current_time)
                self.pressure_data['value'].append(pressure)

                # Обновляем текстовое поле
                self.measured_pressure_var.set(f"{pressure:.1f} Pa")

                # Обновляем графики
                #self._update_graphs()

        while not self.controller.set_pressure_queue.empty():
            address, value = self.controller.set_pressure_queue.get()
            if address == REG_SET_PRESSURE and not self.pressure_spinbox.focus_displayof():
                self.set_pressure_var.set(str(value / 10))

    def _update_data(self):
        """Обновляет все данные из очередей"""
        try:
            self._update_status()
            self._update_temperature()
            self._update_position()
            self._update_pressure()
        except Exception as e:
            print(f"Ошибка обновления интерфейса: {e}")

    # Остальные методы остаются без изменений...
    def _create_status_frame(self, parent):
        """Создает фрейм статуса"""
        frame = ttk.LabelFrame(parent, text="Статус", padding="5")
        frame.pack(fill='x', pady=5)

        for name, var in self.status_vars.items():
            cb = ttk.Checkbutton(frame, text=name, variable=var, state='disabled')
            cb.pack(anchor='w')

    def _create_temperature_frame(self, parent):
        """Создает фрейм температуры"""
        frame = ttk.LabelFrame(parent, text="Температура", padding="5")
        frame.pack(fill='x', pady=5)
        ttk.Label(frame, textvariable=self.temperature_var, font=('Arial', 12)).pack()

    def _create_position_frame(self, parent):
        """Создает фрейм позиции"""
        frame = ttk.LabelFrame(parent, text="Позиция заслонки", padding="5")
        frame.pack(fill='x', pady=5)
        ttk.Label(frame, textvariable=self.position_text_var).pack()
        ttk.Scale(frame, variable=self.position_var, from_=0, to=4095, length=300).pack()
        ttk.Button(frame, text="Применить", command=self._set_position).pack(pady=5)

    def _create_pressure_frame(self, parent):
        """Создает фрейм давления"""
        frame = ttk.LabelFrame(parent, text="Давление", padding="5")
        frame.pack(fill='x', pady=5)

        ttk.Label(frame, text="Измеренное:").grid(row=0, column=0, padx=5, sticky='w')
        ttk.Label(frame, textvariable=self.measured_pressure_var).grid(row=0, column=1, padx=5, sticky='w')

        ttk.Label(frame, text="Уставка:").grid(row=1, column=0, padx=5, sticky='w')
        self.pressure_spinbox = ttk.Spinbox(
            frame, from_=0, to=10000, textvariable=self.set_pressure_var, width=10
        )
        self.pressure_spinbox.grid(row=1, column=1, padx=5)
        ttk.Button(frame, text="Прочитать", command=self._read_pressure).grid(row=1, column=2, padx=5)
        ttk.Button(frame, text="Применить", command=self._set_pressure).grid(row=1, column=3, padx=5)

    def _create_command_frame(self, parent):
        """Создает фрейм команд"""
        frame = ttk.LabelFrame(parent, text="Команды", padding="5")
        frame.pack(fill='x', pady=10)

        ttk.Button(frame, text="СТАРТ", command=lambda: self._send_command(REG_COMMAND, CMD_START)).grid(
            row=0, column=0, padx=5, pady=2)
        ttk.Button(frame, text="СТОП", command=lambda: self._send_command(REG_COMMAND, CMD_STOP)).grid(
            row=0, column=1, padx=5, pady=2)
        ttk.Button(frame, text="СОХР.FLASH", command=lambda: self._send_command(REG_COMMAND, CMD_SAVE_FLASH)).grid(
            row=0, column=2, padx=5, pady=2)

        ttk.Button(frame, text="ОТКРЫТО", command=lambda: self._send_command(REG_COMMAND, CMD_OPEN)).grid(
            row=1, column=0, padx=5, pady=2)
        ttk.Button(frame, text="ЗАКРЫТО", command=lambda: self._send_command(REG_COMMAND, CMD_CLOSE)).grid(
            row=1, column=1, padx=5, pady=2)
        ttk.Button(frame, text="СРЕДНЕЕ", command=self._set_middle_position).grid(
            row=1, column=2, padx=5, pady=2)

        for i in range(3):
            frame.grid_columnconfigure(i, weight=1)

    def _start_background_tasks(self):
        """Запускает фоновые задачи"""
        self._update_data()
        #self._check_connection()
        self._log_data()

        if self.window.winfo_exists():
            self.window.after(100, self._start_background_tasks)

    def _check_connection(self):
        """Проверяет соединение с устройством"""
        if not self.controller._ensure_connection():
            print("Предупреждение: проблемы с соединением")

        # if self.window.winfo_exists():
        #     self.window.after(5000, self._check_connection)

    def _send_command(self, register, value):
        """Отправляет команду устройству"""
        if self.controller.write_register(register, value):
            print(f"Команда отправлена: регистр 0x{register:02X}, значение 0x{value:04X}")

    def _set_pressure(self):
        """Устанавливает давление"""
        try:
            value = int(float(self.set_pressure_var.get()) * 10)
            status = self.controller.read_register(REG_STATUS)
            if status is None:
                return

            was_stab = status & 0x01
            if was_stab:
                self.controller.write_register(REG_COMMAND, CMD_STOP)

            if self.controller.write_register(REG_SET_PRESSURE, value):
                print(f"Давление установлено: {value / 10} Pa")

            if was_stab:
                self.controller.write_register(REG_COMMAND, CMD_START)
        except ValueError:
            print("Ошибка: введите число")

    def _read_pressure(self):
        """Читает текущее значение уставки давления"""
        value = self.controller.read_register(REG_SET_PRESSURE)
        if value is not None:
            self.set_pressure_var.set(str(value / 10))

    def _set_position(self):
        """Устанавливает позицию заслонки"""
        value = self.position_var.get()
        if self.controller.write_register(REG_SET_POSITION, value):
            print(f"Позиция установлена: {value}")

    def _set_middle_position(self):
        """Устанавливает среднее положение заслонки"""
        if self.controller.read_register(REG_STATUS) is None:
            return

        self.controller.write_register(REG_COMMAND, CMD_OPEN)
        star_time = time.time()
        open = False
        while (not open and not (star_time - time.time() > 5)):
            try:
                open = (self.controller.read_register(REG_STATUS) & 0x02)
            except Exception as e:
                print(f"Ошибка при чтении стуса: {e}")

            time.sleep(1)

        self.controller.write_register(REG_COMMAND, CMD_MIDDLE_POSITION)

    def _log_data(self):
        """Логирование данных через модуль DataLogger"""
        if (self.resive_new_pressure_data & self.resive_new_status_data & \
            self.resive_new_position_data & self.resive_new_status_data):
            print("log")
            try:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Получаем текущие значения
                temp = self.temperature_var.get().replace(" °C", "") if self.temperature_var.get() != "---" else None
                pressure = self.measured_pressure_var.get().replace(" Pa",
                                                                    "") if self.measured_pressure_var.get() != "---" else None
                position = self.position_var.get()

                # Получаем статус в виде битовой маски
                status = 0
                for i, (name, var) in enumerate(self.status_vars.items()):
                    status |= int(var.get()) << i

                # Передаем данные логгеру
                self.logger.add_data(current_time, temp, pressure, position, status)

            except Exception as e:
                print(f"Ошибка при логировании данных: {e}")
        else:
            if time.time() - self.last_time_log > 0.5:
                self.resive_new_pressure_data = False
                self.resive_new_status_data = False
                self.resive_new_position_data = False
                self.resive_new_status_data = False

    def on_close(self):
        """Обработчик закрытия окна"""
        self.logger.flush()  # Сохраняем данные перед выходом
        self.controller.disconnect()
        self.window.destroy()

    def run(self):
        """Запускает главный цикл приложения"""
        self.window.mainloop()