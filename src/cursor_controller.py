import math
import numpy as np
import pyautogui

# Disable default PyAutoGUI latency between calls for smooth real-time control
pyautogui.PAUSE = 0


class CursorController:
    """Handles active region mapping, smoothing, dead-zone filtering, and mouse cursor movement."""

    def __init__(
        self,
        margin_x: int = 60,
        margin_y: int = 40,
        alpha: float = 0.25,
        dead_zone: float = 4.0,
        enabled: bool = True,
    ):
        self.screen_width, self.screen_height = pyautogui.size()
        self.margin_x = margin_x
        self.margin_y = margin_y
        self.alpha = alpha
        self.dead_zone = dead_zone
        self.enabled = enabled

        self.prev_smooth_x = None
        self.prev_smooth_y = None

    def get_active_region(self, frame_width: int, frame_height: int):
        """Returns the inner active region coordinates (left, top, right, bottom)."""
        left = self.margin_x
        right = max(left + 1, frame_width - self.margin_x)
        top = self.margin_y
        bottom = max(top + 1, frame_height - self.margin_y)
        return left, top, right, bottom

    def reset(self):
        """Reset internal smoothing state (e.g. when hand is lost)."""
        self.prev_smooth_x = None
        self.prev_smooth_y = None

    def toggle_enabled(self) -> bool:
        """Toggle cursor control ON/OFF."""
        self.enabled = not self.enabled
        return self.enabled

    def update(
        self,
        index_x: int,
        index_y: int,
        frame_width: int,
        frame_height: int,
        freeze_cursor: bool = False,
    ) -> tuple[int, int]:
        """Maps camera index fingertip position to screen coordinates with smoothing and dead zone.

        If freeze_cursor is True, holds cursor position static (e.g. during pending click evaluation).
        Returns (screen_x, screen_y).
        """
        left, top, right, bottom = self.get_active_region(frame_width, frame_height)

        # Clamp camera coordinates within the active tracking region
        clamped_x = max(left, min(index_x, right))
        clamped_y = max(top, min(index_y, bottom))

        # Map active region to screen dimensions using NumPy interpolation
        target_x = float(
            np.interp(clamped_x, [left, right], [0, self.screen_width - 1])
        )
        target_y = float(
            np.interp(clamped_y, [top, bottom], [0, self.screen_height - 1])
        )

        # Exponential Moving Average (EMA) smoothing
        if self.prev_smooth_x is None or self.prev_smooth_y is None:
            smooth_x = target_x
            smooth_y = target_y
        elif freeze_cursor:
            # Freeze cursor position during pending click evaluation
            smooth_x = self.prev_smooth_x
            smooth_y = self.prev_smooth_y
        else:
            smooth_x = self.alpha * target_x + (1.0 - self.alpha) * self.prev_smooth_x
            smooth_y = self.alpha * target_y + (1.0 - self.alpha) * self.prev_smooth_y

            # Dead zone filter: suppress tiny movements below threshold
            dist = math.hypot(
                smooth_x - self.prev_smooth_x, smooth_y - self.prev_smooth_y
            )
            if dist < self.dead_zone:
                smooth_x = self.prev_smooth_x
                smooth_y = self.prev_smooth_y

        self.prev_smooth_x = smooth_x
        self.prev_smooth_y = smooth_y

        # Clamp screen coordinates safely within bounds
        screen_x = int(max(0, min(smooth_x, self.screen_width - 1)))
        screen_y = int(max(0, min(smooth_y, self.screen_height - 1)))

        # Perform mouse movement if cursor control is enabled
        if self.enabled:
            try:
                pyautogui.moveTo(screen_x, screen_y)
            except pyautogui.FailSafeException:
                pass
            except Exception as e:
                print(f"Cursor move error: {e}")

        return screen_x, screen_y


