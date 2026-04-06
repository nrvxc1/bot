import telebot
import random
import time
import threading
import string
import requests
import re
import cloudscraper
import os
import json
from bs4 import BeautifulSoup
from telebot import types
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8442771928:AAEsiakjmFbJFDrCTGofcK4G-JysbSg84Hw"
bot = telebot.TeleBot(BOT_TOKEN)

ADMIN_ID = 8746165041
SUPPORT_USERNAME = "@supp0rt_tagforce"

# Цены на запросы
PRICES = {
    "1": 30,
    "3": 90,
    "10": 250,
    "unlimited": 1000
}

TARIFFS = {
    30: {"name": "1 поиск", "key": "1", "searches": 1, "unlimited": False},
    90: {"name": "3 поиска", "key": "3", "searches": 3, "unlimited": False},
    250: {"name": "10 поисков", "key": "10", "searches": 10, "unlimited": False},
    1000: {"name": "Безлимит", "key": "unlimited", "searches": 0, "unlimited": True}
}

consonants = 'bcdfghjklmnpqrstvwxz'
vowels = 'aeiouy'
all_letters = string.ascii_lowercase
digits = '0123456789'

checked_usernames = set()
available_usernames = set()
user_stats = {}
search_active = {}

scraper = cloudscraper.create_scraper()
executor = ThreadPoolExecutor(max_workers=15)

# Создаём папку для данных
if not os.path.exists('data'):
    os.makedirs('data')

def ensure_files():
    for f in ['checked.txt', 'found.txt', 'users.json']:
        path = os.path.join('data', f)
        if not os.path.exists(path):
            with open(path, 'w') as file:
                if f.endswith('.json'):
                    file.write('{}')
                else:
                    file.write('')

def load_data():
    global checked_usernames, available_usernames, user_stats
    ensure_files()
    try:
        with open('data/checked.txt', 'r') as f:
            checked_usernames = set(line.strip().replace('@', '') for line in f)
        print(f"📂 Загружено проверенных: {len(checked_usernames)}")
    except:
        checked_usernames = set()
    try:
        with open('data/found.txt', 'r') as f:
            available_usernames = set(line.strip().replace('@', '') for line in f)
        print(f"📂 Загружено найденных: {len(available_usernames)}")
    except:
        available_usernames = set()
    try:
        with open('data/users.json', 'r') as f:
            user_stats = json.load(f)
        print(f"📂 Загружено пользователей: {len(user_stats)}")
    except:
        user_stats = {}

def save_data():
    with open('data/checked.txt', 'w') as f:
        for username in checked_usernames:
            f.write(f"@{username}\n")
    with open('data/found.txt', 'w') as f:
        for username in available_usernames:
            f.write(f"@{username}\n")
    with open('data/users.json', 'w') as f:
        json.dump(user_stats, f, indent=2, ensure_ascii=False)

def get_user_info(user):
    user_id = str(user.id)
    username = f"@{user.username}" if user.username else "без юзернейма"
    if user_id not in user_stats:
        try:
            user_stats[user_id] = {
                'first_seen': datetime.now().isoformat(),
                'searches_left': 1,
                'total_searches': 0,
                'found': 0,
                'unlimited': False,
                'username': username,
                'purchases': []
            }
            save_data()
            print(f"👤 Новый пользователь: {user_id}")
            # Отправляем приветствие новому пользователю
            try:
                bot.send_message(int(user_id), "🎉 Добро пожаловать! У тебя есть 1 бесплатный поиск (3 ника). Используй кнопки ниже.")
            except:
                pass
        except Exception as e:
            print(f"❌ Ошибка при создании пользователя {user_id}: {e}")
            user_stats[user_id] = {
                'first_seen': datetime.now().isoformat(),
                'searches_left': 1,
                'total_searches': 0,
                'found': 0,
                'unlimited': False,
                'username': username,
                'purchases': []
            }
    return {
        'id': user_id,
        'username': username,
        'first_name': user.first_name or "",
        'stats': user_stats[user_id]
    }

def can_search(user_info):
    stats = user_info['stats']
    return stats['unlimited'] or stats['searches_left'] > 0

def add_searches(user_id, amount):
    if amount in TARIFFS:
        tariff = TARIFFS[amount]
        if user_id not in user_stats:
            user_stats[user_id] = {
                'searches_left': 0,
                'total_searches': 0,
                'found': 0,
                'unlimited': False,
                'purchases': []
            }
        if tariff['unlimited']:
            user_stats[user_id]['unlimited'] = True
            user_stats[user_id]['searches_left'] = 0
            msg = f"🎉 БЕЗЛИМИТ АКТИВИРОВАН!"
        else:
            user_stats[user_id]['searches_left'] += tariff['searches']
            msg = f"✅ ОПЛАЧЕНО! Начислено {tariff['searches']} поисков."
        if 'purchases' not in user_stats[user_id]:
            user_stats[user_id]['purchases'] = []
        user_stats[user_id]['purchases'].append({
            'date': datetime.now().isoformat(),
            'amount': amount,
            'tariff': tariff['name']
        })
        save_data()
        try:
            bot.send_message(int(user_id), msg)
        except:
            pass
        return True
    return False

def is_valid_username(username):
    if not username or len(username) < 5 or len(username) > 32:
        return False
    if not username[0].isalpha():
        return False
    for char in username:
        if not (char.isalnum() or char == '_'):
            return False
    return True

def generate_username(mode, length=5):
    attempts = 0
    while attempts < 200:
        attempts += 1
        if mode == "pattern":
            username = ""
            for i in range(length):
                if i % 2 == 0:
                    username += random.choice(consonants)
                else:
                    username += random.choice(vowels)
        elif mode == "digits":
            if length == 5:
                letters_count = random.randint(2, 4)
            elif length == 6:
                letters_count = random.randint(2, 5)
            else:
                letters_count = random.randint(3, 5)
            digits_count = length - letters_count
            letters = ''.join(random.choice(all_letters) for _ in range(letters_count))
            nums = ''.join(random.choice(digits) for _ in range(digits_count))
            if random.choice([True, False]):
                username = letters + nums
            else:
                username = nums + letters
                if username[0].isdigit():
                    continue
        elif mode == "combo":
            username = ""
            for i in range(length):
                if i == 0:
                    username += random.choice(all_letters)
                else:
                    if random.random() < 0.5:
                        username += random.choice(digits)
                    else:
                        username += random.choice(all_letters)
        else:
            username = ''.join(random.choice(all_letters) for _ in range(length))
        if is_valid_username(username):
            return username
    return ''.join(random.choice(all_letters) for _ in range(length))

def check_username_telegram(username):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        try:
            response = scraper.get(f"https://t.me/{username}", headers=headers, timeout=10, allow_redirects=True)
        except:
            response = requests.get(f"https://t.me/{username}", headers=headers, timeout=10, allow_redirects=True)
        if response.status_code == 404:
            return True
        if response.status_code in [301,302,303,307,308] and ('telegram.org' in response.url or response.url.endswith('/')):
            return True
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            if soup.find('div', class_='tgme_page_title') or soup.find('div', class_='tgme_channel_info'):
                return False
            text_lower = soup.get_text().lower()
            if any(phrase in text_lower for phrase in ['if you have telegram', 'doesn\'t exist', 'не существует', 'страница не найдена']):
                return True
            if any(phrase in text_lower for phrase in ['subscribers', 'members', 'online', 'created', 'создан', 'подписчиков']):
                return False
        return False
    except Exception as e:
        print(f"❌ Ошибка Telegram: {e}")
        return False

def check_username_fragment(username):
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        try:
            driver.get(f"https://fragment.com/username/{username}")
            time.sleep(3)
            page_source = driver.page_source.lower()
            page_title = driver.title.lower()
            if "auction" in page_title or "аукцион" in page_title:
                return "auction"
            if "for sale" in page_source or "продажа" in page_source:
                return "available"
            try:
                if driver.find_element(By.XPATH, "//*[contains(text(), 'Buy') or contains(text(), 'Купить')]"):
                    return "available"
            except:
                pass
            if "not found" in page_source or "не найдено" in page_source:
                return "taken"
            return "unknown"
        finally:
            driver.quit()
    except Exception as e:
        print(f"❌ Ошибка Fragment: {e}")
        return "error"

def check_username_complete(username):
    if check_username_telegram(username):
        return True
    fragment = check_username_fragment(username)
    return fragment in ["available", "auction"]

def check_username_parallel(username):
    return username, check_username_complete(username)

def search_three_usernames(chat_id, mode, mode_name, user_info, length):
    user_id = user_info['id']
    search_active[user_id] = True
    SEARCH_COST = 1
    RESULTS_COUNT = 3
    msg = bot.send_message(chat_id, f"🔍 Ищу {RESULTS_COUNT} {mode_name} длиной {length}...")
    if not user_info['stats']['unlimited'] and user_info['stats']['searches_left'] < SEARCH_COST:
        bot.send_message(chat_id, f"❌ Недостаточно поисков. Нужно: {SEARCH_COST}")
        search_active[user_id] = False
        return
    found = []
    checked = 0
    start = time.time()
    while len(found) < RESULTS_COUNT and search_active.get(user_id):
        candidates = []
        for _ in range(30):
            u = generate_username(mode, length)
            if u not in checked_usernames and u not in available_usernames and is_valid_username(u):
                candidates.append(u)
        if not candidates:
            continue
        futures = [executor.submit(check_username_parallel, u) for u in candidates]
        for f in as_completed(futures):
            if not search_active.get(user_id):
                break
            u, avail = f.result()
            checked += 1
            checked_usernames.add(u)
            if avail:
                print(f"✅ @{u} доступен")
                found.append(u)
                available_usernames.add(u)
                if len(found) >= RESULTS_COUNT:
                    break
            else:
                print(f"❌ @{u} занят")
        if checked % 5 == 0:
            try:
                speed = checked / (time.time() - start)
                bot.edit_message_text(f"🔍 Ищу... Найдено {len(found)}/{RESULTS_COUNT}\nПроверено: {checked} | {speed:.1f}/сек", chat_id, msg.message_id)
            except:
                pass
    if found:
        user_info['stats']['found'] += len(found)
        if not user_info['stats']['unlimited']:
            user_info['stats']['searches_left'] -= SEARCH_COST
        user_info['stats']['total_searches'] += SEARCH_COST
        save_data()
    result = f"✅ **НАЙДЕНО {len(found)} НИКОВ:**\n\n" + "\n".join(f"{i}. @{u}" for i,u in enumerate(found,1)) + f"\n\n💰 Осталось: {user_info['stats']['searches_left'] if not user_info['stats']['unlimited'] else '∞'}" if found else "❌ НЕ НАЙДЕНО НИ ОДНОГО НИКА"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 ЕЩЕ 3", callback_data=f"search_{mode}_{length}"), types.InlineKeyboardButton("◀️ В МЕНЮ", callback_data="back_to_main"))
    bot.edit_message_text(result, chat_id, msg.message_id, reply_markup=markup, parse_mode='Markdown')
    search_active[user_id] = False

def show_payment_menu(chat_id, user_info):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(f"🔹 1 ПОИСК — {PRICES['1']}₽", callback_data="pay_1"),
        types.InlineKeyboardButton(f"🔸 3 ПОИСКА — {PRICES['3']}₽", callback_data="pay_3"),
        types.InlineKeyboardButton(f"🔹 10 ПОИСКОВ — {PRICES['10']}₽", callback_data="pay_10"),
        types.InlineKeyboardButton(f"💎 БЕЗЛИМИТ — {PRICES['unlimited']}₽", callback_data="pay_unlimited"),
        types.InlineKeyboardButton("◀️ НАЗАД В МЕНЮ", callback_data="back_to_main")
    )
    bot.send_message(chat_id, f"💳 ВЫБЕРИ ТАРИФ\n\n👤 Твой ID: {user_info['id']}\n💰 Тарифы:\n▫️ 1 поиск (3 ника) — {PRICES['1']}₽\n▫️ 3 поиска (9 ников) — {PRICES['3']}₽\n▫️ 10 поисков (30 ников) — {PRICES['10']}₽\n▫️ Безлимит — {PRICES['unlimited']}₽", reply_markup=markup)

def show_payment_instruction(chat_id, user_info, tariff_key):
    amount = PRICES[tariff_key]
    tariff_name = {"1":"1 поиск (3 ника)","3":"3 поиска (9 ников)","10":"10 поисков (30 ников)","unlimited":"Безлимит"}[tariff_key]
    user_id = user_info['id']
    send_url = f"https://t.me/send?start=pay_{amount}_{user_id}"
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(f"💳 ОПЛАТИТЬ {amount}₽ ЧЕРЕЗ @send", url=send_url),
        types.InlineKeyboardButton("✅ Я ОПЛАТИЛ", callback_data=f"confirm_payment_{tariff_key}"),
        types.InlineKeyboardButton("◀️ НАЗАД К ТАРИФАМ", callback_data="back_to_tariffs")
    )
    bot.send_message(chat_id, f"💎 ОПЛАТА: {tariff_name}\n💰 Сумма: {amount}₽\n👤 Твой ID: {user_id}\n\n📝 ИНСТРУКЦИЯ:\n1️⃣ Нажми кнопку оплаты\n2️⃣ В @send создай чек на {amount}₽\n3️⃣ В комментарии укажи свой ID: {user_id}\n4️⃣ Оплати чек\n5️⃣ Нажми «✅ Я ОПЛАТИЛ»\n6️⃣ Админ проверит и начислит поиски\n\n❓ Проблемы: {SUPPORT_USERNAME}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    user_info = get_user_info(call.from_user)
    user_id = user_info['id']
    try:
        if call.data == "stop_search":
            if user_id in search_active and search_active[user_id]:
                search_active[user_id] = False
                bot.answer_callback_query(call.id, "⏹ Останавливаю...")
            else:
                bot.answer_callback_query(call.id, "❌ Поиск не активен")
        elif call.data == "back_to_main":
            bot.answer_callback_query(call.id)
            bot.delete_message(chat_id, call.message.message_id)
            show_main_menu(chat_id, user_info)
        elif call.data == "back_to_tariffs":
            bot.answer_callback_query(call.id)
            bot.delete_message(chat_id, call.message.message_id)
            show_payment_menu(chat_id, user_info)
        elif call.data.startswith("search_"):
            parts = call.data.split("_")
            if len(parts) >= 3:
                mode, length = parts[1], int(parts[2])
                mode_name = {"pattern":"Паттерн","digits":"С цифрами","combo":"Комбо"}.get(mode, mode)
                if user_id in search_active and search_active[user_id]:
                    bot.answer_callback_query(call.id, "⏳ Поиск уже идет")
                    return
                if not can_search(user_info):
                    bot.answer_callback_query(call.id, "❌ Нет поисков")
                    bot.delete_message(chat_id, call.message.message_id)
                    show_payment_menu(chat_id, user_info)
                    return
                bot.answer_callback_query(call.id, f"🔄 Ищу 3 {mode_name}...")
                bot.delete_message(chat_id, call.message.message_id)
                threading.Thread(target=search_three_usernames, args=(chat_id, mode, mode_name, user_info, length), daemon=True).start()
        elif call.data.startswith("pay_"):
            tariff_key = call.data.replace("pay_", "")
            bot.answer_callback_query(call.id, "✅ Выбран тариф")
            bot.delete_message(chat_id, call.message.message_id)
            show_payment_instruction(chat_id, user_info, tariff_key)
        elif call.data.startswith("confirm_payment_"):
            tariff_key = call.data.replace("confirm_payment_", "")
            amount = int(PRICES[tariff_key])
            tariff = TARIFFS[amount]
            admin_markup = types.InlineKeyboardMarkup(row_width=2)
            admin_markup.add(
                types.InlineKeyboardButton(f"✅ ВЫДАТЬ {tariff['searches'] if tariff['searches']>0 else 'БЕЗЛИМИТ'}", callback_data=f"admin_give_{user_id}_{amount}"),
                types.InlineKeyboardButton("❌ ОТКАЗАТЬ", callback_data="admin_deny")
            )
            try:
                bot.send_message(
                    ADMIN_ID,
                    f"💰 ЗАПРОС НА ПРОВЕРКУ ОПЛАТЫ\n\n👤 {user_info['username']}\n🆔 ID: {user_id}\n💰 Сумма: {amount}₽\n📦 Тариф: {tariff['name']}\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    reply_markup=admin_markup
                )
                bot.answer_callback_query(call.id, "✅ Запрос отправлен админу!")
                bot.send_message(chat_id, f"✅ Запрос отправлен! Админ {SUPPORT_USERNAME} проверит оплату.")
            except Exception as e:
                print(f"Ошибка при отправке админу: {e}")
                bot.answer_callback_query(call.id, "❌ Не удалось отправить запрос админу.")
        elif call.data.startswith("admin_give_"):
            if call.from_user.id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ Только для админа")
                return
            parts = call.data.split("_")
            if len(parts) >= 4:
                target_user_id = parts[2]
                amount = int(parts[3])
                if add_searches(target_user_id, amount):
                    bot.answer_callback_query(call.id, "✅ Поиски начислены!")
                    bot.edit_message_reply_markup(ADMIN_ID, call.message.message_id, reply_markup=None)
                    searches_text = TARIFFS[amount]['searches'] if amount != 1000 else 'безлимит'
                    bot.send_message(ADMIN_ID, f"✅ Пользователю {target_user_id} начислено {searches_text} поисков.")
                else:
                    bot.answer_callback_query(call.id, "❌ Ошибка начисления")
        elif call.data == "admin_deny":
            if call.from_user.id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ Только для админа")
                return
            bot.answer_callback_query(call.id, "❌ Отказано")
            bot.edit_message_reply_markup(ADMIN_ID, call.message.message_id, reply_markup=None)
        else:
            bot.answer_callback_query(call.id, "❌ Неизвестная команда")
    except Exception as e:
        print(f"Ошибка в callback: {e}")
        try:
            bot.answer_callback_query(call.id, "❌ Ошибка. Попробуй ещё раз.")
        except:
            pass

@bot.message_handler(commands=['give','add','user'])
def admin_commands(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Нет прав")
        return
    cmd = message.text.split()[0].lower()
    if cmd == '/give':
        try:
            user_id = message.text.split()[1]
            if user_id in user_stats:
                user_stats[user_id]['unlimited'] = True
                user_stats[user_id]['searches_left'] = 0
                save_data()
                bot.reply_to(message, f"✅ Безлимит выдан {user_id}")
                try:
                    bot.send_message(int(user_id), "🎉 Админ выдал тебе БЕЗЛИМИТ!")
                except:
                    pass
            else:
                bot.reply_to(message, "❌ Пользователь не найден")
        except:
            bot.reply_to(message, "❌ /give 123456789")
    elif cmd == '/add':
        try:
            _, user_id, count = message.text.split()
            count = int(count)
            if user_id in user_stats:
                user_stats[user_id]['searches_left'] += count
                save_data()
                bot.reply_to(message, f"✅ Добавлено {count} поисков {user_id}")
                try:
                    bot.send_message(int(user_id), f"✅ Админ добавил {count} поисков!")
                except:
                    pass
            else:
                bot.reply_to(message, "❌ Пользователь не найден")
        except:
            bot.reply_to(message, "❌ /add 123456789 10")
    elif cmd == '/user':
        try:
            user_id = message.text.split()[1]
            if user_id in user_stats:
                s = user_stats[user_id]
                text = f"👤 Пользователь {user_id}\n📅 Регистрация: {s.get('first_seen','')[:10]}\n💰 Поисков: {s.get('searches_left',0)}\n💎 Безлимит: {'✅' if s.get('unlimited') else '❌'}\n✅ Найдено: {s.get('found',0)}\n🔄 Всего поисков: {s.get('total_searches',0)}"
                bot.reply_to(message, text)
            else:
                bot.reply_to(message, "❌ Не найден")
        except:
            bot.reply_to(message, "❌ /user 123456789")

def show_main_menu(chat_id, user_info):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎯 ПАТТЕРН", "🔢 С ЦИФРАМИ", "⚡️ КОМБО", "⏹ СТОП")
    markup.add("📊 СТАТИСТИКА", "💎 КУПИТЬ", "👤 ПРОФИЛЬ", "📞 ПОДДЕРЖКА")
    searches = "∞" if user_info['stats']['unlimited'] else str(user_info['stats']['searches_left'])
    bot.send_message(chat_id, f"🔍 ПОИСК НИКОВ\n\n💰 Поисков: {searches} (1 поиск = 3 ника)\n📊 Всего найдено: {len(available_usernames)}\n\n👇 Выбери режим:", reply_markup=markup)

@bot.message_handler(func=lambda m: True)
def handle_buttons(message):
    chat_id = message.chat.id
    user_info = get_user_info(message.from_user)
    user_id = user_info['id']
    text = message.text
    if text == "⏹ СТОП":
        if search_active.get(user_id):
            search_active[user_id] = False
            bot.send_message(chat_id, "⏹ Останавливаю...")
        else:
            bot.send_message(chat_id, "❌ Нет активного поиска")
    elif text == "📞 ПОДДЕРЖКА":
        bot.send_message(chat_id, f"📞 ПОДДЕРЖКА\n👤 Твой ID: {user_id}\n💬 {SUPPORT_USERNAME}")
    elif text == "💎 КУПИТЬ":
        if search_active.get(user_id):
            bot.send_message(chat_id, "⚠️ Сначала останови поиск (⏹ СТОП)")
        else:
            show_payment_menu(chat_id, user_info)
    elif text in ["🎯 ПАТТЕРН", "🔢 С ЦИФРАМИ", "⚡️ КОМБО"]:
        if search_active.get(user_id):
            bot.send_message(chat_id, "⚠️ Сначала останови поиск (⏹ СТОП)")
            return
        mode = {"🎯 ПАТТЕРН":"pattern","🔢 С ЦИФРАМИ":"digits","⚡️ КОМБО":"combo"}[text]
        markup = types.InlineKeyboardMarkup(row_width=3)
        markup.add(
            types.InlineKeyboardButton("5 символов", callback_data=f"search_{mode}_5"),
            types.InlineKeyboardButton("6 символов", callback_data=f"search_{mode}_6"),
            types.InlineKeyboardButton("7 символов", callback_data=f"search_{mode}_7"),
            types.InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_main")
        )
        bot.send_message(chat_id, f"Выбери длину (будет найдено 3 ника):", reply_markup=markup)
    elif text == "👤 ПРОФИЛЬ":
        s = user_info['stats']
        status = "💎 PREMIUM" if s['unlimited'] else "👤 FREE"
        searches = "∞" if s['unlimited'] else str(s['searches_left'])
        bot.send_message(chat_id, f"👤 ПРОФИЛЬ\n🆔 ID: {user_id}\n📊 Статус: {status}\n💰 Осталось: {searches}\n✅ Найдено: {s['found']}\n🔄 Всего поисков: {s['total_searches']}")
    elif text == "📊 СТАТИСТИКА":
        premium = sum(1 for u in user_stats.values() if u.get('unlimited'))
        bot.send_message(chat_id, f"📊 СТАТИСТИКА\n✅ Найдено ников: {len(available_usernames)}\n👥 Пользователей: {len(user_stats)}\n💎 Премиум: {premium}")

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_info = get_user_info(message.from_user)
    show_main_menu(chat_id, user_info)

if __name__ == "__main__":
    load_data()
    print("\n" + "="*80)
    print("🤖 БОТ ЗАПУЩЕН (работает для всех пользователей)")
    print(f"👤 Админ: {ADMIN_ID}")
    print(f"📞 Поддержка: {SUPPORT_USERNAME}")
    print("="*80)
    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=20)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        time.sleep(5)
        bot.infinity_polling()
