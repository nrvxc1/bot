import telebot
import random
import time
import threading
import string
import requests
import re
import os
import json
from bs4 import BeautifulSoup
from telebot import types
from datetime import datetime, timedelta

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8442771928:AAEsiakjmFbJFDrCTGofcK4G-JysbSg84Hw"
bot = telebot.TeleBot(BOT_TOKEN)

ADMIN_ID = 8746165041
SUPPORT_USERNAME = "@supp0rt_tagforce"
REQUIRED_CHANNEL = "@Tag_Force"
REQUIRED_CHANNEL_LINK = "https://t.me/Tag_Force"

PREMIUM_PRICES = {
    "1d": {"price_rub": 20, "price_stars": 15, "days": 1},
    "3d": {"price_rub": 60, "price_stars": 45, "days": 3},
    "7d": {"price_rub": 140, "price_stars": 100, "days": 7},
    "1m": {"price_rub": 600, "price_stars": 450, "days": 30},
    "3m": {"price_rub": 1800, "price_stars": 1350, "days": 90},
    "1y": {"price_rub": 6000, "price_stars": 4500, "days": 365},
    "forever": {"price_rub": 8000, "price_stars": 6000, "days": -1}
}

SEARCH_PRICE_RUB = 6
SEARCH_PRICE_STARS = 5

user_states = {}

consonants = 'bcdfghjklmnpqrstvwxz'
vowels = 'aeiouy'
all_letters = string.ascii_lowercase
digits = '0123456789'

checked_usernames = set()
available_usernames = set()
user_stats = {}
search_active = {}

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
    
    # Преобразуем datetime в строку для JSON
    data_to_save = {}
    for uid, data in user_stats.items():
        data_copy = data.copy()
        if 'premium_until' in data_copy and isinstance(data_copy['premium_until'], datetime):
            data_copy['premium_until'] = data_copy['premium_until'].isoformat()
        data_to_save[uid] = data_copy
    
    with open('data/users.json', 'w') as f:
        json.dump(data_to_save, f, indent=2, ensure_ascii=False)

def is_premium(user_id):
    if user_id not in user_stats:
        return False
    if user_stats[user_id].get('premium_forever', False):
        return True
    premium_until = user_stats[user_id].get('premium_until')
    if premium_until:
        if isinstance(premium_until, str):
            premium_until = datetime.fromisoformat(premium_until)
        return datetime.now() < premium_until
    return False

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
                'username': username,
                'purchases': [],
                'last_hourly_add': 0,
                'has_subscribed': False,
                'premium_forever': False
            }
            save_data()
            print(f"👤 Новый пользователь: {user_id}")
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            user_stats[user_id] = {
                'first_seen': datetime.now().isoformat(),
                'searches_left': 1,
                'total_searches': 0,
                'found': 0,
                'username': username,
                'purchases': [],
                'last_hourly_add': 0,
                'has_subscribed': False,
                'premium_forever': False
            }
    return {
        'id': user_id,
        'username': username,
        'first_name': user.first_name or "",
        'stats': user_stats[user_id]
    }

def can_search(user_info):
    return is_premium(user_info['id']) or user_info['stats']['searches_left'] > 0

def add_searches(user_id, amount):
    if user_id not in user_stats:
        user_stats[user_id] = {
            'searches_left': 0, 'total_searches': 0, 'found': 0, 'purchases': [], 
            'last_hourly_add': 0, 'has_subscribed': False, 'premium_forever': False
        }
    user_stats[user_id]['searches_left'] += amount
    user_stats[user_id].setdefault('purchases', []).append({
        'date': datetime.now().isoformat(), 'type': 'searches', 'amount': amount
    })
    save_data()
    try:
        bot.send_message(int(user_id), f"✅ Начислено {amount} поисков!")
    except:
        pass
    return True

def add_premium(user_id, days):
    if user_id not in user_stats:
        user_stats[user_id] = {
            'searches_left': 0, 'total_searches': 0, 'found': 0, 'purchases': [], 
            'last_hourly_add': 0, 'has_subscribed': False, 'premium_forever': False
        }
    if days == -1:
        user_stats[user_id]['premium_forever'] = True
        if 'premium_until' in user_stats[user_id]:
            del user_stats[user_id]['premium_until']
        msg = "💎 ПРЕМИУМ НАВСЕГДА АКТИВИРОВАН!"
    else:
        current_premium = user_stats[user_id].get('premium_until')
        if current_premium:
            if isinstance(current_premium, str):
                current_premium = datetime.fromisoformat(current_premium)
            new_date = max(datetime.now(), current_premium) + timedelta(days=days)
        else:
            new_date = datetime.now() + timedelta(days=days)
        user_stats[user_id]['premium_until'] = new_date
        msg = f"💎 ПРЕМИУМ АКТИВИРОВАН НА {days} ДНЕЙ!"
    user_stats[user_id].setdefault('purchases', []).append({
        'date': datetime.now().isoformat(), 'type': 'premium', 'days': days
    })
    save_data()
    try:
        bot.send_message(int(user_id), msg)
    except:
        pass
    return True

def check_subscription(user_id):
    try:
        member = bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def add_bonus_for_subscription(user_id):
    if user_id in user_stats and not user_stats[user_id].get('has_subscribed', False):
        user_stats[user_id]['searches_left'] += 2
        user_stats[user_id]['has_subscribed'] = True
        save_data()
        try:
            bot.send_message(int(user_id), "🎁 Спасибо за подписку! +2 поиска начислено!")
        except:
            pass
        return True
    return False

def hourly_free_searches():
    while True:
        time.sleep(3600)
        now = time.time()
        print(f"🕐 Ежечасное начисление: {datetime.now()}")
        updated = 0
        for user_id, data in user_stats.items():
            if is_premium(user_id):
                continue
            last = data.get('last_hourly_add', 0)
            if now - last < 3600:
                continue
            current = data.get('searches_left', 0)
            new_total = min(current + 2, 10)
            if new_total != current:
                data['searches_left'] = new_total
                data['last_hourly_add'] = now
                updated += 1
                try:
                    bot.send_message(int(user_id), f"🎁 Ежечасный бонус! +2 поиска. Теперь у тебя {new_total} поисков (макс. 10).")
                except:
                    pass
        if updated:
            save_data()
            print(f"✅ Начислено {updated} пользователям")

hourly_thread = threading.Thread(target=hourly_free_searches, daemon=True)
hourly_thread.start()
print("✅ Ежечасное начисление запущено")

def is_valid_username(username):
    if not username or len(username) < 5 or len(username) > 32:
        return False
    if not username[0].isalpha():
        return False
    return all(c.isalnum() or c == '_' for c in username)

def generate_username(mode, length=5):
    for _ in range(200):
        if mode == "pattern":
            username = ''.join(random.choice(consonants) if i%2==0 else random.choice(vowels) for i in range(length))
        elif mode == "digits":
            letters_cnt = random.randint(2, length-1) if length>2 else 1
            digits_cnt = length - letters_cnt
            letters = ''.join(random.choice(all_letters) for _ in range(letters_cnt))
            nums = ''.join(random.choice(digits) for _ in range(digits_cnt))
            username = (letters + nums) if random.choice([True, False]) else (nums + letters)
            if username[0].isdigit():
                continue
        elif mode == "combo":
            username = ''.join(random.choice(all_letters) if i==0 else (random.choice(digits) if random.random()<0.5 else random.choice(all_letters)) for i in range(length))
        else:
            username = ''.join(random.choice(all_letters) for _ in range(length))
        if is_valid_username(username):
            return username
    return ''.join(random.choice(all_letters) for _ in range(length))

def check_username(username):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9',
        }
        response = requests.get(f"https://t.me/{username}", headers=headers, timeout=5)
        
        if response.status_code == 404:
            return True
        if response.status_code in [301, 302, 303, 307, 308]:
            return True
        if response.status_code == 200:
            if 'tgme_page_title' in response.text or 'subscribers' in response.text:
                return False
            return True
        return False
    except:
        return False

def search_username(chat_id, mode, mode_name, user_info, length):
    user_id = user_info['id']
    search_active[user_id] = True
    SEARCH_COST, RESULTS_COUNT = 1, 1
    
    stop_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    stop_markup.add(types.KeyboardButton("⏹ СТОП"))
    bot.send_message(chat_id, f"🔍 Ищу {RESULTS_COUNT} {mode_name} длиной {length}...\n⏹ Нажми СТОП для остановки", reply_markup=stop_markup)
    msg = bot.send_message(chat_id, f"🔍 Ищу {RESULTS_COUNT} {mode_name} длиной {length}...")
    
    if not is_premium(user_id) and user_info['stats']['searches_left'] < SEARCH_COST:
        bot.edit_message_text(f"❌ Недостаточно поисков. Нужно: {SEARCH_COST}", chat_id, msg.message_id)
        search_active[user_id] = False
        show_main_menu(chat_id, user_info)
        return
    
    found, checked, start = [], 0, time.time()
    
    while len(found) < RESULTS_COUNT and search_active.get(user_id):
        u = generate_username(mode, length)
        if u in checked_usernames or u in available_usernames:
            continue
        if not is_valid_username(u):
            continue
        
        checked += 1
        checked_usernames.add(u)
        
        if check_username(u):
            found.append(u)
            available_usernames.add(u)
            save_data()
            break
        
        if checked % 5 == 0:
            try:
                bot.edit_message_text(f"🔍 Ищу... Найдено {len(found)}/{RESULTS_COUNT}\nПроверено: {checked} | {(checked/(time.time()-start)):.1f}/сек", chat_id, msg.message_id)
            except:
                pass
    
    if found:
        user_info['stats']['found'] += len(found)
        if not is_premium(user_id):
            user_info['stats']['searches_left'] -= SEARCH_COST
        user_info['stats']['total_searches'] += SEARCH_COST
        save_data()
    
    search_time = time.time() - start
    searches_left = "∞" if is_premium(user_id) else str(user_info['stats']['searches_left'])
    
    if found:
        result_text = f"✅ **НАЙДЕН НИК:**\n\n@{found[0]}\n\n📊 Проверено: {checked} ников за {search_time:.1f}с\n💰 Осталось поисков: {searches_left}"
    else:
        result_text = f"❌ **НЕ НАЙДЕН НИ ОДИН НИК**\n\n📊 Проверено: {checked} ников за {search_time:.1f}с\n💰 Осталось поисков: {searches_left}"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔄 ЕЩЕ 1", callback_data=f"search_{mode}_{length}"),
        types.InlineKeyboardButton("◀️ В МЕНЮ", callback_data="back_to_main")
    )
    bot.edit_message_text(result_text, chat_id, msg.message_id, reply_markup=markup, parse_mode='Markdown')
    search_active[user_id] = False
    show_main_menu(chat_id, user_info)

# ========== АДМИН КОМАНДЫ ==========
@bot.message_handler(commands=['add'])
def cmd_add(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Нет прав")
        return
    try:
        parts = message.text.split()
        if len(parts) != 3:
            bot.reply_to(message, "❌ /add 123456789 10")
            return
        user_id = parts[1]
        count = int(parts[2])
        if user_id in user_stats:
            user_stats[user_id]['searches_left'] += count
            save_data()
            bot.reply_to(message, f"✅ +{count} поисков пользователю {user_id}")
            try:
                bot.send_message(int(user_id), f"✅ Админ добавил тебе {count} поисков!")
            except:
                pass
        else:
            bot.reply_to(message, f"❌ Пользователь {user_id} не найден")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['premium'])
def cmd_premium(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Нет прав")
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ /premium 123456789 30 (или -1 для навсегда)")
            return
        user_id = parts[1]
        days = int(parts[2]) if len(parts) > 2 else -1
        add_premium(user_id, days)
        bot.reply_to(message, f"✅ Премиум выдан {user_id} на {days if days != -1 else 'НАВСЕГДА'}")
        try:
            if days == -1:
                bot.send_message(int(user_id), "💎 Админ выдал тебе ПРЕМИУМ НАВСЕГДА!")
            else:
                bot.send_message(int(user_id), f"💎 Админ выдал тебе ПРЕМИУМ на {days} дней!")
        except:
            pass
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['user'])
def cmd_user(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Нет прав")
        return
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.reply_to(message, "❌ /user 123456789")
            return
        user_id = parts[1]
        if user_id in user_stats:
            s = user_stats[user_id]
            premium_status = "✅ ДА" if is_premium(user_id) else "❌ НЕТ"
            text = f"👤 ПОЛЬЗОВАТЕЛЬ {user_id}\n📅 Регистрация: {s.get('first_seen', '')[:10]}\n💰 Поисков: {s.get('searches_left', 0)}\n💎 Премиум: {premium_status}\n✅ Найдено: {s.get('found', 0)}"
            bot.reply_to(message, text)
        else:
            bot.reply_to(message, f"❌ Пользователь {user_id} не найден")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['stats'])
def cmd_stats(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Нет прав")
        return
    premium_count = sum(1 for uid in user_stats if is_premium(uid))
    text = f"📊 СТАТИСТИКА\n\n✅ Найдено ников: {len(available_usernames)}\n👥 Пользователей: {len(user_stats)}\n💎 Премиум: {premium_count}\n🔍 Проверено ников: {len(checked_usernames)}"
    bot.reply_to(message, text)

# ========== ОБРАБОТКА КОЛБЭКОВ ==========
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    user_info = get_user_info(call.from_user)
    user_id = user_info['id']
    
    try:
        if call.data == "bonus_subscribe":
            if user_info['stats'].get('has_subscribed', False):
                bot.answer_callback_query(call.id, "❌ Вы уже получали бонус!")
                bot.delete_message(chat_id, call.message.message_id)
                show_main_menu(chat_id, user_info)
                return
            if check_subscription(user_id):
                add_bonus_for_subscription(user_id)
                bot.answer_callback_query(call.id, "✅ Подписка подтверждена! +2 поиска")
                bot.delete_message(chat_id, call.message.message_id)
                show_main_menu(chat_id, user_info)
            else:
                bot.answer_callback_query(call.id, "❌ Вы не подписаны на канал!")
        
        elif call.data == "buy_searches":
            bot.answer_callback_query(call.id)
            bot.delete_message(chat_id, call.message.message_id)
            user_states[user_id] = {'state': 'waiting_search_amount'}
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_shop"))
            bot.send_message(chat_id, f"🔍 ПОКУПКА ПОИСКОВ\n\n💰 Цена: {SEARCH_PRICE_STARS}⭐️ / {SEARCH_PRICE_RUB}₽ за 1 поиск\n📞 Купить: {SUPPORT_USERNAME}\n\n✏️ Введите количество (1-1000):", reply_markup=markup)
        
        elif call.data == "back_to_shop":
            bot.answer_callback_query(call.id)
            bot.delete_message(chat_id, call.message.message_id)
            if user_id in user_states:
                del user_states[user_id]
            show_shop_menu(chat_id, user_info)
        
        elif call.data == "buy_premium":
            bot.answer_callback_query(call.id)
            bot.delete_message(chat_id, call.message.message_id)
            show_premium_menu(chat_id, user_info)
        
        elif call.data.startswith("premium_"):
            key = call.data.replace("premium_", "")
            price_rub = PREMIUM_PRICES[key]["price_rub"]
            price_stars = PREMIUM_PRICES[key]["price_stars"]
            
            name_map = {
                "1d": "1 день", "3d": "3 дня", "7d": "7 дней",
                "1m": "1 месяц", "3m": "3 месяца", "1y": "1 год", "forever": "Навсегда"
            }
            name = name_map.get(key, key)
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📩 НАПИСАТЬ ПОДДЕРЖКЕ", url=f"https://t.me/{SUPPORT_USERNAME.replace('@', '')}"))
            markup.add(types.InlineKeyboardButton("◀️ НАЗАД", callback_data="buy_premium"))
            bot.answer_callback_query(call.id)
            bot.delete_message(chat_id, call.message.message_id)
            bot.send_message(chat_id, f"💎 ПОКУПКА ПРЕМИУМ\n\n📦 Тариф: {name}\n💰 Цена: {price_stars}⭐️ / {price_rub}₽\n👤 ID: {user_id}\n\n📞 Для оплаты напишите в поддержку:\n{SUPPORT_USERNAME}", reply_markup=markup)
        
        elif call.data.startswith("search_"):
            parts = call.data.split("_")
            if len(parts) >= 3:
                mode, length = parts[1], int(parts[2])
                mode_name = {"pattern":"Паттерн","digits":"С цифрами","combo":"Комбо"}.get(mode, mode)
                
                if not is_premium(user_id) and mode != "combo":
                    bot.answer_callback_query(call.id, "❌ Для FREE пользователей доступен только режим КОМБО!\n💎 Купи PREMIUM для доступа к ПАТТЕРН и С ЦИФРАМИ")
                    return
                
                if search_active.get(user_id):
                    bot.answer_callback_query(call.id, "⏳ Поиск уже идет")
                    return
                if not can_search(user_info):
                    bot.answer_callback_query(call.id, "❌ Нет поисков")
                    bot.delete_message(chat_id, call.message.message_id)
                    show_shop_menu(chat_id, user_info)
                    return
                bot.answer_callback_query(call.id, f"🔄 Ищу...")
                bot.delete_message(chat_id, call.message.message_id)
                threading.Thread(target=search_username, args=(chat_id, mode, mode_name, user_info, length), daemon=True).start()
        
        elif call.data == "back_to_main":
            bot.answer_callback_query(call.id)
            bot.delete_message(chat_id, call.message.message_id)
            show_main_menu(chat_id, user_info)
        
    except Exception as e:
        print(f"Ошибка: {e}")
        try:
            bot.answer_callback_query(call.id, "❌ Ошибка")
        except:
            pass

def show_shop_menu(chat_id, user_info):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🔍 КУПИТЬ ПОИСКИ", callback_data="buy_searches"),
        types.InlineKeyboardButton("💎 КУПИТЬ ПРЕМИУМ", callback_data="buy_premium"),
        types.InlineKeyboardButton("◀️ В МЕНЮ", callback_data="back_to_main")
    )
    bot.send_message(chat_id, f"🛒 МАГАЗИН\n\n👤 ID: {user_info['id']}\n\nВыберите категорию:", reply_markup=markup)

def show_premium_menu(chat_id, user_info):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(f"💎 1 день — 15⭐️/20₽", callback_data="premium_1d"),
        types.InlineKeyboardButton(f"💎 3 дня — 45⭐️/60₽", callback_data="premium_3d"),
        types.InlineKeyboardButton(f"💎 7 дней — 100⭐️/140₽", callback_data="premium_7d"),
        types.InlineKeyboardButton(f"💎 1 месяц — 450⭐️/600₽", callback_data="premium_1m"),
        types.InlineKeyboardButton(f"💎 3 месяца — 1350⭐️/1800₽", callback_data="premium_3m"),
        types.InlineKeyboardButton(f"💎 1 год — 4500⭐️/6000₽", callback_data="premium_1y"),
        types.InlineKeyboardButton(f"💎 Навсегда — 6000⭐️/8000₽", callback_data="premium_forever"),
        types.InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_shop")
    )
    bot.send_message(chat_id, f"💎 ПОКУПКА ПРЕМИУМ\n\n👤 ID: {user_info['id']}\n\nВыберите срок:", reply_markup=markup)

def show_main_menu(chat_id, user_info):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    markup.add("🎯 ПАТТЕРН", "🔢 С ЦИФРАМИ", "⚡️ КОМБО")
    markup.add("📊 СТАТИСТИКА", "🛒 МАГАЗИН", "👤 ПРОФИЛЬ")
    markup.add("📞 ПОДДЕРЖКА", "🎁 БОНУСЫ")
    
    searches = "∞" if is_premium(user_info['id']) else str(user_info['stats']['searches_left'])
    
    if not is_premium(user_info['id']):
        menu_text = f"🔍 ПОИСК НИКОВ\n\n💰 Поисков: {searches} (1 поиск = 1 ник)\n📊 Найдено: {len(available_usernames)}\n\n⚠️ FREE режим: доступен только ⚡️ КОМБО\n💎 Купи PREMIUM для доступа ко всем режимам!\n\n👇 Выбери режим:"
    else:
        menu_text = f"🔍 ПОИСК НИКОВ\n\n💰 Поисков: {searches} (1 поиск = 1 ник)\n📊 Найдено: {len(available_usernames)}\n💎 PREMIUM: все режимы доступны\n\n👇 Выбери режим:"
    
    bot.send_message(chat_id, menu_text, reply_markup=markup)

def show_bonus_menu(chat_id, user_info):
    user_id = user_info['id']
    is_subscribed = check_subscription(user_id)
    has_bonus = user_info['stats'].get('has_subscribed', False)
    
    if has_bonus:
        bot.send_message(chat_id, f"🎁 БОНУСЫ\n\n✅ Вы уже получали бонус за подписку!\n\n📢 Канал: {REQUIRED_CHANNEL_LINK}")
        return
    if is_subscribed and not has_bonus:
        add_bonus_for_subscription(user_id)
        bot.send_message(chat_id, f"🎁 БОНУСЫ\n\n✅ Подписка подтверждена! Вам начислено +2 поиска!\n\n📢 Канал: {REQUIRED_CHANNEL_LINK}")
        show_main_menu(chat_id, user_info)
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📢 ПОДПИСАТЬСЯ НА КАНАЛ", url=REQUIRED_CHANNEL_LINK),
        types.InlineKeyboardButton("🎁 ПОЛУЧИТЬ БОНУС (+2 поиска)", callback_data="bonus_subscribe")
    )
    bot.send_message(chat_id, f"🎁 БОНУСЫ\n\nПодпишись на наш канал и получи +2 поиска!\n\n📢 {REQUIRED_CHANNEL_LINK}\n\n👇 Нажми кнопку после подписки:", reply_markup=markup)

@bot.message_handler(func=lambda m: True)
def handle_buttons(message):
    chat_id = message.chat.id
    user_info = get_user_info(message.from_user)
    user_id = user_info['id']
    text = message.text
    
    print(f"📩 Сообщение: {text} от {user_id}")
    
    if user_id in user_states and user_states[user_id].get('state') == 'waiting_search_amount':
        try:
            amount = int(text)
            if amount < 1 or amount > 1000:
                bot.send_message(chat_id, "❌ Введите число от 1 до 1000")
                return
            price_rub = amount * SEARCH_PRICE_RUB
            price_stars = amount * SEARCH_PRICE_STARS
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📩 НАПИСАТЬ ПОДДЕРЖКЕ", url=f"https://t.me/{SUPPORT_USERNAME.replace('@', '')}"))
            markup.add(types.InlineKeyboardButton("◀️ В МАГАЗИН", callback_data="back_to_shop"))
            bot.send_message(chat_id, f"🔍 ПОКУПКА ПОИСКОВ\n\n📦 Количество: {amount} поисков\n💰 Цена: {price_stars}⭐️ / {price_rub}₽\n👤 ID: {user_id}\n\n📞 Для оплаты напишите в поддержку:\n{SUPPORT_USERNAME}", reply_markup=markup)
            del user_states[user_id]
        except:
            bot.send_message(chat_id, "❌ Введите целое число")
        return
    
    if text == "⏹ СТОП":
        if search_active.get(user_id):
            search_active[user_id] = False
            bot.send_message(chat_id, "⏹ Поиск остановлен!")
            show_main_menu(chat_id, user_info)
        else:
            bot.send_message(chat_id, "❌ Нет активного поиска")
        return
    
    if text == "📞 ПОДДЕРЖКА":
        bot.send_message(chat_id, f"📞 ПОДДЕРЖКА\n\n👤 Твой ID: {user_id}\n💬 Связь: {SUPPORT_USERNAME}\n\n📧 Email: support@tagforce.com\n\n⏱ Время ответа: до 24 часов")
        return
    
    if text == "🎁 БОНУСЫ":
        show_bonus_menu(chat_id, user_info)
        return
    
    if text == "🛒 МАГАЗИН":
        if search_active.get(user_id):
            bot.send_message(chat_id, "⚠️ Сначала останови поиск кнопкой ⏹ СТОП")
            return
        show_shop_menu(chat_id, user_info)
        return
    
    if text in ["🎯 ПАТТЕРН", "🔢 С ЦИФРАМИ", "⚡️ КОМБО"]:
        if search_active.get(user_id):
            bot.send_message(chat_id, "⚠️ Сначала останови поиск кнопкой ⏹ СТОП")
            return
        
        mode = {"🎯 ПАТТЕРН":"pattern","🔢 С ЦИФРАМИ":"digits","⚡️ КОМБО":"combo"}[text]
        
        if not is_premium(user_id) and mode != "combo":
            bot.send_message(chat_id, "❌ Для FREE пользователей доступен только режим КОМБО!\n💎 Купи PREMIUM для доступа к ПАТТЕРН и С ЦИФРАМИ")
            return
        
        markup = types.InlineKeyboardMarkup(row_width=3)
        markup.add(
            types.InlineKeyboardButton("5 символов", callback_data=f"search_{mode}_5"),
            types.InlineKeyboardButton("6 символов", callback_data=f"search_{mode}_6"),
            types.InlineKeyboardButton("7 символов", callback_data=f"search_{mode}_7"),
            types.InlineKeyboardButton("◀️ НАЗАД", callback_data="back_to_main")
        )
        bot.send_message(chat_id, "📏 ВЫБЕРИ ДЛИНУ (будет найдено 1 ник)", reply_markup=markup)
        return
    
    if text == "👤 ПРОФИЛЬ":
        s = user_info['stats']
        if is_premium(user_id):
            if s.get('premium_forever'):
                status = "💎 PREMIUM (НАВСЕГДА)"
            else:
                premium_until = s.get('premium_until')
                if isinstance(premium_until, str):
                    premium_until = datetime.fromisoformat(premium_until)
                days_left = (premium_until - datetime.now()).days if premium_until else 0
                status = f"💎 PREMIUM (осталось {days_left} дн.)"
            searches = "∞"
        else:
            status = "👤 FREE"
            searches = str(s['searches_left'])
        bot.send_message(chat_id, f"👤 ПРОФИЛЬ\n\n🆔 ID: {user_id}\n📊 Статус: {status}\n💰 Осталось: {searches} (1 поиск = 1 ник)\n✅ Найдено: {s['found']}\n🔄 Всего поисков: {s['total_searches']}")
        return
    
    if text == "📊 СТАТИСТИКА":
        premium = sum(1 for uid in user_stats if is_premium(uid))
        bot.send_message(chat_id, f"📊 ГЛОБАЛЬНАЯ СТАТИСТИКА\n\n✅ Найдено ников: {len(available_usernames)}\n👥 Пользователей: {len(user_stats)}\n💎 Премиум: {premium}")
        return
    
    else:
        show_main_menu(chat_id, user_info)

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_info = get_user_info(message.from_user)
    show_main_menu(chat_id, user_info)

if __name__ == "__main__":
    load_data()
    print("\n" + "="*80)
    print("🤖 БОТ ЗАПУЩЕН")
    print("📌 FREE: только КОМБО | PREMIUM: все режимы")
    print(f"👤 Админ: {ADMIN_ID}")
    print("📋 АДМИН КОМАНДЫ:")
    print("   /add 123456789 10")
    print("   /premium 123456789 30 (-1 навсегда)")
    print("   /user 123456789")
    print("   /stats")
    print("="*80)
    bot.infinity_polling()
