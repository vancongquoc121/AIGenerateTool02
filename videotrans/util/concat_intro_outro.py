# -*- coding: utf-8 -*-
"""Ghép video intro (đầu) và/hoặc outro (cuối) vào video chính bằng ffmpeg filter_complex concat.

Các clip intro/outro thường có độ phân giải/fps/codec khác video chính nên không thể dùng
concat demuxer (-c copy) trực tiếp. Ở đây chuẩn hóa từng clip về scale/fps/sample rate của
video chính trước khi nối, đồng thời tự chèn track câm (anullsrc) cho clip không có audio.
"""
import shutil
from pathlib import Path

from videotrans.util import help_ffmpeg


def add_intro_outro(video_path: str, intro_path: str = "", outro_path: str = "") -> str:
    """Chèn intro_path vào đầu và/hoặc outro_path vào cuối video_path, ghi đè lên chính video_path.

    Không làm gì nếu cả hai đều rỗng/không tồn tại. Trả về video_path.
    """
    intro_path = (intro_path or "").strip()
    outro_path = (outro_path or "").strip()
    intro_path = intro_path if intro_path and Path(intro_path).exists() else ""
    outro_path = outro_path if outro_path and Path(outro_path).exists() else ""
    if not intro_path and not outro_path:
        return video_path

    clips = [c for c in (intro_path, video_path, outro_path) if c]
    main_info = help_ffmpeg.get_video_info(video_path)
    target_w, target_h = main_info["width"], main_info["height"]
    target_fps = main_info.get("video_fps") or 30

    inputs = []
    filter_parts = []
    concat_refs = []
    for i, clip in enumerate(clips):
        info = main_info if clip == video_path else help_ffmpeg.get_video_info(clip)
        inputs += ["-i", str(Path(clip).as_posix())]
        filter_parts.append(
            f"[{i}:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
            f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={target_fps}[v{i}]"
        )
        if info.get("streams_audio"):
            filter_parts.append(f"[{i}:a]aresample=async=1[a{i}]")
        else:
            duration = max(info.get("time", 0) / 1000, 0.1)
            filter_parts.append(
                f"anullsrc=channel_layout=stereo:sample_rate=44100,atrim=duration={duration}[a{i}]"
            )
        concat_refs.append(f"[v{i}][a{i}]")

    filter_complex = ";".join(filter_parts) + ";" + "".join(concat_refs) + f"concat=n={len(clips)}:v=1:a=1[outv][outa]"

    src = Path(video_path)
    tmp_out = str(src.with_name(f"__introoutro_{src.name}"))
    cmd = inputs + ["-filter_complex", filter_complex, "-map", "[outv]", "-map", "[outa]", tmp_out]
    help_ffmpeg.runffmpeg(cmd)
    shutil.move(tmp_out, video_path)
    return video_path
