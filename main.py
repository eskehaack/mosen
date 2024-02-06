import webview
import threading
import logging

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
    print("Running....")
    if run_in_web:
        app.run(debug=False)
    else:
        threading.Thread(target=run_my_server, daemon=True).start()
        webview.create_window(
            "The Swamp Machine",
            "http://127.0.0.1:8050",
            fullscreen=True,
            frameless=True,
            easy_drag=False,
            on_top=True,
        )
        webview.start()
