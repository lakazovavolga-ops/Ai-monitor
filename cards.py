import os
import json
import urllib.parse
from datetime import datetime, timezone, timedelta
import google.generativeai as genai
import requests

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
1. "caption": Щире, живе і тепле побажання українською мовою (2-3 короткі речення). Жодних шаблонних віршів із мережі. Акцент на затишок дому, тепло, чай або каву, тишу, природу, спокій і мир.
2. "image_prompt": Детальний промпт для фотогенерації АНГЛІЙСЬКОЮ мовою.
Стиль: Ultra-realistic cozy lifestyle and nature photography, warm natural sunlight, authentic country house terrace, wooden table with ceramic mug, fresh garden flowers, morning dew or warm lamp glow, 35mm film photography aesthetic, soft warm shadows. Без людей у кадрі, тільки чиста затишна атмосфера та природа.

Відповідай СУВОРО у форматі JSON:
{{
  "caption": "текст побажання українською",
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

def send_postcard():
    slot = get_time_slot()
    print(f"Генерація листівки ({slot})...", flush=True)
    data = generate_card_data(slot)
    
    caption = data.get("caption", "Доброго та затишного дня!")
    raw_prompt = data.get("image_prompt", "cozy country morning garden flowers soft light")
    
    encoded_prompt = urllib.parse.quote(raw_prompt)
    image_url = f"[https://image.pollinations.ai/prompt/](https://image.pollinations.ai/prompt/){encoded_prompt}?width=1080&height=1350&model=flux&nologo=true"
    
    print("Відправка в Telegram...", flush=True)
    tg_url = "".join(["https://", "api.telegram.org", "/bot", TELEGRAM_BOT_TOKEN, "/sendPhoto"])
    payload = {
        "chat_id": CHAT_ID,
        "photo": image_url,
        "caption": f"🌿 {caption}",
        "parse_mode": "HTML"
    }
    
    res = requests.post(tg_url, json=payload, timeout=35)
    print(f"Статус відправки: {res.status_code}", flush=True)
    res.raise_for_status()

if __name__ == "__main__":
    send_postcard()
