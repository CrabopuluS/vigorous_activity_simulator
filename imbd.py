# -*- coding: utf-8 -*-
"""
Имитатор бурной деятельности — миниатюрный джигглер мыши.
UI: tkinter (стандартная библиотека), движение мыши: pyautogui.
Запуск (Windows/Linux/macOS)
"""

from __future__ import annotations

import random
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Optional

import pyautogui
import tkinter as tk
from tkinter import ttk, messagebox


# Безопасность: при резком увода мыши в угол экрана PyAutoGUI прерывает работу (по умолчанию True).
pyautogui.FAILSAFE = True


@dataclass
class JiggleConfig:
    """Конфигурация для джигглера."""
    interval_sec: float = 30.0     # Пауза между движениями
    amplitude_px: int = 3          # Максимальный сдвиг по каждой оси (в пикселях)
    randomize: bool = True         # Случайность интервала и шага


class MouseJiggler(threading.Thread):
    """
    Поток, который чуть-чуть двигает мышь.
    """

    def __init__(self, get_config_callable, is_running_event: threading.Event):
        super().__init__(daemon=True)
        self._get_config = get_config_callable
        self._is_running_event = is_running_event
        self._stop_event = threading.Event()
        self._paused = threading.Event()
        self._paused.set()  # стартуем в режиме "пауза" (кнопкой включим)

    def run(self) -> None:
        while not self._stop_event.is_set():
            # Если на паузе — подождать и продолжить проверку.
            if self._paused.is_set():
                time.sleep(0.2)
                continue

            cfg: JiggleConfig = self._get_config()

            # Интервал ожидания перед следующим микродвижением.
            interval = cfg.interval_sec
            if cfg.randomize:
                # Лёгкая рандомизация, чтобы не было "идеальных" интервалов
                interval *= random.uniform(0.85, 1.15)

            slept = 0.0
            # Спим по кусочкам, чтобы быстро реагировать на паузу/стоп
            while slept < interval and not self._stop_event.is_set() and not self._paused.is_set():
                time.sleep(0.2)
                slept += 0.2

            if self._stop_event.is_set() or self._paused.is_set():
                continue

            try:
                # Мини-джиггл: смещаем курсор на 1–A пикселей и возвращаем
                dx = random.randint(1, max(1, cfg.amplitude_px)) * random.choice((-1, 1))
                dy = random.randint(1, max(1, cfg.amplitude_px)) * random.choice((-1, 1))
                x, y = pyautogui.position()
                pyautogui.moveTo(x + dx, y + dy, duration=0.05)
                # Небольшая задержка и возврат (вариант, чтобы не «уплывал»)
                time.sleep(0.05)
                pyautogui.moveTo(x, y, duration=0.05)
            except pyautogui.FailSafeException:
                # Пользователь дёрнул в угол — уважаем сигнал, ставим паузу
                self.pause()
            except Exception:
                # Не падаем: логируем и продолжаем
                traceback.print_exc()

    def start_work(self) -> None:
        self._paused.clear()

    def pause(self) -> None:
        self._paused.set()

    def stop(self) -> None:
        self._stop_event.set()
        # Снять паузу, чтобы поток мог завершиться, если завис на ожидании
        self._paused.clear()


class App(tk.Tk):

    APP_TITLE = "Имитатор бурной деятельности"

    def __init__(self):
        super().__init__()
        self.title(self.APP_TITLE)
        self.resizable(False, False)
        self.minsize(280, 220)

        # Центрируем окно
        self.update_idletasks()
        w, h = 300, 240
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        # Стиль
        self._init_style()

        # Состояние/конфиг
        self._config = JiggleConfig()
        self._is_running_event = threading.Event()

        # UI
        self._build_ui()

        # Воркер
        self._jiggler = MouseJiggler(self._get_config, self._is_running_event)
        self._jiggler.start()

        # Обработчик закрытия
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- UI ----------
    def _init_style(self) -> None:
        style = ttk.Style(self)
        # Встроенные темы: 'clam', 'alt', 'default', 'classic'
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass

        style.configure("TButton", padding=6)
        style.configure("TLabel", padding=2)
        style.configure("Status.TLabel", font=("Segoe UI", 9, "italic"))
        style.configure("Header.TLabel", font=("Segoe UI", 11, "bold"))

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 6}

        header = ttk.Label(self, text="Микродвижения курсора", style="Header.TLabel")
        header.pack(**pad)

        frm = ttk.Frame(self)
        frm.pack(fill="x", **pad)

        # Интервал
        ttk.Label(frm, text="Интервал (сек.):").grid(row=0, column=0, sticky="w")
        self.interval_var = tk.DoubleVar(value=self._config.interval_sec)
        interval_scale = ttk.Scale(
            frm, from_=2, to=120, orient="horizontal",
            variable=self.interval_var, command=lambda e: self._sync_interval_label()
        )
        interval_scale.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        self.interval_lbl = ttk.Label(frm, text=f"{int(self._config.interval_sec)}")
        self.interval_lbl.grid(row=0, column=2, sticky="e")
        frm.columnconfigure(1, weight=1)

        # Амплитуда
        ttk.Label(frm, text="Амплитуда (пикс.):").grid(row=1, column=0, sticky="w")
        self.amp_var = tk.IntVar(value=self._config.amplitude_px)
        amp_scale = ttk.Scale(
            frm, from_=1, to=10, orient="horizontal",
            variable=self.amp_var, command=lambda e: self._sync_amp_label()
        )
        amp_scale.grid(row=1, column=1, sticky="ew", padx=(8, 8))
        self.amp_lbl = ttk.Label(frm, text=f"{self._config.amplitude_px}")
        self.amp_lbl.grid(row=1, column=2, sticky="e")

        # Флажки
        self.random_var = tk.BooleanVar(value=self._config.randomize)
        chk_random = ttk.Checkbutton(self, text="Случайный паттерн", variable=self.random_var)
        chk_random.pack(anchor="w", **pad)

        self.topmost_var = tk.BooleanVar(value=False)
        chk_topmost = ttk.Checkbutton(
            self, text="Всегда сверху",
            variable=self.topmost_var,
            command=self._toggle_topmost
        )
        chk_topmost.pack(anchor="w", **pad)

        # Кнопки управления
        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=10, pady=(2, 6))

        self.toggle_btn = ttk.Button(btns, text="Старт", command=self._toggle)
        self.toggle_btn.pack(side="left", padx=(0, 6))

        pause_btn = ttk.Button(btns, text="Пауза", command=self._pause)
        pause_btn.pack(side="left", padx=(0, 6))

        quit_btn = ttk.Button(btns, text="Выход", command=self._on_close)
        quit_btn.pack(side="right")

        # Статус
        self.status_var = tk.StringVar(value="Статус: пауза")
        status = ttk.Label(self, textvariable=self.status_var, style="Status.TLabel")
        status.pack(anchor="w", padx=12, pady=(0, 6))

        ttk.Label(self, text="Подсказка: быстро остановить можно, резко уведя мышь в угол экрана.").pack(
            anchor="w", padx=12, pady=(0, 8)
        )

    def _sync_interval_label(self) -> None:
        self.interval_lbl.config(text=f"{int(self.interval_var.get())}")

    def _sync_amp_label(self) -> None:
        self.amp_lbl.config(text=f"{int(self.amp_var.get())}")

    def _toggle_topmost(self) -> None:
        self.attributes("-topmost", self.topmost_var.get())

    # ---------- Логика ----------
    def _get_config(self) -> JiggleConfig:
        # Чтение значений из UI — с простым ограничением диапазона
        interval = max(1.0, float(self.interval_var.get()))
        amp = max(1, int(self.amp_var.get()))
        randomize = bool(self.random_var.get())
        self._config.interval_sec = interval
        self._config.amplitude_px = amp
        self._config.randomize = randomize
        return self._config

    def _toggle(self) -> None:
        # Старт, если сейчас пауза; иначе поставить паузу
        if self.status_var.get().endswith("пауза"):
            self._jiggler.start_work()
            self._is_running_event.set()
            self.status_var.set("Статус: работает")
            self.toggle_btn.config(text="Пауза")
        else:
            self._jiggler.pause()
            self._is_running_event.clear()
            self.status_var.set("Статус: пауза")
            self.toggle_btn.config(text="Старт")

    def _pause(self) -> None:
        self._jiggler.pause()
        self._is_running_event.clear()
        self.status_var.set("Статус: пауза")
        self.toggle_btn.config(text="Старт")

    def _on_close(self) -> None:
        # Корректное завершение потока
        try:
            self._jiggler.stop()
        except Exception:
            pass
        self.destroy()

    # ---------- Хук для глобальных ошибок ----------
    def report_callback_exception(self, exc, val, tb):
        # Перехват исключений из обработчиков tkinter (чтобы не падало молча)
        traceback.print_exception(exc, val, tb)
        messagebox.showerror("Ошибка", f"{exc.__name__}: {val}")


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
