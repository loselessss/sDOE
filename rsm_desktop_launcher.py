from __future__ import annotations

import ctypes
from importlib.metadata import version
from logging.handlers import RotatingFileHandler
import logging
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen


APP_NAME = "sDOE - DOE RSM"


def executable_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


APP_ROOT = executable_dir()
PORTABLE_MODE = (APP_ROOT / "portable.flag").exists()
APP_DATA_DIR = (
    APP_ROOT / "data"
    if PORTABLE_MODE
    else Path(os.environ.get("LOCALAPPDATA", Path.home())) / "DOE RSM"
)
if PORTABLE_MODE:
    os.environ["RSM_PORTABLE_DATA_DIR"] = str(APP_DATA_DIR)
LOG_DIR = APP_DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "rsm_desktop.log"
MUTEX_NAME = "Local\\DOE_RSM_Analysis_App"


def configure_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("doe_rsm_desktop")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(threadName)s %(message)s")
        )
        logger.addHandler(handler)
    return logger


LOGGER = configure_logging()


def show_error(message: str) -> None:
    LOGGER.error(message)
    try:
        ctypes.windll.user32.MessageBoxW(0, message, APP_NAME, 0x10)
    except Exception:
        pass


def acquire_single_instance() -> object | None:
    kernel32 = ctypes.windll.kernel32
    kernel32.SetLastError(0)
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        return None
    if kernel32.GetLastError() == 183:
        kernel32.CloseHandle(handle)
        return None
    return handle


def resource_path(name: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return root / name


def available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def streamlit_server_main(script_path: Path, port: int) -> int:
    os.environ["RSM_APP_NO_AUTO_LAUNCH"] = "1"
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    os.environ["STREAMLIT_SERVER_ADDRESS"] = "127.0.0.1"
    os.environ["STREAMLIT_SERVER_PORT"] = str(port)
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
    LOGGER.info("Starting internal Streamlit server on 127.0.0.1:%s", port)
    try:
        from streamlit import config
        from streamlit.web import bootstrap

        flag_options = {
            "server_address": "127.0.0.1",
            "server_port": port,
            "server_headless": True,
            "server_fileWatcherType": "none",
            "browser_gatherUsageStats": False,
            "global_developmentMode": False,
        }
        bootstrap.load_config_options(flag_options)
        LOGGER.info(
            "Resolved Streamlit config address=%s port=%s headless=%s",
            config.get_option("server.address"),
            config.get_option("server.port"),
            config.get_option("server.headless"),
        )
        bootstrap.run(
            str(script_path),
            False,
            [],
            flag_options,
        )
        return 0
    except BaseException:
        LOGGER.exception("Streamlit server stopped unexpectedly")
        return 20


def start_streamlit(script_path: Path, port: int) -> subprocess.Popen[bytes]:
    if getattr(sys, "frozen", False):
        command = [
            sys.executable,
            "--streamlit-server",
            str(script_path),
            str(port),
        ]
    else:
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--streamlit-server",
            str(script_path),
            str(port),
        ]
    environment = os.environ.copy()
    environment["RSM_APP_NO_AUTO_LAUNCH"] = "1"
    environment["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    environment["STREAMLIT_SERVER_ADDRESS"] = "127.0.0.1"
    environment["STREAMLIT_SERVER_PORT"] = str(port)
    environment["STREAMLIT_SERVER_HEADLESS"] = "true"
    environment["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"
    environment["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
    server_log = open(LOG_DIR / "streamlit_server.log", "ab", buffering=0)
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=server_log,
            stderr=subprocess.STDOUT,
            env=environment,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        LOGGER.info("Spawned internal server PID %s on port %s", process.pid, port)
        return process
    finally:
        server_log.close()


def stop_streamlit(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=8.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5.0)


def wait_for_server(
    port: int,
    process: subprocess.Popen[bytes],
    timeout: float = 40.0,
) -> bool:
    health_url = f"http://127.0.0.1:{port}/_stcore/health"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            with urlopen(health_url, timeout=1.0) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


def run_self_test() -> int:
    import webview

    webview.settings["ALLOW_DOWNLOADS"] = True
    if not webview.settings["ALLOW_DOWNLOADS"]:
        LOGGER.error("Self-test failed: pywebview downloads are disabled")
        return 5

    script_path = resource_path("rsm_streamlit_app.py")
    if not script_path.exists():
        LOGGER.error("Self-test failed: app script is missing at %s", script_path)
        return 2
    port = available_port()
    process = start_streamlit(script_path, port)
    try:
        if not wait_for_server(port, process):
            LOGGER.error("Self-test failed: Streamlit did not become healthy")
            return 3
        with urlopen(f"http://127.0.0.1:{port}", timeout=5.0) as response:
            if response.status != 200:
                LOGGER.error("Self-test failed: app returned HTTP %s", response.status)
                return 4
        LOGGER.info(
            "Self-test passed with pywebview %s on port %s",
            version("pywebview"),
            port,
        )
        return 0
    finally:
        stop_streamlit(process)


def main() -> int:
    LOGGER.info("Starting %s; executable=%s", APP_NAME, sys.executable)
    if "--streamlit-server" in sys.argv:
        option_index = sys.argv.index("--streamlit-server")
        try:
            script_path = Path(sys.argv[option_index + 1])
            port = int(sys.argv[option_index + 2])
        except (IndexError, ValueError):
            LOGGER.error("Invalid internal server arguments: %r", sys.argv)
            return 21
        return streamlit_server_main(script_path, port)
    if "--self-test" in sys.argv:
        return run_self_test()

    mutex_handle = acquire_single_instance()
    if mutex_handle is None:
        show_error("sDOE is already running.\nDOE RSM 분석 앱이 이미 실행 중입니다.")
        return 1

    script_path = resource_path("rsm_streamlit_app.py")
    if not script_path.exists():
        show_error(f"Application file not found. / 앱 실행 파일을 찾을 수 없습니다.\n\n{script_path}\n\nLog / 로그: {LOG_FILE}")
        return 2

    server_process: subprocess.Popen[bytes] | None = None
    try:
        port = available_port()
        server_process = start_streamlit(script_path, port)
        if not wait_for_server(port, server_process):
            show_error(f"Could not start the analysis server. / 내부 분석 서버를 시작하지 못했습니다.\n\nLog / 로그: {LOG_FILE}")
            return 3

        import webview

        webview.settings["ALLOW_DOWNLOADS"] = True
        LOGGER.info("pywebview file downloads enabled")
        storage_path = APP_DATA_DIR / "webview"
        storage_path.mkdir(parents=True, exist_ok=True)
        webview.create_window(
            APP_NAME,
            f"http://127.0.0.1:{port}",
            width=1440,
            height=920,
            min_size=(1024, 700),
            resizable=True,
            text_select=True,
            zoomable=True,
        )
        webview.start(
            gui="edgechromium",
            private_mode=False,
            storage_path=str(storage_path),
            debug=False,
        )
        LOGGER.info("Desktop window closed normally")
        return 0
    except BaseException as exc:
        LOGGER.exception("Desktop application failed")
        show_error(f"Application error. / 앱 실행 중 오류가 발생했습니다.\n\n{exc}\n\nLog / 로그: {LOG_FILE}")
        return 10
    finally:
        stop_streamlit(server_process)
        try:
            ctypes.windll.kernel32.CloseHandle(mutex_handle)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
