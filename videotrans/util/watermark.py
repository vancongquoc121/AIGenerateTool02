# -*- coding: utf-8 -*-
"""Chèn watermark văn bản (vd chú thích bản quyền) lên video bằng bộ lọc drawtext của ffmpeg."""
import shutil
from pathlib import Path

from videotrans.util import help_ffmpeg

WATERMARK_POSITIONS = {
    "top-left": ("20", "20"),
    "top-right": ("w-tw-20", "20"),
    "bottom-left": ("20", "h-th-20"),
    "bottom-right": ("w-tw-20", "h-th-20"),
    "center": ("(w-tw)/2", "(h-th)/2"),
}


def _escape_drawtext(text: str) -> str:
    # Dấu nháy đơn sẽ kết thúc sớm chuỗi text='...' của drawtext nên thay bằng dấu nháy kiểu chữ
    return text.replace("\\", "\\\\").replace("'", "\u2019")


def add_text_watermark(video_path: str, text: str, position: str = "bottom-right",
                        fontsize: int = 24, fontcolor: str = "white", fontfile: str = "") -> str:
    """Ghi đè watermark text lên chính video_path. Không làm gì nếu text rỗng. Trả về video_path."""
    if not text or not text.strip():
        return video_path

    x_expr, y_expr = WATERMARK_POSITIONS.get(position, WATERMARK_POSITIONS["bottom-right"])
    safe_text = _escape_drawtext(text.strip())

    draw_opts = [
        f"text='{safe_text}'",
        f"fontsize={int(fontsize)}",
        f"fontcolor={fontcolor or 'white'}@0.85",
        f"x={x_expr}", f"y={y_expr}",
        "box=1", "boxcolor=black@0.35", "boxborderw=6",
    ]
    if fontfile and Path(fontfile).exists():
        draw_opts.insert(0, f"fontfile='{Path(fontfile).as_posix()}'")
    else:
        draw_opts.insert(0, "font='Noto Sans'")

    drawtext_filter = "drawtext=" + ":".join(draw_opts)

    src = Path(video_path)
    tmp_out = str(src.with_name(f"__wm_{src.name}"))
    help_ffmpeg.runffmpeg(["-i", str(src), "-vf", drawtext_filter, "-c:a", "copy", tmp_out])
    shutil.move(tmp_out, video_path)
    return video_path
