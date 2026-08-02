# -*- coding: utf-8 -*-
"""Tiền xử lý: gọi video-subtitle-remover (VSR, https://github.com/YaoFANGUK/video-subtitle-remover)
qua subprocess để xóa phụ đề cứng (burn-in) khỏi video gốc trước khi chạy pipeline dịch.

VSR là một dự án Python độc lập, cần được cài đặt/deploy riêng (venv hoặc conda env riêng
vì phụ thuộc PaddleOCR/Torch phiên bản khác). Ở đây chỉ gọi CLI có sẵn của nó:
    python backend/main.py -i <input> -o <output> [--inpaint-mode MODE] [-c YMIN YMAX XMIN XMAX]
"""
import subprocess
import sys
import time
from pathlib import Path

from videotrans.configure.config import logger

VSR_INPAINT_MODES = ("sttn-auto", "sttn-det", "lama", "propainter", "opencv")


class SubtitleRemoverError(Exception):
    pass


def iter_remove_hard_subtitle(input_path: str, output_path: str, vsr_dir: str, vsr_python: str = "",
                               inpaint_mode: str = "", sub_area=None, timeout: int = 3600):
    """Chạy VSR và yield từng dòng log của nó theo thời gian thực (kể cả thanh tiến trình dùng '\\r'),
    để không bị hiểu nhầm là treo trong khi VSR (đặc biệt chạy CPU) vẫn đang xử lý.

    :param vsr_dir: thư mục gốc mã nguồn video-subtitle-remover (chứa backend/main.py)
    :param vsr_python: đường dẫn python thực thi trong venv/conda env riêng của VSR;
                        để trống thì dùng python hiện tại (sys.executable)
    :param inpaint_mode: một trong VSR_INPAINT_MODES, để trống dùng mặc định của VSR
    :param sub_area: tuple/list (ymin, ymax, xmin, xmax) giới hạn vùng chứa phụ đề, None = toàn khung hình
    :raises SubtitleRemoverError: nếu thiếu cấu hình, quá thời gian, lệnh lỗi hoặc không sinh ra file đầu ra
    """
    if not vsr_dir:
        raise SubtitleRemoverError("Chưa cấu hình thư mục video-subtitle-remover (vsr_dir)")

    main_py = Path(vsr_dir) / "backend" / "main.py"
    if not main_py.exists():
        raise SubtitleRemoverError(f"Không tìm thấy {main_py}, kiểm tra lại đường dẫn vsr_dir")

    python_exe = vsr_python.strip() or sys.executable
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = [python_exe, str(main_py), "-i", str(input_path), "-o", str(output_path)]
    if inpaint_mode and inpaint_mode in VSR_INPAINT_MODES:
        cmd += ["--inpaint-mode", inpaint_mode]
    if sub_area:
        cmd += ["-c", *[str(v) for v in sub_area]]

    logger.info(f"[VSR] Chạy lệnh xóa phụ đề cứng: {' '.join(cmd)}")
    try:
        # stdin=DEVNULL để tránh treo vĩnh viễn nếu VSR chờ input() tương tác.
        proc = subprocess.Popen(
            cmd, cwd=str(vsr_dir), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
    except OSError as e:
        raise SubtitleRemoverError(f"Không thể chạy VSR: {e}") from e

    start = time.monotonic()
    buf = ""
    try:
        while True:
            ch = proc.stdout.read(1)
            if ch == "" and proc.poll() is not None:
                break
            if ch in ("\n", "\r"):
                if buf.strip():
                    yield buf.strip()
                buf = ""
            else:
                buf += ch
            if timeout and time.monotonic() - start > timeout:
                proc.kill()
                proc.wait(timeout=10)
                raise SubtitleRemoverError(f"VSR chạy quá thời gian cho phép ({timeout}s), đã hủy tiến trình")
        if buf.strip():
            yield buf.strip()
    finally:
        if proc.stdout:
            proc.stdout.close()

    returncode = proc.wait()
    if returncode != 0:
        raise SubtitleRemoverError(f"VSR trả về mã lỗi {returncode}")

    if not Path(output_path).exists() or Path(output_path).stat().st_size == 0:
        raise SubtitleRemoverError(f"VSR chạy xong nhưng không tạo ra file đầu ra hợp lệ: {output_path}")


def remove_hard_subtitle(input_path: str, output_path: str, vsr_dir: str, vsr_python: str = "",
                          inpaint_mode: str = "", sub_area=None, timeout: int = 3600) -> str:
    """Phiên bản không streaming: chạy xong mới trả về output_path. Xem iter_remove_hard_subtitle
    để lấy log thời gian thực (khuyến nghị dùng khi có UI để tránh trông như bị treo)."""
    for _ in iter_remove_hard_subtitle(input_path, output_path, vsr_dir, vsr_python, inpaint_mode, sub_area, timeout):
        pass
    return output_path
