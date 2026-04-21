from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup
from aiogram.fsm.context import FSMContext
from states import Booking
from constants import SERVICES
from database import add_client, save_appointment, check_id_in_BD, add_client, update_client_phone, has_appointment_on_date, update_client_name
from database import get_available_dates, get_client_by_tg_id
from keyboards_booking import get_services_keyboard, get_dates_keyboard, get_times_keyboard
import re
from keyboards import get_main_keyboard
from handlers_admin import ADMIN_ID
from database import set_confirmed_2h, cancel_booking_by_id, get_booking_by_id


router = Router()

@router.message(F.text == "📅 Записаться") 
async def appointment_handler(message: Message, state: FSMContext):
    print("🔔 Сработала запись!")
    await state.set_state(Booking.waiting_for_service)
    await message.answer("Выберите процедуру 🤩",
                          reply_markup=get_services_keyboard())
    

# ==================================== Выбор услуг (НОВАЯ ЗАПИСЬ) =========================================
@router.message(Booking.waiting_for_service, F.text.in_(SERVICES))
async def choice_service(message: Message, state: FSMContext):
    """Состояние выбора услуги (1 шаг выбор даты)"""
    service = message.text
    await state.update_data(service=service)
    await state.set_state(Booking.waiting_for_date)
    await message.answer("Выберите дату.", reply_markup=get_dates_keyboard())   

@router.message(F.text == "📜 В главное меню")
async def back_to_main_menu(message: Message, state: FSMContext):
    await state.clear()
    keyboard = get_main_keyboard()
    await message.answer("❌ Запись отменена. Возвращаю в главное меню.", reply_markup=keyboard)


@router.message(Booking.waiting_for_date)
async def process_date(message: Message, state: FSMContext):
    """Выбор даты после кнопки 'записаться'"""
    date = message.text.strip()
    
    dates = get_available_dates()
    if date not in dates:
        await message.answer("❌ Нет доступных слотов на эту дату. Выбери из кнопок.")
        return
    
    await state.update_data(date=date)
    await state.set_state(Booking.waiting_for_time)
    
    keyboard = get_times_keyboard(date)
    if not keyboard:
        await message.answer("❌ На эту дату нет свободного времени.")
        return
    
    await message.answer("Выбери время:", reply_markup=keyboard)


@router.message(Booking.waiting_for_time)
async def process_time(message: Message, state: FSMContext):
    """Выбор времени из доступных"""
    time = message.text.strip()
    if len(time) != 5 or time[2] != ':':
        await message.answer("❌ Неверный формат. Введи время как ЧЧ:ММ (например, 14:30)")
        return
    
    await state.update_data(time=time)
    
    # Проверяем, есть ли клиент в БД
    tg_id = message.from_user.id
    client = get_client_by_tg_id(tg_id)
    
    if client:
        await state.update_data(existing_client=True)
        await state.update_data(existing_name=client['name'])
        await state.update_data(existing_phone=client['phone'])
        
        # Клавиатура выбора для имени
        name_keyboard = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text=f"👤 Оставить имя {client['name']}")],
            [KeyboardButton(text="✏️ Ввести новое имя")]
        ], resize_keyboard=True)
        
        await state.set_state(Booking.waiting_for_name_choice)
        await message.answer(
            f"📝 У вас уже есть имя в системе: {client['name']}\n"
            f"Оставить или ввести новое?",
            reply_markup=name_keyboard
        )
    else:
        # Новый клиент — запрашиваем телефон как обычно
        await state.set_state(Booking.waiting_for_phone)
        await message.answer("📞 Введи свой номер телефона для связи (например, +79991234567)")


@router.message(Booking.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    """Обработчик. Получаем номер телефона и далее переходим к записи имени"""
    phone = message.text.strip()
    if not re.match(r'^\+?\d{10,15}$', phone):
        await message.answer("❌ Неверный формат. Введи номер в формате +79991234567 или 89991234567")
        return
    
    await state.update_data(phone=phone)
    await state.set_state(Booking.waiting_for_name)
    await message.answer("📝 Введи своё имя (как к тебе обращаться)")

@router.message(Booking.waiting_for_phone_choice)
async def process_phone_choice(message: Message, state: FSMContext):
    """Обработчик. Выбор или вводим новый или оставляем старый номер телефона"""
    data = await state.get_data()
    
    if message.text.startswith("📞 Оставить номер"):
        # Оставляем существующий телефон
        phone = data.get('existing_phone')
        await state.update_data(phone=phone)
        
        # Переходим к сохранению записи
        await save_booking(message, state)
    
    elif message.text == "✏️ Ввести новый номер":
        await state.set_state(Booking.waiting_for_phone)
        await message.answer("📞 Введи свой новый номер телефона (например, +79991234567)")
    
    else:
        await message.answer("❌ Пожалуйста, выбери из кнопок.")



@router.message(Booking.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    """Обработчик. Получаем имя клиента и также проверяем запись на дубль в БД
    Также приходит уведомление админу о новой записи"""
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Имя слишком короткое. Введи хотя бы 2 буквы.")
        return
    
    await state.update_data(name=name)
    data = await state.get_data()
    
    tg_id = message.from_user.id
    tg_name = message.from_user.first_name
    
    # ПРОВЕРКА НА ДУБЛЬ
    if has_appointment_on_date(tg_id, data['date']):
        keyboard = get_main_keyboard()
        await message.answer(
            f"❌ У тебя уже есть запись на {data['date']}.\n"
            f"Выбери другой день или отмени существующую запись через «Мои записи».",
            reply_markup=keyboard
        )
        await state.clear()
        return
    
    # Проверяем, есть ли клиент
    if not check_id_in_BD(tg_id):
        add_client(tg_id, tg_name, data['phone'], name)
    else:
        update_client_name(tg_id, name)
        update_client_phone(tg_id, data['phone'])
    
    # Сохраняем запись
    save_appointment(tg_id, data['service'], data['date'], data['time'])
    
    # Уведомление админу о новой записи
    await message.bot.send_message(
        ADMIN_ID,
        f"🆕 *Новая запись!*\n\n"
        f"👤 Клиент: {name}\n"
        f"📞 Телефон: {data['phone']}\n"
        f"💅 Услуга: {data['service']}\n"
        f"📅 Дата: {data['date']}\n"
        f"⏰ Время: {data['time']}\n",
        parse_mode="Markdown"
    )
    
    keyboard = get_main_keyboard()
    await message.answer(
        f"✅ Ты записан, {name}!\n"
        f"Услуга: {data['service']}\n"
        f"Дата: {data['date']}\n"
        f"Время: {data['time']}\n"
        f"Телефон: {data['phone']}\n\n"
        f"Возвращаю в главное меню.",
        reply_markup=keyboard
    )
    await state.clear()

@router.message(Booking.waiting_for_name_choice)
async def process_name_choice(message: Message, state: FSMContext):
    """Обработчик. Выбор добавить новое имя или оставить старое"""
    data = await state.get_data()
    
    if message.text.startswith("👤 Оставить имя"):
        # Оставляем существующее имя
        name = data.get('existing_name')
        await state.update_data(name=name)
        
        # Переходим к выбору телефона
        client = get_client_by_tg_id(message.from_user.id)
        phone_keyboard = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text=f"📞 Оставить номер {client['phone']}")],
            [KeyboardButton(text="✏️ Ввести новый номер")]
        ], resize_keyboard=True)
        
        await state.set_state(Booking.waiting_for_phone_choice)
        await message.answer(
            f"📞 У вас есть номер: {client['phone']}\n"
            f"Оставить или ввести новый?",
            reply_markup=phone_keyboard
        )
    
    elif message.text == "✏️ Ввести новое имя":
        await state.set_state(Booking.waiting_for_name)
        await message.answer("📝 Введи своё новое имя (как к тебе обращаться)")
    
    else:
        await message.answer("❌ Пожалуйста, выбери из кнопок.")


async def save_booking(message: Message, state: FSMContext):
    """Сохраняем запись"""
    data = await state.get_data()
    
    tg_id = message.from_user.id
    tg_name = message.from_user.first_name
    name = data.get('name')
    phone = data.get('phone')
    
    # Проверка на дубль
    if has_appointment_on_date(tg_id, data['date']):
        keyboard = get_main_keyboard()
        await message.answer(
            f"❌ У тебя уже есть запись на {data['date']}.\n"
            f"Выбери другой день или отмени существующую запись через «Мои записи».",
            reply_markup=keyboard
        )
        await state.clear()
        return
    
    # Сохраняем или обновляем клиента
    if not check_id_in_BD(tg_id):
        add_client(tg_id, tg_name, phone, name)
    else:
        update_client_name(tg_id, name)
        update_client_phone(tg_id, phone)
    
    # Сохраняем запись
    save_appointment(tg_id, data['service'], data['date'], data['time'])
    
    # Уведомление админу
    await message.bot.send_message(
        ADMIN_ID,
        f"🆕 *Новая запись!*\n\n"
        f"👤 Клиент: [{name}](tg://user?id={tg_id})\n"
        f"📞 Телефон: {phone}\n"
        f"💅 Услуга: {data['service']}\n"
        f"📅 Дата: {data['date']}\n"
        f"⏰ Время: {data['time']}",
        parse_mode="Markdown"
    )
    
    keyboard = get_main_keyboard()
    await message.answer(
        f"✅ Ты записан, {name}!\n"
        f"Услуга: {data['service']}\n"
        f"Дата: {data['date']}\n"
        f"Время: {data['time']}\n"
        f"Телефон: {phone}\n\n"
        f"Возвращаю в главное меню.",
        reply_markup=keyboard
    )
    await state.clear()
# ==================================================================================================
# ========================== Напоминалка (уведы мастеру) ===========================================
@router.callback_query(lambda c: c.data.startswith('confirm_2h_'))
async def confirm_2h(callback: CallbackQuery):
    """Отправляет уведомление мастеру о подтверждении записи за 2 часа"""
    appointment_id = int(callback.data.split('_')[2])
    set_confirmed_2h(appointment_id)
    
    # Получаем данные записи для уведомления мастера
    booking = get_booking_by_id(appointment_id)
    
    # Уведомление клиенту
    await callback.message.edit_text("✅ Спасибо! Ждём вас через 2 часа.")
    
    # Уведомление мастеру
    await callback.bot.send_message(
        ADMIN_ID,
        f"✅ *Клиент подтвердил запись за 2 часа!*\n\n"
        f"👤 Клиент: [{booking['client_name']}](tg://user?id={booking['client_id']})\n"
        f"💅 Услуга: {booking['service']}\n"
        f"📅 Дата: {booking['date']}\n"
        f"⏰ Время: {booking['time']}",
        parse_mode="Markdown"
    )
    
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith('cancel_2h_'))
async def cancel_2h(callback: CallbackQuery):
    """Уведомление мастеру об отмене записи за 2 часа"""
    appointment_id = int(callback.data.split('_')[2])
    booking = get_booking_by_id(appointment_id)
    cancel_booking_by_id(appointment_id)
    
    await callback.message.edit_text("❌ Запись отменена по вашему желанию.")
    
    # Уведомление мастеру
    await callback.bot.send_message(
        ADMIN_ID,
        f"❌ *Клиент отменил запись за 2 часа!*\n\n"
        f"👤 Клиент: [{booking['client_name']}](tg://user?id={booking['client_id']})\n"
        f"💅 Услуга: {booking['service']}\n"
        f"📅 Дата: {booking['date']}\n"
        f"⏰ Время: {booking['time']}",
        parse_mode="Markdown"
    )
    
    await callback.answer()