# -*- coding: utf-8 -*-
import base64
import socket
import select
import threading
import os
import shutil
import subprocess
import re
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

TERMUX_CHROMIUM_BIN = "/data/data/com.termux/files/usr/bin/chromium"
TERMUX_CHROMEDRIVER_BIN = "/data/data/com.termux/files/usr/bin/chromedriver"
_CACHED_VERSION = None

def _resolve_browser_binary():
    """Return a usable Chrome/Chromium executable on Windows or Termux."""
    configured = os.environ.get("CHROME_BINARY") or os.environ.get("CHROMIUM_BINARY")
    if configured:
        configured = os.path.abspath(os.path.expandvars(os.path.expanduser(configured)))
        if os.path.isfile(configured):
            return configured
        raise FileNotFoundError(
            f"CHROME_BINARY/CHROMIUM_BINARY không tồn tại: {configured}"
        )

    candidates = [TERMUX_CHROMIUM_BIN]
    for command in (
        "chrome", "chrome.exe", "chromium", "chromium.exe",
        "chromium-browser", "google-chrome", "google-chrome-stable",
    ):
        found = shutil.which(command)
        if found:
            candidates.append(found)

    if os.name == "nt":
        candidates.extend([
            os.path.join(os.environ.get("PROGRAMFILES", ""),
                         "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", ""),
                         "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""),
                         "Google", "Chrome", "Application", "chrome.exe"),
        ])

    return next((path for path in candidates if path and os.path.isfile(path)), None)


def _resolve_driver_binary():
    """Use an installed driver when present; otherwise let Selenium Manager fetch it."""
    configured = os.environ.get("CHROMEDRIVER_BINARY") or os.environ.get("CHROMEDRIVER_BIN")
    if configured:
        configured = os.path.abspath(os.path.expandvars(os.path.expanduser(configured)))
        if os.path.isfile(configured):
            return configured
        raise FileNotFoundError(
            f"CHROMEDRIVER_BINARY/CHROMEDRIVER_BIN không tồn tại: {configured}"
        )

    candidates = [TERMUX_CHROMEDRIVER_BIN]
    installed = shutil.which("chromedriver") or shutil.which("chromedriver.exe")
    if installed:
        candidates.append(installed)
    return next((path for path in candidates if path and os.path.isfile(path)), None)


def _windows_chrome_version():
    if os.name != "nt":
        return None
    try:
        import winreg
        keys = (
            (winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Google\Chrome\BLBeacon"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Google\Chrome\BLBeacon"),
        )
        for hive, key_name in keys:
            try:
                with winreg.OpenKey(hive, key_name) as key:
                    version, _ = winreg.QueryValueEx(key, "version")
                if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", str(version)):
                    return str(version)
            except OSError:
                continue
    except (ImportError, OSError):
        pass
    return None


def _get_chromium_version(browser_binary=None):
    global _CACHED_VERSION
    if _CACHED_VERSION:
        return _CACHED_VERSION
    windows_version = _windows_chrome_version()
    if windows_version:
        _CACHED_VERSION = windows_version
        return _CACHED_VERSION
    try:
        if not browser_binary:
            raise FileNotFoundError("Không tìm thấy Chrome/Chromium")
        result = subprocess.run(
            [browser_binary, "--version"], capture_output=True, text=True, timeout=5
        )
        match = re.search(r'(\d+\.\d+\.\d+\.\d+)', result.stdout + result.stderr)
        if match:
            _CACHED_VERSION = match.group(1)
            return _CACHED_VERSION
    except Exception:
        pass
    _CACHED_VERSION = "120.0.6099.144"
    return _CACHED_VERSION

def _build_device_profile(version_str):
    major = version_str.split('.')[0]
    devices = [
        {"model": "SM-S918B", "android": "13", "w": 412, "h": 915},
        {"model": "SM-S921B", "android": "14", "w": 412, "h": 915},
        {"model": "Pixel 7",  "android": "13", "w": 412, "h": 915},
        {"model": "Pixel 8",  "android": "14", "w": 412, "h": 915},
        {"model": "2211133G", "android": "13", "w": 393, "h": 873},
        {"model": "CPH2449",  "android": "13", "w": 412, "h": 919},
    ]
    dev = random.choice(devices)
    ua = (
        f"Mozilla/5.0 (Linux; Android {dev['android']}; {dev['model']}) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{major}.0.0.0 Mobile Safari/537.36"
    )
    return {
        "ua": ua,
        "device": dev,
        "full_version": version_str,
    }

class _LocalProxyBridge:
    def __init__(self, ip, port, user, pw):
        self.ip, self.port = ip, int(port)
        tok = base64.b64encode(f"{user}:{pw}".encode()).decode()
        self.auth = f"Proxy-Authorization: Basic {tok}\r\n".encode()
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(32)
        self.port_local = self.srv.getsockname()[1]
        self._closed = False
        threading.Thread(target=self._loop, daemon=True).start()

    def close(self):
        self._closed = True
        try:
            self.srv.close()
        except Exception:
            pass

    def _loop(self):
        while not self._closed:
            try:
                c, _ = self.srv.accept()
                threading.Thread(target=self._h, args=(c,), daemon=True).start()
            except Exception:
                break

    def _h(self, c):
        u = None
        try:
            c.settimeout(20)
            d = b""
            while b"\r\n\r\n" not in d:
                k = c.recv(4096)
                if not k:
                    return
                d += k
            u = socket.create_connection((self.ip, self.port), timeout=20)
            i = d.find(b"\r\n")
            u.sendall(d[:i+2] + self.auth + d[i+2:] if i != -1 else d)
            while True:
                r, _, x = select.select([c, u], [], [c, u], 30)
                if x or not r:
                    break
                for s in r:
                    bf = s.recv(8192)
                    if not bf:
                        return
                    (u if s is c else c).sendall(bf)
        except Exception:
            pass
        finally:
            for s in (c, u):
                try:
                    if s:
                        s.close()
                except Exception:
                    pass

def _inject_stealth(driver, profile):
    w = profile["device"]["w"]
    h = profile["device"]["h"]
    # Sử dụng chuỗi thường và hàm replace để tránh lỗi cú pháp f-string
    stealth_js = """
    (() => {
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        for (const key in window) {
            if (/^cdc_|^__webdriver|^__selenium|^__fxdriver/.test(key)) {
                try { delete window[key]; } catch (e) {}
            }
        }
        Object.defineProperty(navigator, 'platform', { get: () => 'Linux armv81' });
        Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 5 });
        Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
        Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
        Object.defineProperty(navigator, 'languages', { get: () => ['vi-VN', 'vi', 'en-US', 'en'] });
        Object.defineProperty(window, 'outerWidth', { get: () => __WIDTH_VAL__ });
        Object.defineProperty(window, 'outerHeight', { get: () => __HEIGHT_VAL__ });

        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) return 'Google Inc. (ARM)';
            if (parameter === 37446) return 'ANGLE (ARM, Mali-G715 Immortalis MC10, OpenGL ES 3.2)';
            return getParameter.apply(this, arguments);
        };
    })();
    """
    stealth_js = stealth_js.replace("__WIDTH_VAL__", str(w)).replace("__HEIGHT_VAL__", str(h))
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": stealth_js})
    except Exception as exc:
        print(f"[WARN] Không thể tiêm CDP script: {exc}")

def create_session_driver(session_dir, proxy_info):
    profile_dir = os.path.join(session_dir, "chrome_profile")
    os.makedirs(profile_dir, exist_ok=True)
    options = webdriver.ChromeOptions()
    browser_binary = _resolve_browser_binary()
    if browser_binary:
        options.binary_location = browser_binary

    chromium_version = _get_chromium_version(browser_binary)
    profile = _build_device_profile(chromium_version)
    termux_mobile_viewport = (
        os.path.normpath(browser_binary or "") == os.path.normpath(TERMUX_CHROMIUM_BIN)
    )

    if termux_mobile_viewport:
        print(f"📱 Chromium {chromium_version} | Thiết bị: {profile['device']['model']}")
    else:
        print(
            f"🖥️ PC Viewport | "
            f"Fake Android {profile['device']['android']} {profile['device']['model']}"
        )

    if termux_mobile_viewport:
        mobile_emulation = {
            "deviceMetrics": {
                "width": profile["device"]["w"],
                "height": profile["device"]["h"],
                "pixelRatio": 3.0,
                "touch": True,
            },
            "userAgent": profile["ua"],
        }
        options.add_experimental_option("mobileEmulation", mobile_emulation)
        options.add_argument(f"--window-size={profile['device']['w']},{profile['device']['h']}")
    else:
        # Windows: giữ User-Agent/touch của điện thoại nhưng dùng viewport máy tính.
        # Nhờ vậy trang phủ hết màn hình thay vì bị bó trong khung 412 px.
        options.add_argument(f"--user-agent={profile['ua']}")
        options.add_argument("--touch-events=enabled")
        options.add_argument("--start-maximized")
    options.add_argument("--lang=vi-VN")

    options.add_experimental_option("prefs", {
        "webrtc.ip_handling_policy": "disable_non_proxied_udp",
        "webrtc.multiple_routes_enabled": False,
        "webrtc.nonproxied_udp_enabled": False,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
    })

    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    options.page_load_strategy = "eager"
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--user-data-dir={profile_dir}")

    bridge = None
    if proxy_info and proxy_info.get("ip") and proxy_info.get("port"):
        if proxy_info.get("user") and proxy_info.get("pass"):
            bridge = _LocalProxyBridge(proxy_info['ip'], proxy_info['port'], proxy_info['user'], proxy_info['pass'])
            options.add_argument(f"--proxy-server=http://127.0.0.1:{bridge.port_local}")
        else:
            options.add_argument(f"--proxy-server=http://{proxy_info['ip']}:{proxy_info['port']}")

    driver_binary = _resolve_driver_binary()
    # Không truyền executable_path trên PC: Selenium Manager sẽ tự lấy đúng
    # ChromeDriver theo phiên bản Chrome đang cài. Termux vẫn dùng driver hệ thống.
    service = Service(executable_path=driver_binary) if driver_binary else Service()
    try:
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        if bridge is not None:
            bridge.close()
        raise e

    if termux_mobile_viewport:
        _inject_stealth(driver, profile)
    else:
        try:
            driver.maximize_window()
            driver.execute_cdp_cmd(
                "Network.setUserAgentOverride",
                {"userAgent": profile["ua"], "platform": "Android"},
            )
            driver.execute_cdp_cmd(
                "Emulation.setTouchEmulationEnabled",
                {"enabled": True, "maxTouchPoints": 5},
            )
        except Exception as exc:
            print(f"[WARN] Không thể áp dụng đầy đủ giao diện PC/mobile: {exc}")

    if bridge is not None:
        orig_quit = driver.quit
        def _safe_quit():
            try:
                orig_quit()
            finally:
                bridge.close()
        driver.quit = _safe_quit

    return driver
