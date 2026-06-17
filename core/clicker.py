"""pyautogui click helpers."""
from __future__ import annotations

import time
from typing import Tuple

import pyautogui


def click_point(x: int, y: int) -> Tuple[bool, str]:
    """Click a single coordinate. Returns (success, error_msg)."""
    try:
        pyautogui.moveTo(x, y, duration=0.05)
        pyautogui.click()
        return True, ""
    except Exception as e:
        return False, str(e)


def click_with_delay(x: int, y: int, delay: float = 0.1) -> Tuple[bool, str]:
    """Click and pause."""
    ok, err = click_point(x, y)
    if ok and delay > 0:
        time.sleep(delay)
    return ok, err
