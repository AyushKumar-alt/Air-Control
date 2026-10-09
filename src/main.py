import time
from pathlib import Path
import cv2
import mediapipe as mp
import pyautogui
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from cursor_controller import CursorController
from gesture_detector import GestureDetector, PinchState
from scroll_controller import ScrollController

# Hand connections for standard 21 MediaPipe hand landmarks
HAND_CONNECTIONS = [
    # Thumb
    (0, 1), (1, 2), (2, 3), (3, 4),
    # Index finger
    (0, 5), (5, 6), (6, 7), (7, 8),
    # Middle finger
    (5, 9), (9, 10), (10, 11), (11, 12),
    # Ring finger
    (9, 13), (13, 14), (14, 15), (15, 16),
    # Pinky finger
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),
    # Palm connections
    (5, 9), (9, 13)
]


def main():
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    model_path = project_root / "models" / "hand_landmarker.task"

    if not model_path.exists():
        print(f"Error: Model file not found at '{model_path}'")
        return

    # Initialize MediaPipe HandLandmarker in VIDEO mode
    base_options = python.BaseOptions(model_asset_path=str(model_path))
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.6,
        min_hand_presence_confidence=0.6,
        min_tracking_confidence=0.6,
    )

    detector = vision.HandLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("AirControl could not access the webcam.")
        detector.close()
        return

    # Initialize Controllers & Detectors
    cursor_controller = CursorController(
        margin_x=60,
        margin_y=40,
        alpha=0.25,
        dead_zone=4.0,
        enabled=True,
    )

    gesture_detector = GestureDetector(
        activation_threshold=0.28,
        release_threshold=0.38,
        drag_hold_time=0.35,
        drag_move_threshold=25.0,
        enabled=True,
        scroll_enabled=True,
    )

    scroll_controller = ScrollController(
        movement_threshold=8.0,
        sensitivity=5.0,
        cooldown=0.04,
        enabled=True,
    )

    print("AirControl Stage 6 started")
    print("Show your hand to the camera.")
    print("Quick pinch + release -> LEFT CLICK")
    print("Pinch + hold -> DRAG, release -> DROP")
    print("Index + Middle extended -> SCROLL MODE")
    print("Press C to toggle cursor control ON/OFF.")
    print("Press P to toggle click/drag interactions ON/OFF.")
    print("Press S to toggle scroll mode ON/OFF.")
    print("Press Q to quit.")

    last_timestamp_ms = 0
    prev_frame_time = time.perf_counter()
    current_screen_pos = (cursor_controller.screen_width // 2, cursor_controller.screen_height // 2)
    prev_gesture_state = PinchState.OPEN

    try:
        while True:
            success, frame = cap.read()
            if not success:
                print("Failed to capture frame.")
                break

            current_time = time.perf_counter()
            fps = 1.0 / (current_time - prev_frame_time) if (current_time - prev_frame_time) > 0 else 0
            prev_frame_time = current_time

            # Mirror image horizontally
            frame = cv2.flip(frame, 1)
            height, width, _ = frame.shape

            # Convert BGR to RGB for MediaPipe
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            # Generate monotonically increasing timestamp in milliseconds
            frame_timestamp_ms = int(time.perf_counter() * 1000)
            if frame_timestamp_ms <= last_timestamp_ms:
                frame_timestamp_ms = last_timestamp_ms + 1
            last_timestamp_ms = frame_timestamp_ms

            # Perform detection in VIDEO mode
            result = detector.detect_for_video(mp_image, frame_timestamp_ms)

            # Draw Active Tracking Region Box
            left, top, right, bottom = cursor_controller.get_active_region(width, height)
            cv2.rectangle(frame, (left, top), (right, bottom), (255, 255, 0), 2)
            cv2.putText(
                frame,
                "ACTIVE REGION",
                (left + 5, top + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 0),
                1,
            )

            # HUD Header
            cv2.putText(
                frame,
                "AirControl | Multi-Gesture Control",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (0, 255, 0),
                2,
            )

            # Status Indicators (Top Right)
            cursor_status_str = "CURSOR: ON" if cursor_controller.enabled else "CURSOR: OFF"
            cursor_color = (0, 255, 0) if cursor_controller.enabled else (0, 165, 255)
            cv2.putText(
                frame,
                cursor_status_str,
                (width - 180, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                cursor_color,
                2,
            )

            click_status_str = "CLICK: ON" if gesture_detector.enabled else "CLICK: OFF"
            click_color = (0, 255, 0) if gesture_detector.enabled else (0, 165, 255)
            cv2.putText(
                frame,
                click_status_str,
                (width - 180, 48),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                click_color,
                2,
            )

            scroll_status_str = "SCROLL: ON" if gesture_detector.scroll_enabled else "SCROLL: OFF"
            scroll_color = (0, 255, 0) if gesture_detector.scroll_enabled else (0, 165, 255)
            cv2.putText(
                frame,
                scroll_status_str,
                (width - 180, 71),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                scroll_color,
                2,
            )

            # FPS Display
            cv2.putText(
                frame,
                f"FPS: {int(fps)}",
                (width - 180, 94),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )

            if result.hand_landmarks and len(result.hand_landmarks) > 0:
                cv2.putText(
                    frame,
                    "HAND DETECTED",
                    (20, 65),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 255, 0),
                    2,
                )

                hand_landmarks = result.hand_landmarks[0]

                # Convert normalized landmarks to pixel coordinates
                points = []
                for lm in hand_landmarks:
                    px = int(lm.x * width)
                    py = int(lm.y * height)
                    points.append((px, py))

                # Update gesture state machine
                (
                    pinch_state,
                    pinch_ratio,
                    click_event,
                    drag_start_event,
                    drag_end_event,
                ) = gesture_detector.update(points, current_screen_pos)

                # Reset cursor smoothing when exiting scroll mode to avoid jumps
                if prev_gesture_state == PinchState.SCROLL and pinch_state != PinchState.SCROLL:
                    cursor_controller.reset()
                    scroll_controller.reset()
                prev_gesture_state = pinch_state

                # Execute OS Mouse Actions
                if gesture_detector.enabled:
                    if click_event:
                        try:
                            pyautogui.click()
                        except pyautogui.FailSafeException:
                            pass
                        except Exception as e:
                            print(f"Click error: {e}")
                    elif drag_start_event:
                        try:
                            pyautogui.mouseDown()
                        except pyautogui.FailSafeException:
                            pass
                        except Exception as e:
                            print(f"MouseDown error: {e}")

                if drag_end_event:
                    try:
                        pyautogui.mouseUp()
                    except pyautogui.FailSafeException:
                        pass
                    except Exception as e:
                        print(f"MouseUp error: {e}")

                # Process Scrolling if in SCROLL state
                scroll_direction = None
                if pinch_state == PinchState.SCROLL:
                    scroll_direction = scroll_controller.update(points[8], points[12])
                else:
                    scroll_controller.reset()

                # Draw skeleton (green lines)
                for start_idx, end_idx in HAND_CONNECTIONS:
                    cv2.line(frame, points[start_idx], points[end_idx], (0, 255, 0), 2)

                # Visual Highlights based on Gesture State
                if pinch_state == PinchState.DRAGGING:
                    cv2.line(frame, points[4], points[8], (0, 0, 255), 5)
                elif pinch_state == PinchState.PINCH_HOLD:
                    cv2.line(frame, points[4], points[8], (0, 255, 255), 3)
                elif pinch_state == PinchState.SCROLL:
                    # Highlight line between Index tip #8 and Middle tip #12
                    cv2.line(frame, points[8], points[12], (255, 255, 0), 3)
                    # Highlight Middle tip #12 in Cyan
                    cv2.circle(frame, points[12], 12, (255, 255, 0), -1)

                # Draw all 21 landmarks as small green circles
                for px, py in points:
                    cv2.circle(frame, (px, py), 5, (0, 255, 0), -1)

                # Highlight Thumb fingertip (landmark #4) - Purple/Magenta
                thumb_x, thumb_y = points[4]
                cv2.circle(frame, (thumb_x, thumb_y), 12, (255, 0, 255), -1)

                # Highlight Index fingertip (landmark #8) - Red
                index_x, index_y = points[8]
                cv2.circle(frame, (index_x, index_y), 12, (0, 0, 255), -1)

                # Freeze cursor during PINCH_HOLD evaluation or SCROLL mode
                freeze_cursor = (pinch_state in (PinchState.PINCH_HOLD, PinchState.SCROLL))
                current_screen_pos = cursor_controller.update(
                    index_x, index_y, width, height, freeze_cursor=freeze_cursor
                )
                screen_x, screen_y = current_screen_pos

                # Determine Mode Display String
                if pinch_state == PinchState.SCROLL:
                    mode_str = "Mode: SCROLL"
                    mode_color = (255, 255, 0)
                elif pinch_state == PinchState.DRAGGING:
                    mode_str = "Mode: DRAG"
                    mode_color = (0, 0, 255)
                elif pinch_state == PinchState.PINCH_HOLD:
                    mode_str = "Mode: CLICK HOLD"
                    mode_color = (0, 255, 255)
                else:
                    mode_str = "Mode: CURSOR"
                    mode_color = (255, 255, 255)

                cv2.putText(
                    frame,
                    mode_str,
                    (20, 95),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    mode_color,
                    2,
                )

                cv2.putText(
                    frame,
                    f"Pinch Ratio: {pinch_ratio:.2f}",
                    (20, 120),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (255, 255, 255),
                    1,
                )

                cv2.putText(
                    frame,
                    f"Index camera coordinate: ({index_x}, {index_y})",
                    (20, 145),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (255, 255, 255),
                    1,
                )

                cv2.putText(
                    frame,
                    f"Mapped screen coordinate: ({screen_x}, {screen_y})",
                    (20, 170),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (255, 255, 0),
                    1,
                )

                # Visual HUD Notifications
                if gesture_detector.click_flash_timer > 0:
                    cv2.putText(
                        frame,
                        "*** LEFT CLICK ***",
                        (width // 2 - 120, 110),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.85,
                        (0, 255, 255),
                        3,
                    )
                elif gesture_detector.drag_flash_timer > 0 or pinch_state == PinchState.DRAGGING:
                    cv2.putText(
                        frame,
                        "*** DRAGGING ***",
                        (width // 2 - 110, 110),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.85,
                        (0, 0, 255),
                        3,
                    )
                elif gesture_detector.drop_flash_timer > 0:
                    cv2.putText(
                        frame,
                        "*** DROP ***",
                        (width // 2 - 80, 110),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.85,
                        (0, 255, 0),
                        3,
                    )
                elif scroll_controller.last_scroll_direction:
                    scroll_text = f"SCROLL {scroll_controller.last_scroll_direction}"
                    cv2.putText(
                        frame,
                        scroll_text,
                        (width // 2 - 80, 110),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.85,
                        (255, 255, 0),
                        3,
                    )
            else:
                cursor_controller.reset()
                gesture_detector.reset()
                scroll_controller.reset()
                cv2.putText(
                    frame,
                    "NO HAND DETECTED",
                    (20, 65),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 0, 255),
                    2,
                )

            cv2.imshow("AirControl", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == ord("Q"):
                break
            elif key == ord("c") or key == ord("C"):
                new_state = cursor_controller.toggle_enabled()
                print(f"Cursor control toggled: {'ENABLED' if new_state else 'DISABLED'}")
            elif key == ord("p") or key == ord("P"):
                new_state = gesture_detector.toggle_enabled()
                print(f"Click/drag interactions toggled: {'ENABLED' if new_state else 'DISABLED'}")
            elif key == ord("s") or key == ord("S"):
                new_gesture_scroll = gesture_detector.toggle_scroll_enabled()
                scroll_controller.toggle_enabled()
                print(f"Scroll mode toggled: {'ENABLED' if new_gesture_scroll else 'DISABLED'}")
    finally:
        gesture_detector.ensure_mouse_up()
        scroll_controller.reset()
        detector.close()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()