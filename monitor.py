import os
import json
import time
import requests
import feedparser
from google import genai

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_telegram(text):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True}
    )

# 1. Загрузка новостей
feed = feedparser.parse("https://news.ycombinator.com/rss")
entries = [f"- {e.title}: {e.link}" for e in feed.entries[:15]]
raw_news = "\n".join(entries)

prompt = f"""Ты — аналитический агент по IT.
Отфильтруй входящий поток новостей. Оставь только фундаментальные события:
- Релизы важных моделей AI и обновлений архитектур
- Инциденты и сбои облачной инфраструктуры
- Крупные регуляторные штрафы, M&A и законодательные решения по Big Tech

Игнорируй мелкие стартапы и маркетинговый шум.
Верни строго валидный JSON-массив объектов:
[{{"title": "Краткая суть на русском", "url": "ссылка"}}]
Если важных новостей нет, верни: []

Новости:
{raw_news}"""

# 2. Запрос к Gemini с повторными попытками при 503
client = genai.Client(api_key=GEMINI_KEY)
response = None

for attempt in range(1, 5):
    try:
        print(f"Попытка {attempt} подключения к gemini-3.6-flash...")
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt
        )
        if response and response.text:
            break
    except Exception as e:
        print(f"Сервер занят ({e}), ждем...")
        time.sleep(12)

# 3. Отправка результата
if response and response.text:
    clean_json = response.text.replace("```json", "").replace("```", "").strip()
    try:
        items = json.loads(clean_json)
        if items:
            msg = "🤖 **IT-мониторинг:**\n\n"
            for item in items:
                msg += f"• {item['title']}\n🔗 {item['url']}\n\n"
            send_telegram(msg)
        else:
            send_telegram("✅ Связь установлена! Бот активен, критических событий в IT за последние часы нет.")
    except Exception:
        send_telegram("✅ Связь установлена! Бот активен и готов к мониторингу.")
else:
    send_telegram("🤖 Бот успешно запущен на GitHub! Серверы Google AI сейчас испытывают пиковую нагрузку (503), следующий сбор новостей пройдет по расписанию.")
