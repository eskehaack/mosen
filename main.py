import webview
import threading
import logging
import keyboard as k
from ctypes import windll
import pythonnet  # <---- Hook for .NET framework

from src.main_layout import layout_func
from app import app

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

app.layout = layout_func


def run_my_server():
    app.run(debug=False)


run_in_web = False

# Run the app
if __name__ == "__main__":

    # Disable ways of closing the app
    print("Running....")
    # k.block_key("alt")
    k.block_key("windows")
    h = windll.user32.FindWindowA(b"Shell_TrayWnd", None)
    windll.user32.ShowWindow(h, 0)

    if run_in_web:
        run_my_server()
    else:
        threading.Thread(target=run_my_server, daemon=True).start()
        webview.create_window(
            "Mosemaskinen",
            "http://127.0.0.1:8050",
            fullscreen=True,
            frameless=True,
            easy_drag=False,
            on_top=True,
        )
        webview.start()

    # Renable all keys and taskbars
    k.unhook_all()
    windll.user32.ShowWindow(h, 9)
