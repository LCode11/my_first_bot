from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from keyboards import get_main_keyboard, get_admin_keyboard
from database import check_id_in_BD, get_client_bookings, get_booking_by_id, cancel_booking_by_id
from handlers_admin import ADMIN_ID

router = Router()

@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    """Обработчик /start и для админа, и для клиента"""
    await state.clear()
    tg_id = message.from_user.id
    
    if tg_id == ADMIN_ID:
        keyboard = get_admin_keyboard()
        await message.answer("👋 Добро пожаловать в админ-панель!", reply_markup=keyboard)
    else:
        keyboard = get_main_keyboard()
        await message.answer("Привет! Я бот для записи на маникюр.", reply_markup=keyboard)
    
@router.message(F.text == "💰 Прайс")
async def price_handler(message: Message):
    await message.answer("💅 Маникюр - 1500₽\n✨ Педикюр - 2000₽\n🎨 Дизайн - от 500₽\n Покрытие - 1000₽")

@router.message(F.text == "📍 Контакты")
async def contacts_handler(message: Message):
    await message.answer("📍 ул. Ленина, 10\n📞 +7 (999) 123-45-67")

@router.message(F.text == "❓ О нас")
async def about_handler(message: Message):
    await message.answer("💅 Салон красоты 'Уют'\nРаботаем с 2015 года.")

@router.message(F.text == "💇 Услуги")
async def services_handler(message: Message):
    await message.answer("Маникюр, педикюр, покрытие гель-лаком, дизайн, парафинотерапия.")

@router.message(F.text == "/myid")
async def show_my_id(message: Message):
    await message.answer(f"Твой ID: `{message.from_user.id}`", parse_mode="Markdown")

@router.message(F.text == "📋 Мои записи")
async def my_bookings(message: Message):
    """Открывает меню активных записей или возвращает 'у вас пока нет записей' """
    tg_id = message.from_user.id
    
    bookings = get_client_bookings(tg_id)
    if not bookings:
        await message.answer("📭 У вас пока нет записей.")
        return
    
    for b in bookings:
        status_emoji = "⏳" if b['status'] == 'pending' else "✅" if b['status'] == 'confirmed' else "❌"
        status_text = "ожидает" if b['status'] == 'pending' else "подтверждена" if b['status'] == 'confirmed' else "отменена"
        
        keyboard = None # Если 
        if b['status'] in ('pending', 'confirmed'):
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_booking_{b['id']}")]
            ])
        
        text = f"{status_emoji} {b['date']} {b['time']} — {b['service']} ({status_text})"
        await message.answer(text, reply_markup=keyboard)

@router.callback_query(lambda c: c.data.startswith('cancel_booking_'))
async def cancel_booking(callback: CallbackQuery):
    booking_id = int(callback.data.split('_')[2])
    
    booking = get_booking_by_id(booking_id)
    if not booking:
        await callback.answer("❌ Запись не найдена.")
        return
    
    cancel_booking_by_id(booking_id)
    
    # Уведомление клиенту
    await callback.message.edit_text(
        f"❌ Запись на {booking['date']} {booking['time']} ({booking['service']}) отменена.",
        reply_markup=None
    )
    
    # Уведомление мастеру — с именем клиента из БД и ссылкой на профиль
    client_name = booking.get('client_name') or "Клиент"
    client_tg_id = booking.get('client_id')
    
    await callback.bot.send_message(
        ADMIN_ID,
        f"🔄 Клиент [{client_name}](tg://user?id={client_tg_id}) отменил запись:\n"
        f"{booking['date']} {booking['time']} — {booking['service']}",
        parse_mode="Markdown"
    )
    
    await callback.answer("Запись отменена.")