import math
import time
from enum import Enum
import pyautogui


class PinchState(Enum):
    OPEN = "OPEN"
    PINCH_HOLD = "PINCH HOLD"
    DRAGGING = "DRAGGING"
    SCROLL = "SCROLL"


def is_finger_extended(
    points: list[tuple[int, int]], tip_idx: int, pip_idx: int, mcp_idx: int, wrist_idx: int = 0
) -> bool:
    """Checks if a finger is extended relative to the wrist and MCP geometry."""
    wrist = points[wrist_idx]
    tip = points[tip_idx]
    pip = points[pip_idx]
    mcp = points[mcp_idx]

    dist_tip_wrist = math.hypot(tip[0] - wrist[0], tip[1] - wrist[1])
    dist_pip_wrist = math.hypot(pip[0] - wrist[0], pip[1] - wrist[1])
    dist_tip_mcp = math.hypot(tip[0] - mcp[0], tip[1] - mcp[1])
    dist_pip_mcp = math.hypot(pip[0] - mcp[0], pip[1] - mcp[1])

    return (dist_tip_wrist > dist_pip_wrist) and (dist_tip_mcp > dist_pip_mcp)


def is_two_finger_scroll_pose(points: list[tuple[int, int]]) -> bool:
    """Checks if hand is in two-finger pose (Index & Middle extended, Ring & Pinky folded)."""
    if len(points) < 21:
        return False

    index_ext = is_finger_extended(points, tip_idx=8, pip_idx=6, mcp_idx=5)
    middle_ext = is_finger_extended(points, tip_idx=12, pip_idx=10, mcp_idx=9)
    ring_ext = is_finger_extended(points, tip_idx=16, pip_idx=14, mcp_idx=13)
    pinky_ext = is_finger_extended(points, tip_idx=20, pip_idx=18, mcp_idx=17)

    return index_ext and middle_ext and (not ring_ext) and (not pinky_ext)


class GestureDetector:
    """Detects pinch clicks, drag-and-drop, and two-finger scroll gestures."""

    def __init__(
        self,
        activation_threshold: float = 0.28,
        release_threshold: float = 0.38,
        drag_hold_time: float = 0.35,
        drag_move_threshold: float = 25.0,
        enabled: bool = True,
        scroll_enabled: bool = True,
    ):
        self.activation_threshold = activation_threshold
        self.release_threshold = release_threshold
        self.drag_hold_time = drag_hold_time
        self.drag_move_threshold = drag_move_threshold
        self.enabled = enabled
        self.scroll_enabled = scroll_enabled

        self.state = PinchState.OPEN
        self.pinch_start_time = 0.0
        self.start_screen_pos = None

        self.scroll_consecutive_frames = 0
        self.min_scroll_frames = 3

        self.click_flash_timer = 0
        self.drag_flash_timer = 0
        self.drop_flash_timer = 0

    def ensure_mouse_up(self):
        """Safety check to guarantee OS mouse button is released."""
        if self.state == PinchState.DRAGGING:
            try:
                pyautogui.mouseUp()
            except Exception as e:
                print(f"Mouse release error: {e}")
        self.state = PinchState.OPEN

    def toggle_enabled(self) -> bool:
        """Toggle click/drag gesture interactions ON/OFF."""
        self.enabled = not self.enabled
        if not self.enabled:
            self.ensure_mouse_up()
        return self.enabled

    def toggle_scroll_enabled(self) -> bool:
        """Toggle scrolling feature ON/OFF."""
        self.scroll_enabled = not self.scroll_enabled
        if not self.scroll_enabled and self.state == PinchState.SCROLL:
            self.state = PinchState.OPEN
            self.scroll_consecutive_frames = 0
        return self.scroll_enabled

    def reset(self):
        """Reset gesture state and release mouse if hand tracking is lost."""
        self.ensure_mouse_up()
        self.state = PinchState.OPEN
        self.pinch_start_time = 0.0
        self.start_screen_pos = None
        self.scroll_consecutive_frames = 0
        self.click_flash_timer = 0
        self.drag_flash_timer = 0
        self.drop_flash_timer = 0

    def update(
        self,
        points: list[tuple[int, int]],
        current_screen_pos: tuple[int, int] | None = None,
    ) -> tuple[PinchState, float, bool, bool, bool]:
        """Process 21 hand landmarks and current screen position.

        Returns (state, pinch_ratio, click_event, drag_start_event, drag_end_event).
        """
        if len(points) < 21:
            self.reset()
            return PinchState.OPEN, 0.0, False, False, False

        wrist = points[0]
        middle_mcp = points[9]
        thumb_tip = points[4]
        index_tip = points[8]

        # Calculate hand reference distance (Wrist #0 to Middle MCP #9)
        ref_dist = math.hypot(middle_mcp[0] - wrist[0], middle_mcp[1] - wrist[1])
        if ref_dist == 0:
            ref_dist = 1.0

        # Calculate pinch distance (Thumb tip #4 to Index tip #8)
        pinch_dist = math.hypot(index_tip[0] - thumb_tip[0], index_tip[1] - thumb_tip[1])
        pinch_ratio = pinch_dist / ref_dist

        click_event = False
        drag_start_event = False
        drag_end_event = False

        now = time.perf_counter()

        # Priority 1: DRAGGING & PINCH gestures (highest priority over scrolling)
        if self.state in (PinchState.PINCH_HOLD, PinchState.DRAGGING) or (pinch_ratio < self.activation_threshold and self.enabled):
            self.scroll_consecutive_frames = 0
            if self.state == PinchState.OPEN:
                if pinch_ratio < self.activation_threshold and self.enabled:
                    self.state = PinchState.PINCH_HOLD
                    self.pinch_start_time = now
                    self.start_screen_pos = current_screen_pos

            elif self.state == PinchState.PINCH_HOLD:
                if pinch_ratio > self.release_threshold:
                    # Quick pinch release -> Trigger LEFT CLICK
                    click_event = True
                    self.click_flash_timer = 12
                    self.state = PinchState.OPEN
                else:
                    elapsed = now - self.pinch_start_time
                    moved_dist = 0.0
                    if self.start_screen_pos and current_screen_pos:
                        moved_dist = math.hypot(
                            current_screen_pos[0] - self.start_screen_pos[0],
                            current_screen_pos[1] - self.start_screen_pos[1],
                        )

                    if elapsed >= self.drag_hold_time or moved_dist >= self.drag_move_threshold:
                        # Pinch held beyond duration or distance threshold -> Begin DRAG
                        drag_start_event = True
                        self.drag_flash_timer = 12
                        self.state = PinchState.DRAGGING

            elif self.state == PinchState.DRAGGING:
                if pinch_ratio > self.release_threshold:
                    # Pinch released after dragging -> Trigger DROP
                    drag_end_event = True
                    self.drop_flash_timer = 12
                    self.state = PinchState.OPEN

        # Priority 2: TWO-FINGER SCROLL GESTURE
        elif self.scroll_enabled and is_two_finger_scroll_pose(points):
            self.scroll_consecutive_frames += 1
            if self.scroll_consecutive_frames >= self.min_scroll_frames:
                self.state = PinchState.SCROLL

        # Priority 3: OPEN (Cursor mode)
        else:
            if self.scroll_consecutive_frames > 0:
                self.scroll_consecutive_frames -= 1
            if self.scroll_consecutive_frames == 0 and self.state == PinchState.SCROLL:
                self.state = PinchState.OPEN

        # Decrement flash timers
        if self.click_flash_timer > 0:
            self.click_flash_timer -= 1
        if self.drag_flash_timer > 0:
            self.drag_flash_timer -= 1
        if self.drop_flash_timer > 0:
            self.drop_flash_timer -= 1

        return self.state, pinch_ratio, click_event, drag_start_event, drag_end_event
