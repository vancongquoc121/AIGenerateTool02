"""
pyVideoTrans WebUI — Gradio-based web interface for video translation.

Usage:
    uv run webui.py
    # or
    uv run python webui.py

Requires: uv sync --extra webui
"""

import os
import sys
import json
import time
import asyncio
import traceback
from pathlib import Path
from typing import List

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ---------------------------------------------------------------------------
# Hằng số ngôn ngữ
# ---------------------------------------------------------------------------
CLI_LANG = "vi"
os.environ['PYVIDEOTRANS_LANG'] = CLI_LANG

# ---------------------------------------------------------------------------
# Khởi tạo môi trường videotrans
# ---------------------------------------------------------------------------
from videotrans.configure import config
config.init_run()

from videotrans.configure.config import ROOT_DIR, TEMP_DIR, app_cfg, params, settings
from videotrans.configure.contants import FASTER_MODELS_DICT, DEEPGRAM_MODEL, Openai_Whisper_Models, FUNASR_MODEL
from videotrans import recognition, translator, tts
from videotrans.util import tools
from videotrans.util.gpus import getset_gpu
from videotrans.util.help_role import role_menu

# ---------------------------------------------------------------------------
# Đường dẫn lưu trữ params / settings
# ---------------------------------------------------------------------------
PARAMS_JSON = Path(ROOT_DIR) / "videotrans" / "params.json"
SETTINGS_JSON = Path(ROOT_DIR) / "videotrans" / "cfg.json"


def _load_params() -> dict:
    """Tải từ params.json"""
    try:
        if PARAMS_JSON.exists():
            return json.loads(PARAMS_JSON.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_params(data: dict):
    """Lưu vào params.json"""
    PARAMS_JSON.parent.mkdir(parents=True, exist_ok=True)
    PARAMS_JSON.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
    # đồng bộ cập nhật params trong bộ nhớ
    params.getset_params(data)


def _load_settings() -> dict:
    try:
        if SETTINGS_JSON.exists():
            return json.loads(SETTINGS_JSON.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_settings(data: dict):
    SETTINGS_JSON.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_JSON.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
    settings.parse_init(data)


# Tải cấu hình hiện tại
_user_params = _load_params()
_user_settings = _load_settings()

# ---------------------------------------------------------------------------
# Danh sách tên kênh
# ---------------------------------------------------------------------------
RECOGN_NAMES: List[str] = recognition.RECOGN_NAME_LIST
TRANSLATE_NAMES: List[str] = translator.TRANSLASTE_NAME_LIST
TTS_NAMES: List[str] = tts.TTS_NAME_LIST
LANGNAME_DICT: dict = translator.LANGNAME_DICT

# ---------------------------------------------------------------------------
# Chỉ số kênh có thể chọn
# ---------------------------------------------------------------------------
SELECTABLE_RECOGN = {0, 1, 2, 3, 4}
DEFAULT_RECOGN = 0
SELECTABLE_TRANSLATE = {0, 1, 2}
DEFAULT_TRANSLATE = 0
SELECTABLE_TTS = {0, 1, 3, 4, 5, 6, 7, 31}
DEFAULT_TTS = 0

FASTER_MODEL_NAMES = list(FASTER_MODELS_DICT.keys())
DEFAULT_MODEL = "large-v3-turbo" if "large-v3-turbo" in FASTER_MODEL_NAMES else FASTER_MODEL_NAMES[0]

LANG_DISPLAY_NAMES = list(LANGNAME_DICT.values())
DEFAULT_SOURCE_LANG = LANG_DISPLAY_NAMES[0]
DEFAULT_TARGET_LANG = '-'

SUBTITLE_TYPES = {"Không nhúng phụ đề": 0, "Nhúng phụ đề cứng": 1, "Nhúng phụ đề mềm": 2, "Nhúng phụ đề cứng (song ngữ)": 3, "Nhúng phụ đề mềm (song ngữ)": 4}
DEFAULT_SUBTITLE_TYPE = "Nhúng phụ đề cứng"
PUNC_OPTIONS = {"Dấu câu mặc định": 0, "Khôi phục dấu câu": 1, "Xóa dấu câu": 2}
LOOP_BGM_OPTIONS = {"Cắt nhạc nền": 0, "Lặp nhạc nền": 1}
WATERMARK_POSITION_OPTIONS = {"Trên trái": "top-left", "Trên phải": "top-right", "Dưới trái": "bottom-left", "Dưới phải": "bottom-right", "Chính giữa": "center"}

# ---------------------------------------------------------------------------
# Kiểu phụ đề ASS
# ---------------------------------------------------------------------------
ASS_JSON_FILE = f'{ROOT_DIR}/videotrans/ass.json'

DEFAULT_ASS_STYLE = {
    'Name': 'Default', 'Fontname': 'Noto Sans', 'Bottom_Fontname': 'Noto Sans',
    'Fontsize': 16, 'Bottom_Fontsize': 16,
    'PrimaryColour': '&H00FFFFFF&', 'Bottom_PrimaryColour': '&H00FFFFFF&',
    'SecondaryColour': '&H00FFFFFF&', 'OutlineColour': '&H00000000&', 'BackColour': '&H00000000&',
    'Bold': 0, 'Italic': 0,
    'Bottom_SecondaryColour': '&H00FFFFFF&', 'Bottom_OutlineColour': '&H00000000&',
    'Bottom_BackColour': '&H00000000&', 'Bottom_Bold': 0, 'Bottom_Italic': 0,
    'Underline': 0, 'StrikeOut': 0, 'ScaleX': 100, 'ScaleY': 100,
    'Spacing': 0, 'Angle': 0, 'BorderStyle': 1, 'Outline': 0.5, 'Shadow': 0.5,
    'Alignment': 2, 'MarginL': 10, 'MarginR': 10, 'MarginV': 10, 'Encoding': 1,
}


def _parse_ass_color(c):
    if not c.startswith('&H') or not c.endswith('&'):
        return '#ffffff'
    h = c[2:-1].upper()
    if len(h) == 6:
        return f'#{int(h[4:6],16):02x}{int(h[2:4],16):02x}{int(h[0:2],16):02x}'
    elif len(h) == 8:
        return f'#{int(h[6:8],16):02x}{int(h[4:6],16):02x}{int(h[2:4],16):02x}'
    return '#ffffff'


def _to_ass_color(h):
    h = h.lstrip('#')
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f'&H00{b:02X}{g:02X}{r:02X}&'
    return '&H00FFFFFF&'


def _load_ass_style():
    try:
        if Path(ASS_JSON_FILE).exists():
            return json.loads(Path(ASS_JSON_FILE).read_text(encoding='utf-8'))
    except Exception:
        pass
    return DEFAULT_ASS_STYLE.copy()


def _save_ass_style(s):
    Path(ASS_JSON_FILE).parent.mkdir(parents=True, exist_ok=True)
    Path(ASS_JSON_FILE).write_text(json.dumps(s, indent=4, ensure_ascii=False), encoding='utf-8')


# ---------------------------------------------------------------------------
# Hàm hỗ trợ
# ---------------------------------------------------------------------------
def _lang_code_from_display(d):
    for code, name in LANGNAME_DICT.items():
        if name == d:
            return code
    return d


def _display_from_lang_code(v, default='-'):
    """params.json lưu mã ngôn ngữ thô (vd 'en'), chuyển sang tên hiển thị cho Dropdown"""
    if not v or v == '-':
        return default
    return LANGNAME_DICT.get(v, v)


def _tts_index_from_display(d):
    for i, name in enumerate(TTS_NAMES):
        if name == d:
            return i
    return 0


def _recogn_index_from_display(d):
    for i, name in enumerate(RECOGN_NAMES):
        if name == d:
            return i
    return 0


def _translate_index_from_display(d):
    for i, name in enumerate(TRANSLATE_NAMES):
        if name == d:
            return i
    return 0


def _format_rate(v):
    return f"+{v}%" if v >= 0 else f"{v}%"


def _format_pitch(v):
    return f"+{v}Hz" if v >= 0 else f"{v}Hz"


def _safe_get(key, default=""):
    """Đọc giá trị từ _user_params, hỗ trợ str/int/float/bool"""
    v = _user_params.get(key, default)
    if v is None:
        return default
    return v


# ---------------------------------------------------------------------------
# Định nghĩa bảng cài đặt kênh
# ---------------------------------------------------------------------------
CHANNEL_SETTINGS = {
    # === Kênh dịch ===
    "ChatGPT (Dịch)": {
        "category": "Kênh dịch phụ đề",
        "fields": [
            {"key": "chatgpt_api", "label": "API URL", "type": "text", "default": "", "placeholder": "Để trống để dùng API chính thức"},
            {"key": "chatgpt_key", "label": "Khóa SK", "type": "text", "default": "", "placeholder": "API Key"},
            {"key": "chatgpt_max_token", "label": "Token đầu ra tối đa", "type": "text", "default": "8192"},
            {"key": "chatgpt_model", "label": "Mô hình", "type": "text", "default": "gpt-4o-mini", "placeholder": "Nhập tên mô hình"},
        ],
    },
    "DeepSeek (Dịch)": {
        "category": "Kênh dịch phụ đề",
        "fields": [
            {"key": "deepseek_key", "label": "Khóa SK", "type": "text", "default": "", "placeholder": "API Key"},
            {"key": "deepseek_model", "label": "Mô hình", "type": "text", "default": "deepseek-chat", "placeholder": "Nhập tên mô hình"},
            {"key": "deepseek_max_token", "label": "Token đầu ra tối đa", "type": "text", "default": "8192"},
        ],
    },
    "Gemini (Dịch)": {
        "category": "Kênh dịch phụ đề",
        "fields": [
            {"key": "gemini_key", "label": "Gemini Key", "type": "text", "default": ""},
            {"key": "gemini_model", "label": "Mô hình", "type": "text", "default": "gemini-2.5-flash", "placeholder": "Nhập tên mô hình"},
            {"key": "gemini_maxtoken", "label": "Token tối đa", "type": "text", "default": "8192"},
        ],
    },
    "AzureGPT (Dịch)": {
        "category": "Kênh dịch phụ đề",
        "fields": [
            {"key": "azure_api", "label": "API URL", "type": "text", "default": ""},
            {"key": "azure_key", "label": "Khóa SK", "type": "text", "default": ""},
            {"key": "azure_model", "label": "Mô hình", "type": "text", "default": "gpt-4o-mini", "placeholder": "Nhập tên mô hình"},
        ],
    },
    "Mô hình lớn cục bộ (LocalLLM)": {
        "category": "Kênh dịch phụ đề",
        "fields": [
            {"key": "localllm_api", "label": "API URL", "type": "text", "default": "http://127.0.0.1:11434/v1", "placeholder": "Ví dụ: http://127.0.0.1:11434/v1"},
            {"key": "localllm_key", "label": "Khóa SK", "type": "text", "default": "no-key", "placeholder": "Thường điền no-key"},
            {"key": "localllm_max_token", "label": "Token đầu ra tối đa", "type": "text", "default": "8192"},
            {"key": "localllm_model", "label": "Mô hình", "type": "text", "default": "", "placeholder": "Nhập tên mô hình"},
        ],
    },
    "DeepL (Dịch)": {
        "category": "Kênh dịch phụ đề",
        "fields": [
            {"key": "deepl_authkey", "label": "AUTH KEY", "type": "text", "default": ""},
            {"key": "deepl_api", "label": "API URL (bên thứ 3)", "type": "text", "default": "", "placeholder": "Để trống để dùng API chính thức"},
            {"key": "deepl_gid", "label": "ID bảng thuật ngữ", "type": "text", "default": ""},
        ],
    },
    "Baidu Dịch": {
        "category": "Kênh dịch phụ đề",
        "fields": [
            {"key": "baidu_appid", "label": "App ID", "type": "text", "default": ""},
            {"key": "baidu_miyue", "label": "Khóa bí mật", "type": "text", "default": ""},
        ],
    },
    "Tencent Dịch": {
        "category": "Kênh dịch phụ đề",
        "fields": [
            {"key": "tencent_SecretId", "label": "SecretId", "type": "text", "default": ""},
            {"key": "tencent_SecretKey", "label": "SecretKey", "type": "text", "default": ""},
        ],
    },
    "Alibaba Bailian (QwenMT)": {
        "category": "Kênh dịch phụ đề",
        "fields": [
            {"key": "qwenmt_key", "label": "Khóa Bailian", "type": "text", "default": ""},
            {"key": "qwenmt_model", "label": "Mô hình dịch", "type": "text", "default": "qwen-mt-plus", "placeholder": "Phải bắt đầu bằng qwen-mt"},
            {"key": "qwenmt_asr_model", "label": "Mô hình nhận dạng giọng nói", "type": "text", "default": "qwen3-asr-flash", "placeholder": "Phải bắt đầu bằng qwen3-asr"},
        ],
    },
    "ByteDance Volcano (VolcEngine)": {
        "category": "Kênh dịch phụ đề",
        "fields": [
            {"key": "zijiehuoshan_key", "label": "Khóa SK", "type": "text", "default": ""},
            {"key": "zijiehuoshan_model", "label": "Điểm truy cập suy luận", "type": "text", "default": "", "placeholder": "Nhập tên điểm truy cập"},
        ],
    },
    "MiniMax (Dịch)": {
        "category": "Kênh dịch phụ đề",
        "fields": [
            {"key": "minimax_key", "label": "Khóa SK", "type": "text", "default": ""},
            {"key": "minimax_api", "label": "API URL", "type": "text", "default": "api.minimax.io"},
            {"key": "minimax_model", "label": "Mô hình", "type": "text", "default": "MiniMax-M3", "placeholder": "Nhập tên mô hình"},
            {"key": "minimax_max_tokens", "label": "Token đầu ra tối đa", "type": "text", "default": "8192"},
        ],
    },
    "Zhipu AI (Dịch)": {
        "category": "Kênh dịch phụ đề",
        "fields": [
            {"key": "zhipu_key", "label": "Khóa SK", "type": "text", "default": ""},
            {"key": "zhipu_model", "label": "Mô hình", "type": "text", "default": "glm-4-flash", "placeholder": "Nhập tên mô hình"},
            {"key": "zhipu_max_token", "label": "Token đầu ra tối đa", "type": "text", "default": "8192"},
        ],
    },
    "SiliconFlow": {
        "category": "Kênh dịch phụ đề",
        "fields": [
            {"key": "guiji_key", "label": "Khóa SK", "type": "text", "default": ""},
            {"key": "guiji_model", "label": "Mô hình", "type": "text", "default": "Qwen/Qwen3-32B", "placeholder": "Nhập tên mô hình"},
            {"key": "guiji_max_token", "label": "Token đầu ra tối đa", "type": "text", "default": "8192"},
        ],
    },
    "OpenRouter (Dịch)": {
        "category": "Kênh dịch phụ đề",
        "fields": [
            {"key": "openrouter_key", "label": "Khóa SK", "type": "text", "default": ""},
            {"key": "openrouter_model", "label": "Mô hình", "type": "text", "default": "", "placeholder": "Nhập tên mô hình"},
            {"key": "openrouter_max_token", "label": "Token đầu ra tối đa", "type": "text", "default": "8192"},
        ],
    },
    "Xiaomi AI (Dịch)": {
        "category": "Kênh dịch phụ đề",
        "fields": [
            {"key": "xiaomi_key", "label": "Khóa Xiaomi", "type": "text", "default": ""},
            {"key": "xiaomi_model", "label": "Mô hình", "type": "text", "default": "mimo-v2.5-pro", "placeholder": "Nhập tên mô hình"},
            {"key": "xiaomi_maxtoken", "label": "Token tối đa", "type": "text", "default": "8192"},
        ],
    },

    # === Kênh nhận dạng giọng nói ===
    "OpenAI ASR": {
        "category": "Kênh nhận dạng giọng nói",
        "fields": [
            {"key": "openairecognapi_url", "label": "API URL", "type": "text", "default": "", "placeholder": "Để trống để dùng API chính thức"},
            {"key": "openairecognapi_key", "label": "Khóa SK", "type": "text", "default": ""},
            {"key": "openairecognapi_model", "label": "Mô hình", "type": "text", "default": "whisper-1", "placeholder": "Nhập tên mô hình"},
        ],
    },
    "Deepgram ASR": {
        "category": "Kênh nhận dạng giọng nói",
        "fields": [
            {"key": "deepgram_apikey", "label": "API Key", "type": "text", "default": ""},
        ],
    },
    "Parakeet ASR": {
        "category": "Kênh nhận dạng giọng nói",
        "fields": [
            {"key": "parakeet_address", "label": "API URL", "type": "text", "default": "http://127.0.0.1:8080"},
        ],
    },
    "ByteDance Nhận dạng giọng nói": {
        "category": "Kênh nhận dạng giọng nói",
        "fields": [
            {"key": "zijierecognmodel_appid", "label": "AppID", "type": "text", "default": ""},
            {"key": "zijierecognmodel_token", "label": "Access Token", "type": "text", "default": ""},
        ],
    },

    # === Kênh lồng tiếng ===
    "OpenAI TTS": {
        "category": "Kênh lồng tiếng",
        "fields": [
            {"key": "openaitts_api", "label": "API URL", "type": "text", "default": "", "placeholder": "Để trống để dùng API chính thức"},
            {"key": "openaitts_key", "label": "Khóa SK", "type": "text", "default": ""},
            {"key": "openaitts_model", "label": "Mô hình", "type": "text", "default": "tts-1", "placeholder": "Nhập tên mô hình"},
        ],
    },
    "Azure TTS": {
        "category": "Kênh lồng tiếng",
        "fields": [
            {"key": "azure_speech_key", "label": "SPEECH KEY", "type": "text", "default": ""},
            {"key": "azure_speech_region", "label": "Region / URL", "type": "text", "default": "eastasia", "placeholder": "Ví dụ: eastasia hoặc URL đầy đủ"},
        ],
    },
    "ElevenLabs TTS": {
        "category": "Kênh lồng tiếng",
        "fields": [
            {"key": "elevenlabstts_key", "label": "API Key", "type": "text", "default": ""},
        ],
    },
    "GPT-SoVITS": {
        "category": "Kênh lồng tiếng",
        "fields": [
            {"key": "gptsovits_url", "label": "API URL", "type": "text", "default": "http://127.0.0.1:9880"},
        ],
    },
    "Spark / Index / VoxCPM": {
        "category": "Kênh lồng tiếng",
        "fields": [
            {"key": "sparktts_url", "label": "Spark-TTS URL", "type": "text", "default": "http://127.0.0.1:7860"},
            {"key": "indextts_url", "label": "Index-TTS URL", "type": "text", "default": "http://127.0.0.1:7860"},
            {"key": "voxcpmtts_url", "label": "VoxCPM URL", "type": "text", "default": "http://127.0.0.1:7860"},
        ],
    },
    "CosyVoice TTS": {
        "category": "Kênh lồng tiếng",
        "fields": [
            {"key": "cosyvoice_url", "label": "WebUI URL", "type": "text", "default": "http://127.0.0.1:8000"},
            {"key": "cosyvoice_instruct_text", "label": "Prompt (gợi ý)", "type": "text", "default": ""},
        ],
    },

    "Alibaba Bailian TTS (Qwen-TTS)": {
        "category": "Kênh lồng tiếng",
        "fields": [
            {"key": "qwentts_key", "label": "Khóa Bailian", "type": "text", "default": ""},
            {"key": "qwentts_model", "label": "Mô hình", "type": "text", "default": "qwen3-tts-flash", "placeholder": "Nhập tên mô hình"},
        ],
    },
    "Qwen-TTS (Cục bộ)": {
        "category": "Kênh lồng tiếng",
        "fields": [
            {"key": "qwenttslocal_prompt", "label": "Prompt giọng nói tùy chỉnh", "type": "text", "default": ""},
        ],
    },
    "Doubao Tổng hợp giọng nói 2.0": {
        "category": "Kênh lồng tiếng",
        "fields": [
            {"key": "doubao2_appid", "label": "App ID", "type": "text", "default": ""},
            {"key": "doubao2_access", "label": "Access Token", "type": "text", "default": ""},
        ],
    },
    "Minimaxi TTS": {
        "category": "Kênh lồng tiếng",
        "fields": [
            {"key": "minimaxi_apikey", "label": "Khóa SK", "type": "text", "default": ""},
            {"key": "minimaxi_apiurl", "label": "API URL", "type": "text", "default": "api.minimaxi.com"},
        ],
    },
    "X.AI TTS": {
        "category": "Kênh lồng tiếng",
        "fields": [
            {"key": "xaitts_key", "label": "Khóa SK", "type": "text", "default": ""},
        ],
    },
    "Xiaomi TTS": {
        "category": "Kênh lồng tiếng",
        "fields": [
            {"key": "xiaomi_key", "label": "Khóa Xiaomi", "type": "text", "default": ""},
        ],
    },
}


# ---------------------------------------------------------------------------
# Trình chỉnh sửa kiểu ASS (thuần Gradio)
# ---------------------------------------------------------------------------
def build_ass_editor():
    import gradio as gr

    style = _load_ass_style()

    with gr.Accordion("🎨 Chỉnh sửa kiểu phụ đề cứng", open=False):
        gr.Markdown("Sau khi chỉnh sửa, nhấn \"Lưu kiểu\", kiểu sẽ áp dụng cho tất cả tác vụ nhúng phụ đề cứng.")
        with gr.Tabs():
            with gr.Tab("Phụ đề chính"):
                with gr.Row():
                    ass_fontname = gr.Textbox(label="Tên phông chữ", value=style.get('Fontname', 'Noto Sans'))
                    ass_fontsize = gr.Slider(label="Cỡ chữ", minimum=1, maximum=200, value=style.get('Fontsize', 16), step=1)
                with gr.Row():
                    ass_primary_color = gr.ColorPicker(label="Màu chính", value=_parse_ass_color(style.get('PrimaryColour', '&H00FFFFFF&')))
                    ass_outline_color = gr.ColorPicker(label="Màu viền", value=_parse_ass_color(style.get('OutlineColour', '&H00000000&')))
                    ass_back_color = gr.ColorPicker(label="Màu nền", value=_parse_ass_color(style.get('BackColour', '&H00000000&')))
                with gr.Row():
                    ass_bold = gr.Checkbox(label="Đậm", value=bool(style.get('Bold', 0)))
                    ass_italic = gr.Checkbox(label="Nghiêng", value=bool(style.get('Italic', 0)))
                    ass_underline = gr.Checkbox(label="Gạch chân", value=bool(style.get('Underline', 0)))
                    ass_strikeout = gr.Checkbox(label="Gạch ngang", value=bool(style.get('StrikeOut', 0)))
            with gr.Tab("Phụ đề dưới (khi song ngữ)"):
                with gr.Row():
                    ass_bottom_fontname = gr.Textbox(label="Tên phông chữ", value=style.get('Bottom_Fontname', 'Noto Sans'))
                    ass_bottom_fontsize = gr.Slider(label="Cỡ chữ", minimum=1, maximum=200, value=style.get('Bottom_Fontsize', 16), step=1)
                with gr.Row():
                    ass_bottom_primary_color = gr.ColorPicker(label="Màu chính", value=_parse_ass_color(style.get('Bottom_PrimaryColour', '&H00FFFFFF&')))
                    ass_bottom_outline_color = gr.ColorPicker(label="Màu viền", value=_parse_ass_color(style.get('Bottom_OutlineColour', '&H00000000&')))
                    ass_bottom_back_color = gr.ColorPicker(label="Màu nền", value=_parse_ass_color(style.get('Bottom_BackColour', '&H00000000&')))
                with gr.Row():
                    ass_bottom_bold = gr.Checkbox(label="Đậm", value=bool(style.get('Bottom_Bold', 0)))
                    ass_bottom_italic = gr.Checkbox(label="Nghiêng", value=bool(style.get('Bottom_Italic', 0)))
            with gr.Tab("Kiểu toàn cục"):
                with gr.Row():
                    ass_border_style = gr.Dropdown(label="Kiểu viền", choices=["Viền nét", "Nền đục"], value="Viền nét" if style.get('BorderStyle', 1) == 1 else "Nền đục")
                    ass_outline = gr.Slider(label="Độ dày viền", minimum=0.0, maximum=10.0, value=style.get('Outline', 0.5), step=0.1)
                    ass_shadow = gr.Slider(label="Đổ bóng", minimum=0.0, maximum=10.0, value=style.get('Shadow', 0.5), step=0.1)
                with gr.Row():
                    ass_scale_x = gr.Slider(label="Tỷ lệ ngang %", minimum=1, maximum=1000, value=style.get('ScaleX', 100), step=1)
                    ass_scale_y = gr.Slider(label="Tỷ lệ dọc %", minimum=1, maximum=1000, value=style.get('ScaleY', 100), step=1)
                    ass_spacing = gr.Slider(label="Giãn cách chữ", minimum=-100, maximum=100, value=style.get('Spacing', 0), step=1)
                    ass_angle = gr.Slider(label="Góc xoay", minimum=-360, maximum=360, value=style.get('Angle', 0), step=1)
                with gr.Row():
                    ass_margin_l = gr.Slider(label="Lề trái", minimum=0, maximum=1000, value=style.get('MarginL', 10), step=1)
                    ass_margin_r = gr.Slider(label="Lề phải", minimum=0, maximum=1000, value=style.get('MarginR', 10), step=1)
                    ass_margin_v = gr.Slider(label="Lề dọc", minimum=0, maximum=1000, value=style.get('MarginV', 10), step=1)
                ass_alignment = gr.Dropdown(label="Vị trí căn chỉnh", choices=["Dưới trái", "Dưới giữa", "Dưới phải", "Giữa trái", "Chính giữa", "Giữa phải", "Trên trái", "Trên giữa", "Trên phải"],
                    value={1: "Dưới trái", 2: "Dưới giữa", 3: "Dưới phải", 4: "Giữa trái", 5: "Chính giữa", 6: "Giữa phải", 7: "Trên trái", 8: "Trên giữa", 9: "Trên phải"}.get(style.get('Alignment', 2), "Dưới giữa"))
        with gr.Row():
            ass_save_btn = gr.Button("💾 Lưu kiểu", variant="primary")
            ass_reset_btn = gr.Button("🔄 Khôi phục mặc định")
            ass_status = gr.Textbox(label="Trạng thái", interactive=False, visible=True)

        def save_ass_style(fontname, fontsize, primary_color, outline_color, back_color, bold, italic, underline, strikeout,
                           bottom_fontname, bottom_fontsize, bottom_primary_color, bottom_outline_color, bottom_back_color,
                           bottom_bold, bottom_italic, border_style, outline, shadow, scale_x, scale_y, spacing, angle,
                           margin_l, margin_r, margin_v, alignment):
            am = {"Dưới trái": 1, "Dưới giữa": 2, "Dưới phải": 3, "Giữa trái": 4, "Chính giữa": 5, "Giữa phải": 6, "Trên trái": 7, "Trên giữa": 8, "Trên phải": 9}
            _save_ass_style({
                'Name': 'Default', 'Fontname': fontname, 'Bottom_Fontname': bottom_fontname,
                'Fontsize': int(fontsize), 'Bottom_Fontsize': int(bottom_fontsize),
                'PrimaryColour': _to_ass_color(primary_color), 'Bottom_PrimaryColour': _to_ass_color(bottom_primary_color),
                'SecondaryColour': '&H00FFFFFF&', 'OutlineColour': _to_ass_color(outline_color),
                'BackColour': _to_ass_color(back_color), 'Bold': 1 if bold else 0, 'Italic': 1 if italic else 0,
                'Bottom_SecondaryColour': '&H00FFFFFF&', 'Bottom_OutlineColour': _to_ass_color(bottom_outline_color),
                'Bottom_BackColour': _to_ass_color(bottom_back_color), 'Bottom_Bold': 1 if bottom_bold else 0,
                'Bottom_Italic': 1 if bottom_italic else 0, 'Underline': 1 if underline else 0, 'StrikeOut': 1 if strikeout else 0,
                'ScaleX': int(scale_x), 'ScaleY': int(scale_y), 'Spacing': int(spacing), 'Angle': int(angle),
                'BorderStyle': 1 if border_style == "Viền nét" else 3, 'Outline': float(outline), 'Shadow': float(shadow),
                'Alignment': am.get(alignment, 2), 'MarginL': int(margin_l), 'MarginR': int(margin_r),
                'MarginV': int(margin_v), 'Encoding': 1,
            })
            return "✅ Đã lưu kiểu"

        def reset_ass_style():
            _save_ass_style(DEFAULT_ASS_STYLE.copy())
            s = DEFAULT_ASS_STYLE
            return (s['Fontname'], s['Fontsize'], _parse_ass_color(s['PrimaryColour']), _parse_ass_color(s['OutlineColour']),
                    _parse_ass_color(s['BackColour']), bool(s['Bold']), bool(s['Italic']), bool(s['Underline']), bool(s['StrikeOut']),
                    s['Bottom_Fontname'], s['Bottom_Fontsize'], _parse_ass_color(s['Bottom_PrimaryColour']),
                    _parse_ass_color(s['Bottom_OutlineColour']), _parse_ass_color(s['Bottom_BackColour']),
                    bool(s['Bottom_Bold']), bool(s['Bottom_Italic']),
                    "Viền nét" if s['BorderStyle'] == 1 else "Nền đục",
                    s['Outline'], s['Shadow'], s['ScaleX'], s['ScaleY'], s['Spacing'], s['Angle'],
                    s['MarginL'], s['MarginR'], s['MarginV'],
                    {1: "Dưới trái", 2: "Dưới giữa", 3: "Dưới phải", 4: "Giữa trái", 5: "Chính giữa", 6: "Giữa phải", 7: "Trên trái", 8: "Trên giữa", 9: "Trên phải"}.get(s['Alignment'], "Dưới giữa"),
                    "✅ Đã khôi phục kiểu mặc định")

        ass_save_btn.click(fn=save_ass_style,
            inputs=[ass_fontname, ass_fontsize, ass_primary_color, ass_outline_color, ass_back_color,
                    ass_bold, ass_italic, ass_underline, ass_strikeout, ass_bottom_fontname, ass_bottom_fontsize,
                    ass_bottom_primary_color, ass_bottom_outline_color, ass_bottom_back_color,
                    ass_bottom_bold, ass_bottom_italic, ass_border_style, ass_outline, ass_shadow,
                    ass_scale_x, ass_scale_y, ass_spacing, ass_angle, ass_margin_l, ass_margin_r, ass_margin_v, ass_alignment],
            outputs=[ass_status])

        ass_reset_btn.click(fn=reset_ass_style, inputs=[],
            outputs=[ass_fontname, ass_fontsize, ass_primary_color, ass_outline_color, ass_back_color,
                     ass_bold, ass_italic, ass_underline, ass_strikeout, ass_bottom_fontname, ass_bottom_fontsize,
                     ass_bottom_primary_color, ass_bottom_outline_color, ass_bottom_back_color,
                     ass_bottom_bold, ass_bottom_italic, ass_border_style, ass_outline, ass_shadow,
                     ass_scale_x, ass_scale_y, ass_spacing, ass_angle, ass_margin_l, ass_margin_r, ass_margin_v,
                     ass_alignment, ass_status])


# ---------------------------------------------------------------------------
# Xây dựng bảng cài đặt kênh
# ---------------------------------------------------------------------------
def build_channel_settings():
    """Xây dựng tất cả các bảng cài đặt kênh"""
    import gradio as gr

    # nhóm theo category
    categories = {}
    for name, cfg in CHANNEL_SETTINGS.items():
        cat = cfg["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append((name, cfg))

    gr.Markdown("### Cài đặt kênh")
    gr.Markdown("Cấu hình địa chỉ API, khóa SK... cho từng kênh. **Sau khi lưu sẽ dùng chung với bản desktop (sp.exe)**, tệp cấu hình lưu tại `videotrans/params.json`.")

    with gr.Tabs():
        for cat_name, channels in categories.items():
            with gr.Tab(cat_name):
                for ch_name, ch_cfg in channels:
                    with gr.Accordion(ch_name, open=False):
                        fields = []
                        for f in ch_cfg["fields"]:
                            val = str(_safe_get(f["key"], f.get("default", "")))
                            tb = gr.Textbox(
                                label=f["label"],
                                value=val,
                                placeholder=f.get("placeholder", ""),
                                interactive=True,
                            )
                            fields.append((f["key"], tb))

                        save_btn = gr.Button("💾 Lưu", size="sm")
                        status = gr.Textbox(label="", interactive=False, visible=True,show_label=False)

                        # dùng closure để lưu giá trị hiện tại
                        def make_save_handler(field_keys, field_widgets):
                            def handler(*values):
                                data = {}
                                for k, v in zip(field_keys, values):
                                    data[k] = v
                                _save_params(data)
                                return "✅ Đã lưu"
                            return handler

                        save_btn.click(
                            fn=make_save_handler([f[0] for f in fields], [f[1] for f in fields]),
                            inputs=[f[1] for f in fields],
                            outputs=[status],
                        )

        # === Tab Âm thanh tham chiếu ===
        with gr.Tab("Thiết lập âm thanh tham chiếu"):
            gr.Markdown("### Cài đặt âm thanh tham chiếu để nhân bản giọng nói")
            gr.Markdown(
                "Cấu hình âm thanh tham chiếu dùng cho nhân bản giọng nói (clone). Mỗi dòng một mục, định dạng: `tên_tệp.wav#văn bản lời thoại trong âm thanh`\n"
                f"- Tệp âm thanh cần đặt trong thư mục `{ROOT_DIR}/f5-tts/`\n"
                "- Định dạng tệp phải là wav\n"
                "- Mỗi dòng dùng `#` để phân tách tên tệp và văn bản tương ứng"
            )

            ref_audio_text = gr.Textbox(
                label="Danh sách âm thanh tham chiếu",
                value=str(_safe_get("f5tts_role", "")),
                placeholder="myaudio1.wav#Xin chào, đây là văn bản mẫu\nmyaudio2.wav#Hello, this is a test audio",
                lines=8,
                interactive=True,
            )

            ref_audio_save = gr.Button("💾 Lưu âm thanh tham chiếu", variant="primary")
            ref_audio_status = gr.Markdown("", visible=False)

            def save_ref_audio(text):
                text = text.strip()
                if not text:
                    return gr.Markdown("⚠️ Vui lòng nhập thông tin âm thanh tham chiếu", visible=True)

                lines = text.split("\n")
                errors = []
                for i, line in enumerate(lines):
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split("#")
                    if len(parts) != 2:
                        errors.append(f"Dòng {i+1} sai định dạng, cần dùng # để phân tách tên tệp và văn bản")
                        continue

                    filename = parts[0].strip()
                    f5tts_dir = Path(ROOT_DIR) / "f5-tts"

                    # kiểm tra tệp tồn tại (có/không có đuôi .wav)
                    if not (f5tts_dir / filename).exists() and not (f5tts_dir / f"{filename}.wav").exists():
                        errors.append(f"Dòng {i+1}: tệp `{filename}` không tồn tại trong thư mục f5-tts/")
                        continue

                    # tự động thêm đuôi .wav
                    if not filename.endswith(".wav") and (f5tts_dir / f"{filename}.wav").exists():
                        lines[i] = f"{filename}.wav#{parts[1].strip()}"

                if errors:
                    return gr.Markdown("⚠️ Lưu thất bại:\n" + "\n".join(errors), visible=True)

                role_text = "\n".join(line for line in lines if line.strip())
                _save_params({"f5tts_role": role_text})
                return gr.Markdown("✅ Đã lưu âm thanh tham chiếu", visible=True)

            ref_audio_save.click(
                fn=save_ref_audio,
                inputs=[ref_audio_text],
                outputs=[ref_audio_status],
            )


# ---------------------------------------------------------------------------
# Bảng tùy chọn nâng cao
# ---------------------------------------------------------------------------
COMBO_BOX_KEYS = {
    'cuda_com_type', 'llm_ai_type', 'vad_type', 'speaker_type',
    'video_codec', 'preset', 'lang', 'uvr_models', 'out_video_ext', 'fps_mode',
    'vsr_inpaint_mode',
}
COMBO_BOX_OPTIONS = {
    "vsr_inpaint_mode": ['sttn-auto', 'sttn-det', 'lama', 'propainter', 'opencv'],
    "cuda_com_type": ['default', 'auto', 'int8', 'int16', 'float16', 'float32', 'bfloat16', 'int8_float16', 'int8_float32', 'int8_bfloat16'],
    "fps_mode": ["vfr", "cfr"],
    "llm_ai_type": ['chatgpt', 'deepseek'],
    "vad_type": ['tenvad', 'silero'],
    "speaker_type": ['built', 'ali_CAM', 'pyannote', 'reverb'],
    "video_codec": ['264', '265'],
    "preset": ['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow'],
    "uvr_models": ['spleeter', 'UVR-MDX-NET-Inst_HQ_4', 'UVR-MDX-NET-Inst_HQ_1', 'UVR-MDX-NET-Inst_HQ_2', 'UVR-MDX-NET-Inst_HQ_3', 'UVR-MDX-NET-Inst_HQ_5', 'UVR-MDX-NET-Inst_Main', 'UVR-MDX-NET-Inst_1', 'UVR-MDX-NET-Inst_2', 'UVR-MDX-NET-Inst_3'],
    "out_video_ext": ['.mp4', '.mkv'],
}

# Whisper danh sách key prompt và nhãn hiển thị
_prompt_keys_list = [
    "initial_prompt_zh-cn", "initial_prompt_zh-tw", "initial_prompt_en",
    "initial_prompt_ja", "initial_prompt_ko", "initial_prompt_fr",
    "initial_prompt_de", "initial_prompt_ru", "initial_prompt_es",
    "initial_prompt_pt", "initial_prompt_it", "initial_prompt_ar",
    "initial_prompt_vi", "initial_prompt_th", "initial_prompt_tr",
    "initial_prompt_hi",
]
_prompt_labels = {k: f"Prompt whisper {k.replace('initial_prompt_', '')}" for k in _prompt_keys_list}

# Bảng đăng ký widget toàn cục
_all_widgets = {}


def _w(key, label, tip="", area=False):
    """Tạo một mục cài đặt: tiêu đề ở trên, thành phần ở dưới"""
    import gradio as gr
    val = str(_user_settings.get(key, ""))
    with gr.Column():
        label_text = f"**{label}**" + (f"\n<sub>{tip}</sub>" if tip else "")
        gr.Markdown(label_text)
        if key in COMBO_BOX_KEYS:
            options = COMBO_BOX_OPTIONS.get(key, [val])
            w = gr.Dropdown(choices=options, value=val if val in options else options[0],
                            label="", interactive=True,show_label=False)
        elif val.lower() in ('true', 'false'):
            w = gr.Checkbox(value=val.lower() == 'true', label="", show_label=False,interactive=True)
        else:
            w = gr.Textbox(value=val, label=None,show_label=False, lines=3 if area else 1, interactive=True)
    _all_widgets[key] = w


def _save_section(section_key, keys):
    """Tạo nút lưu và trạng thái cho một nhóm cài đặt"""
    import gradio as gr
    with gr.Row():
        save_btn = gr.Button(f"💾 Lưu {ADVANCED_SECTION_TITLES.get(section_key, section_key)}", variant="primary", size="sm")
        status = gr.Markdown("", visible=False)

    def _make_handler(k_list):
        def handler(*values):
            data = {}
            for k, v in zip(k_list, values):
                data[k] = str(v)
            _save_settings(data)
            return gr.Markdown(f"✅ Đã lưu", visible=True)
        return handler

    save_btn.click(fn=_make_handler(keys), inputs=[_all_widgets[k] for k in keys], outputs=[status])


# ---------------------------------------------------------------------------
# Bảng tùy chọn nâng cao (bố cục lưới thu gọn)
# ---------------------------------------------------------------------------
ADVANCED_SECTION_TITLES = {
    "common": "Cài đặt chung", "video": "Điều khiển xuất video", "whisper": "Tham số nhận dạng giọng nói",
    "trans": "Điều chỉnh dịch phụ đề", "dubbing": "Điều chỉnh lồng tiếng phụ đề",
    "justify": "Đồng bộ âm thanh và hình ảnh", "prompt_init": "Prompt mẫu cho Whisper",
}


def build_advanced_settings():
    import gradio as gr
    gr.Markdown("Cấu hình tham số nâng cao toàn cục. **Sau khi lưu sẽ dùng chung với bản desktop (sp.exe)**, tệp cấu hình lưu tại `videotrans/cfg.json`.\n⚠️ Một số tham số cần **khởi động lại phần mềm** sau khi thay đổi mới có hiệu lực.")

    # ---- Cài đặt chung ----
    with gr.Accordion("📋 Cài đặt chung", open=True):
        with gr.Row():
            _w("lang", "Ngôn ngữ giao diện phần mềm", "Cần khởi động lại sau khi đặt")
            _w("countdown_sec", "Đếm ngược tạm dừng mỗi video", "Đặt 0 để bỏ qua cửa sổ chỉnh sửa")
            _w("retry_nums", "Số lần thử lại khi thất bại", "")
        with gr.Row():
            _w("llm_chunk_size", "Số dòng phụ đề mỗi lần ngắt câu LLM", "Mặc định 20")
            _w("llm_ai_type", "Kênh AI ngắt câu LLM", "chatgpt/deepseek")
            _w("batch_nums", "Số lượng mỗi đợt xử lý hàng loạt", "0=không giới hạn")
        with gr.Row():
            _w("dont_notify", "Tắt thông báo desktop", "")
            _w("show_more_settings", "Hiển thị tất cả tham số trên giao diện chính?", "")
            _w("homedir", "Thư mục xuất độc lập", "")
        with gr.Row():
            _w("process_max", "Số tác vụ CPU [khởi động lại]", "Không vượt quá số nhân CPU")
            _w("process_max_gpu", "Số tác vụ GPU [khởi động lại]", "Nhiều card hoặc VRAM>24G mới >1")
            _w("multi_gpus", "Chế độ nhiều card GPU [khởi động lại]", "")
        with gr.Row():
            _w("vsr_dir", "Thư mục cài video-subtitle-remover", "Chứa backend/main.py, để trống để tắt xóa phụ đề cứng gốc")
            _w("vsr_python", "Python thực thi của VSR", "Để trống dùng python hiện tại")
            _w("vsr_inpaint_mode", "Thuật toán xóa phụ đề VSR", "sttn-auto/sttn-det/lama/propainter/opencv")
        _save_section("common", ["lang", "countdown_sec", "retry_nums", "llm_chunk_size", "llm_ai_type",
                                  "batch_nums", "dont_notify", "show_more_settings", "homedir",
                                  "process_max", "process_max_gpu", "multi_gpus",
                                  "vsr_dir", "vsr_python", "vsr_inpaint_mode"])

    # ---- Điều khiển xuất video ----
    with gr.Accordion("📋 Điều khiển xuất video", open=False):
        with gr.Row():
            _w("crf", "Chất lượng video (0=không mất, 51=kém)", "")
            _w("preset", "Tỷ lệ nén", "ultrafast→veryslow")
            _w("video_codec", "Mã hóa 264/265", "")
        with gr.Row():
            _w("out_video_ext", "Định dạng xuất", "mp4/mkv")
            _w("fps_mode", "Chế độ khung hình", "vfr/cfr")
            _w("force_lib", "Buộc mã hóa mềm?", "")
        with gr.Row():
            _w("hw_decode", "Giải mã cứng cuda", "")
            _w("ffmpeg_cmd", "Tham số ffmpeg tùy chỉnh", "")
        _save_section("video", ["crf", "preset", "video_codec", "out_video_ext", "fps_mode",
                                 "force_lib", "hw_decode", "ffmpeg_cmd"])

    # ---- Tham số nhận dạng giọng nói ----
    with gr.Accordion("📋 Tham số nhận dạng giọng nói", open=False):
        with gr.Row():
            _w("vad_type", "Chọn VAD", "tenvad/silero")
            _w("threshold", "Ngưỡng giọng nói", "")
            _w("no_speech_threshold", "Ngưỡng không có giọng nói", "")
        with gr.Row():
            _w("max_speech_duration_s", "Thời lượng giọng nói tối đa (giây)", "")
            _w("min_speech_duration_ms", "Thời lượng giọng nói tối thiểu (ms)", "")
            _w("min_silence_duration_ms", "Tách im lặng (ms)", "")
        with gr.Row():
            _w("max_speech_duration_s2", "Tối đa nhận dạng lần 2 (giây)", "")
            _w("min_speech_duration_ms2", "Tối thiểu nhận dạng lần 2 (ms)", "")
            _w("merge_short_sub", "Gộp phụ đề quá ngắn", "")
        with gr.Row():
            _w("whisper_prepare", "Tách trước bằng Whisper?", "Chọn khi lồng tiếng clone")
            _w("speaker_type", "Mô hình tách người nói", "built-in/pyannote")
            _w("hf_token", "Huggingface token", "Cần cho pyannote")
        with gr.Row():
            _w("cuda_com_type", "Kiểu dữ liệu tính toán", "int8/float16/float32")
            _w("beam_size", "beam_size", "1-5")
            _w("best_of", "best_of", "1-5")
        with gr.Row():
            _w("condition_on_previous_text", "Nhận thức ngữ cảnh", "")
            _w("repetition_penalty", "Phạt lặp lại", "")
            _w("compression_ratio_threshold", "Tỷ lệ nén văn bản", "")
        with gr.Row():
            _w("temperature", "Nhiệt độ lấy mẫu", "")
            _w("hotwords", "Từ khóa nóng", "Phân cách bằng dấu phẩy")
            _w("gemini_recogn_chunk", "Số đoạn cắt Gemini", "")
        with gr.Row():
            _w("zh_hant_s", "Chuyển phiến thể sang giản thể", "")
            _w("del_end_punc", "Xóa dấu câu cuối", "")
        with gr.Row():
            _w("model_list", "Mô hình faster-whisper", "Phân cách bằng dấu phẩy", area=True)
        with gr.Row():
            _w("Whisper_cpp_models", "Mô hình whisper.cpp", "Phân cách bằng dấu phẩy", area=True)
        _save_section("whisper", ["vad_type", "threshold", "no_speech_threshold",
                                   "max_speech_duration_s", "min_speech_duration_ms",
                                   "max_speech_duration_s2", "min_speech_duration_ms2",
                                   "min_silence_duration_ms", "merge_short_sub",
                                   "whisper_prepare", "speaker_type", "hf_token",
                                   "cuda_com_type", "beam_size", "best_of",
                                   "condition_on_previous_text", "repetition_penalty",
                                   "compression_ratio_threshold", "temperature", "hotwords",
                                   "gemini_recogn_chunk", "zh_hant_s", "del_end_punc",
                                   "model_list", "Whisper_cpp_models"])

    # ---- Điều chỉnh dịch phụ đề ----
    with gr.Accordion("📋 Điều chỉnh dịch phụ đề", open=False):
        with gr.Row():
            _w("trans_thread", "Số dòng mỗi đợt dịch truyền thống", "")
            _w("aitrans_thread", "Số dòng mỗi đợt dịch AI", "")
            _w("aitrans_temperature", "Giá trị nhiệt độ AI", "Mặc định 1.0")
        with gr.Row():
            _w("translation_wait", "Tạm dừng sau dịch (giây)", "")
            _w("aisendsrt", "Gửi toàn bộ phụ đề", "")
            _w("aitrans_context", "Dịch tất cả các dòng cùng lúc", "Cần mô hình ngữ cảnh siêu dài")
        _save_section("trans", ["trans_thread", "aitrans_thread", "aitrans_temperature",
                                 "translation_wait", "aisendsrt", "aitrans_context"])

    # ---- Điều chỉnh lồng tiếng phụ đề ----
    with gr.Accordion("📋 Điều chỉnh lồng tiếng phụ đề", open=False):
        with gr.Row():
            _w("dubbing_thread", "Số luồng lồng tiếng đồng thời", "")
            _w("dubbing_wait", "Tạm dừng sau lồng tiếng (giây)", "")
            _w("remove_dubb_silence", "Xóa khoảng lặng trước/sau lồng tiếng", "")
        with gr.Row():
            _w("save_segment_audio", "Giữ lại tệp lồng tiếng mỗi dòng", "")
            _w("normal_text", "Chuẩn hóa văn bản", "")
            _w("chattts_voice", "Giá trị giọng ChatTTS", "")
        with gr.Row():
            _w("edgetts_max_concurrent_tasks", "Số tác vụ đồng thời EdgeTTS", "Càng lớn càng nhanh nhưng dễ bị giới hạn")
            _w("edgetts_retry_nums", "Số lần thử lại EdgeTTS", "")
            _w("noise_separate_nums", "Số luồng tách giọng nói", "")
        with gr.Row():
            _w("uvr_models", "Mô hình tách âm thanh nền", "")
        _save_section("dubbing", ["dubbing_thread", "dubbing_wait", "remove_dubb_silence",
                                   "save_segment_audio", "normal_text", "chattts_voice",
                                   "edgetts_max_concurrent_tasks", "edgetts_retry_nums",
                                   "noise_separate_nums", "uvr_models"])

    # ---- Đồng bộ âm thanh và hình ảnh ----
    with gr.Accordion("📋 Đồng bộ âm thanh và hình ảnh", open=False):
        with gr.Row():
            _w("max_audio_speed_rate", "Biên độ tăng tốc âm thanh tối đa", "Mặc định 100")
            _w("max_video_pts_rate", "Biên độ làm chậm video tối đa", "Mặc định 10, ≤10")
        with gr.Row():
            _w("cjk_len", "Số ký tự mỗi dòng phụ đề Trung/Nhật/Hàn", "")
            _w("other_len", "Số ký tự mỗi dòng phụ đề ngôn ngữ khác", "")
        _save_section("justify", ["max_audio_speed_rate", "max_video_pts_rate", "cjk_len", "other_len"])

    # ---- Prompt mẫu cho Whisper ----
    with gr.Accordion("📋 Prompt mẫu cho Whisper", open=False):
        for i in range(0, len(_prompt_keys_list), 3):
            with gr.Row():
                for k in _prompt_keys_list[i:i+3]:
                    _w(k, _prompt_labels.get(k, k), "")
        _save_section("prompt_init", _prompt_keys_list)


# ---------------------------------------------------------------------------
# Bảng dịch nhanh Việt -> Anh, dùng cho công tắc ngôn ngữ giao diện (thay thế
# văn bản trực tiếp trên DOM, không cần build lại giao diện Gradio)
# ---------------------------------------------------------------------------
UI_I18N_VI_EN = {
    # Tiêu đề / thẻ tab
    "AIGenerate Video Translation WebUI": "AIGenerate Video Translation WebUI",
    "Giao diện này chỉ triển khai một phần tính năng, để dùng đầy đủ tính năng vui lòng dùng bản desktop (sp.exe hoặc sp.py)": "This interface only implements a subset of features, please use the desktop version (sp.exe or sp.py) for full features",
    "Tài liệu sử dụng": "Documentation",
    "Mã nguồn": "Source code",
    "Gặp sự cố": "Report an issue",
    "🎬 Dịch video": "🎬 Translate Video",
    "⚙️ Cài đặt kênh": "⚙️ Channel Settings",
    "🔧 Tùy chọn nâng cao": "🔧 Advanced Options",

    # Tab dịch video chính
    "Chọn tệp video": "Select video file",
    "Kênh nhận dạng": "Recognition channel",
    "Mô hình": "Model",
    "Kênh dịch": "Translation channel",
    "Ngôn ngữ phát âm (ngôn ngữ nguồn)": "Spoken language (source language)",
    "Ngôn ngữ đích": "Target language",
    "Kênh lồng tiếng": "Dubbing channel",
    "Nhân vật lồng tiếng": "Voice role",
    "Tăng tốc lồng tiếng": "Auto speed up dubbing",
    "Làm chậm video": "Slow down video",
    "Tốc độ lồng tiếng (%)": "Dubbing speed (%)",
    "Điều chỉnh âm lượng (%)": "Volume adjustment (%)",
    "Cao độ (Hz)": "Pitch (Hz)",
    "Kiểu nhúng phụ đề": "Subtitle embedding type",
    "📋 Cài đặt thêm": "📋 Additional settings",
    "Khử nhiễu": "Noise reduction",
    "Xử lý dấu câu": "Punctuation handling",
    "Tách giọng nói và âm thanh nền": "Separate voice and background audio",
    "Nhúng lại âm thanh nền": "Re-embed background audio",
    "Xử lý âm thanh nền": "Background audio handling",
    "Âm lượng nền": "Background volume",
    "Xóa phụ đề cứng gốc trước khi dịch (video-subtitle-remover)": "Remove original hardcoded subtitles before translation (video-subtitle-remover)",
    "🏷️ Watermark bản quyền": "🏷️ Copyright Watermark",
    "Chữ watermark bản quyền": "Copyright watermark text",
    "Để trống để tắt, ví dụ: © 2026 Kênh của bạn": "Leave blank to disable, e.g. © 2026 Your Channel",
    "Vị trí": "Position",
    "Cỡ chữ": "Font size",
    "Màu chữ (tên hoặc mã hex, vd white/yellow/#FFCC00)": "Text color (name or hex code, e.g. white/yellow/#FFCC00)",
    "Bật tăng tốc CUDA": "Enable CUDA acceleration",
    "🚀 Bắt đầu thực hiện": "🚀 Start",
    "Nhật ký thực thi": "Execution log",
    "Xem trước video": "Video preview",
    "Tệp kết quả (nhấn để tải)": "Result files (click to download)",

    # Dropdown lựa chọn tĩnh
    "Không nhúng phụ đề": "No subtitles",
    "Nhúng phụ đề cứng": "Hardcode subtitles",
    "Nhúng phụ đề mềm": "Soft subtitles",
    "Nhúng phụ đề cứng (song ngữ)": "Hardcode subtitles (bilingual)",
    "Nhúng phụ đề mềm (song ngữ)": "Soft subtitles (bilingual)",
    "Dấu câu mặc định": "Default punctuation",
    "Khôi phục dấu câu": "Restore punctuation",
    "Xóa dấu câu": "Remove punctuation",
    "Cắt nhạc nền": "Trim background music",
    "Lặp nhạc nền": "Loop background music",

    # Kênh «...» hiện chưa khả dụng, đã tự động quay lại
    "hiện chưa khả dụng, đã tự động quay lại": "is currently unavailable, reverted automatically",

    # Nhật ký chạy tác vụ
    "Tệp nguồn: ": "Source file: ",
    "Nhận dạng: ": "Recognition: ",
    "  Dịch: ": "  Translate: ",
    "  Lồng tiếng: ": "  Dubbing: ",
    "Ngôn ngữ: ": "Language: ",
    "  Nhân vật: ": "  Voice: ",
    "▶ Bắt đầu thực hiện dịch video...": "▶ Starting video translation...",
    "Giai đoạn 1/8: Xử lý trước...": "Stage 1/8: Preprocessing...",
    "Giai đoạn 2/8: Nhận dạng giọng nói...": "Stage 2/8: Speech recognition...",
    "Giai đoạn 3/8: Tách người nói...": "Stage 3/8: Speaker diarization...",
    "Giai đoạn 4/8: Dịch phụ đề...": "Stage 4/8: Translating subtitles...",
    "Giai đoạn 5/8: Tạo lồng tiếng...": "Stage 5/8: Generating dubbing...",
    "Giai đoạn 6/8: Đồng bộ âm thanh và hình ảnh...": "Stage 6/8: Syncing audio and video...",
    "Giai đoạn 7/8: Nhận dạng lần 2...": "Stage 7/8: Second-pass recognition...",
    "Giai đoạn 8/8: Tổng hợp cuối cùng...": "Stage 8/8: Final assembly...",
    "Đã xử lý trước xong": "Preprocessing done",
    "Đã nhận dạng giọng nói xong": "Speech recognition done",
    "Đã tách người nói xong": "Speaker diarization done",
    "Đã dịch phụ đề xong": "Subtitle translation done",
    "Đã tạo lồng tiếng xong": "Dubbing done",
    "Đã đồng bộ xong": "Sync done",
    "Đã nhận dạng lần 2 xong": "Second-pass recognition done",
    "Đã tổng hợp xong": "Assembly done",
    "Đã ghép video xong": "Video merged",
    "Toàn bộ tác vụ đã hoàn thành!": "All tasks completed!",
    "Thư mục đầu ra: ": "Output folder: ",
    "Lỗi thực hiện: ": "Execution error: ",

    # Trình chỉnh sửa kiểu phụ đề (ASS)
    "🎨 Chỉnh sửa kiểu phụ đề cứng": "🎨 Edit hardcoded subtitle style",
    "Sau khi chỉnh sửa, nhấn \"Lưu kiểu\", kiểu sẽ áp dụng cho tất cả tác vụ nhúng phụ đề cứng.": "After editing, click \"Save style\" to apply it to all hardcoded-subtitle tasks.",
    "Phụ đề chính": "Main subtitle",
    "Phụ đề dưới (khi song ngữ)": "Bottom subtitle (bilingual)",
    "Kiểu toàn cục": "Global style",
    "Tên phông chữ": "Font name",
    "Cỡ chữ": "Font size",
    "Màu chính": "Primary color",
    "Màu viền": "Outline color",
    "Màu nền": "Background color",
    "Đậm": "Bold",
    "Nghiêng": "Italic",
    "Gạch chân": "Underline",
    "Gạch ngang": "Strikeout",
    "Kiểu viền": "Border style",
    "Viền nét": "Outline",
    "Nền đục": "Opaque box",
    "Độ dày viền": "Outline width",
    "Đổ bóng": "Shadow",
    "Tỷ lệ ngang %": "Horizontal scale %",
    "Tỷ lệ dọc %": "Vertical scale %",
    "Giãn cách chữ": "Letter spacing",
    "Góc xoay": "Rotation angle",
    "Lề trái": "Left margin",
    "Lề phải": "Right margin",
    "Lề dọc": "Vertical margin",
    "Vị trí căn chỉnh": "Alignment position",
    "Dưới trái": "Bottom left",
    "Dưới giữa": "Bottom center",
    "Dưới phải": "Bottom right",
    "Giữa trái": "Middle left",
    "Chính giữa": "Center",
    "Giữa phải": "Middle right",
    "Trên trái": "Top left",
    "Trên giữa": "Top center",
    "Trên phải": "Top right",
    "💾 Lưu kiểu": "💾 Save style",
    "🔄 Khôi phục mặc định": "🔄 Reset to default",
    "Trạng thái": "Status",
    "✅ Đã lưu kiểu": "✅ Style saved",
    "✅ Đã khôi phục kiểu mặc định": "✅ Default style restored",

    # Cài đặt kênh
    "### Cài đặt kênh": "### Channel Settings",
    "Cấu hình địa chỉ API, khóa SK... cho từng kênh. **Sau khi lưu sẽ dùng chung với bản desktop (sp.exe)**, tệp cấu hình lưu tại `videotrans/params.json`.":
        "Configure API address, API key, etc. for each channel. **Once saved, it is shared with the desktop version (sp.exe)**, config file stored at `videotrans/params.json`.",
    "Kênh dịch phụ đề": "Subtitle Translation Channels",
    "Kênh nhận dạng giọng nói": "Speech Recognition Channels",
    "Kênh lồng tiếng": "Dubbing Channels",
    "ChatGPT (Dịch)": "ChatGPT (Translate)",
    "DeepSeek (Dịch)": "DeepSeek (Translate)",
    "Gemini (Dịch)": "Gemini (Translate)",
    "AzureGPT (Dịch)": "AzureGPT (Translate)",
    "Mô hình lớn cục bộ (LocalLLM)": "Local Large Model (LocalLLM)",
    "DeepL (Dịch)": "DeepL (Translate)",
    "Baidu Dịch": "Baidu Translate",
    "Tencent Dịch": "Tencent Translate",
    "MiniMax (Dịch)": "MiniMax (Translate)",
    "Zhipu AI (Dịch)": "Zhipu AI (Translate)",
    "OpenRouter (Dịch)": "OpenRouter (Translate)",
    "Xiaomi AI (Dịch)": "Xiaomi AI (Translate)",
    "ByteDance Nhận dạng giọng nói": "ByteDance Speech Recognition",
    "Qwen-TTS (Cục bộ)": "Qwen-TTS (Local)",
    "Doubao Tổng hợp giọng nói 2.0": "Doubao Voice Synthesis 2.0",
    "💾 Lưu": "💾 Save",
    "✅ Đã lưu": "✅ Saved",
    "Thiết lập âm thanh tham chiếu": "Reference Audio Setup",
    "### Cài đặt âm thanh tham chiếu để nhân bản giọng nói": "### Reference Audio Setup for Voice Cloning",
    "Danh sách âm thanh tham chiếu": "Reference audio list",
    "💾 Lưu âm thanh tham chiếu": "💾 Save reference audio",
    "⚠️ Vui lòng nhập thông tin âm thanh tham chiếu": "⚠️ Please enter reference audio information",
    "⚠️ Lưu thất bại:": "⚠️ Save failed:",
    "✅ Đã lưu âm thanh tham chiếu": "✅ Reference audio saved",

    # Trường cấu hình kênh dùng chung
    "Khóa SK": "API Key",
    "Token đầu ra tối đa": "Max output tokens",
    "Để trống để dùng API chính thức": "Leave blank to use the official API",
    "Nhập tên mô hình": "Enter model name",
    "Token tối đa": "Max tokens",
    "API URL (bên thứ 3)": "API URL (3rd-party)",
    "ID bảng thuật ngữ": "Glossary ID",
    "Khóa bí mật": "Secret key",
    "Khóa Bailian": "Bailian key",
    "Mô hình dịch": "Translation model",
    "Phải bắt đầu bằng qwen-mt": "Must start with qwen-mt",
    "Mô hình nhận dạng giọng nói": "Speech recognition model",
    "Phải bắt đầu bằng qwen3-asr": "Must start with qwen3-asr",
    "Điểm truy cập suy luận": "Inference endpoint",
    "Nhập tên điểm truy cập": "Enter endpoint name",
    "Khóa Xiaomi": "Xiaomi key",
    "Ví dụ: http://127.0.0.1:11434/v1": "e.g. http://127.0.0.1:11434/v1",
    "Thường điền no-key": "Usually enter no-key",
    "Ví dụ: eastasia hoặc URL đầy đủ": "e.g. eastasia or full URL",
    "Prompt (gợi ý)": "Prompt (hint)",
    "Prompt giọng nói tùy chỉnh": "Custom voice prompt",

    # Tùy chọn nâng cao
    "Cấu hình tham số nâng cao toàn cục. **Sau khi lưu sẽ dùng chung với bản desktop (sp.exe)**, tệp cấu hình lưu tại `videotrans/cfg.json`.\n⚠️ Một số tham số cần **khởi động lại phần mềm** sau khi thay đổi mới có hiệu lực.":
        "Configure global advanced parameters. **Once saved, it is shared with the desktop version (sp.exe)**, config file stored at `videotrans/cfg.json`.\n⚠️ Some parameters require **restarting the software** to take effect.",
    "📋 Cài đặt chung": "📋 General Settings",
    "📋 Điều khiển xuất video": "📋 Video Output Control",
    "📋 Tham số nhận dạng giọng nói": "📋 Speech Recognition Parameters",
    "📋 Điều chỉnh dịch phụ đề": "📋 Subtitle Translation Tuning",
    "📋 Điều chỉnh lồng tiếng phụ đề": "📋 Subtitle Dubbing Tuning",
    "📋 Đồng bộ âm thanh và hình ảnh": "📋 Audio-Video Sync",
    "📋 Prompt mẫu cho Whisper": "📋 Whisper Prompt Templates",
    "💾 Lưu ": "💾 Save ",
    "Cài đặt chung": "General Settings",
    "Điều khiển xuất video": "Video Output Control",
    "Tham số nhận dạng giọng nói": "Speech Recognition Parameters",
    "Điều chỉnh dịch phụ đề": "Subtitle Translation Tuning",
    "Điều chỉnh lồng tiếng phụ đề": "Subtitle Dubbing Tuning",
    "Đồng bộ âm thanh và hình ảnh": "Audio-Video Sync",
    "Prompt mẫu cho Whisper": "Whisper Prompt Templates",

    "Ngôn ngữ giao diện phần mềm": "Software UI language",
    "Cần khởi động lại sau khi đặt": "Restart required after setting",
    "Đếm ngược tạm dừng mỗi video": "Pause countdown per video",
    "Đặt 0 để bỏ qua cửa sổ chỉnh sửa": "Set to 0 to skip the edit window",
    "Số lần thử lại khi thất bại": "Retry count on failure",
    "Số dòng phụ đề mỗi lần ngắt câu LLM": "Subtitle lines per LLM sentence split",
    "Mặc định 20": "Default 20",
    "Kênh AI ngắt câu LLM": "AI channel for LLM sentence splitting",
    "Số lượng mỗi đợt xử lý hàng loạt": "Batch size per run",
    "0=không giới hạn": "0 = unlimited",
    "Tắt thông báo desktop": "Disable desktop notifications",
    "Hiển thị tất cả tham số trên giao diện chính?": "Show all parameters on the main interface?",
    "Thư mục xuất độc lập": "Independent output folder",
    "Số tác vụ CPU [khởi động lại]": "Number of CPU tasks [restart required]",
    "Không vượt quá số nhân CPU": "Must not exceed the number of CPU cores",
    "Số tác vụ GPU [khởi động lại]": "Number of GPU tasks [restart required]",
    "Nhiều card hoặc VRAM>24G mới >1": "Only use >1 with multiple GPUs or VRAM>24G",
    "Chế độ nhiều card GPU [khởi động lại]": "Multi-GPU mode [restart required]",
    "Thư mục cài video-subtitle-remover": "video-subtitle-remover install folder",
    "Chứa backend/main.py, để trống để tắt xóa phụ đề cứng gốc": "Contains backend/main.py; leave blank to disable original hardsub removal",
    "Python thực thi của VSR": "VSR python executable",
    "Để trống dùng python hiện tại": "Leave blank to use current python",
    "Thuật toán xóa phụ đề VSR": "VSR removal algorithm",
    "sttn-auto/sttn-det/lama/propainter/opencv": "sttn-auto/sttn-det/lama/propainter/opencv",

    "Chất lượng video (0=không mất, 51=kém)": "Video quality (0=lossless, 51=poor)",
    "Tỷ lệ nén": "Compression ratio",
    "ultrafast→veryslow": "ultrafast→veryslow",
    "Mã hóa 264/265": "264/265 codec",
    "Định dạng xuất": "Output format",
    "mp4/mkv": "mp4/mkv",
    "Chế độ khung hình": "Frame rate mode",
    "vfr/cfr": "vfr/cfr",
    "Buộc mã hóa mềm?": "Force software encoding?",
    "Giải mã cứng cuda": "CUDA hardware decoding",
    "Tham số ffmpeg tùy chỉnh": "Custom ffmpeg parameters",

    "Chọn VAD": "Select VAD",
    "tenvad/silero": "tenvad/silero",
    "Ngưỡng giọng nói": "Speech threshold",
    "Ngưỡng không có giọng nói": "No-speech threshold",
    "Thời lượng giọng nói tối đa (giây)": "Max speech duration (s)",
    "Thời lượng giọng nói tối thiểu (ms)": "Min speech duration (ms)",
    "Tách im lặng (ms)": "Silence split (ms)",
    "Tối đa nhận dạng lần 2 (giây)": "Max 2nd-pass recognition (s)",
    "Tối thiểu nhận dạng lần 2 (ms)": "Min 2nd-pass recognition (ms)",
    "Gộp phụ đề quá ngắn": "Merge overly short subtitles",
    "Tách trước bằng Whisper?": "Pre-split with Whisper?",
    "Chọn khi lồng tiếng clone": "Enable when dubbing with voice cloning",
    "Mô hình tách người nói": "Speaker diarization model",
    "built-in/pyannote": "built-in/pyannote",
    "Huggingface token": "Huggingface token",
    "Cần cho pyannote": "Required for pyannote",
    "Kiểu dữ liệu tính toán": "Compute data type",
    "int8/float16/float32": "int8/float16/float32",
    "1-5": "1-5",
    "Nhận thức ngữ cảnh": "Context awareness",
    "Phạt lặp lại": "Repetition penalty",
    "Tỷ lệ nén văn bản": "Text compression ratio",
    "Nhiệt độ lấy mẫu": "Sampling temperature",
    "Từ khóa nóng": "Hotwords",
    "Phân cách bằng dấu phẩy": "Comma-separated",
    "Số đoạn cắt Gemini": "Gemini chunk count",
    "Chuyển phiến thể sang giản thể": "Convert traditional to simplified",
    "Xóa dấu câu cuối": "Remove trailing punctuation",
    "Mô hình faster-whisper": "faster-whisper models",
    "Mô hình whisper.cpp": "whisper.cpp models",

    "Số dòng mỗi đợt dịch truyền thống": "Lines per traditional translation batch",
    "Số dòng mỗi đợt dịch AI": "Lines per AI translation batch",
    "Giá trị nhiệt độ AI": "AI temperature value",
    "Mặc định 1.0": "Default 1.0",
    "Tạm dừng sau dịch (giây)": "Pause after translation (s)",
    "Gửi toàn bộ phụ đề": "Send all subtitles at once",
    "Dịch tất cả các dòng cùng lúc": "Translate all lines at once",
    "Cần mô hình ngữ cảnh siêu dài": "Requires an ultra-long context model",

    "Số luồng lồng tiếng đồng thời": "Concurrent dubbing threads",
    "Tạm dừng sau lồng tiếng (giây)": "Pause after dubbing (s)",
    "Xóa khoảng lặng trước/sau lồng tiếng": "Remove silence before/after dubbing",
    "Giữ lại tệp lồng tiếng mỗi dòng": "Keep per-line dubbing audio files",
    "Chuẩn hóa văn bản": "Normalize text",
    "Giá trị giọng ChatTTS": "ChatTTS voice value",
    "Số tác vụ đồng thời EdgeTTS": "Concurrent EdgeTTS tasks",
    "Càng lớn càng nhanh nhưng dễ bị giới hạn": "Higher is faster but more likely to be rate-limited",
    "Số lần thử lại EdgeTTS": "EdgeTTS retry count",
    "Số luồng tách giọng nói": "Voice separation threads",
    "Mô hình tách âm thanh nền": "Background audio separation model",

    "Biên độ tăng tốc âm thanh tối đa": "Max audio speed-up ratio",
    "Mặc định 100": "Default 100",
    "Biên độ làm chậm video tối đa": "Max video slow-down ratio",
    "Mặc định 10, ≤10": "Default 10, ≤10",
    "Số ký tự mỗi dòng phụ đề Trung/Nhật/Hàn": "Characters per line for CJK subtitles",
    "Số ký tự mỗi dòng phụ đề ngôn ngữ khác": "Characters per line for other languages",

    # Tên kênh / ngôn ngữ động (từ videotrans/language/vi.json)
    "Tích hợp sẵn": "Built-in",
    "Cục bộ ": "Local ",
    "miễn phí": "Free",
    "Edge-TTS (miễn phí)": "Edge-TTS (Free)",
    "FunASR (Tiếng Trung)": "Alibaba FunASR",
    "FireRed": "FireRed Chinese",
    "Dolphin": "Dolphin Asian",
    "parakeet-ja": "parakeet Japanese",
    "OpenAI Speech to Text": "OpenAI STT API",
    "Alibaba Qwen3-ASR": "Bailian / Qwen3-ASR",
    "ByteDance Volcano STT": "ByteDance STT Turbo",
    "Google Speech to Text": "Google STT API (Free)",
    "API tùy chỉnh": "Custom API",
    "ZipVoice": "ZipVoice ZH/EN",
    "VITS": "VITS ZH/EN",
    "Doubao2": "Doubao Voice 2.0",
    "Alibaba Bailian": "Bailian API",
    "Google (miễn phí)": "Google Translate (Free)",
    "Microsoft (miễn phí)": "Microsoft Translate (Free)",
    "LLM cục bộ": "CompatibleAI/LocalModel",
    "ByteDance Volcano LLM": "ByteDance Ark LLM",
    "Tencent": "Tencent Translate",
    "Baidu": "Baidu Translate",
    "Alibaba dịch máy": "Alibaba Machine Translation",

    # Tên ngôn ngữ hiển thị
    "Tiếng Anh": "English",
    "Tiếng Trung giản thể": "Simplified Chinese",
    "Tiếng Trung phồn thể": "Traditional Chinese",
    "Tiếng Pháp": "French",
    "Tiếng Đức": "German",
    "Tiếng Nhật": "Japanese",
    "Tiếng Hàn": "Korean",
    "Tiếng Nga": "Russian",
    "Tiếng Tây Ban Nha": "Spanish",
    "Tiếng Thái": "Thai",
    "Tiếng Ý": "Italian",
    "Tiếng Hy Lạp": "Greek",
    "Tiếng Bồ Đào Nha": "Portuguese",
    "Tiếng Việt": "Vietnamese",
    "Tiếng Ả Rập": "Arabic",
    "Tiếng Thổ Nhĩ Kỳ": "Turkish",
    "Tiếng Hindi": "Hindi",
    "Tiếng Hungary": "Hungarian",
    "Tiếng Ukraina": "Ukrainian",
    "Tiếng Indonesia": "Indonesian",
    "Tiếng Mã Lai": "Malay",
    "Tiếng Kazakh": "Kazakh",
    "Tiếng Séc": "Czech",
    "Tiếng Ba Lan": "Polish",
    "Tiếng Hà Lan": "Dutch",
    "Tiếng Thụy Điển": "Swedish",
    "Tiếng Do Thái": "Hebrew",
    "Tiếng Bengal": "Bengali",
    "Tiếng Ba Tư": "Persian",
    "Tiếng Philippines": "Filipino",
    "Tiếng Urdu": "Urdu",
    "Tiếng Na Uy": "Norwegian(Bokmål)",
    "Tiếng Quảng Đông": "Cantonese",
    "Tiếng Khmer": "Khmer",
    "Tiếng Romania": "Romanian",
}

# JS: quét toàn bộ văn bản trong trang và thay thế theo từ điển VI<->EN khi
# người dùng đổi ngôn ngữ giao diện (chỉ thay đổi hiển thị, không ảnh hưởng
# tới giá trị dữ liệu Python phía sau, do choices/values gốc không đổi)
_UI_LANG_CORE_JS = """
    if (!window.__pyvtI18nInit) {
        window.__pyvtViToEn = %(MAP_JSON)s;
        window.__pyvtEnToVi = Object.fromEntries(
            Object.entries(window.__pyvtViToEn).map(([k, v]) => [v, k])
        );
        window.__pyvtEscapeRe = function (s) {
            return s.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
        };
        window.__pyvtBuildRe = function (map) {
            const keys = Object.keys(map).sort((a, b) => b.length - a.length);
            if (!keys.length) return null;
            return new RegExp(keys.map(window.__pyvtEscapeRe).join('|'), 'g');
        };
        // Dùng 1 regex gộp tất cả các khóa, thay thế 1 lượt duy nhất dựa trên
        // chuỗi GỐC (không lặp lại theo từng khóa) để tránh thay thế chồng lặp
        // khi giá trị thay thế của 1 khóa lại chứa 1 khóa khác làm chuỗi con
        // (vd: "Baidu Dịch" -> "Baidu Translate" và "Baidu" -> "Baidu Translate").
        window.__pyvtViRe = window.__pyvtBuildRe(window.__pyvtViToEn);
        window.__pyvtEnRe = window.__pyvtBuildRe(window.__pyvtEnToVi);
        window.__pyvtReplace = function (str, map, re) {
            if (!re || !str) return str;
            return str.replace(re, (m) => (Object.prototype.hasOwnProperty.call(map, m) ? map[m] : m));
        };
        window.__pyvtApply = function () {
            const isEn = window.__pyvtLang === 'en';
            const map = isEn ? window.__pyvtViToEn : window.__pyvtEnToVi;
            const re = isEn ? window.__pyvtViRe : window.__pyvtEnRe;
            const curLang = window.__pyvtLang;
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
            const nodes = [];
            let n;
            while ((n = walker.nextNode())) nodes.push(n);
            for (const tn of nodes) {
                // Bỏ qua node đã được chuyển sang đúng ngôn ngữ hiện tại, tránh
                // thay thế chồng lặp khi 1 khóa (vd "Baidu") là chuỗi con ASCII
                // xuất hiện lại bên trong giá trị đã dịch (vd "Baidu Translate").
                if (tn.__pyvtLangDone === curLang) continue;
                if (!tn.nodeValue || !tn.nodeValue.trim()) { tn.__pyvtLangDone = curLang; continue; }
                const r = window.__pyvtReplace(tn.nodeValue, map, re);
                if (r !== tn.nodeValue) tn.nodeValue = r;
                tn.__pyvtLangDone = curLang;
            }
            document.querySelectorAll('input, textarea').forEach((el) => {
                if (el.__pyvtLangDone === curLang) return;
                if (el.value) {
                    const r = window.__pyvtReplace(el.value, map, re);
                    if (r !== el.value) el.value = r;
                }
                if (el.placeholder) {
                    const r = window.__pyvtReplace(el.placeholder, map, re);
                    if (r !== el.placeholder) el.placeholder = r;
                }
                el.__pyvtLangDone = curLang;
            });
            document.querySelectorAll('[title]').forEach((el) => {
                if (el.__pyvtTitleLangDone === curLang) return;
                const r = window.__pyvtReplace(el.title, map, re);
                if (r !== el.title) el.title = r;
                el.__pyvtTitleLangDone = curLang;
            });
        };
        document.addEventListener('click', () => setTimeout(window.__pyvtApply, 60));
        document.addEventListener('focusin', () => setTimeout(window.__pyvtApply, 60));
        window.__pyvtI18nInit = true;
    }
""" % {"MAP_JSON": json.dumps(UI_I18N_VI_EN, ensure_ascii=False)}

# JS: xử lý khi người dùng đổi radio ngôn ngữ
_UI_LANG_JS = """
(lang) => {
""" + _UI_LANG_CORE_JS + """
    window.__pyvtLang = (lang.indexOf('English') !== -1) ? 'en' : 'vi';
    window.__pyvtApply();
    return lang;
}
"""

# JS: áp dụng ngôn ngữ mặc định (Tiếng Anh) ngay khi trang tải xong, vì giá
# trị mặc định của ui_lang_switch là "English" nhưng nội dung Python vẫn
# render bằng tiếng Việt.
_UI_LANG_INIT_JS = """
() => {
""" + _UI_LANG_CORE_JS + """
    window.__pyvtLang = 'en';
    window.__pyvtApply();
}
"""

# JS: bật/tắt giao diện tối bằng cách gắn/gỡ lớp "dark" trên thẻ <html>
# (theo quy ước biến CSS chủ đề của Gradio), đồng thời lưu lựa chọn vào
# localStorage để giữ nguyên khi tải lại trang.
_THEME_JS = """
(theme) => {
    const isDark = theme.indexOf('Tối') !== -1 || theme.indexOf('Dark') !== -1;
    document.documentElement.classList.toggle('dark', isDark);
    try { localStorage.setItem('pyvt_theme', isDark ? 'dark' : 'light'); } catch (e) {}
    return theme;
}
"""

# JS: khôi phục giao diện đã lưu ngay khi trang tải xong; mặc định là tối
# trừ khi người dùng từng chọn sáng trước đó (lưu trong localStorage).
_THEME_INIT_JS = """
() => {
    try {
        if (localStorage.getItem('pyvt_theme') === 'light') {
            document.documentElement.classList.remove('dark');
        } else {
            document.documentElement.classList.add('dark');
        }
    } catch (e) {
        document.documentElement.classList.add('dark');
    }
}
"""


# ---------------------------------------------------------------------------
# Xây dựng giao diện
# ---------------------------------------------------------------------------
def build_ui():
    import gradio as gr

    with gr.Blocks(title="pyVideoTrans WebUI") as app:
        with gr.Row():
            with gr.Column(scale=5):
                gr.Markdown("""
# AIGenerate Video Translation WebUI
> [Giao diện này chỉ triển khai một phần tính năng, để dùng đầy đủ tính năng vui lòng dùng bản desktop (sp.exe hoặc sp.py)](https://pyvideotrans.com)
>
>  [Tài liệu sử dụng](https://pyvideotrans.com) |
>  [Mã nguồn](https://github.com/jianchang512/pyvideotrans) |
>  [Gặp sự cố](https://bbs.pyvideotrans.com)
----
                """)
            with gr.Column(scale=1, min_width=170):
                ui_lang_switch = gr.Radio(
                    choices=["🇻🇳 Tiếng Việt", "🇬🇧 English"],
                    value="�🇧 English",
                    label="🌐 Ngôn ngữ / Language",
                    interactive=True,
                )
                theme_switch = gr.Radio(
                    choices=["☀️ Sáng", "🌙 Tối"],
                    value="🌙 Tối",
                    label="🎨 Giao diện",
                    interactive=True,
                )
        # Chỉ đổi văn bản hiển thị trên trình duyệt (JS), không gọi về Python,
        # không ảnh hưởng giá trị dữ liệu (choices/value) gốc của các control.
        ui_lang_switch.change(fn=None, inputs=[ui_lang_switch], outputs=[], js=_UI_LANG_JS)
        theme_switch.change(fn=None, inputs=[theme_switch], outputs=[], js=_THEME_JS)
        app.load(fn=None, inputs=[], outputs=[], js=_THEME_INIT_JS)
        app.load(fn=None, inputs=[], outputs=[], js=_UI_LANG_INIT_JS)

        with gr.Tabs():
            # === Tab 1: Dịch video ===
            with gr.Tab("🎬 Dịch video", id="translate"):
                prev_recogn = gr.State(value=RECOGN_NAMES[DEFAULT_RECOGN])
                prev_translate = gr.State(value=TRANSLATE_NAMES[DEFAULT_TRANSLATE])
                prev_tts = gr.State(value=TTS_NAMES[DEFAULT_TTS])

                with gr.Row():
                    with gr.Column(scale=3):
                        input_file = gr.Video(label="Chọn tệp video", interactive=True)

                        recogn_choice = gr.Dropdown(choices=RECOGN_NAMES, value=RECOGN_NAMES[int(_user_params.get('recogn_type', DEFAULT_RECOGN)) if str(_user_params.get('recogn_type', '')).isdigit() else DEFAULT_RECOGN], label="Kênh nhận dạng", interactive=True)
                        model_choice = gr.Dropdown(choices=FASTER_MODEL_NAMES, value=_user_params.get('model_name', DEFAULT_MODEL), label="Mô hình", interactive=True)

                        translate_choice = gr.Dropdown(choices=TRANSLATE_NAMES, value=TRANSLATE_NAMES[int(_user_params.get('translate_type', DEFAULT_TRANSLATE)) if str(_user_params.get('translate_type', '')).isdigit() else DEFAULT_TRANSLATE], label="Kênh dịch", interactive=True)
                        source_lang = gr.Dropdown(choices=LANG_DISPLAY_NAMES, value=_display_from_lang_code(_user_params.get('source_language'), DEFAULT_SOURCE_LANG), label="Ngôn ngữ phát âm (ngôn ngữ nguồn)", interactive=True)
                        target_lang = gr.Dropdown(choices=['-']+LANG_DISPLAY_NAMES, value=_display_from_lang_code(_user_params.get('target_language'), DEFAULT_TARGET_LANG), label="Ngôn ngữ đích", interactive=True)

                        tts_choice = gr.Dropdown(choices=TTS_NAMES, value=TTS_NAMES[int(_user_params.get('tts_type', DEFAULT_TTS)) if str(_user_params.get('tts_type', '')).isdigit() else DEFAULT_TTS], label="Kênh lồng tiếng", interactive=True)
                                                # tiền điền danh sách nhân vật dựa trên kênh TTS và ngôn ngữ đích đã tải
                        _init_tts_idx = int(_user_params.get('tts_type', DEFAULT_TTS)) if str(_user_params.get('tts_type', '')).isdigit() else DEFAULT_TTS
                        _init_target = _user_params.get('target_language', DEFAULT_TARGET_LANG)
                        _init_langcode = _lang_code_from_display(_init_target) if _init_target and _init_target != '-' else None
                        try:
                            _init_roles = role_menu(_init_tts_idx, langcode=_init_langcode)
                            if not _init_roles:
                                _init_roles = ["No"]
                        except Exception:
                            _init_roles = ["No"]
                        _saved_role = _user_params.get('voice_role', 'No')
                        _init_role_val = _saved_role if _saved_role in _init_roles else _init_roles[0]
                        voice_role = gr.Dropdown(choices=_init_roles, value=_init_role_val, label="Nhân vật lồng tiếng", interactive=True)

                        with gr.Row():
                            voice_autorate = gr.Checkbox(label="Tăng tốc lồng tiếng", value=True)
                            video_autorate = gr.Checkbox(label="Làm chậm video", value=False)
                        with gr.Row():
                            voice_rate = gr.Slider(minimum=-50, maximum=50, value=int(str(_user_params.get("voice_rate", "0")).replace("%","")), step=1, label="Tốc độ lồng tiếng (%)")
                            volume_rate = gr.Slider(minimum=-95, maximum=100, value=int(str(_user_params.get("volume", "0")).replace("%","")), step=1, label="Điều chỉnh âm lượng (%)")
                            pitch_rate = gr.Slider(minimum=-100, maximum=100, value=int(str(_user_params.get("pitch", "0")).replace("Hz","")), step=1, label="Cao độ (Hz)")
                        subtitle_type = gr.Dropdown(choices=list(SUBTITLE_TYPES.keys()), value=list(SUBTITLE_TYPES.keys())[int(_user_params.get('subtitle_type', 1)) if str(_user_params.get('subtitle_type', '')).isdigit() and int(_user_params.get('subtitle_type', 1)) < len(SUBTITLE_TYPES) else 1], label="Kiểu nhúng phụ đề", interactive=True)
                        build_ass_editor()

                        with gr.Accordion("📋 Cài đặt thêm", open=False):
                            with gr.Row():
                                remove_noise = gr.Checkbox(label="Khử nhiễu", value=False)
                                fix_punc = gr.Dropdown(choices=list(PUNC_OPTIONS.keys()), value="Dấu câu mặc định", label="Xử lý dấu câu", interactive=True)
                            with gr.Row():
                                is_separate = gr.Checkbox(label="Tách giọng nói và âm thanh nền", value=False)
                                embed_bgm = gr.Checkbox(label="Nhúng lại âm thanh nền", value=True)
                            with gr.Row():
                                loop_bgm = gr.Dropdown(choices=list(LOOP_BGM_OPTIONS.keys()), value="Cắt nhạc nền", label="Xử lý âm thanh nền", interactive=True)
                                backaudio_volume = gr.Slider(minimum=0.0, maximum=2.0, value=float(_user_params.get("backaudio_volume", settings.get("backaudio_volume", 0.8))), step=0.1, label="Âm lượng nền")
                            with gr.Row():
                                remove_hardsub = gr.Checkbox(label="Xóa phụ đề cứng gốc trước khi dịch (video-subtitle-remover)", value=False)

                        with gr.Accordion("🏷️ Watermark bản quyền", open=False):
                            watermark_text = gr.Textbox(label="Chữ watermark bản quyền", placeholder="Để trống để tắt, ví dụ: © 2026 Kênh của bạn")
                            with gr.Row():
                                watermark_pos = gr.Dropdown(choices=list(WATERMARK_POSITION_OPTIONS.keys()), value="Dưới phải", label="Vị trí", interactive=True)
                                watermark_fontsize = gr.Slider(minimum=10, maximum=72, value=24, step=1, label="Cỡ chữ")
                                watermark_color = gr.Textbox(value="white", label="Màu chữ (tên hoặc mã hex, vd white/yellow/#FFCC00)")

                        cuda_accel = gr.Checkbox(label="Bật tăng tốc CUDA", value=False)
                        channel_warning = gr.Markdown("", visible=False)
                        
                        start_btn = gr.Button("🚀 Bắt đầu thực hiện", variant="primary", size="lg")

                    with gr.Column(scale=2):
                        log_output = gr.Textbox(label="Nhật ký thực thi", lines=20, interactive=False)
                        video_preview = gr.Video(label="Xem trước video", interactive=False)
                        result_files = gr.File(label="Tệp kết quả (nhấn để tải)", interactive=False)

                # Kiểm tra kênh và cập nhật danh sách mô hình
                def validate_recogn(choice, prev):
                    idx = _recogn_index_from_display(choice)

                    _rs=recognition.is_input_api(recogn_type=idx, return_str=True)
                    if _rs is not True:
                        msg = "Kênh «{}» hiện chưa khả dụng, đã tự động quay lại".format(choice)
                        gr.Warning(msg)
                        return prev, f"⚠️ {msg}", gr.update()

                    # cập nhật danh sách mô hình theo kênh
                    models = []
                    disabled = False
                    print(f'{idx=}')
                    print(f'{recognition.Whisper_CPP=}')
                    if idx in [recognition.FASTER_WHISPER, recognition.Faster_Whisper_XXL, recognition.WHISPERX_API]:
                        models = settings.WHISPER_MODEL_LIST
                    elif idx == recognition.OPENAI_WHISPER:
                        models = Openai_Whisper_Models.split(',')
                    elif idx == recognition.Deepgram:
                        models = DEEPGRAM_MODEL
                    elif idx == recognition.Whisper_CPP:
                        models = settings.Whisper_CPP_MODEL_LIST
                    elif idx == recognition.WHISPER_NET:
                        models = settings.Whisper_NET_MODEL_LIST
                    elif idx == recognition.QWENASR:
                        models = ['1.7B', '0.6B']
                    elif idx == recognition.HUGGINGFACE_ASR:
                        models = list(recognition.HUGGINGFACE_ASR_MODELS.keys())
                    elif idx == recognition.FUNASR_CN:
                        models = FUNASR_MODEL
                    else:
                        models = FASTER_MODEL_NAMES
                        disabled = True

                    if models:
                        default_val = models[0] if models else ""
                        return choice, "", gr.update(choices=models, value=default_val, interactive=not disabled)
                    return choice, "", gr.update(interactive=False)

                def validate_translate(choice, prev):
                    idx = _translate_index_from_display(choice)
                    _rs=translator.is_allow_translate(translate_type=idx, return_str=True)
                    if _rs is not True:
                        msg = "Kênh «{}» hiện chưa khả dụng, đã tự động quay lại".format(choice)
                        gr.Warning(msg)
                        return prev, f"⚠️ {msg}"
                    return choice, ""

                def tts_change_handler(choice, prev, target_display):
                    idx = _tts_index_from_display(choice)
                    warning = ""
                    _rs=tts.is_input_api(tts_type=idx, return_str=True)
                    if _rs is not True:
                        msg = "Kênh «{}» hiện chưa khả dụng, đã tự động quay lại".format(choice)
                        gr.Warning(msg)
                        choice = prev
                        warning = f"⚠️ {msg}"
                    tts_idx = _tts_index_from_display(choice)
                    lang_code = _lang_code_from_display(target_display)
                    try:
                        roles = role_menu(tts_idx, langcode=lang_code)
                        if not roles:
                            roles = ["No"]
                    except Exception:
                        roles = ["No"]
                    return choice, gr.update(choices=roles, value=roles[0] if roles else "No"), warning

                recogn_choice.change(fn=validate_recogn, inputs=[recogn_choice, prev_recogn], outputs=[recogn_choice, channel_warning, model_choice])
                translate_choice.change(fn=validate_translate, inputs=[translate_choice, prev_translate], outputs=[translate_choice, channel_warning])
                tts_choice.change(fn=tts_change_handler, inputs=[tts_choice, prev_tts, target_lang], outputs=[tts_choice, voice_role, channel_warning])

                def update_voice_roles(tts_display, target_display):
                    tts_idx = _tts_index_from_display(tts_display)
                    lang_code = _lang_code_from_display(target_display)
                    try:
                        roles = role_menu(tts_idx, langcode=lang_code)
                        if not roles:
                            roles = ["No"]
                    except Exception:
                        roles = ["No"]
                    return gr.update(choices=roles, value=roles[0] if roles else "No")

                target_lang.change(fn=update_voice_roles, inputs=[tts_choice, target_lang], outputs=[voice_role])

                # Thực hiện dịch
                _BTN_RUNNING = gr.update(value="⏳ Đang thực hiện...", interactive=False)
                _BTN_IDLE = gr.update(value="🚀 Bắt đầu thực hiện", interactive=True)
                
                def run_translation(file_path, recogn_display, model_name, translate_display,
                                    source_display, target_display, tts_display, voice_role_name,
                                    voice_autorate_val, video_autorate_val,
                                    voice_rate_val, volume_rate_val, pitch_rate_val,
                                    subtitle_type_name, remove_noise_val, fix_punc_name,
                                    is_separate_val, embed_bgm_val, loop_bgm_name, backaudio_volume_val,
                                    remove_hardsub_val, watermark_text_val, watermark_pos_name,
                                    watermark_fontsize_val, watermark_color_val, cuda_val):
                    print(f'{file_path=}')
                    if not file_path:
                        yield "❌ Vui lòng chọn một tệp video hoặc âm thanh trước", None, [], _BTN_IDLE
                        return
                    app_cfg.current_status = 'ing'
                    # xóa nhật ký, xem trước và đầu ra trước đó, hiển thị trạng thái đang thực hiện
                    yield "", None, [], _BTN_RUNNING

                    log_lines = []
                    def log(msg):
                        log_lines.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
                        return "\n".join(log_lines)

                    recogn_idx = _recogn_index_from_display(recogn_display)
                    translate_idx = _translate_index_from_display(translate_display)
                    tts_idx = _tts_index_from_display(tts_display)
                    source_code = _lang_code_from_display(source_display)
                    target_code = _lang_code_from_display(target_display)
                    subtitle_val = SUBTITLE_TYPES.get(subtitle_type_name, 1)
                    fix_punc_val = PUNC_OPTIONS.get(fix_punc_name, 0)
                    loop_bgm_val = LOOP_BGM_OPTIONS.get(loop_bgm_name, 0)


                    try:
                        app_cfg.exit_soft = False
                        app_cfg.exec_mode = 'cli'
                        
                        getset_gpu()
                        # In rõ trạng thái GPU ra console/terminal (vd để xem trên Colab) và vào log UI
                        _gpu_ok = app_cfg.NVIDIA_GPU_NUMS > 0
                        _gpu_name = ""
                        if _gpu_ok:
                            import torch
                            _gpu_name = torch.cuda.get_device_name(0)
                        _gpu_status_msg = (
                            f"🖥️ GPU phát hiện: {_gpu_name} (số card khả dụng: {app_cfg.NVIDIA_GPU_NUMS})"
                            if _gpu_ok else "🖥️ Không phát hiện GPU khả dụng, sẽ chạy bằng CPU"
                        )
                        if cuda_val and not _gpu_ok:
                            _gpu_status_msg += " ⚠️ Đã bật tăng tốc CUDA nhưng không tìm thấy GPU!"
                        print(_gpu_status_msg, flush=True)
                        yield log(_gpu_status_msg), None, [], _BTN_RUNNING

                        _effective_file_path = Path(file_path).absolute().as_posix()
                        if remove_hardsub_val:
                            yield log("🧹 Đang xóa phụ đề cứng gốc bằng video-subtitle-remover (VSR)..."), None, [], _BTN_RUNNING
                            try:
                                from videotrans.util.subtitle_remover import remove_hard_subtitle, SubtitleRemoverError
                                _vsr_out_dir = Path(TEMP_DIR) / "vsr_cache"
                                _vsr_out_dir.mkdir(parents=True, exist_ok=True)
                                _vsr_output = str(_vsr_out_dir / f"nosub_{Path(file_path).stem}.mp4")
                                remove_hard_subtitle(
                                    input_path=_effective_file_path,
                                    output_path=_vsr_output,
                                    vsr_dir=settings.get('vsr_dir', ''),
                                    vsr_python=settings.get('vsr_python', ''),
                                    inpaint_mode=settings.get('vsr_inpaint_mode', ''),
                                )
                                _effective_file_path = _vsr_output
                                yield log("✓ Đã xóa phụ đề cứng gốc xong"), None, [], _BTN_RUNNING
                            except SubtitleRemoverError as e:
                                yield log(f"⚠️ Xóa phụ đề cứng gốc thất bại, dùng video gốc: {e}"), None, [], _BTN_RUNNING

                        _file_obj = tools.format_video(_effective_file_path)
                        _nospacebasename = _file_obj["basename"].replace(" ", "-").replace(".", "-")
                        _cache_folder = f'{TEMP_DIR}/{_file_obj["uuid"]}'
                        app_cfg.rm_uuid(_file_obj['uuid'])
                        _target_dir = f'{ROOT_DIR}/output/{_nospacebasename}'
                        _file_obj['target_dir'] = _target_dir
                        Path(_cache_folder).mkdir(parents=True, exist_ok=True)
                        target_path = Path(_target_dir)
                        if target_path.exists():
                            for f in sorted(target_path.rglob("*")):
                                if f.is_file():
                                    if f.suffix.lower() in ['.mp4','.mkv']:
                                        f.unlink(missing_ok=True)
                        Path(_target_dir).mkdir(parents=True, exist_ok=True)
                        
                        from dataclasses import asdict
                        common_params = {'name': _effective_file_path, "cache_folder": _cache_folder}
                        common_params.update(asdict(_file_obj))
                        yield log(f"Tệp nguồn: {Path(file_path).name}"), None, [], _BTN_RUNNING

                        vtv_params = {
                            "source_language_code": source_code, "target_language_code": target_code,
                            "recogn_type": recogn_idx, "model_name": model_name, "is_cuda": cuda_val,
                            "remove_noise": remove_noise_val, "enable_diariz": False, "nums_diariz": -1,
                            "detect_language": source_code, "rephrase": 0, "fix_punc": fix_punc_val,
                            "tts_type": tts_idx, "voice_role": voice_role_name,
                            "voice_rate": _format_rate(int(voice_rate_val)),
                            "volume": _format_rate(int(volume_rate_val)),
                            "pitch": _format_pitch(int(pitch_rate_val)),
                            "voice_autorate": voice_autorate_val, "video_autorate": video_autorate_val,
                            "align_sub_audio": True, "translate_type": translate_idx,
                            "is_separate": is_separate_val, "recogn2pass": False,
                            "subtitle_type": subtitle_val, 
                            "clear_cache": True,
                            "embed_bgm": embed_bgm_val, "loop_backaudio": loop_bgm_val,
                            "backaudio_volume": backaudio_volume_val, "background_music": "",
                        }
                        params_dict = {**common_params, **vtv_params}

                        yield log(f"Nhận dạng: {RECOGN_NAMES[recogn_idx]}  Dịch: {TRANSLATE_NAMES[translate_idx]}  Lồng tiếng: {TTS_NAMES[tts_idx]}"), None, [], _BTN_RUNNING
                        yield log(f"Ngôn ngữ: {source_code} → {target_code}  Nhân vật: {voice_role_name}"), None, [], _BTN_RUNNING
                        yield log(""), None, [], _BTN_RUNNING

                        yield log("▶ Bắt đầu thực hiện dịch video..."), None, [], _BTN_RUNNING
                        from videotrans.task.trans_create import TransCreate
                        from videotrans.task.taskcfg import TaskCfgVTT
                        trk = TransCreate(cfg=TaskCfgVTT(**params_dict))

                        stages = [
                            ("Giai đoạn 1/8: Xử lý trước...", "prepare", "Đã xử lý trước xong"),
                            ("Giai đoạn 2/8: Nhận dạng giọng nói...", "recogn", "Đã nhận dạng giọng nói xong"),
                            ("Giai đoạn 3/8: Tách người nói...", "diariz", "Đã tách người nói xong"),
                            ("Giai đoạn 4/8: Dịch phụ đề...", "trans", "Đã dịch phụ đề xong"),
                            ("Giai đoạn 5/8: Tạo lồng tiếng...", "dubbing", "Đã tạo lồng tiếng xong"),
                            ("Giai đoạn 6/8: Đồng bộ âm thanh và hình ảnh...", "align", "Đã đồng bộ xong"),
                            ("Giai đoạn 7/8: Nhận dạng lần 2...", "recogn2pass", "Đã nhận dạng lần 2 xong"),
                            ("Giai đoạn 8/8: Tổng hợp cuối cùng...", "assembling", "Đã tổng hợp xong"),
                        ]
                        for stage_name, method, done_msg in stages:
                            yield log(stage_name), None, [], _BTN_RUNNING
                            getattr(trk, method)()
                            if method != "assembling":
                                yield log(f"✓ {done_msg}"), None, [], _BTN_RUNNING

                        trk.task_done()
                        yield log("✓ Đã ghép video xong"), None, [], _BTN_RUNNING
                        yield log("✅ Toàn bộ tác vụ đã hoàn thành!"), None, [], _BTN_RUNNING

                        output_files, video_preview_path = [], None
                        
                        if target_path.exists():
                            for f in sorted(target_path.rglob("*")):
                                if f.is_file():
                                    if f.suffix.lower() == '.mp4' and video_preview_path is None:
                                        video_preview_path = str(f)
                                    else:
                                        output_files.append(str(f))
                        if not output_files and video_preview_path is None:
                            for f in sorted(Path(_cache_folder).rglob("*")):
                                if f.is_file():
                                    if f.suffix.lower() == '.mp4' and video_preview_path is None:
                                        video_preview_path = str(f)
                                    elif f.suffix.lower() in ('.mkv', '.wav', '.srt', '.txt', '.mp3'):
                                        output_files.append(str(f))

                        if watermark_text_val and watermark_text_val.strip() and video_preview_path:
                            yield log("🏷️ Đang thêm watermark bản quyền vào video..."), None, [], _BTN_RUNNING
                            try:
                                from videotrans.util.watermark import add_text_watermark
                                add_text_watermark(
                                    video_preview_path, watermark_text_val,
                                    position=WATERMARK_POSITION_OPTIONS.get(watermark_pos_name, "bottom-right"),
                                    fontsize=int(watermark_fontsize_val), fontcolor=watermark_color_val,
                                )
                                yield log("✓ Đã thêm watermark bản quyền"), None, [], _BTN_RUNNING
                            except Exception as e:
                                yield log(f"⚠️ Thêm watermark thất bại: {e}"), None, [], _BTN_RUNNING

                        # thêm tệp nhật ký trong ngày vào danh sách đầu ra
                        import datetime
                        log_file = Path(ROOT_DIR) / "logs" / f"{datetime.datetime.now().strftime('%Y%m%d')}.log"
                        if log_file.exists():
                            output_files.append(str(log_file))

                        yield log(f"Thư mục đầu ra: {_target_dir}"), video_preview_path, output_files, _BTN_IDLE

                    except Exception as e:
                        tb = traceback.format_exc()
                        yield log(f"❌ Lỗi thực hiện: {str(e)}\n\n{tb}"), None, [], _BTN_IDLE
                start_btn.click(fn=run_translation,
                    inputs=[input_file, recogn_choice, model_choice, translate_choice,
                            source_lang, target_lang, tts_choice, voice_role,
                            voice_autorate, video_autorate, voice_rate, volume_rate, pitch_rate,
                            subtitle_type, remove_noise, fix_punc,
                            is_separate, embed_bgm, loop_bgm, backaudio_volume,
                            remove_hardsub, watermark_text, watermark_pos, watermark_fontsize,
                            watermark_color, cuda_accel],
                    outputs=[log_output, video_preview, result_files, start_btn])

            # === Tab 2: Cài đặt kênh ===
            with gr.Tab("⚙️ Cài đặt kênh", id="settings"):
                build_channel_settings()

            # === Tab 3: Tùy chọn nâng cao ===
            with gr.Tab("🔧 Tùy chọn nâng cao", id="advanced"):
                build_advanced_settings()

    return app


if __name__ == "__main__":
    try:
        import argparse
        import gradio as gr
        parser = argparse.ArgumentParser(description="pyVideoTrans WebUI")
        parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address")
        parser.add_argument("--port", type=int, default=None, help="Port number (default: auto-pick a free port starting from 7860)")
        parser.add_argument("--share", action="store_true", help="Create a public Gradio link")
        args = parser.parse_args()
        app = build_ui()
        app.launch(server_name=args.host, server_port=args.port, share=args.share, inbrowser=True, theme=gr.themes.Soft(),css="""
        /* Phông chữ mặc định: Microsoft YaHei > PingFang SC > phông hệ thống không chân */
        *, *::before, *::after {
            font-family: "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", "WenQuanYi Micro Hei", "Noto Sans CJK SC", "Source Han Sans SC", "SimHei", sans-serif !important;
        }
        h1{text-align:center}
        /* Đồng bộ phông chữ cho ô nhập và nút */
        input, textarea, select, button, label, .gr-textbox, .gr-dropdown, .gr-checkbox {
            font-family: "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", "WenQuanYi Micro Hei", "Noto Sans CJK SC", "Source Han Sans SC", "SimHei", sans-serif !important;
        }
    """)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n❌ Khởi động thất bại: {e}")



