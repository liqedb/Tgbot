import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ParseMode

# Конфигурация
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Замените на ваш токен от @BotFather
DB_NAME = "users.db"

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Работа с базой данных
def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            is_authorized BOOLEAN DEFAULT FALSE,
            auth_code TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def get_user_by_telegram_id(telegram_id: int):
    """Получение пользователя по Telegram ID"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def create_user(telegram_id: int, username: str, first_name: str, last_name: str = None):
    """Создание нового пользователя"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO users (telegram_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        ''', (telegram_id, username, first_name, last_name))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def generate_auth_code() -> str:
    """Генерация кода авторизации"""
    import random
    return str(random.randint(100000, 999999))

def set_auth_code(telegram_id: int, code: str):
    """Установка кода авторизации"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET auth_code = ? WHERE telegram_id = ?", (code, telegram_id))
    conn.commit()
    conn.close()

def verify_auth_code(telegram_id: int, code: str) -> bool:
    """Проверка кода авторизации"""
    user = get_user_by_telegram_id(telegram_id)
    if user and user[7] == code:  # 7-й индекс - auth_code
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_authorized = TRUE, auth_code = NULL WHERE telegram_id = ?", (telegram_id,))
        conn.commit()
        conn.close()
        return True
    return False

def is_user_authorized(telegram_id: int) -> bool:
    """Проверка статуса авторизации"""
    user = get_user_by_telegram_id(telegram_id)
    return user and user[6]  # 6-й индекс - is_authorized

# Клавиатуры
def get_main_keyboard():
    """Основная клавиатура для авторизованных пользователей"""
    keyboard = [
        [KeyboardButton(text="👤 Мой профиль")],
        [KeyboardButton(text="📋 Информация"), KeyboardButton(text="❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_auth_keyboard():
    """Клавиатура для неавторизованных пользователей"""
    keyboard = [
        [KeyboardButton(text="🔐 Начать авторизацию")],
        [KeyboardButton(text="❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# Обработчики команд
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    telegram_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    
    # Создаем или обновляем пользователя в БД
    if not get_user_by_telegram_id(telegram_id):
        create_user(telegram_id, username, first_name, last_name)
    
    if is_user_authorized(telegram_id):
        await message.answer(
            f"Добро пожаловать обратно, {first_name}! ✅\n\n"
            f"Вы уже авторизованы в системе.",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.answer(
            f"Привет, {first_name}! 👋\n\n"
            f"Для доступа к функциям бота необходимо пройти авторизацию.\n"
            f"Нажмите кнопку ниже, чтобы начать.",
            reply_markup=get_auth_keyboard()
        )

@dp.message(lambda message: message.text == "🔐 Начать авторизацию")
async def start_auth(message: types.Message):
    """Начало процесса авторизации"""
    telegram_id = message.from_user.id
    
    if is_user_authorized(telegram_id):
        await message.answer("✅ Вы уже авторизованы!", reply_markup=get_main_keyboard())
        return
    
    # Генерируем код авторизации
    auth_code = generate_auth_code()
    set_auth_code(telegram_id, auth_code)
    
    await message.answer(
        f"🔐 <b>Код авторизации</b>\n\n"
        f"Ваш код: <code>{auth_code}</code>\n\n"
        f"Отправьте этот код администратору для подтверждения,\n"
        f"или введите команду /verify <code>{auth_code}</code>",
        parse_mode=ParseMode.HTML
    )

@dp.message(Command("verify"))
async def cmd_verify(message: types.Message):
    """Проверка кода авторизации"""
    telegram_id = message.from_user.id
    args = message.text.split()
    
    if len(args) < 2:
        await message.answer("❌ Пожалуйста, укажите код авторизации.\nПример: /verify 123456")
        return
    
    code = args[1]
    
    if verify_auth_code(telegram_id, code):
        await message.answer(
            "✅ <b>Авторизация успешна!</b>\n\n"
            f"Теперь вы имеете доступ ко всем функциям бота.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_keyboard()
        )
    else:
        await message.answer("❌ Неверный код авторизации. Попробуйте еще раз.")

@dp.message(lambda message: message.text == "👤 Мой профиль")
async def show_profile(message: types.Message):
    """Показ профиля пользователя"""
    telegram_id = message.from_user.id
    
    if not is_user_authorized(telegram_id):
        await message.answer("❌ Сначала пройдите авторизацию!", reply_markup=get_auth_keyboard())
        return
    
    user = get_user_by_telegram_id(telegram_id)
    
    await message.answer(
        f"👤 <b>Ваш профиль</b>\n\n"
        f"ID: <code>{user[1]}</code>\n"
        f"Имя: {user[3]} {user[4] or ''}\n"
        f"Username: @{user[2] or 'не указан'}\n"
        f"Статус: ✅ Авторизован\n"
        f"Дата регистрации: {user[8]}",
        parse_mode=ParseMode.HTML
    )

@dp.message(lambda message: message.text == "📋 Информация")
async def show_info(message: types.Message):
    """Показ информации о боте"""
    await message.answer(
        "📋 <b>Информация о боте</b>\n\n"
        f"Это демонстрационный бот с системой авторизации.\n"
        f"База данных: SQLite\n"
        f"Фреймворк: aiogram 3.x\n\n"
        f"Версия: 1.0.0",
        parse_mode=ParseMode.HTML
    )

@dp.message(lambda message: message.text == "❓ Помощь")
async def show_help(message: types.Message):
    """Показ справки"""
    await message.answer(
        "❓ <b>Помощь</b>\n\n"
        "<b>Команды:</b>\n"
        "/start - Запустить бота\n"
        "/verify &lt;код&gt; - Подтвердить код авторизации\n\n"
        "<b>Кнопки:</b>\n"
        "🔐 Начать авторизацию - Получить код авторизации\n"
        "👤 Мой профиль - Показать ваш профиль\n"
        "📋 Информация - Информация о боте\n"
        "❓ Помощь - Эта справка",
        parse_mode=ParseMode.HTML
    )

@dp.message()
async def echo_all(message: types.Message):
    """Обработчик всех остальных сообщений"""
    telegram_id = message.from_user.id
    
    if not is_user_authorized(telegram_id):
        await message.answer(
            "⚠️ Сначала пройдите авторизацию!\n"
            "Нажмите кнопку ниже.",
            reply_markup=get_auth_keyboard()
        )
    else:
        await message.answer("Используйте кнопки меню или команду /help")

# Основной цикл
async def main():
    """Запуск бота"""
    # Инициализация БД
    init_db()
    print("✅ База данных инициализирована")
    print("🤖 Запуск бота...")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен")
