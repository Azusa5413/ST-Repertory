from __future__ import annotations

import importlib


if __name__ == "__main__":
    gui_module = importlib.import_module("strepertory.gui_qt")
    gui_module.launch_gui()
