import os
import json
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
                items.append(f"[{category}] {entry.title}: {entry.get('summary', '')[:250]}")
        except Exception as e:
            print(f"Ошибка загрузки {category}: {e}")
    return "\n".join(items)

def generate_analysis(raw_text):
    prompt = f"""
Ты — ведущий геоэкономический аналитик. На основе входящих новостей сформируй анализ строго в формате валидного JSON-массива из объектов.
Не добавляй никакого вступительного или пояснительного текста, разметки markdown (```json ... ```), выведи только чистый массив JSON.

Формат каждого объекта:
{{
  "category": "Название категории (Геоэкономика, Рынки, ВПК, Технологии или Азия)",
  "icon": "соответствующий эмодзи",
  "summary": "Главный вывод и тезис события в 1-2 предложениях (для быстрого чтения за 15 секунд)",
  "mechanism": "Экономический и производственный механизм (цепочки поставок, капитал, сырье)",
  "precedent": "Исторический прецедент (аналогия из истории XX-XXI века и чем все закончилось)",
  "impact": "Влияние на уровень жизни обычного человека"
}}

Новости для анализа:
{raw_text}
"""
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    text = response.text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:]).strip()
    return text

def send_telegram_alert(cards):
    text_lines = ["🌐 <b>Глобальный Монитор: Свежая сводка</b>\n"]
    for card in cards[:4]:
        text_lines.append(f"{card.get('icon', '🔹')} <b>{card.get('category')}</b>")
        text_lines.append(f"{card.get('summary')}\n")

    text_lines.append("<i>Полный анализ, исторические прецеденты и цепочки поставок — в приложении ниже:</i>")
    message_text = "\n".join(text_lines)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message_text,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [
                [
                    {
                        "text": "📊 Открыть интерактивный монитор",
                        "web_app": {"url": WEB_APP_URL}
                    }
                ]
            ]
        }
    }
    requests.post(url, json=payload)

if __name__ == "__main__":
    raw_data = collect_news()
    analysis_json = generate_analysis(raw_data)
    
    try:
        cards_data = json.loads(analysis_json)
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(cards_data, f, ensure_ascii=False, indent=2)
        send_telegram_alert(cards_data)
        print("Сводка отправлена, data.json успешно записан.")
    except Exception as e:
        print(f"Ошибка обработки JSON: {e}")
