import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import init_db, get_appointments_for_reminder, get_appointments_for_confirmation, mark_reminder_sent
from config import BOT_TOKEN
from handlers_menu import router as menu_router
from handlers_booking import router as booking_router
from handlers_admin import router as admin_router


async def reminder_checker(bot: Bot):
    """Функция напоминаний"""
    while True:
        try:
            # Напоминания за 24 часа
            for app in get_appointments_for_reminder(24):
                await bot.send_message(
                    app['telegram_id'],
                    f"🔔 *Напоминание!*\n\n"
                    f"У вас запись на завтра:\n"
                    f"💅 {app['service']}\n"
                    f"📅 {app['date']} в {app['time']}",
                    parse_mode="Markdown"
                )
                mark_reminder_sent(app['id'], 24)
            
            # Подтверждение за 2 часа
            for app in get_appointments_for_confirmation():
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Да, буду", callback_data=f"confirm_2h_{app['id']}")],
                    [InlineKeyboardButton(text="❌ Отменить запись", callback_data=f"cancel_2h_{app['id']}")]
                ])
                
                await bot.send_message(
                    app['telegram_id'],
                    f"⏰ *Через 2 часа запись!*\n\n"
                    f"💅 {app['service']}\n"
                    f"📅 {app['date']} в {app['time']}\n\n"
                    f"Вы подтверждаете?",
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
        
        except Exception as e:
            print(f"Ошибка в reminder_checker: {e}")
        
        await asyncio.sleep(600)  # каждые 10 минут

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
async def main():
    init_db()
    bot = Bot(token=BOT_TOKEN)
    
    # Запускаем фоновую задачу напоминаний
    asyncio.create_task(reminder_checker(bot))
    
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    dp.include_router(menu_router)
    dp.include_router(booking_router)
    dp.include_router(admin_router)
    
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())