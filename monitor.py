import os
import json
import html
import asyncio
from datetime import datetime, timezone, timedelta
import feedparser
import google.generativeai as genai
import requests
import edge_tts

TELEGRAM_BOT_TOKEN = os.environ["BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["CHAT_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

WEB_APP_URL = "https://" + "lakazovavolga-ops.github.io/Ai-monitor/"

genai.configure(api_key=GEMINI_API_KEY)

RSS_FEEDS = {
    "Геоэкономика": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "Рынки": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "ВПК": "https://www.defensenews.com/arc/outboundfeeds/rss/category/global/?outputType=xml",
    "Технологии": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "Азия": "https://asia.nikkei.com/rss/feed/nar"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def collect_news():
    items = []
    for category, url in RSS_FEEDS.items():
        try:
            print(f"Загрузка RSS: {category}...", flush=True)
            resp = requests.get(url, headers=HEADERS, timeout=6)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:2]:
                summary = entry.get('summary', '')[:250]
                items.append(f"[{category}] {entry.title}: {summary}")
        except Exception as e:
            print(f"Пропуск {category}: {e}", flush=True)
    return "\n".join(items)

def generate_analysis(raw_text):
    prompt = f"""
Ты — ведущий геоэкономический аналитик. На основе входящих новостей сформируй анализ строго в формате JSON-объекта со следующей структурой:
{{
  "voice_script": "Связанный текст для диктора на 40-50 секунд спокойным тоном новостного аналитика. Без эмодзи и спецсимволов. Начни с фразы 'Здравствуйте. Краткий геоэкономический брифинг.' и выдели 2-3 ключевых события и главный вывод для жизни.",
  "cards": [
    {{
      "category": "Название категории",
      "icon": "соответствующий эмодзи",
      "summary": "Главный тезис события в 1-2 предложениях",
      "mechanism": "Производственно-сырьевой механизм (цепочки, дефицит, логистика)",
      "precedent": "Исторический прецедент (XX-XXI век и чем завершился)",
      "impact": "Прикладной вывод: прямое влияние на домохозяйство, кошелек, цены на технику, автозапчасти, инфляцию или валюту"
    }}
  ]
}}

Новости:
{raw_text}
"""
    generation_config = genai.GenerationConfig(
        response_mime_type="application/json"
    )

    models_to_try = ["gemini-3.6-flash", "gemini-flash-latest", "gemini-3.5-flash"]
    response = None

    for model_name in models_to_try:
        try:
            print(f"Запрос к модели: {model_name}...", flush=True)
            model = genai.GenerativeModel(model_name, generation_config=generation_config)
            res = model.generate_content(prompt)
            if res and res.text:
                response = res
                print(f"Ответ получен от: {model_name}", flush=True)
                break
        except Exception as err:
            print(f"Ошибка модели {model_name}: {err}", flush=True)

    if not response:
        raise RuntimeError("Не удалось получить ответ от Gemini.")

    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()

async def create_voice_file(text, output_file="briefing.mp3"):
    communicate = edge_tts.Communicate(text, voice="ru-RU-DmitryNeural")
    await communicate.save(output_file)

def send_telegram_voice(audio_path):
    url = "".join(["https://", "api.telegram.org", "/bot", TELEGRAM_BOT_TOKEN, "/sendVoice"])
    try:
        with open(audio_path, "rb") as audio:
            files = {"voice": audio}
            data = {
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": "🎙 <b>Голосовой экспресс-брифинг</b>",
                "parse_mode": "HTML"
            }
            res = requests.post(url, data=data, files=files, timeout=40)
            print(f"Статус отправки Voice: {res.status_code}", flush=True)
    except Exception as e:
        print(f"Ошибка отправки голосового сообщения: {e}", flush=True)

def send_telegram_alert(cards):
    text_lines = ["🌐 <b>Глобальный Монитор: Свежая сводка</b>\n"]
    for card in cards[:4]:
        icon = card.get('icon', '🔹')
        cat = html.escape(str(card.get('category', '')))
        summary = html.escape(str(card.get('summary', '')))
        impact = html.escape(str(card.get('impact', '')))
        text_lines.append(f"{icon} <b>{cat}</b>")
        text_lines.append(f"{summary}")
        if impact:
            text_lines.append(f"💡 <i>Прикладной вывод: {impact}</i>\n")
        else:
            text_lines.append("")

    text_lines.append("<i>Полный интерактивный разбор и ретроспектива:</i>")
    message_text = "\n".join(text_lines)

    url = "".join(["https://", "api.telegram.org", "/bot", TELEGRAM_BOT_TOKEN, "/sendMessage"])
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
    res = requests.post(url, json=payload, timeout=10)
    print(f"Telegram сообщение: статус {res.status_code}", flush=True)
    res.raise_for_status()

def save_retrospective(cards_data):
    history = []
    if os.path.exists("data.json"):
        try:
            with open("data.json", "r", encoding="utf-8") as f:
                existing = json.load(f)
                if isinstance(existing, dict) and "history" in existing:
                    history = existing["history"]
                elif isinstance(existing, list):
                    history = [{"timestamp": "Предыдущий архивный выпуск", "cards": existing}]
        except Exception as e:
            print(f"Ошибка чтения старого архива: {e}")

    now_str = datetime.now(timezone(timedelta(hours=3))).strftime("%d.%m.%Y %H:%M")
    new_entry = {
        "timestamp": now_str,
        "cards": cards_data
    }
    # Сохраняем свежий выпуск первым + до 14 прошлых выпусков
    history = [new_entry] + history[:14]
    
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump({"history": history}, f, ensure_ascii=False, indent=2)
    print("Архив ретроспективы обновлен.")

if __name__ == "__main__":
    print("Старт пайплайна мониторинга...", flush=True)
    raw_data = collect_news()
    print("Новости получены. Генерация анализа...", flush=True)
    
    result_raw = generate_analysis(raw_data)
    result = json.loads(result_raw)
    
    cards = result.get("cards", [])
    voice_script = result.get("voice_script", "")
    
    # 1. Сохраняем в ретроспективу
    save_retrospective(cards)
    
    # 2. Озвучка и отправка голосового сообщения
    if voice_script:
        print("Синтез голосового брифинга...", flush=True)
        asyncio.run(create_voice_file(voice_script, "briefing.mp3"))
        send_telegram_voice("briefing.mp3")
    
    # 3. Отправка текста с интерактивной кнопкой
    send_telegram_alert(cards)
    print("Всё успешно отправлено!")
