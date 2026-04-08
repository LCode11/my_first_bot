import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = '8532100817:AAH9tF0zcltFxPlQwMB3ka0z8UADyp-AMQI'

bot = Bot(token=BOT_TOKEN) # Объект бота
dp = Dispatcher() # Диспетчер — смотрит, какое сообщение пришло и кому его отдать

def get_main_keyboard(): # Кнопки главного меню
    buttons = [
        [KeyboardButton(text="📅 Записаться"), KeyboardButton(text="💇 Услуги")],
        [KeyboardButton(text="💰 Прайс"), KeyboardButton(text="📍 Контакты")],
        [KeyboardButton(text="❓ О нас")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    return keyboard

@dp.message(CommandStart()) # Отправляет приветствие и кнопки при запуске
async def start_command(message: types.Message):
    keyboard = get_main_keyboard()
    await message.answer("Привет! Я бот для записи на маникюр.", reply_markup=keyboard)

@dp.message(F.text == "💰 Прайс")
async def price_handler(message: types.Message):
    await message.answer("💅 Маникюр — 1500₽\n✨ Педикюр — 2000₽\n🎨 Дизайн — от 500₽")

@dp.message(F.text == "📍 Контакты")
async def contacts_handler(message: Message):
    await message.answer("📍 ул. Ленина, 10\n📞 +7 (999) 123-45-67")

@dp.message(F.text == "❓ О нас")
async def about_handler(message: Message):
    await message.answer("💅 Салон красоты 'Уют'\nРаботаем с 2015 года.")

@dp.message(F.text == "📅 Записаться")
async def appointment_handler(message: Message):
    await message.answer("Скоро здесь будет запись! А пока дай подумать)")

@dp.message(F.text == "💇 Услуги")
async def services_handler(message: Message):
    await message.answer("Маникюр, педикюр, покрытие гель-лаком, дизайн, парафинотерапия.")

async def main(): 
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())