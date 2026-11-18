"""En vanlig (headless) webbläsare som hämtar sidor i lugn takt."""
from __future__ import annotations

import os
import time
from contextlib import contextmanager

from playwright.sync_api import sync_playwright

PAUS_SEKUNDER = 1.0  # var snäll mot sajterna


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
