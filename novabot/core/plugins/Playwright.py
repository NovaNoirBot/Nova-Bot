"""
Copied from `SK-415`, `https://github.com/SK-415/HarukaBot`
"""

import sys
import os

from typing import Optional, Literal
from playwright.__main__ import main
from playwright.async_api import Browser, async_playwright, Playwright

from nonebot import get_driver

__all__ = ["get_firefox_browser", "get_chromium_browser"]

driver = get_driver()
sys.argv = ["", "install", "chromium"]
os.environ["PLAYWRIGHT_DOWNLOAD_HOST"] = "https://playwright.sk415.workers.dev"

PLAYWRIGHT: Optional[Playwright] = None
chromium_browser: Optional[Browser] = None
firefox_browser: Optional[Browser] = None


async def init_chromium(**kwargs) -> Browser:
    global PLAYWRIGHT
    if not PLAYWRIGHT:
        PLAYWRIGHT = await async_playwright().start()
    global chromium_browser
    chromium_browser = await PLAYWRIGHT.chromium.launch(**kwargs)
    return chromium_browser


async def get_chromium_browser(**kwargs) -> Browser:
    return chromium_browser or await init_chromium(**kwargs)


async def init_firefox(**kwargs) -> Browser:
    global PLAYWRIGHT
    if not PLAYWRIGHT:
        PLAYWRIGHT = await async_playwright().start()
    global firefox_browser
    firefox_browser = await PLAYWRIGHT.firefox.launch(**kwargs)
    return firefox_browser


async def get_firefox_browser(**kwargs) -> Browser:
    return firefox_browser or await init_firefox(**kwargs)


def install(browser: Literal["chromium", "firefox"] = "chromium"):
    """自动安装、更新 Chromium"""
    def restore_env():
        del os.environ["PLAYWRIGHT_DOWNLOAD_HOST"]
        if original_proxy is not None:
            os.environ["HTTPS_PROXY"] = original_proxy

    sys.argv = ["", "install", browser]
    original_proxy = os.environ.get("HTTPS_PROXY")
    os.environ["PLAYWRIGHT_DOWNLOAD_HOST"] = "https://playwright.sk415.workers.dev"
    success = False
    try:
        main()
    except SystemExit as e:
        if e.code == 0:
            success = True
    if not success:
        os.environ["PLAYWRIGHT_DOWNLOAD_HOST"] = ""
        try:
            main()
        except SystemExit as e:
            if e.code != 0:
                restore_env()
                raise RuntimeError("未知错误，Chromium 下载失败")
    restore_env()


async def init():
    install("chromium")
    install("firefox")
    await init_chromium()
    await init_firefox()

driver.on_startup(init)
