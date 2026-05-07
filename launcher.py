"""
Windows executable entry point.
PyInstaller bundles this file as RIS.exe.
Starts the Streamlit server and opens the browser automatically.
"""
import multiprocessing
import os
import sys
import threading
import time
import webbrowser


def _open_browser():
    time.sleep(4)
    webbrowser.open("http://localhost:8501")


def main():
    multiprocessing.freeze_support()

    if getattr(sys, "frozen", False):
        # Frozen: bundled files are in sys._MEIPASS, .exe lives in run_dir
        bundle_dir = sys._MEIPASS
        run_dir = os.path.dirname(sys.executable)
    else:
        bundle_dir = os.path.dirname(os.path.abspath(__file__))
        run_dir = bundle_dir

    # .env and db/chroma/ must resolve relative to the .exe, not the bundle
    os.chdir(run_dir)

    app_file = os.path.join(bundle_dir, "app_main.py")

    threading.Thread(target=_open_browser, daemon=True).start()

    from streamlit.web import cli as stcli

    sys.argv = [
        "streamlit", "run", app_file,
        "--global.developmentMode=false",
        "--server.headless=true",
        "--server.port=8501",
        "--browser.gatherUsageStats=false",
        "--server.fileWatcherType=none",
    ]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
