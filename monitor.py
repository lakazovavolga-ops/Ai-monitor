import os
import json
import html
import feedparser
import google.generativeai as genai
import requests

TELEGRAM_BOT_TOKEN = os.environ["BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["CHAT_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
WEB_APP_URL = "https://lakazovavolga-ops.github.io/Ai-monitor/"

genai.configure(api_key=GEMINI_API_KEY)

RSS_FEEDS = {
    "Геоэкономика": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "Рынки": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "ВПК": "https://www.defensenews.com/arc/outboundfeeds/rss/category/global/?outputType=xml",
    "Технологии": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "Азия": "https://asia.nikkei.com/rss/feed/nar"
}

def collect_news():
    items = []
    for category, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:2]:
                summary = entry.get('summary', '')[:250]
                items.append(f"[{category}] {entry.title}: {summary}")
        except Exception as e:
            print(f"Ошибка загрузки {category}: {e}")
    return "\n".join(items)

def generate_analysis(raw_text):
    prompt = f"""
Ты — ведущий геоэкономический аналитик. На основе входящих новостей сформируй анализ строго в формате массива JSON-объектов.
Каждый объект должен содержать:
- "category": название категории
- "icon": эмодзи
- "summary": тезис события в 1-2 предложениях
- "mechanism": экономический и сырьевой механизм
- "precedent": исторический прецедент (XX-XXI век)
- "impact": влияние на обычного человека

Новости:
{raw_text}
"""
    # Включаем принудительный строгий режим JSON на стороне API
    generation_config = genai.GenerationConfig(
        response_mime_type="application/json"
    )

    models_to_try = ["gemini-3.6-flash", "gemini-flash-latest", "gemini-3.5-flash"]
    response = None

    for model_name in models_to_try:
        try:
            print(f"Подключение к модели: {model_name}")
            model = genai.GenerativeModel(model_name, generation_config=generation_config)
            res = model.generate_content(prompt)
            if res and res.text:
                response = res
                break
        except Exception as err:
            print(f"Модель {model_name} вернула ошибку: {err}")

    if not response:
        raise RuntimeError("Не удалось получить валидный ответ от моделей Gemini.")

    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()

def send_telegram_alert(cards):
    text_lines = ["🌐 <b>Глобальный Монитор: Свежая сводка</b>\n"]
    for card in cards[:4]:
        icon = card.get('icon', '🔹')
        cat = html.escape(str(card.get('category', '')))
        summary = html.escape(str(card.get('summary', '')))
        text_lines.append(f"{icon} <b>{cat}</b>")
        text_lines.append(f"{summary}\n")

    text_lines.append("<i>Полный анализ, цепочки поставок и исторические прецеденты:</i>")
    message_text = "\n".join(text_lines)

    url = f"[https://api.telegram.org/bot](https://api.telegram.org/bot){TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message_text,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [
                [
                    {
                        "text": "📊 Открыть интерактивный монитор",
                        "url": WEB_APP_URL
                    }
                ]
            ]
        }
    }
    res = requests.post(url, json=payload)
    print(f"Telegram API: статус {res.status_code}")
    res.raise_for_status()

if __name__ == "__main__":
    raw_data = collect_news()
    analysis_json = generate_analysis(raw_data)
    
    cards_data = json.loads(analysis_json)
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(cards_data, f, ensure_ascii=False, indent=2)
    
    send_telegram_alert(cards_data)
    print("Готово: данные записаны, сводка отправлена.")
