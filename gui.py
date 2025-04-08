"""Модуль графического интерфейса"""

import time
import matplotlib
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

matplotlib.rcParams['path.simplify'] = True
matplotlib.rcParams['path.simplify_threshold'] = 1.0
matplotlib.rcParams['agg.path.chunksize'] = 10000
matplotlib.use('TkAgg')  # Явно указываем бэкенд

class DeviceGUI:
    """Класс графического интерфейса для управления устройством"""

    def __init__(self, controller):
        self.controller = controller
        self.window = Tk()
        self._setup_window()
        self._init_variables()
        #self._init_graphs()
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
        self.receive_new_temperature_data = False
        self.receive_new_pressure_data = False
        self.receive_new_position_data = False
        self.receive_new_status_data = False
        self.last_log_time = time.time()

    def _init_graphs(self, frame):
        # Данные для графиков
        self.max_points = 100  # Фиксированное количество точек
        self.temp_data = {'time': deque(maxlen=self.max_points), 'value': deque(maxlen=self.max_points)}
        self.pressure_data = {'time': deque(maxlen=self.max_points), 'value': deque(maxlen=self.max_points)}

        # Настройка фигуры
        self.fig = Figure(figsize=(6, 5), dpi=80)
        self.fig.set_tight_layout(True)

        # Настройка осей
        self.ax1 = self.fig.add_subplot(211)
        self.ax2 = self.fig.add_subplot(212)

        # Инициализация линий графиков
        self.temp_line, = self.ax1.plot([], [], 'r-', label='Температура')
        self.pressure_line, = self.ax2.plot([], [], 'b-', label='Давление')

        # Настройка осей
        self.ax1.set_title('Температура (°C)')
        self.ax1.set_xlim(0, self.max_points - 1)
        self.ax1.grid(True)
        self.ax1.legend(loc='upper right')
        self.ax2.set_title('Давление (Pa)')
        self.ax2.set_xlim(0, self.max_points - 1)
        self.ax2.grid(True)
        self.ax2.legend(loc='upper right')

        # Инициализация canvas
        self.canvas = FigureCanvasTkAgg(self.fig, master=frame)
        self.canvas.draw()

        # Фон для blitting нужно сохранять после первого отображения
        self.ax1_background = None
        self.ax2_background = None

    def _setup_ui(self):
        """Создание элементов интерфейса"""
        # Основной контейнер с использованием grid для корректного распределения областей
        main_container = ttk.Frame(self.window, padding="10")
        main_container.pack(fill='both', expand=True)
        main_container.columnconfigure(0, weight=0)
        main_container.columnconfigure(1, weight=1)
        main_container.rowconfigure(0, weight=1)

        # Левая колонка (управление)
        left_frame = ttk.Frame(main_container)
        left_frame.grid(row=0, column=0, sticky='nsw', padx=(0, 10))

        # Правая колонка (графики)
        right_frame = ttk.Frame(main_container)
        right_frame.grid(row=0, column=1, sticky='nsew')

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

        # Убедимся, что фигура уже создана
        if not hasattr(self, 'canvas'):
            self._init_graphs(frame)


        # Размещаем canvas так, чтобы он занимал всё пространство фрейма
        self.canvas.get_tk_widget().pack(fill='both', expand=True)

        # Подключаем событие отрисовки
        self.canvas.mpl_connect('draw_event', self._on_draw)

    def _on_draw(self, event):
        """Обработчик события отрисовки для сохранения фона"""
        self.ax1_background = self.canvas.copy_from_bbox(self.ax1.bbox)
        self.ax2_background = self.canvas.copy_from_bbox(self.ax2.bbox)

    def _update_status(self):
        """Обновляет статусные флаги"""
        while not self.controller.status_queue.empty():
            address, value = self.controller.status_queue.get()
            if address == REG_STATUS:
                for i, (name, var) in enumerate(self.status_vars.items()):
                    var.set(bool(value & (1 << i)))

    def _update_position(self):
        """Обновляет позицию заслонки"""
        while not self.controller.position_queue.empty():
            address, value = self.controller.position_queue.get()
            if address == REG_POSITION:
                self.position_var.set(value)
                self.position_text_var.set(f"Позиция: {value}")

    def _update_graphs(self):
        """Оптимизированное обновление графиков"""
        if not (self.receive_new_temperature_data or self.receive_new_pressure_data):
            return

        try:
            redraw_full = False
            # Обновляем данные линий
            if self.receive_new_temperature_data and len(self.temp_data['value']) > 0:
                self.temp_line.set_data(range(len(self.temp_data['value'])), self.temp_data['value'])
                old_ylim = self.ax1.get_ylim()
                self.ax1.relim()
                self.ax1.autoscale_view(scalex=False, scaley=True)
                new_ylim = self.ax1.get_ylim()
                # Проверяем: изменились ли границы Y
                if old_ylim != new_ylim:
                    redraw_full = True
                else:
                    redraw_full = False

            if self.receive_new_pressure_data and len(self.pressure_data['value']) > 0:
                self.pressure_line.set_data(range(len(self.pressure_data['value'])), self.pressure_data['value'])
                old_ylim = self.ax2.get_ylim()
                self.ax2.relim()
                self.ax2.autoscale_view(scalex=False, scaley=True)
                new_ylim = self.ax2.get_ylim()
                # Проверяем: изменились ли границы Y
                if old_ylim != new_ylim:
                    redraw_full = True
                else:
                    redraw_full = False

            # Первая отрисовка - сохраняем фон
            if self.ax1_background is None or redraw_full:
                self.temp_line.set_animated(True)
                self.pressure_line.set_animated(True)
                self.fig.canvas.draw()
                self.ax1_background = self.canvas.copy_from_bbox(self.ax1.bbox)
                self.ax2_background = self.canvas.copy_from_bbox(self.ax2.bbox)


            # Последующие обновления с blitting
            self.canvas.restore_region(self.ax1_background)
            self.ax1.draw_artist(self.temp_line)
            self.canvas.restore_region(self.ax2_background)
            self.ax2.draw_artist(self.pressure_line)

            # Обновляем только измененные области
            self.canvas.blit(self.ax1.bbox)
            self.canvas.blit(self.ax2.bbox)

        except Exception as e:
            print(f"Ошибка обновления графиков: {e}")
            # При ошибке перерисовываем полностью
            self.canvas.draw()
        finally:
            self.receive_new_temperature_data = False
            self.receive_new_pressure_data = False


    def _update_temperature(self):
        """Обновляет показания температуры"""
        max_updates = 10  # Ограничиваем количество обновлений за один вызов
        updates = 0

        while not self.controller.temperature_queue.empty() and updates < max_updates:
            try:
                address, value = self.controller.temperature_queue.get_nowait()
                if address == REG_TEMPERATURE:
                    temp_c = value / 10.0
                    self.temp_data['value'].append(temp_c)
                    self.temperature_var.set(f"{temp_c:.1f} °C")
                    self.receive_new_temperature_data = True
                    updates += 1
            except:
                break

    def _update_pressure(self):
        """Обновляет показания давления"""
        max_updates = 10
        updates = 0

        while not self.controller.measured_pressure_queue.empty() and updates < max_updates:
            try:
                address, value = self.controller.measured_pressure_queue.get_nowait()
                if address == REG_MEASURED_PRESSURE:
                    pressure = value / 10.0
                    self.pressure_data['value'].append(pressure)
                    self.measured_pressure_var.set(f"{pressure:.1f} Pa")
                    self.receive_new_pressure_data = True
                    updates += 1
            except:
                break

    def _update_data(self):
        """Обновляет все данные из очередей"""
        try:
            self._update_status()
            self._update_temperature()
            self._update_position()
            self._update_pressure()
        except Exception as e:
            print(f"Ошибка обновления интерфейса: {e}")

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
        """Оптимизированный планировщик задач"""
        start_time = time.time()

        # Обновляем данные
        self._update_data()

        # Обновляем графики только если есть новые данные
        if self.receive_new_temperature_data or self.receive_new_pressure_data:
            self._update_graphs()

        # Логируем данные (реже)
        if time.time() - self.last_log_time >= 1.0:  # Раз в секунду
            self._log_data()
            self.last_log_time = time.time()

        # Динамически регулируем интервал
        processing_time = time.time() - start_time
        next_interval = max(100, int(processing_time * 1000 * 1.1))  # +10% к времени обработки

        if self.window.winfo_exists():
            self.window.after(next_interval, self._start_background_tasks)

    def _check_connection(self):
        """Проверяет соединение с устройством"""
        if not self.controller._ensure_connection():
            print("Предупреждение: проблемы с соединением")

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
        """Устанавливает среднее положение заслонки без блокировки главного цикла"""
        if self.controller.read_register(REG_STATUS) is None:
            return

        self.controller.write_register(REG_COMMAND, CMD_OPEN)
        # Запускаем проверку каждые 1000 мс до наступления нужного статуса
        self.window.after(1000, self._check_and_set_middle)

    def _check_and_set_middle(self):
        """Проверяет, установлен ли нужный статус, и отправляет команду установки среднего положения"""
        status = self.controller.read_register(REG_STATUS)
        if status is not None and (status & 0x02):
            self.controller.write_register(REG_COMMAND, CMD_MIDDLE_POSITION)
        else:
            # Если условие не выполнено, проверяем снова через 1000 мс
            self.window.after(1000, self._check_and_set_middle)

    def _log_data(self):
        """Логирование данных через модуль DataLogger"""
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Получаем текущие значения
            temp = self.temperature_var.get().replace(" °C", "") if self.temperature_var.get() != "---" else None
            pressure = self.measured_pressure_var.get().replace(" Pa", "") if self.measured_pressure_var.get() != "---" else None
            position = self.position_var.get()

            # Получаем статус в виде битовой маски
            status = 0
            for i, (name, var) in enumerate(self.status_vars.items()):
                status |= int(var.get()) << i

            # Передаем данные логгеру
            self.logger.add_data(current_time, temp, pressure, position, status)

        except Exception as e:
            print(f"Ошибка при логировании данных: {e}")

    def on_close(self):
        """Обработчик закрытия окна"""
        self.logger.flush()  # Сохраняем данные перед выходом
        self.controller.disconnect()
        self.window.destroy()

    def run(self):
        """Запускает главный цикл приложения"""
        self.window.mainloop()
