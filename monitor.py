import os
import json
import time
import requests
import feedparser
from bs4 import BeautifulSoup
from google import genai

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_telegram(text):
    # Telegram ограничивает длину сообщения в 4096 символов
    if len(text) > 4000:
        for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": CHAT_ID, "text": chunk, "disable_web_page_preview": True}
            )
    else:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True}
        )

# 1. Сбор данных по RSS
def fetch_rss(url, limit=7):
    try:
        f = feedparser.parse(url)
        return "\n".join([f"- {e.title}: {e.link}" for e in f.entries[:limit]])
    except Exception:
        return ""

# 2. Сбор постов из публичных Telegram-каналов Сумской области без авторизации
def fetch_tg_channel(channel_username, limit=5):
    try:
        url = f"https://t.me/s/{channel_username}"
        headers = {"User-Agent": "Mozilla/5.0 (Android; Mobile)"}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        posts = soup.find_all("div", class_="tgme_widget_message_text")
        texts = [p.get_text(separator=" ", strip=True) for p in posts[-limit:]]
        return "\n---\n".join(texts)
    except Exception:
        return ""

print("Сбор входящих данных...")
raw_it = fetch_rss("https://news.ycombinator.com/rss", limit=10)
raw_ua = fetch_rss("https://www.epravda.com.ua/rss/", limit=8)
raw_eu = fetch_rss("https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines", limit=8)
raw_migration = fetch_rss("https://ec.europa.eu/commission/presscorner/api/rss?language=en", limit=8)
raw_sumy = fetch_tg_channel("sumska_ova", limit=6)

# Промпт для сведения 5 аналитических потоков
prompt = f"""Ты — аналитический супервайзер, координирующий 5 направлений мониторинга.
Обработай входящие данные по каждому направлению, удали эмоциональный шум, мнения блогеров и рекламу. 
Оставь только твердые факты, цифры, официальные решения и нормативные акты.

ДАННЫЕ:
1. Экономика Украины:
{raw_ua}

2. Европейский рынок / ЕЦБ:
{raw_eu}

3. IT-индустрия / AI:
{raw_it}

4. Миграционное право ЕС:
{raw_migration}

5. Сумская область (безопасность, выплаты инвалидам 2 группы, помощь детям до 16 лет):
{raw_sumy}

СФОРМИРУЙ ИТОГОВЫЙ ТЕКСТ ДЛЯ TELEGRAM СТРОГО ПО ШАБЛОНУ:
📊 **ЭКОНОМИКА УКРАИНЫ**
• [1-2 главных факта с цифрами и сутью]

🇪🇺 **ЕВРОПЕЙСКИЙ РЫНОК**
• [1-2 главных факта по ставкам/инфляции/рынку]

💻 **IT & ТЕХНОЛОГИИ**
• [1-2 ключевых релиза или сбоя]

⚖️ **МИГРАЦИОННОЕ ПРАВО ЕС**
• [Изменения правил, виз, статусов]

🛡️ **СУМСКАЯ ОБЛАСТЬ**
• Безопасность: [сводка обстрелов/эвакуации]
• Гуманитарная помощь / Выплаты: [программы для инвалидов 2 гр, детей до 16 лет или соцподдержка]

Если по какому-то блоку нет подтвержденных важных фактов, напиши: «• Без существенных изменений».
Не используй вступительных и заключительных фраз, сразу начинай с первого заголовка."""

# 3. Вызов Gemini с повторами
client = genai.Client(api_key=GEMINI_KEY)
response = None

for attempt in range(1, 5):
    try:
        print(f"Попытка {attempt} обращения к Gemini...")
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt
        )
        if response and response.text:
            break
    except Exception as e:
        print(f"Сервер занят ({e}), ждем...")
        time.sleep(12)

if response and response.text:
    send_telegram(response.text)
else:
    send_telegram("⚠️ Не удалось сформировать дайджест: серверы генерации временно перегружены. Следующий опрос пройдет по расписанию.")
