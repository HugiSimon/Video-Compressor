import tkinter as tk
from tkinter import ttk


class BitrateControl(ttk.Frame):
    """Composite widget: Scale + Spinbox synchronized via a shared IntVar."""

    MIN_VALUE = 50
    MAX_VALUE = 10000
    INCREMENT = 50

    def __init__(self, parent: tk.Widget, variable: tk.IntVar, on_change=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._var = variable
        self._on_change = on_change
        self._updating = False

        self._scale = ttk.Scale(
            self, from_=self.MIN_VALUE, to=self.MAX_VALUE, orient="horizontal",
            command=self._on_scale,
        )
        self._scale.set(self._var.get())
        self._scale.pack(side="left", fill="x", expand=True)

        self._spinbox = ttk.Spinbox(
            self, from_=self.MIN_VALUE, to=self.MAX_VALUE, increment=self.INCREMENT,
            width=6, command=self._on_spinbox,
        )
        self._spinbox.set(str(self._var.get()))
        self._spinbox.pack(side="left", padx=(6, 0))

        self._spinbox.bind("<Return>", lambda e: self._validate_spinbox())
        self._spinbox.bind("<FocusOut>", lambda e: self._validate_spinbox())

        self._label = ttk.Label(self, text=f"{self._var.get()} kb/s")
        self._label.pack(side="left", padx=(6, 0))

    def _clamp(self, value: int) -> int:
        return max(self.MIN_VALUE, min(self.MAX_VALUE, value))

    def _on_scale(self, val_str: str) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            value = self._clamp(int(float(val_str)))
            self._var.set(value)
            self._spinbox.set(str(value))
            self._label.configure(text=f"{value} kb/s")
            if self._on_change:
                self._on_change()
        finally:
            self._updating = False

    def _on_spinbox(self) -> None:
        if self._updating:
            return
        self._validate_spinbox()

    def _validate_spinbox(self) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            raw = self._spinbox.get()
            try:
                value = self._clamp(int(float(raw)))
            except (ValueError, TypeError):
                value = self._var.get()
            self._var.set(value)
            self._spinbox.set(str(value))
            self._scale.set(value)
            self._label.configure(text=f"{value} kb/s")
            if self._on_change:
                self._on_change()
        finally:
            self._updating = False

    def set_state(self, enabled: bool) -> None:
        state = ["!disabled"] if enabled else ["disabled"]
        try:
            self._scale.state(state)
        except Exception:
            pass
        try:
            self._spinbox.state(state)
        except Exception:
            pass
