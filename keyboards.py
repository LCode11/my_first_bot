from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_keyboard():
    """Основная клавиатура для клинта"""
    buttons = [
        [KeyboardButton(text="📅 Записаться"), KeyboardButton(text="💇 Услуги")],
        [KeyboardButton(text="💰 Прайс"), KeyboardButton(text="📍 Контакты")],
        [KeyboardButton(text="❓ О нас"), KeyboardButton(text="📋 Мои записи")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_admin_keyboard():
    """Клавиатура админа"""
    buttons = [
        [KeyboardButton(text="📋 Список записей"), KeyboardButton(text="📋 Записи с кнопками")],
        [KeyboardButton(text="📋 Список слотов"), KeyboardButton(text="➕ Добавить слот")],
        [KeyboardButton(text="🗑 Удалить прошедшие записи"), KeyboardButton(text="📊 Экспорт в Excel")],
        [KeyboardButton(text="🗑 Удалить все записи")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)