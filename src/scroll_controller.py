import time
import pyautogui

# Disable default PyAutoGUI latency between calls for smooth real-time control
pyautogui.PAUSE = 0


class ScrollController:
    """Handles rate-limited, threshold-filtered two-finger scrolling using PyAutoGUI."""

    def __init__(
        self,
        movement_threshold: float = 8.0,
        sensitivity: float = 5.0,
        cooldown: float = 0.04,
        enabled: bool = True,
    ):
        self.movement_threshold = movement_threshold
        self.sensitivity = sensitivity
        self.cooldown = cooldown
        self.enabled = enabled

        self.prev_y = None
        self.last_scroll_time = 0.0
        self.accumulated_dy = 0.0
        self.last_scroll_direction = None  # "UP", "DOWN", or None
        self.scroll_flash_timer = 0

    def toggle_enabled(self) -> bool:
        """Toggle scrolling feature ON/OFF."""
        self.enabled = not self.enabled
        if not self.enabled:
            self.reset()
        return self.enabled

    def reset(self):
        """Reset scroll tracking reference and state."""
        self.prev_y = None
        self.accumulated_dy = 0.0
        self.last_scroll_direction = None
        self.scroll_flash_timer = 0

    def update(self, index_tip: tuple[int, int], middle_tip: tuple[int, int]) -> str | None:
        """Process two-finger vertical position and perform scrolling.

        Returns scroll direction ("UP" or "DOWN") if scroll triggered, else None.
        """
        if not self.enabled:
            return None

        current_y = (index_tip[1] + middle_tip[1]) / 2.0
        now = time.perf_counter()

        if self.prev_y is None:
            self.prev_y = current_y
            return None

        dy = current_y - self.prev_y
        self.prev_y = current_y
        self.accumulated_dy += dy

        direction = None

        # Check threshold and cooldown rate limiting
        if (now - self.last_scroll_time) >= self.cooldown:
            if abs(self.accumulated_dy) >= self.movement_threshold:
                # In image coordinates, Y increases downward.
                # Moving fingers UP -> dy < 0 -> scroll UP (positive pyautogui amount)
                # Moving fingers DOWN -> dy > 0 -> scroll DOWN (negative pyautogui amount)
                scroll_amount = int(-self.accumulated_dy * self.sensitivity)

                if scroll_amount != 0:
                    try:
                        pyautogui.scroll(scroll_amount)
                    except Exception as e:
                        print(f"Scroll error: {e}")

                    direction = "UP" if scroll_amount > 0 else "DOWN"
                    self.last_scroll_direction = direction
                    self.scroll_flash_timer = 10
                    self.last_scroll_time = now
                    self.accumulated_dy = 0.0

        if self.scroll_flash_timer > 0:
            self.scroll_flash_timer -= 1
        else:
            self.last_scroll_direction = None

        return direction
