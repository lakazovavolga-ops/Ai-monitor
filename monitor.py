import os
import json
import time
import requests
import feedparser
from google import genai

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

client = genai.Client(api_key=GEMINI_KEY)

# 1. Загрузка новостей
feed = feedparser.parse("https://news.ycombinator.com/rss")
entries = [f"- {e.title}: {e.link}" for e in feed.entries[:15]]
raw_news = "\n".join(entries)

# 2. Промпт для агента
prompt = f"""Ты — аналитический агент по IT.
Отфильтруй входящий поток новостей. Оставь только фундаментальные события:
- Релизы важных моделей AI и обновлений архитектур
- Инциденты и сбои облачной инфраструктуры
- Крупные штрафы, сделки и законы по Big Tech

Игнорируй мелкие стартапы и маркетинговый шум.
Верни строго валидный JSON-массив объектов:
[{{"title": "Краткая суть на русском", "url": "ссылка"}}]
Если важных новостей нет, верни: []

Новости:
{raw_news}"""

# 3. Каскадный перебор моделей (если одна перегружена, пробуем следующую)
candidate_models = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-2.0-flash-lite",
    "gemini-3.6-flash"
]

response = None
for model_name in candidate_models:
    try:
        print(f"Запрос к модели: {model_name}...")
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        if response and response.text:
            print(f"Успешно обработано моделью {model_name}")
            break
    except Exception as err:
        print(f"Модель {model_name} временно недоступна: {err}")
        time.sleep(3)

if not response:
    raise RuntimeError("Все доступные модели временно заняты. Повторите запуск через 5 минут.")

clean_json = response.text.replace("```json", "").replace("```", "").strip()

# 4. Отправка результата в Telegram
try:
    items = json.loads(clean_json)
    if items:
        text = "🤖 **IT-мониторинг:**\n\n"
        for item in items:
            text += f"• {item['title']}\n🔗 {item['url']}\n\n"
    else:
        text = "✅ Тест пройден успешно. Критических событий в IT за последние часы не зафиксировано."
    
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True}
    )
except Exception as err:
    print(f"Ошибка парсинга или отправки: {err}")            
