"""
Copied from `SK-415`, `https://github.com/SK-415/HarukaBot`
"""

import os
import sys
from typing import Optional, Literal, Dict

from playwright.__main__ import main
from playwright.async_api import Browser, async_playwright, Playwright

__all__ = ["get_firefox_browser", "get_chromium_browser"]

sys.argv = ["", "install", "chromium"]

PLAYWRIGHT: Optional[Playwright] = None
chromium_browser: Optional[Browser] = None
firefox_browser: Optional[Browser] = None
success: Optional[Dict[Literal['chromium', 'firefox'], bool]] = {
    "chromium": False,
    "firefox": False
}


async def init_chromium(**kwargs) -> Browser:
    if not success['chromium']:
        install('chromium')
    global PLAYWRIGHT
    if not PLAYWRIGHT:
        PLAYWRIGHT = await async_playwright().start()
    global chromium_browser
    chromium_browser = await PLAYWRIGHT.chromium.launch(**kwargs)
    return chromium_browser


async def get_chromium_browser(**kwargs) -> Browser:
    return chromium_browser or await init_chromium(**kwargs)


async def init_firefox(**kwargs) -> Browser:
    if not success['firefox']:
        install('firefox')
    global PLAYWRIGHT
    if not PLAYWRIGHT:
        PLAYWRIGHT = await async_playwright().start()
    global firefox_browser
    firefox_browser = await PLAYWRIGHT.firefox.launch(**kwargs)
    return firefox_browser


async def get_firefox_browser(**kwargs) -> Browser:
    return firefox_browser or await init_firefox(**kwargs)


def install(browser: Literal["chromium", "firefox"] = "chromium"):
    """自动安装、更新浏览器"""

    def restore_env():
        if original_proxy is not None:
            os.environ["HTTPS_PROXY"] = original_proxy

    sys.argv = ["", "install", browser]
    original_proxy = os.environ.get("HTTPS_PROXY")
    global success
    success[browser] = False
    try:
        main()
    except SystemExit as e:
        if e.code == 0:
            success[browser] = True
    if not success[browser]:
        os.environ["PLAYWRIGHT_DOWNLOAD_HOST"] = ""
        try:
            main()
        except SystemExit as e:
            if e.code != 0:
                restore_env()
                raise RuntimeError(f"未知错误，{browser} 下载失败")
    restore_env()

