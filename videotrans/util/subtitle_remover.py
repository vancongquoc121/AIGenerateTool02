# -*- coding: utf-8 -*-
"""Tiền xử lý: gọi video-subtitle-remover (VSR, https://github.com/YaoFANGUK/video-subtitle-remover)
qua subprocess để xóa phụ đề cứng (burn-in) khỏi video gốc trước khi chạy pipeline dịch.

VSR là một dự án Python độc lập, cần được cài đặt/deploy riêng (venv hoặc conda env riêng
vì phụ thuộc PaddleOCR/Torch phiên bản khác). Ở đây chỉ gọi CLI có sẵn của nó:
    python backend/main.py -i <input> -o <output> [--inpaint-mode MODE] [-c YMIN YMAX XMIN XMAX]
"""
import subprocess
import sys
from pathlib import Path

from videotrans.configure.config import logger

VSR_INPAINT_MODES = ("sttn-auto", "sttn-det", "lama", "propainter", "opencv")


class SubtitleRemoverError(Exception):
    pass


def remove_hard_subtitle(input_path: str, output_path: str, vsr_dir: str, vsr_python: str = "",
                          inpaint_mode: str = "", sub_area=None, timeout: int = 3600) -> str:
    """Xóa phụ đề cứng khỏi input_path, ghi kết quả ra output_path.

    :param vsr_dir: thư mục gốc mã nguồn video-subtitle-remover (chứa backend/main.py)
    :param vsr_python: đường dẫn python thực thi trong venv/conda env riêng của VSR;
                        để trống thì dùng python hiện tại (sys.executable)
    :param inpaint_mode: một trong VSR_INPAINT_MODES, để trống dùng mặc định của VSR
    :param sub_area: tuple/list (ymin, ymax, xmin, xmax) giới hạn vùng chứa phụ đề, None = toàn khung hình
    :return: output_path nếu thành công
    :raises SubtitleRemoverError: nếu thiếu cấu hình, lệnh lỗi hoặc không sinh ra file đầu ra
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
        proc = subprocess.run(cmd, cwd=str(vsr_dir), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise SubtitleRemoverError(f"VSR chạy quá thời gian cho phép ({timeout}s)") from e
    except OSError as e:
        raise SubtitleRemoverError(f"Không thể chạy VSR: {e}") from e

    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-4000:]
        raise SubtitleRemoverError(f"VSR trả về mã lỗi {proc.returncode}:\n{tail}")

    if not Path(output_path).exists() or Path(output_path).stat().st_size == 0:
        raise SubtitleRemoverError(f"VSR chạy xong nhưng không tạo ra file đầu ra hợp lệ: {output_path}")

    return output_path
