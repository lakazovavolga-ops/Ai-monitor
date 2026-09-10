import os
import re
import html
import time
import requests
import feedparser
from bs4 import BeautifulSoup
from google import genai

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_telegram(text):
    """Отправляет длинный текст частями, чтобы не упереться в лимит Telegram (4096 символов)."""
    for chunk in [text[i:i+3900] for i in range(0, len(text), 3900)]:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": chunk,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
        )

def clean_html(raw_html):
    if not raw_html:
        return ""
    clean = re.sub(r"<[^>]+>", " ", raw_html)
    return " ".join(html.unescape(clean).split())

def fetch_rich_rss(url, limit=5):
    try:
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:limit]:
            title = entry.get("title", "").strip()
            desc = entry.get("summary") or entry.get("description") or ""
            clean_desc = clean_html(desc)[:450]
            link = entry.get("link", "").strip()
            articles.append(f"Заголовок: {title}\nСуть: {clean_desc}\nURL: {link}")
        return "\n---\n".join(articles)
    except Exception as e:
        print(f"Ошибка сбора {url}: {e}")
        return ""

print("Сбор данных по международным потокам...")
data_macro = fetch_rich_rss("https://search.cnbc.com/rs/search/view.html?partnerId=2000&keywords=tariffs%20economy%20fed&sort=date", limit=5)
data_markets = fetch_rich_rss("https://finance.yahoo.com/news/rssindex", limit=5)
data_deftech = fetch_rich_rss("https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml", limit=5)
data_musk = fetch_rich_rss("https://techcrunch.com/tag/elon-musk/feed/", limit=4)
data_asia = fetch_rich_rss("https://asia.nikkei.com/rss/feed/nar", limit=5)
data_migration = fetch_rich_rss("https://ec.europa.eu/commission/presscorner/api/rss?language=en", limit=4)

prompt = f"""Ты — старший геоэкономический аналитик и фактчекер. Твоя методика анализа основана на принципах доказательного бизнес-анализа (кейс-метод): каждое явление объясняется через механизм действия, документальный исторический прецедент и осязаемое влияние на людей и капитал.

СТРОГИЕ ПРАВИЛА:
1. Только верифицированные факты, цифры, даты и имена из предоставленных данных. Запрещено выдумывать новости.
2. В блоке динамики войны КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО называть вымышленные даты завершения конфликта. Оценивай исключительно материально-технические маркеры: темпы работы ВПК, объемы снарядного производства, статус финансирования и переговорные позиции сторон.
3. Исторические прецеденты должны быть реальными событиями XX–XXI веков (с точными годами).
4. Связывай шаги Восточной Азии, Илона Маска и рынков в единую причинно-следственную цепочку.

ВХОДЯЩИЕ ДАННЫЕ:
- Макроэкономика и мировые решения:
{data_macro}
- Фондовый рынок:
{data_markets}
- Оборонные технологии и ВПК:
{data_deftech}
- Илон Маск и сделки:
{data_musk}
- Восточная Азия (Китай, Япония, Южная Корея):
{data_asia}
- Миграция и регуляции ЕС:
{data_migration}

СФОРМИРУЙ ОТЧЕТ СТРОГО В СЛЕДУЮЩЕМ ВИДЕ (без вводных приветствий и эпилогов):

🌐 **1. ГЕОЭКОНОМИКА И ВНЕШНЯЯ ПОЛИТИКА**
* **Событие:** [Кто, что утвердил/ввел, ключевые цифры]
* **Экономический механизм:** [Как это повлияет на пошлины, торговые балансы или инфляцию]
* **Исторический прецедент:** [Аналогичный кризис/решение XX–XXI века с датами]
* **Последствия для обычного человека:** [Цены, сбережения, рабочие места]

📈 **2. ФОНДОВЫЙ РЫНОК И КАПИТАЛ**
* **Ключевой драйвер:** [Решения ФРС/ЕЦБ или движение индексов]
* **Акции в фокусе (Тикеры):** [Причины аномалий, квартальные отчеты, апгрейды]
* **Исторический прецедент:** [Аналог из истории биржевых циклов]

🎖️ **3. ВОЕННЫЕ ТЕХНОЛОГИИ И РЕСУРСНЫЕ МАРКЕРЫ ВОЙНЫ В УКРАИНЕ**
* **Технологии и ВПК:** [Новые разработки, поставки, масштабирование дронов/РЭБ]
* **Ресурсные индикаторы завершения:** [Оценка истощения арсеналов, внешняя помощь, экономическая стойкость]
* **Историческая параллель:** [Пример позиционного/технологического противостояния прошлого]

⚡ **4. ИЛОН МАСК: АКТИВЫ, СДЕЛКИ И СТРАТЕГИЯ**
* **Фактические действия:** [Движения капитала, раунды финансирования, контракты Tesla/xAI/SpaceX]
* **Аналитика ИИ:** [Скрытая логика шагов: синергия данных, регуляторные риски, концентрация контроля]
* **Исторический прототип:** [Сравнение с промышленниками прошлого]

🌏 **5. ВОСТОЧНАЯ АЗИЯ: КИТАЙ, ЯПОНИЯ, ЮЖНАЯ КОРЕЯ**
* **Ключевой факт:** [Решения в регионе, сырье, чипы, валюты]
* **Связка с западным рынком и Маском:** [Как шаги Пекина/Сеула/Токио отражаются на американском техсекторе и автопроме]
* **Исторический прецедент:** [Аналог в истории региона]

⚖️ **6. МИГРАЦИОННОЕ ПРАВО И ЛЕГАЛИЗАЦИЯ В ЕС**
* **Фактические изменения:** [Решения Еврокомиссии, статусы защиты, разрешения на работу]
* **Практический вывод:** [Что это меняет для иностранцев и рынка труда Европы]
"""

# Инициализация Gemini с каскадным повтором при 503 ошибках
client = genai.Client(api_key=GEMINI_KEY)
response = None

for attempt in range(1, 5):
    try:
        print(f"Попытка {attempt}: обращение к Gemini...")
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config={"temperature": 0.1}  # Строгий фактчекинг без фантазий
        )
        if response and response.text:
            break
    except Exception as e:
        print(f"Сервер занят ({e}), ожидание...")
        time.sleep(15)

if response and response.text:
    send_telegram(response.text)
    print("Отчет успешно сформирован и отправлен в Telegram.")
else:
    send_telegram("⚠️ Не удалось получить отчет: серверы генерации временно перегружены. Следующий запуск пройдет по расписанию.")
