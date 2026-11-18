"""En vanlig (headless) webbläsare som hämtar sidor i lugn takt."""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from contextlib import contextmanager

from playwright.sync_api import sync_playwright

PAUS_SEKUNDER = 1.0  # var snäll mot sajterna
FELSOK = Path(os.environ.get("FELSOK_MAPP", "felsokning"))
log = logging.getLogger(__name__)


@contextmanager
def browser():
    with sync_playwright() as pw:
        kwargs = {}
        if os.environ.get("CHROMIUM_PATH"):
            kwargs["executable_path"] = os.environ["CHROMIUM_PATH"]
        b = pw.chromium.launch(**kwargs)
        try:
            ctx = b.new_context(locale="sv-SE")
            yield ctx
        finally:
            b.close()


def pause():
    time.sleep(PAUS_SEKUNDER)


def felsok(page, namn: str) -> None:
    """Sparar skärmbild och text från sidan när något går fel, för att se varför."""
    try:
        FELSOK.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(FELSOK / f"{namn}.png"), full_page=True)
        (FELSOK / f"{namn}.html").write_text(page.content(), encoding="utf-8")
        text = page.inner_text("body")[:500].replace("\n", " | ")
        log.error("Sidan %s hade titeln %r. Början av texten: %s", page.url, page.title(), text)
    except Exception as e:  # noqa: BLE001
        log.error("Kunde inte spara felsökning: %s", e)
