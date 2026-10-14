import webview
import threading
import logging
import keyboard as k
from ctypes import windll
import pythonnet  # <---- Hook for .NET framework

from src.main_layout import layout_func
from app import app
from src.diagnostics import configure_logging
from src.version import APP_VERSION


configure_logging()
logger = logging.getLogger("swampmachine.lifecycle")

logging.getLogger("werkzeug").setLevel(logging.ERROR)

app.layout = layout_func


def run_my_server():
    try:
        app.run(debug=False)
    except Exception:
        logger.exception("dash_server_failed")
        raise


run_in_web = False

# Run the app
if __name__ == "__main__":
    h = None
    try:
        # Disable ways of closing the app
        print("Running....")
        logger.info("application_started version=%s run_in_web=%s", APP_VERSION, run_in_web)
        k.block_key("alt")
        k.block_key("windows")
        h = windll.user32.FindWindowA(b"Shell_TrayWnd", None)
        windll.user32.ShowWindow(h, 0)

        if run_in_web:
            run_my_server()
        else:
            threading.Thread(target=run_my_server, daemon=True).start()
            webview.create_window(
                app.title,
                "http://127.0.0.1:8050",
                fullscreen=True,
                frameless=True,
                easy_drag=False,
                on_top=True,
            )
            webview.start()
    except Exception:
        logger.exception("application_failed")
        raise
    finally:
        # Re-enable all keys and taskbars even if startup or webview fails.
        k.unhook_all()
        if h is not None:
            windll.user32.ShowWindow(h, 9)
        logger.info("application_stopped")
