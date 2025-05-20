"""Модуль графического интерфейса"""

import time
import matplotlib
from datetime import datetime
from tkinter import Tk, BooleanVar, StringVar, IntVar, Frame
from tkinter import ttk
from tkinter import scrolledtext
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import deque
from logger import DataLogger  # Добавляем импорт
from constants import (
    REG_STATUS, REG_TEMPERATURE, REG_MEASURED_PRESSURE,
    REG_POSITION_LO, REG_POSITION_HI, REG_COMMAND, REG_SET_PRESSURE, REG_SET_POSITION,
    CMD_START, CMD_STOP, CMD_SAVE_FLASH, CMD_OPEN, CMD_CLOSE, CMD_MIDDLE_POSITION
)

matplotlib.rcParams['path.simplify'] = True
matplotlib.rcParams['path.simplify_threshold'] = 1.0
matplotlib.rcParams['agg.path.chunksize'] = 10000
matplotlib.use('TkAgg')  # Явно указываем бэкенд

class DeviceGUI:
    """Класс графического интерфейса для управления устройством"""

    def __init__(self, controller):
        self.start_time = time.time()
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
        self.window.geometry("1200x700")
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

    def _init_variables(self):
        """Инициализация переменных интерфейса"""
        self.status_vars = {
            'STAB': BooleanVar(),
            'OPEN': BooleanVar(),
            'CLOSE': BooleanVar(),
            'POSITION': BooleanVar(),
            'KEY STAB': BooleanVar(),
            'KEY OPEN': BooleanVar(),
            'KEY CLOSE': BooleanVar(),
            'ERROR': BooleanVar(),
            'RESET': BooleanVar(),
            'PING': BooleanVar(),
        }
        self.measured_pressure_var = StringVar(value="--- Pa")
        self.set_pressure_var = StringVar(value="0")
        self.temperature_var = StringVar(value="--- °C")
        self.position_var = IntVar(value=0)
        self.position_var_set = IntVar(value=0)
        self.position_text_var = StringVar(value="Позиция изм.: 0")
        self.position_text_var_set = StringVar(value="Позиция уст.: 0")
        self.receive_new_temperature_data = False
        self.receive_new_pressure_data = False
        self.receive_new_position_data = False
        self.receive_new_status_data = False
        self.last_log_time = time.time()
        self.calc_speed = False
        self.text_press = "Давление"
        self.log_enable = BooleanVar(value=False)

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
        main_container = ttk.Frame(self.window, padding="30")
        main_container.pack(fill='both', expand=True)

        # Настройка колонок: [0] — левая, [1] — графики, [2] — журнал команд
        main_container.columnconfigure(0, weight=0)
        main_container.columnconfigure(1, weight=1)
        main_container.columnconfigure(2, weight=0)  # вывод команд — фиксированный размер
        main_container.rowconfigure(0, weight=1)

        # Левая колонка (управление)
        left_frame = ttk.Frame(main_container)
        left_frame.grid(row=0, column=0, sticky='nsw', padx=(0, 10))

        # Центральная колонка (графики)
        right_frame = ttk.Frame(main_container)
        right_frame.grid(row=0, column=1, sticky='nsew')

        # Правая колонка (вывод команд)
        output_frame = ttk.Frame(main_container)
        output_frame.grid(row=0, column=2, sticky='nse', padx=(10, 0))

        # Элементы управления
        self._create_status_frame(left_frame)
        self._create_temperature_frame(left_frame)
        self._create_position_frame(left_frame)
        self._create_pressure_frame(left_frame)
        self._create_command_frame(left_frame)
        self._create_log_frame(left_frame)

        # Графики
        self._create_graphs_frame(right_frame)

        # Элемент вывода команд (правая колонка)
        self.command_output = scrolledtext.ScrolledText(output_frame, width=40, height=30, state='disabled',
                                                        wrap='word')
        self.command_output.pack(fill='both', expand=True)

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
        """Обновляет позицию заслонки (32-битное значение)"""
        position_lo = None
        position_hi = None

        while not self.controller.position_queue_LO.empty() and not self.controller.position_queue_HI.empty():
            address, value = self.controller.position_queue_LO.get()
            position_lo = value
            address, value = self.controller.position_queue_HI.get()
            position_hi = value

        if position_lo is not None and position_hi is not None:
            position = (position_hi << 16) | position_lo
            self.position_var.set(position)
            self.position_text_var.set(f"Позиция изм.: {position}")
            #print(f'pos_lo: {position_lo}, pos_hi: {position_hi}, pos: {position}')

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
            self.append_command_log(f"Ошибка обновления интерфейса: {e}")

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
            self.append_command_log(f"Ошибка обновления графиков: {e}")
            # При ошибке перерисовываем полностью
            self.canvas.draw()
        finally:
            self.receive_new_temperature_data = False
            self.receive_new_pressure_data = False

    def _create_status_frame(self, parent):
        """Создает фрейм статуса"""
        frame = ttk.LabelFrame(parent, text="Статус", padding="5")
        frame.pack(fill='x', pady=5)

        n = 0
        for name, var in self.status_vars.items():
            if n < 5:
                cb = ttk.Checkbutton(frame, text=name, variable=var, state='disabled')
                cb.grid(row=n, column=0, padx=5, sticky='w')
                n += 1
            else:
                cb = ttk.Checkbutton(frame, text=name, variable=var, state='disabled')
                cb.grid(row=n-5, column=1, padx=5, sticky='w')
                n += 1


    def _create_temperature_frame(self, parent):
        """Создает фрейм температуры"""
        frame = ttk.LabelFrame(parent, text="Температура", padding="5")
        frame.pack(fill='x', pady=5)
        ttk.Label(frame, textvariable=self.temperature_var, font=('Arial', 12)).pack()

    def _create_position_frame(self, parent):
        """Создает фрейм позиции"""
        frame = ttk.LabelFrame(parent, text="Позиция заслонки", padding="5")
        frame.pack(fill='x', pady=5)
        ttk.Label(frame, textvariable=self.position_text_var).grid(row=0, column=0, padx=5, sticky='w')
        ttk.Label(frame, textvariable=self.position_text_var_set).grid(row=0, column=1, padx=5, sticky='w')
        ttk.Scale(frame, variable=self.position_var_set, from_=0, to=4294967295, length=300, command=self._set_position_var).grid(
            row=1, column=0, columnspan=2, padx=5, sticky='w'
        )
        ttk.Button(frame, text="Применить", command=self._set_position).grid(
            row=2, column=0, columnspan=2, padx=5, sticky='n'
        )

    def _change_speed_press(self):
        if self.calc_speed:
            self.text_press = "Скорость"
        else:
            self.text_press = "Давление"

    def _create_pressure_frame(self, parent):
        """Создает фрейм давления"""
        frame = ttk.LabelFrame(parent, text=self.text_press, padding="5")
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

        cb = ttk.Checkbutton(frame, text="Скорость", variable=self.calc_speed, command=self._change_speed_press)
        cb.grid(row=2, column=0, padx=5, sticky='w')

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

    def _create_log_frame(self, parent):
        """Создает фрейм управления логом"""
        frame = ttk.LabelFrame(parent, text="Лог", padding="5")
        frame.pack(fill='x', pady=10)

        ttk.Button(frame, text="СТАРТ", command=lambda: self._start_log(True)).grid(
            row=0, column=0, padx=5, pady=2)
        ttk.Button(frame, text="СТОП", command=lambda: self._start_log(False)).grid(
            row=0, column=1, padx=5, pady=2)
        ttk.Button(frame, text="20 изм", command=lambda: self._rec_to_log(20)).grid(
            row=0, column=2, padx=5, pady=2)

        cb = ttk.Checkbutton(frame, text="Запущен", variable=self.log_enable, state='disabled')
        cb.grid(row=1, column=0, padx=5, sticky='w')

        for i in range(3):
            frame.grid_columnconfigure(i, weight=1)

    def _start_background_tasks(self):
        """Оптимизированный планировщик задач"""
        start_time = time.time()

        #self.controller.start_polling(one_poll=True)

        # Обновляем данные
        self._update_data()

        # Обновляем графики только если есть новые данные
        if self.receive_new_temperature_data or self.receive_new_pressure_data:
            self._update_graphs()

        # Логируем данные (реже)
        if time.time() - self.last_log_time >= 0.5 and self.log_enable.get():  # Раз в секунду
            self._log_data()
            self.last_log_time = time.time()

        # Динамически регулируем интервал
        processing_time = time.time() - start_time
        next_interval = max(2, int(processing_time * 1000 * 1.1))  # +10% к времени обработки

        if self.window.winfo_exists():
            self.window.after(next_interval, self._start_background_tasks)

    def _check_connection(self):
        """Проверяет соединение с устройством"""
        if not self.controller._ensure_connection():
            self.append_command_log("Предупреждение: проблемы с соединением")
            print("Предупреждение: проблемы с соединением")

    def _send_command(self, register, value):
        """Отправляет команду устройству"""
        if self.controller.write_register(register, value):
            self.append_command_log(f"Команда отправлена: регистр 0x{register:02X}, значение 0x{value:04X}")
            print(f"Команда отправлена: регистр 0x{register:02X}, значение 0x{value:04X}")

    def _set_pressure(self):
        """Устанавливает давление"""
        try:
            value = int(float(self.set_pressure_var.get()) * 10)
            # status = self.controller.read_register(REG_STATUS)
            # if status is None:
            #     return

            # was_stab = False #status & 0x01
            # if was_stab:
            #     self.controller.write_register(REG_COMMAND, CMD_STOP)

            if self.controller.write_register(REG_SET_PRESSURE, value):
                self.append_command_log(f"Команда отправлена: регистр 0x{REG_SET_PRESSURE:02X}, значение 0x{value:04X}")
                self.append_command_log(f"Давление установлено: {value / 10} Pa")

            # if was_stab:
            #     self.controller.write_register(REG_COMMAND, CMD_START)
        except ValueError:
            self.append_command_log("Ошибка: введите число")

    def _read_pressure(self):
        """Читает текущее значение уставки давления"""
        value = self.controller.read_register(REG_SET_PRESSURE)
        if value is not None:
            self.set_pressure_var.set(str(value / 10))
            self.append_command_log(f"Команда отправлена: регистр 0x{REG_SET_PRESSURE:02X}, ответ 0x{value:04X}")
        else:
            self.append_command_log(f"Команда отправлена: регистр 0x{REG_SET_PRESSURE:02X}, ответа НЕТ")

    def _set_position(self):
        """Устанавливает позицию заслонки"""
        value = self.position_var_set.get()
        if self.controller.write_register(REG_SET_POSITION, value):
            self.append_command_log(f"Позиция установлена: {value}")
            self.append_command_log(f"Команда отправлена: регистр 0x{REG_SET_POSITION:02X}, ответ 0x{value:04X}")
        else:
            self.append_command_log(f"Команда отправлена: регистр 0x{REG_SET_POSITION:02X}, ответа НЕТ")

    def _set_position_var(self, value):
        """Меняет значение переменной с текстом установленного положения заслонки"""
        value = self.position_var_set.get()
        self.position_text_var_set.set(f"Позиция уст.: {value}")

    def _set_middle_position(self):
        """Устанавливает среднее положение заслонки без блокировки главного цикла"""
        value = self.controller.read_register(REG_STATUS)
        if value is None:
            self.append_command_log(f"Команда отправлена: регистр 0x{REG_STATUS:02X}, ответ 0x{value:04X}")
            return

        self.controller.write_register(REG_COMMAND, CMD_OPEN)
        self.append_command_log(f"Команда отправлена: регистр 0x{REG_COMMAND:02X}, значение  0x{CMD_OPEN:04X}")
        # Запускаем проверку каждые 1000 мс до наступления нужного статуса
        self.window.after(1000, self._check_and_set_middle)

    def _check_and_set_middle(self):
        """Проверяет, установлен ли нужный статус, и отправляет команду установки среднего положения"""
        status = self.controller.read_register(REG_STATUS)
        if status is not None and (status & 0x02):
            self.append_command_log(f"Команда отправлена: регистр 0x{REG_STATUS:02X}, ответ 0x{status:04X}")
            self.controller.write_register(REG_COMMAND, CMD_MIDDLE_POSITION)
            self.append_command_log(f"Команда отправлена: регистр 0x{REG_COMMAND:02X}, значение  0x{CMD_MIDDLE_POSITION:04X}")
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
            self.append_command_log(f"Ошибка при логировании данных: {e}")

    def _start_log(self, is_on):
        self.log_enable.set(is_on)

    def _rec_to_log(self, n):
        """Выполняет n измерений и сохраняет их в лог"""
        start_measurement_time = time.time()
        measurements = []

        while len(measurements) < n and time.time() - start_measurement_time < 60:
            # Получаем текущие значения
            temp = self.controller.read_register(REG_TEMPERATURE)
            pressure = self.controller.read_register(REG_MEASURED_PRESSURE)
            address, value = self.controller.position_queue.get()
            if address == REG_POSITION_LO:
                position_lo = value
                self.append_command_log(f'pos_lo: {position_lo}')
            elif address == REG_POSITION_HI:
                position_hi = value
                self.append_command_log(f'pos_hi: {position_hi}')
            position = (position_hi << 16) | position_lo
            status = self.controller.read_register(REG_STATUS)

            if None in (temp, pressure, position, status):
                continue  # Пропускаем если нет данных

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            measurements.append([
                current_time,
                temp / 10.0,  # Температура
                pressure / 10.0,  # Давление
                position,  # Позиция
                status  # Статус
            ])

            time.sleep(0.2)  # Интервал между измерениями

        # Сохраняем все измерения одним пакетом
        if measurements:
            try:
                for measurement in measurements:
                    self.logger.add_data(*measurement)
                self.logger.flush()  # Принудительно сохраняем
                self.append_command_log(f"Успешно сохранено {len(measurements)} измерений")
            except Exception as e:
                self.append_command_log(f"Ошибка при сохранении измерений: {e}")

    def append_command_log(self, message: str):
        """Добавляет строку в окно вывода команд"""
        self.command_output.configure(state='normal')
        self.command_output.insert('end', message + '\n')
        self.command_output.see('end')  # автопрокрутка
        self.command_output.configure(state='disabled')

    def on_close(self):
        """Обработчик закрытия окна"""
        self.logger.flush()  # Сохраняем данные перед выходом
        self.controller.disconnect()
        self.window.destroy()

    def run(self):
        """Запускает главный цикл приложения"""
        self.window.mainloop()