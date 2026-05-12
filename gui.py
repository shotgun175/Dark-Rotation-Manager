"""
gui.py - Dark Rotation Manager GUI entry point

Usage:
    python gui.py
"""

import sys
import os
import ctypes
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from modules.gui_app import ConfigApp
from modules.paths import get_base_dir, get_resource, ensure_user_files

# Tell Windows this is a standalone app so it gets its own taskbar icon
# (without this, Windows groups it under the generic Python process)
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DarkRotationBot.DarkTimer")
except Exception:
    pass

BASE_DIR = get_base_dir()


def main():
    ensure_user_files(BASE_DIR)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    icon_path = get_resource(os.path.join("assets", "icon.ico"))
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    config_path = os.path.join(BASE_DIR, "config.yaml")
    window = ConfigApp(config_path)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
