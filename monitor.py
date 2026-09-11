import os
import json
import html
import subprocess
from datetime import datetime, timezone, timedelta
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
    "Рынки и сырье": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "Энергетика": "https://oilprice.com/rss/main",
    "ВПК и логистика": "https://www.defensenews.com/arc/outboundfeeds/rss/category/global/?outputType=xml",
    "Азия и торговля": "https://asia.nikkei.com/rss/feed/nar"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def collect_news():
    items = []
    for category, url in RSS_FEEDS.items():
        try:
            print(f"Загрузка RSS: {category}...", flush=True)
            resp = requests.get(url, headers=HEADERS, timeout=10)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:4]:
                summary = entry.get('summary', '')[:600]
                items.append(f"[{category}] {entry.title}\nКонтекст: {summary}\n")
        except Exception as e:
            print(f"Пропуск {category}: {e}", flush=True)
    return "\n---\n".join(items)

def generate_analysis(raw_text):
    prompt = f"""
Ты — ведущий геоэкономический и промышленный аналитик. Перед тобой сырые сводки новостей:
{raw_text}

Сформируй полноценный, плотный аналитический отчет без воды и лозунгов. 
Выбери 4-5 ключевых системных событий и разбери их глубоко.

Верни строго JSON со следующей структурой:
{{
  "voice_script": "Связанный текст для диктора на 45-60 секунд спокойным тоном новостного обозревателя. Начни с 'Здравствуйте. Краткий геоэкономический брифинг.' Озвучь 2-3 ключевых сдвига без спецсимволов.",
  "cards": [
    {{
      "category": "Тематика (например: Рынок энергоносителей, ВПК, Полупроводники)",
      "icon": "соответствующий эмодзи",
      "title": "Суть события емко и точно",
      "deep_analysis": "Обстоятельный разбор: что произошло, какие производственные или финансовые цепочки затронуты, кто теряет маржу, какие объемы или логистические маршруты под угрозой (3-5 содержательных предложений с фактурой).",
      "precedent": "Исторический прецедент (XX-XXI век, аналог текущей ситуации и к чему он привел).",
      "impact": "Прикладной вывод: реальные последствия для бытовых потребителей (цены на технику, бензин, автозапчасти, продовольствие или курсы валют)."
    }}
  ]
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

def create_voice_file(text, output_file="briefing.mp3"):
    try:
        from gtts import gTTS
    except ImportError:
        subprocess.run(["pip", "install", "gTTS"], check=True)
        from gtts import gTTS
    
    tts = gTTS(text=text, lang="ru")
    tts.save(output_file)

def send_telegram_voice(audio_path):
    url = f"[https://api.telegram.org/bot](https://api.telegram.org/bot){TELEGRAM_BOT_TOKEN}/sendVoice"
    try:
        with open(audio_path, "rb") as audio:
            files = {"voice": audio}
            data = {
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": "🎙 <b>Голосовой аналитический брифинг</b>",
                "parse_mode": "HTML"
            }
            requests.post(url, data=data, files=files, timeout=40)
    except Exception as e:
        print(f"Ошибка аудио: {e}", flush=True)

def send_telegram_posts(cards):
    tg_url = f"[https://api.telegram.org/bot](https://api.telegram.org/bot){TELEGRAM_BOT_TOKEN}/sendMessage"
    
    messages = []
    current_chunk = ["🌐 <b>Глобальный Монитор: Развернутый анализ</b>\n"]
    
    for c in cards:
        icon = c.get('icon', '🔹')
        cat = html.escape(str(c.get('category', '')))
        title = html.escape(str(c.get('title', '')))
        analysis = html.escape(str(c.get('deep_analysis', '')))
        precedent = html.escape(str(c.get('precedent', '')))
        impact = html.escape(str(c.get('impact', '')))
        
        block = (
            f"{icon} <b>{cat} | {title}</b>\n"
            f"{analysis}\n"
            f"🏛 <i>Прецедент:</i> {precedent}\n"
            f"💡 <i>Прикладной вывод:</i> {impact}\n"
        )
        
        # Контроль длины сообщения Telegram (до 4096 символов)
        if len("\n".join(current_chunk)) + len(block) > 3800:
            messages.append("\n".join(current_chunk))
            current_chunk = [block]
        else:
            current_chunk.append(block)
            
    if current_chunk:
        messages.append("\n".join(current_chunk))
        
    for i, msg in enumerate(messages):
        is_last = (i == len(messages) - 1)
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }
        if is_last:
            payload["reply_markup"] = {
                "inline_keyboard": [
                    [{"text": "📊 Интерактивный архив и графики", "url": WEB_APP_URL}]
                ]
            }
        requests.post(tg_url, json=payload, timeout=15)

def save_retrospective(cards_data):
    history = []
    if os.path.exists("data.json"):
        try:
            with open("data.json", "r", encoding="utf-8") as f:
                existing = json.load(f)
                if isinstance(existing, dict) and "history" in existing:
                    history = existing["history"]
        except Exception as e:
            print(f"Ошибка архива: {e}")

    now_str = datetime.now(timezone(timedelta(hours=3))).strftime("%d.%m.%Y %H:%M")
    new_entry = {
        "timestamp": now_str,
        "cards": cards_data
    }
    history = [new_entry] + history[:14]
    
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump({"history": history}, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    print("Сбор расширенной сводки новостей...", flush=True)
    raw = collect_news()
    
    print("Глубокий анализ через Gemini...", flush=True)
    res = generate_analysis(raw)
    
    cards = res.get("cards", [])
    voice = res.get("voice_script", "")
    
    save_retrospective(cards)
    
    if voice:
        try:
            create_voice_file(voice, "briefing.mp3")
            send_telegram_voice("briefing.mp3")
        except Exception as err:
            print(f"Ошибка голосового модуля: {err}")
            
    send_telegram_posts(cards)
    print("Аналитический выпуск отправлен.")
