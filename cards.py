import os
import json
import urllib.parse
import textwrap
import io
from datetime import datetime, timezone, timedelta
import google.generativeai as genai
import requests
from PIL import Image, ImageDraw, ImageFont

TELEGRAM_BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CARDS_CHAT_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

genai.configure(api_key=GEMINI_API_KEY)

def get_time_slot():
    now_hour = datetime.now(timezone(timedelta(hours=3))).hour
    if 4 <= now_hour < 12:
        return "ранок"
    elif 12 <= now_hour < 20:
        return "вечір"
    else:
        return "ніч"

def generate_card_data(slot):
    prompt = f"""
Ти створюєш теплу естетичну листівку українською мовою.
Час доби: {slot} (ранок = доброго ранку/гарного дня; вечір = затишного теплого вечора; ніч = спокійної тихої мирної ночі).

Вимоги:
1. "caption": Щире, коротке і тепле побажання українською мовою (1-2 лаконічних речення, щоб гарно виглядало на фото). Без віршів. Акцент на затишок, тепло, ранкову каву/чай, спокій і мир.
2. "image_prompt": Детальний промпт для фотогенерації АНГЛІЙСЬКОЮ мовою.
Стиль: Ultra-realistic cozy lifestyle and nature photography, warm natural golden hour sunlight, authentic country house terrace, wooden table with ceramic mug, fresh garden flowers, morning dew, 35mm film aesthetic. Без людей у кадрі, тільки природа і затишок.

Відповідай СУВОРО у форматі JSON:
{{
  "caption": "коротке побажання українською",
  "image_prompt": "detailed english prompt for realistic photography"
}}
"""
    generation_config = genai.GenerationConfig(response_mime_type="application/json")
    model = genai.GenerativeModel("gemini-3.6-flash", generation_config=generation_config)
    res = model.generate_content(prompt)
    
    text = res.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())

def add_text_watermark(image_bytes, text_to_draw):
    # Открываем картинку через Pillow
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    
    draw = ImageDraw.Draw(img, "RGBA")
    
    # Пытаемся загрузить стандартный шрифт Ubuntu
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font_size = int(w * 0.038)
    try:
        font = ImageFont.truetype(font_path, font_size)
    except:
        font = ImageFont.load_default()
        
    # Форматируем текст по строкам
    max_chars = int(w / (font_size * 0.55))
    lines = textwrap.wrap(text_to_draw, width=max_chars)
    
    line_height = font_size * 1.4
    box_height = int(len(lines) * line_height + font_size * 1.5)
    
    # Координаты для нижней плашки
    margin = int(w * 0.04)
    box_y0 = h - box_height - margin
    box_y1 = h - margin
    box_x0 = margin
    box_x1 = w - margin
    
    # Рисуем полупрозрачную элегантную плашку с закругленными углами
    draw.rounded_rectangle([box_x0, box_y0, box_x1, box_y1], radius=16, fill=(0, 0, 0, 150))
    
    # Рисуем текст по центру плашки
    current_y = box_y0 + font_size * 0.75
    for line in lines:
        try:
            bbox = font.getbbox(line)
            text_w = bbox[2] - bbox[0]
        except:
            text_w = font.getlength(line)
            
        text_x = (w - text_w) / 2
        draw.text((text_x, current_y), line, font=font, fill=(255, 255, 255, 255))
        current_y += line_height
        
    # Сохраняем в байты JPEG
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=95)
    return output.getvalue()

def send_postcard():
    slot = get_time_slot()
    print(f"Генерація листівки ({slot})...", flush=True)
    data = generate_card_data(slot)
    
    caption_text = data.get("caption", "Доброго та затишного дня!")
    raw_prompt = data.get("image_prompt", "cozy country morning garden flowers soft light")
    
    encoded_prompt = urllib.parse.quote(raw_prompt)
    flux_base = "".join(["https://", "image.pollinations.ai", "/prompt/"])
    image_url = f"{flux_base}{encoded_prompt}?width=1080&height=1350&model=flux&nologo=true"
    
    print("Завантаження зображення...", flush=True)
    img_resp = requests.get(image_url, timeout=60)
    img_resp.raise_for_status()
    
    print("Накладання тексту на листівку...", flush=True)
    final_image_bytes = add_text_watermark(img_resp.content, caption_text)
    
    print("Відправка готової листівки в Telegram...", flush=True)
    tg_url = "".join(["https://", "api.telegram.org", "/bot", TELEGRAM_BOT_TOKEN, "/sendPhoto"])
    
    data_payload = {
        "chat_id": CHAT_ID,
        "caption": "🌿 Затишна листівка для вас",
        "parse_mode": "HTML"
    }
    files = {
        "photo": ("postcard.jpg", final_image_bytes, "image/jpeg")
    }
    
    res = requests.post(tg_url, data=data_payload, files=files, timeout=40)
    print(f"Статус відправки: {res.status_code}", flush=True)
    res.raise_for_status()

if __name__ == "__main__":
    send_postcard()
