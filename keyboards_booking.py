from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from constants import SERVICES
from database import get_available_dates, get_available_times

def get_services_keyboard():
    """Возвращает клавиатуру со списком 'SERVICES' и кнопкой 'В главное меню' """
    buttons = [[KeyboardButton(text=service)] for service in SERVICES]
    buttons.append([KeyboardButton(text="📜 В главное меню")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_dates_keyboard():
    """Возвращает актуальные даты поставленные мастером, если дат нет, то ничего"""
    dates = get_available_dates() # Возвращает уникальные даты
    if not dates: # Вернёт None, если актуальных дат нет, и в обработчике вернёт сообщение об отсутствие дат
        return None
    buttons = [[KeyboardButton(text=d)] for d in dates] # Если не None, то возвращает клаву 
    buttons.append([KeyboardButton(text="📜 В главное меню")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True) 

def get_times_keyboard(date):
    """Возвращает так же актуальное время поставленное мастером, если есть актуальны даты"""
    times = get_available_times(date)
    if not times:
        return None
    buttons = [[KeyboardButton(text=t)] for t in times]
    buttons.append([KeyboardButton(text="📜 В главное меню")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)