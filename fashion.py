import os
import json
import html
import re
from datetime import datetime, timezone, timedelta
import feedparser
import google.generativeai as genai
import requests

TELEGRAM_BOT_TOKEN = os.environ["BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["CHAT_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

WEB_APP_URL = "https://" + "lakazovavolga-ops.github.io/Ai-monitor/"

genai.configure(api_key=GEMINI_API_KEY)

FASHION_FEEDS = [
    "https://fashionista.com/.rss/excerpt/",
    "https://hypebeast.com/fashion/feed"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def extract_image_url(entry):
    if 'media_content' in entry and len(entry['media_content']) > 0:
        return entry['media_content'][0].get('url', '')
    if 'enclosures' in entry and len(entry['enclosures']) > 0:
        return entry['enclosures'][0].get('href', '')
    text = entry.get('summary', '')
    match = re.search(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', text)
    if match:
        return match.group(1)
    return ""

def collect_fashion_news():
    candidates = []
    for url in FASHION_FEEDS:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=8)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:6]:
                img = extract_image_url(entry)
                summary = re.sub(r'<[^>]+>', '', entry.get('summary', ''))[:300]
                candidates.append({
                    "title": entry.title,
                    "summary": summary,
                    "image": img
                })
        except Exception as e:
            print(f"Пропуск RSS: {e}", flush=True)
    return candidates

def analyze_fashion(news_items):
    prompt = f"""
Ты — профессиональный куратор высокой моды и эксперт по крою.
Ниже список свежих модных релизов и показов с фото:
{json.dumps(news_items, ensure_ascii=False)}

Выбери ОДИН самый эстетичный, знаковый образ или новинку (приоритет люксовым брендам уровня Hermès, Burberry, Chanel, Prada, The Row, Loewe, Saint Laurent или ключевым подиумным трендам сезона).
Сформируй анализ строго в формате JSON-объекта:
{{
  "brand": "Бренд или модный дом",
  "topic": "Название образа или коллекции в 3-5 словах",
  "image_url": "Точная ссылка на изображение из предоставленного объекта (не меняй её)",
  "colors": "Модная палитра (назови 2-3 сложных трендовых оттенка)",
  "cut_silhouette": "Фасон и архитектура кроя (линия плеча, талия, посадка, пропорции)",
  "materials": "Материалы и фактуры (шерсть, плотный габардин, шелк, кожа)",
  "practical_tip": "Как применить этот образ в повседневном гардеробе обычной жизни без люксовых затрат"
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

def send_fashion_telegram(data):
    brand = html.escape(str(data.get("brand", "Модный дайджест")))
    topic = html.escape(str(data.get("topic", "")))
    colors = html.escape(str(data.get("colors", "")))
    cut = html.escape(str(data.get("cut_silhouette", "")))
    materials = html.escape(str(data.get("materials", "")))
    tip = html.escape(str(data.get("practical_tip", "")))
    image_url = data.get("image_url", "")

    caption_lines = [
        f"✨ <b>{brand}</b> | <i>{topic}</i>\n",
        f"🎨 <b>Палитра:</b> {colors}",
        f"✂️ <b>Крой и силуэт:</b> {cut}",
        f"🧵 <b>Материалы:</b> {materials}\n",
        f"💡 <b>В гардероб:</b> {tip}\n",
        "<i>Подробный разбор и галерея образов — в мониторе:</i>"
    ]
    caption = "\n".join(caption_lines)

    reply_markup = {
        "inline_keyboard": [
            [{"text": "👗 Открыть раздел Мода", "url": WEB_APP_URL}]
        ]
    }

    tg_api_base = "".join(["https://", "api.telegram.org", "/bot", TELEGRAM_BOT_TOKEN])

    if image_url and image_url.startswith("http"):
        send_photo_url = tg_api_base + "/sendPhoto"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "photo": image_url,
            "caption": caption,
            "parse_mode": "HTML",
            "reply_markup": reply_markup
        }
        res = requests.post(send_photo_url, json=payload, timeout=20)
        if res.status_code == 200:
            print("Фото-пост моды успешно отправлен в Telegram.", flush=True)
            return

    send_msg_url = tg_api_base + "/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": caption,
        "parse_mode": "HTML",
        "reply_markup": reply_markup
    }
    requests.post(send_msg_url, json=payload, timeout=15)
    print("Текстовый пост моды отправлен.", flush=True)

def save_fashion_history(item):
    history = []
    if os.path.exists("fashion_data.json"):
        try:
            with open("fashion_data.json", "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception as e:
            print(f"Ошибка чтения архива моды: {e}")

    now_str = datetime.now(timezone(timedelta(hours=3))).strftime("%d.%m.%Y")
    item["date"] = now_str
    
    history = [item] + history[:9]
    with open("fashion_data.json", "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print("fashion_data.json сохранен.", flush=True)

if __name__ == "__main__":
    print("Запуск модного мониторинга...", flush=True)
    news = collect_fashion_news()
    if news:
        analysis = analyze_fashion(news)
        save_fashion_history(analysis)
        send_fashion_telegram(analysis)
    print("Модный блок завершил работу!", flush=True)
