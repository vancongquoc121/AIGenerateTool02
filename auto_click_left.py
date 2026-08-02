"""Tự động click chuột vào vùng bên trái màn hình.

Yêu cầu cài đặt thư viện pyautogui (chưa có trong requirements.txt của dự án):
    pip install pyautogui
"""

import time

import pyautogui


def click_left_screen(y_ratio: float = 0.5, x_ratio: float = 0.25) -> tuple[int, int]:
    """Click chuột vào vùng bên trái màn hình.

    Args:
        y_ratio: Vị trí theo chiều dọc, tính theo tỉ lệ chiều cao màn hình (0.0 -> 1.0).
        x_ratio: Vị trí theo chiều ngang, tính theo tỉ lệ chiều rộng màn hình,
            nên để < 0.5 để nằm ở nửa trái màn hình.

    Returns:
        Toạ độ (x, y) đã click.
    """
    screen_width, screen_height = pyautogui.size()
    x = int(screen_width * x_ratio)
    y = int(screen_height * y_ratio)

    pyautogui.moveTo(x, y, duration=0.2)
    pyautogui.click(x, y)
    return x, y


def click_left_screen_forever(
    interval: float = 10.0,
    y_ratio: float = 0.5,
    x_ratio: float = 0.25,
) -> None:
    """Click liên tục, mãi mãi vào vùng bên trái màn hình.

    Args:
        interval: Số giây nghỉ giữa 2 lần click.
        y_ratio: Vị trí theo chiều dọc, tính theo tỉ lệ chiều cao màn hình (0.0 -> 1.0).
        x_ratio: Vị trí theo chiều ngang, tính theo tỉ lệ chiều rộng màn hình.

    Nhấn Ctrl+C trong terminal để dừng lại.
    """
    print("Đang click liên tục vào bên trái màn hình. Nhấn Ctrl+C để dừng...")
    try:
        while True:
            x, y = click_left_screen(y_ratio=y_ratio, x_ratio=x_ratio)
            print(f"Đã click tại: ({x}, {y})")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nĐã dừng click.")


def click_right_screen(y_ratio: float = 0.5, x_ratio: float = 0.75) -> tuple[int, int]:
    """Click chuột vào vùng bên phải màn hình.

    Args:
        y_ratio: Vị trí theo chiều dọc, tính theo tỉ lệ chiều cao màn hình (0.0 -> 1.0).
        x_ratio: Vị trí theo chiều ngang, tính theo tỉ lệ chiều rộng màn hình,
            nên để > 0.5 để nằm ở nửa phải màn hình.

    Returns:
        Toạ độ (x, y) đã click.
    """
    screen_width, screen_height = pyautogui.size()
    x = int(screen_width * x_ratio)
    y = int(screen_height * y_ratio)

    pyautogui.moveTo(x, y, duration=0.2)
    pyautogui.click(x, y)
    return x, y


def click_right_screen_forever(
    interval: float = 30.0,
    y_ratio: float = 0.5,
    x_ratio: float = 0.75,
) -> None:
    """Click liên tục, mãi mãi vào vùng bên phải màn hình.

    Args:
        interval: Số giây nghỉ giữa 2 lần click.
        y_ratio: Vị trí theo chiều dọc, tính theo tỉ lệ chiều cao màn hình (0.0 -> 1.0).
        x_ratio: Vị trí theo chiều ngang, tính theo tỉ lệ chiều rộng màn hình.

    Nhấn Ctrl+C trong terminal để dừng lại.
    """
    print("Đang click liên tục vào bên phải màn hình. Nhấn Ctrl+C để dừng...")
    try:
        while True:
            x, y = click_right_screen(y_ratio=y_ratio, x_ratio=x_ratio)
            print(f"Đã click tại: ({x}, {y})")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nĐã dừng click.")


if __name__ == "__main__":
    # Cho vài giây để chuyển sang cửa sổ/màn hình mong muốn trước khi click.
    time.sleep(3)
    click_right_screen_forever()
