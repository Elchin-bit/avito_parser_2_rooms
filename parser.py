import asyncio
import json
import logging
import os
import random
import re
import time
import html as html_lib

import pandas as pd
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests
from playwright.async_api import async_playwright
from telegram import Bot
from telegram.error import TelegramError


from config import TELEGRAM_BOT_TOKEN, CHAT_ID

# ================= КОНФИГУРАЦИЯ =================
MIN_PRICE = 35000
MAX_PRICE = 45000
CHECK_INTERVAL = 300  # 5 минут
CSV_FILENAME = "avito_data.csv"


logging.basicConfig(
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


HEADERS = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'sec-ch-ua': '"Chromium";v="120", "Not=A?Brand";v="24", "Google Chrome";v="120"',
    'sec-ch-ua-platform': '"Windows"',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}


class AvitoParser:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.cookies = {}
        self.seen_links = set()
        self._load_history()

    def _load_history(self):
        """Загрузка истории объявлений из CSV для предотвращения дубликатов"""
        if os.path.isfile(CSV_FILENAME):
            try:
                df = pd.read_csv(CSV_FILENAME)
                self.seen_links.update(df['link'].tolist())
                logger.info(f"База данных инициализирована. Загружено {len(self.seen_links)} записей.")
            except pd.errors.EmptyDataError:
                logger.warning("Файл CSV пуст, начинаем с чистой базы.")

    def get_url(self):
        return f"https://www.avito.ru/kazan/kvartiry/sdam/na_dlitelnyy_srok/2-komnatnye-ASgBAgICA0SSA8gQ8AeQUswIkFk?pmin={MIN_PRICE}&pmax={MAX_PRICE}"

    async def get_cookies_via_playwright(self):
        """Эмуляция реального пользователя для обхода WAF и получения токена 'ft'"""
        logger.info("Инициализация браузера для получения токена доступа (cookies)...")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--window-size=1920,1080'
                ]
            )
            context = await browser.new_context(
                user_agent=HEADERS['user-agent'],
                viewport={'width': 1920, 'height': 1080}
            )
            page = await context.new_page()

            # Внедрение Stealth-скриптов
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            """)

            try:
                random_id = str(random.randint(1111111111, 9999999999))
                await page.goto(f"https://www.avito.ru/{random_id}", timeout=60000, wait_until='domcontentloaded')

                for attempt in range(5):
                    await asyncio.sleep(4)
                    cookies_list = await context.cookies()
                    cookie_dict = {c['name']: c['value'] for c in cookies_list}

                    title = await page.title()
                    if "проблема с ip" in title.lower() or "докажите, что вы человек" in title.lower():
                        logger.error("Сработала защита WAF (IP заблокирован). Требуется ротация прокси.")
                        break

                    if cookie_dict.get("ft"):
                        logger.info("Токен 'ft' успешно получен.")
                        self.cookies = cookie_dict
                        return True

                logger.warning("Не удалось получить токен 'ft'. Возможна блокировка подсети.")
                return False
            except Exception as e:
                logger.error(f"Ошибка эмуляции браузера: {e}")
                return False
            finally:
                await browser.close()

    def fetch_data(self):
        """Выполнение быстрого запроса через curl_cffi с подменой TLS-отпечатков"""
        session = curl_requests.Session(impersonate="chrome110")
        session.headers.update(HEADERS)
        url = self.get_url()

        try:
            response = session.get(url, cookies=self.cookies, timeout=20, allow_redirects=False)

            if response.status_code == 200:
                logger.info("HTML код страницы успешно загружен.")
                return response.text
            elif response.status_code in (301, 302):
                logger.error(f"Получен HTTP {response.status_code} Redirect. Защита Авито заблокировала IP.")
                return None
            elif response.status_code in (401, 403, 429):
                logger.warning(f"HTTP {response.status_code}. Токен устарел или доступ ограничен.")
                return None
            else:
                logger.warning(f"Неожиданный код ответа: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Сетевая ошибка при запросе: {e}")
            return None

    def parse_html(self, html_content):
        """Парсинг защищенных JSON-данных из DOM-дерева"""
        if not html_content:
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
        apartments = []

        for script in soup.find_all('script', type='mime/invalid', attrs={'data-mfe-state': 'true'}):
            if 'sandbox' in script.text:
                continue
            try:
                data = json.loads(html_lib.unescape(script.text))
                items = data.get('state', {}).get('data', {}).get('catalog', {}).get('items', [])

                for item in items:
                    if not item.get('id'):
                        continue

                    title = item.get('title', '')
                    price = int(item.get('priceDetailed', {}).get('value', 0))
                    url_path = item.get('urlPath', '')

                    if re.search(r'2-к\.|2к\.|2-комн|2 комн|двухкомн|двушк', title.lower()):
                        if MIN_PRICE <= price <= MAX_PRICE and url_path:
                            link = f"https://www.avito.ru{url_path}"
                            apartments.append({'title': title, 'price': price, 'link': link})
            except Exception:
                continue

        logger.info(f"Спарсено подходящих объявлений: {len(apartments)}")
        return apartments

    def save_to_csv(self, new_apartments):
        """Экспорт данных в аналитический формат CSV"""
        if not new_apartments:
            return
        df = pd.DataFrame(new_apartments)
        file_exists = os.path.isfile(CSV_FILENAME)
        df.to_csv(CSV_FILENAME, mode='a', index=False, header=not file_exists, encoding='utf-8-sig')
        logger.info(f"Сохранено {len(new_apartments)} новых записей в {CSV_FILENAME}.")

    async def send_notifications(self, new_apartments):
        """Асинхронная отправка уведомлений через Telegram API"""
        for apt in new_apartments:
            message = f"🏠 <b>Новая 2-комнатная!</b>\n\n💰 {apt['price']:,} ₽/мес\n📝 {apt['title']}\n\n🔗 <a href='{apt['link']}'>Смотреть объявление</a>"
            try:
                await self.bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='HTML',
                                            disable_web_page_preview=True)
                await asyncio.sleep(1)  # Защита от Flood Control
            except TelegramError as e:
                logger.error(f"Ошибка отправки Telegram: {e}")

    async def run(self):
        logger.info("🚀 Запуск Avito Parser")

        await self.get_cookies_via_playwright()

        while True:
            html = self.fetch_data()

            if not html:
                logger.info("Инициирую повторное получение токенов...")
                await self.get_cookies_via_playwright()
            else:
                all_apartments = self.parse_html(html)

                # Фильтрация только новых (уникальных) объявлений
                new_apartments = [apt for apt in all_apartments if apt['link'] not in self.seen_links]

                if new_apartments:
                    logger.info(f"Обнаружено {len(new_apartments)} новых объявлений.")
                    self.save_to_csv(new_apartments)
                    await self.send_notifications(new_apartments)

                    # Добавляем в просмотренные
                    for apt in new_apartments:
                        self.seen_links.add(apt['link'])
                else:
                    logger.info("Новых объявлений с момента последней проверки не найдено.")

            logger.info(f"Переход в режим ожидания. Следующий цикл через {CHECK_INTERVAL} секунд.")
            await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        parser = AvitoParser()
        asyncio.run(parser.run())
    except KeyboardInterrupt:
        logger.info("Работа скрипта прервана пользователем.")