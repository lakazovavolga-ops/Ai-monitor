import os
import json
import html
import urllib.parse
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
Час доби: {slot} (ранок = доброго ранку; вечір = затишного вечора; ніч = мирної спокійної ночі).

Вимоги:
1. "caption": Коротке, дуже містке та щире побажання українською мовою (строго 1-2 речення, до 15-18 слів, щоб красиво лягло на листівку). Теми: спокій, домашнє тепло, гармонія, чашка чаю/кави, тихий вечір.
2. "image_prompt": Детальний промпт для фотогенерації АНГЛІЙСЬКОЮ мовою.
Стиль: Ultra-realistic cozy lifestyle and nature photography, warm natural sunlight, authentic country house terrace, wooden table with ceramic mug, fresh garden flowers, 35mm film photography aesthetic, soft warm shadows. Без людей у кадрі.

Відповідай СУВОРО у форматі JSON:
{{
  "caption": "коротке лаконічне побажання українською",
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

def wrap_by_pixels(text, font, max_px):
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test = " ".join(current_line + [word])
        try:
            bbox = font.getbbox(test)
            w = bbox[2] - bbox[0]
        except:
            w = font.getlength(test)
            
        if w <= max_px:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                lines.append(word)
                current_line = []
    if current_line:
        lines.append(" ".join(current_line))
    return lines

def process_card_image(image_bytes, text_to_draw):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    
    # Срезаем нижнюю полосу (55px), полностью удаляя водяной знак pollinations
    img = img.crop((0, 0, w, h - 55))
    w, h = img.size
    
    draw = ImageDraw.Draw(img, "RGBA")
    
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font_size = int(w * 0.033)
    try:
        font = ImageFont.truetype(font_path, font_size)
    except:
        font = ImageFont.load_default()
        
    # Ограничиваем ширину текста до 78% от ширины кадра (гарантированная защита от обрезки)
    max_text_px = int(w * 0.78)
    lines = wrap_by_pixels(text_to_draw, font, max_text_px)
    
    line_h = int(font_size * 1.45)
    pad_y = int(font_size * 1.1)
    pad_x = int(w * 0.05)
    
    # Вычисляем точную ширину самой длинной строки
    max_measured_w = 0
    for line in lines:
        try:
            bb = font.getbbox(line)
            lw = bb[2] - bb[0]
        except:
            lw = font.getlength(line)
        if lw > max_measured_w:
            max_measured_w = lw
            
    box_w = max_measured_w + (pad_x * 2)
    box_h = (len(lines) * line_h) + (pad_y * 1.5)
    
    # Центрируем плашку снизу
    box_x0 = int((w - box_w) / 2)
    box_x1 = box_x0 + box_w
    box_y1 = int(h - (w * 0.05))
    box_y0 = int(box_y1 - box_h)
    
    # Полупрозрачная черная подложка
    draw.rounded_rectangle([box_x0, box_y0, box_x1, box_y1], radius=18, fill=(0, 0, 0, 160))
    
    # Отрисовка строк строго по центру плашки
    cur_y = box_y0 + pad_y
    for line in lines:
        try:
            bb = font.getbbox(line)
            lw = bb[2] - bb[0]
        except:
            lw = font.getlength(line)
        text_x = int(box_x0 + (box_w - lw) / 2)
        draw.text((text_x, cur_y), line, font=font, fill=(255, 255, 255, 255))
        cur_y += line_h
        
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=95)
    return out.getvalue()

def send_postcard():
    slot = get_time_slot()
    print(f"Генерація листівки ({slot})...", flush=True)
    data = generate_card_data(slot)
    
    caption_text = data.get("caption", "Доброго та затишного дня!")
    raw_prompt = data.get("image_prompt", "cozy country evening garden flowers tea soft light")
    
    encoded_prompt = urllib.parse.quote(raw_prompt)
    flux_base = "".join(["https://", "image.pollinations.ai", "/prompt/"])
    image_url = f"{flux_base}{encoded_prompt}?width=1080&height=1350&model=flux&nologo=true"
    
    print("Завантаження зображення...", flush=True)
    img_resp = requests.get(image_url, timeout=60)
    img_resp.raise_for_status()
    
    print("Обробка: зріз логотипу та точне центрування тексту...", flush=True)
    final_bytes = process_card_image(img_resp.content, caption_text)
    
    print("Відправка готової листівки в Telegram...", flush=True)
    tg_url = "".join(["https://", "api.telegram.org", "/bot", TELEGRAM_BOT_TOKEN, "/sendPhoto"])
    
    data_payload = {
        "chat_id": CHAT_ID,
        "caption": "🌿 Затишна листівка",
        "parse_mode": "HTML"
    }
    files = {
        "photo": ("postcard.jpg", final_bytes, "image/jpeg")
    }
    
    res = requests.post(tg_url, data=data_payload, files=files, timeout=40)
    print(f"Статус відправки: {res.status_code}", flush=True)
    res.raise_for_status()

if __name__ == "__main__":
    send_postcard()
