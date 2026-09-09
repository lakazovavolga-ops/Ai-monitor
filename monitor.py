import os
import json
import requests
import feedparser
from google import genai

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

client = genai.Client(api_key=GEMINI_KEY)

# 1. Загружаем свежие IT-новости
feed = feedparser.parse("https://news.ycombinator.com/rss")
entries = [f"- {e.title}: {e.link}" for e in feed.entries[:15]]
raw_news = "\n".join(entries)

# 2. Промпт для фильтрации
prompt = f"""Ты — аналитический агент по IT.
Отфильтруй входящий поток новостей. Оставь только фундаментальные события:
- Релизы важных моделей AI и крупных обновлений архитектур
- Инциденты и сбои глобальной облачной инфраструктуры
- Крупные регуляторные штрафы, M&A и законодательные решения по Big Tech

Игнорируй мелкие стартапы, маркетинговые анонсы и обзоры потребительской электроники.
Верни строго валидный JSON-массив без markdown-тегов вокруг:
[{{"title": "Краткая суть на русском", "url": "ссылка"}}]
Если важных новостей нет, верни: []

Новости для анализа:
{raw_news}"""

response = client.models.generate_content(
    model="gemini-3.6-flash",
    contents=prompt
)

clean_json = response.text.replace("```json", "").replace("```", "").strip()

# 3. Отправка отфильтрованных данных в Telegram
try:
    items = json.loads(clean_json)
    if items:
        text = "🤖 **IT-мониторинг:**\n\n"
        for item in items:
            text += f"• {item['title']}\n🔗 {item['url']}\n\n"
        
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True}
        )
    else:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": "✅ Тест пройден. Критических событий в IT за последние часы не зафиксировано."}
        )
except Exception as err:
    print(f"Ошибка обработки: {err}")
