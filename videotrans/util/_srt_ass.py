# -*- coding: utf-8 -*-
import os, json, re
from pathlib import Path

from videotrans.configure.config import ROOT_DIR, logger
from videotrans.util._srt_parse import get_subtitle_from_srt


def set_ass_font(srtfile: str, video_width: int = 0, video_height: int = 0) -> str:
    from . import help_ffmpeg
    """
    Convert SRT to ASS with custom styles:
    - Main style (Default) for primary text
    - Bottom style for secondary text after '###' marker
    - Remove '###' markers
    """
    if not os.path.exists(srtfile) or os.path.getsize(srtfile) == 0:
        return os.path.basename(srtfile)

    srt_str = ""
    for it in get_subtitle_from_srt(srtfile, is_file=True):
        text = re.sub(r'\n|\\n', r'\\N', it['text'].strip())
        if text:
            _time = f'{it["startraw"]} --> {it["endraw"]}'
            _time = re.sub(r'(\d{2}:\d{2}:\d{2}),(\d{2})\d?', r'\1,\g<2>0', _time)
            srt_str += f'{it["line"]}\n{_time}\n{text}\n\n'
    edit_srt = srtfile[:-4] + '-edit.srt'
    with open(edit_srt, 'w', encoding='utf-8') as f:
        f.write(srt_str.strip())
    ass_file_path = f'{srtfile[:-3]}ass'
    help_ffmpeg.runffmpeg(['-y', '-i', edit_srt, ass_file_path])

    # ffmpeg tạo ASS với độ phân giải kịch bản mặc định 384x288, không khớp
    # kích thước thật của video khiến các giá trị Margin/Fontsize tính theo
    # pixel thật (vd tính năng chèn phụ đề vào đúng vùng) bị lệch hoặc bị đẩy
    # hẳn ra ngoài khung hình (không hiển thị). Đồng bộ lại PlayResX/PlayResY
    # theo đúng kích thước video để mọi giá trị margin/fontsize theo pixel đều đúng.
    if video_width and video_height:
        try:
            _ass_content = Path(ass_file_path).read_text(encoding='utf-8-sig')
            _ass_content = re.sub(r'PlayResX:\s*\d+', f'PlayResX: {int(video_width)}', _ass_content)
            _ass_content = re.sub(r'PlayResY:\s*\d+', f'PlayResY: {int(video_height)}', _ass_content)
            Path(ass_file_path).write_text(_ass_content, encoding='utf-8')
        except Exception as e:
            logger.exception(f"[set_ass_font] 错误：无法同步 PlayRes 到视频真实分辨率: {e}", exc_info=True)

    JSON_FILE = f'{ROOT_DIR}/videotrans/ass.json'
    if not os.path.exists(JSON_FILE):
        logger.debug(f"[set_ass_font] 未修改硬字幕样式，跳过样式替换")
        return ass_file_path

    try:
        with open(JSON_FILE, 'r', encoding='utf-8-sig') as f:
            style = json.load(f)
    except Exception as e:
        logger.exception(f"[set_ass_font] 错误：无法读取或解析 JSON 文件 {JSON_FILE}: {e}", exc_info=True)
        return ass_file_path

    default_style = (
        f"Style: {style.get('Name', 'Default')},"
        f"{style.get('Fontname', 'Noto Sans')},"
        f"{style.get('Fontsize', 16)},"
        f"{style.get('PrimaryColour', '&H00FFFFFF&')},"
        f"{style.get('SecondaryColour', '&H00FFFFFF&')},"
        f"{style.get('OutlineColour', '&H00000000&')},"
        f"{style.get('BackColour', '&H00000000&')},"
        f"{style.get('Bold', 0)},"
        f"{style.get('Italic', 0)},"
        f"{style.get('Underline', 0)},"
        f"{style.get('StrikeOut', 0)},"
        f"{style.get('ScaleX', 100)},"
        f"{style.get('ScaleY', 100)},"
        f"{style.get('Spacing', 0)},"
        f"{style.get('Angle', 0)},"
        f"{style.get('BorderStyle', 1)},"
        f"{style.get('Outline', 1)},"
        f"{style.get('Shadow', 0)},"
        f"{style.get('Alignment', 2)},"
        f"{style.get('MarginL', 10)},"
        f"{style.get('MarginR', 10)},"
        f"{style.get('MarginV', 10)},"
        f"{style.get('Encoding', 1)}\n"
    )

    bottom_fontsize = style.get('Bottom_Fontsize', 14)
    bottom_color = style.get('Bottom_PrimaryColour', '&H0000FFFF&')
    bottom_bold = style.get('Bottom_Bold', 0)
    bottom_italic = style.get('Bottom_Italic', 0)
    bottom_secondarycolour = style.get('Bottom_SecondaryColour', '&H00FFFFFF&')
    bottom_outlinecolour = style.get('Bottom_OutlineColour', '&H00000000&')
    bottom_backcolour = style.get('Bottom_BackColour', '&H00000000&')

    bottom_style = (
        f"Style: Bottom,"
        f"{style.get('Fontname', 'Noto Sans')},"
        f"{bottom_fontsize},"
        f"{bottom_color},"
        f"{bottom_secondarycolour},"
        f"{bottom_outlinecolour},"
        f"{bottom_backcolour},"
        f"{bottom_bold},"
        f"{bottom_italic},"
        f"{style.get('Underline', 0)},"
        f"{style.get('StrikeOut', 0)},"
        f"{style.get('ScaleX', 100)},"
        f"{style.get('ScaleY', 100)},"
        f"{style.get('Spacing', 0)},"
        f"{style.get('Angle', 0)},"
        f"{style.get('BorderStyle', 1)},"
        f"{style.get('Outline', 1)},"
        f"{style.get('Shadow', 0)},"
        f"{style.get('Alignment', 2)},"
        f"{style.get('MarginL', 10)},"
        f"{style.get('MarginR', 10)},"
        f"{style.get('MarginV', 10)},"
        f"{style.get('Encoding', 1)}\n"
    )

    try:
        with open(ass_file_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    except Exception as e:
        logger.exception(f"[set_ass_font] 错误：无法读取 ASS 文件: {e}", exc_info=True)
        return ass_file_path

    pattern = r'(^\[V4\+ Styles\]\s*\r?\n' \
              r'Format:[^\r\n]*\r?\n' \
              r'(?:Style:[^\r\n]*\r?\n)*)' \
              r'(?=\[|$)'

    def replacer(match):
        format_line = None
        for line in match.group(0).splitlines():
            if line.strip().startswith("Format:"):
                format_line = line.strip() + "\n"
                break
        if not format_line:
            format_line = "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        return f"[V4+ Styles]\n{format_line}{default_style}{bottom_style}"

    try:
        new_content, _ = re.subn(pattern, replacer, content, flags=re.MULTILINE)
    except Exception as e:
        logger.exception(f"[set_ass_font] 错误：正则替换样式失败: {e}", exc_info=True)
        return ass_file_path

    lines = new_content.splitlines(keepends=True)
    processed_lines = []
    inside_events = False
    dialogue_pattern = re.compile(r'^(Dialogue:.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,)(.*)$')

    for line in lines:
        if line.strip().startswith('[Events]'):
            inside_events = True
        elif line.strip().startswith('[') and inside_events:
            inside_events = False

        if inside_events and line.startswith('Dialogue:'):
            match = dialogue_pattern.match(line.rstrip('\r\n'))
            if match:
                prefix = match.group(1)
                text = match.group(2)
                if '###' in text:
                    parts = text.split('###', 1)
                    left = parts[0]
                    right = parts[1] if len(parts) > 1 else ''
                    new_text = ''
                    if left:
                        new_text += left
                    if right:
                        new_text += f'{{\\rBottom}}{right}{{\\r}}'
                    line = f'{prefix}{new_text}\n'
        processed_lines.append(line)

    try:
        with open(ass_file_path, 'w', encoding='utf-8', newline='') as f:
            f.writelines(processed_lines)
    except Exception as e:
        logger.exception(f"[set_ass_font] 错误：无法写入 ASS 文件: {e}", exc_info=True)

    return ass_file_path
