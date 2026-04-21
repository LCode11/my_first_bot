from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BufferedInputFile
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from database import update_appointment_status, get_appointment_by_id, get_all_appointments, get_appointments_page
from database import get_setting, set_setting, get_available_dates, get_available_times, add_work_slot
from database import get_all_appointments_for_export, delete_expired_appointments, get_connection
from states import AddSlot
from datetime import datetime
from openpyxl import Workbook
from keyboards import get_admin_keyboard

router = Router()

ADMIN_ID = 2061735365 #ID АДМИНА

ITEMS_PER_PAGE = 10

@router.callback_query(lambda c: c.data.startswith('confirm_') and c.data != "confirm_clear_all")
async def confirm_appointment(callback: CallbackQuery):
    appointment_id = int(callback.data.split('_')[1])
    # Меняем статус в БД
    update_appointment_status(appointment_id, 'confirmed')
    # Получаем данные о записи и клиенте
    appointment = get_appointment_by_id(appointment_id)
    # Уведомляем клиента
    await callback.bot.send_message(
        appointment['telegram_id'],
        f"✅ Ваша запись на {appointment['service']} ({appointment['date']} {appointment['time']}) подтверждена!")
    
    await callback.answer("Запись подтверждена!")
    # убираем кнопки
    await callback.message.edit_reply_markup(reply_markup=None)

@router.callback_query(lambda c: c.data.startswith('cancel_') and c.data != "cancel_clear_all")
async def cancel_appointment(callback: CallbackQuery):
    appointment_id = int(callback.data.split('_')[1])
    update_appointment_status(appointment_id, 'cancelled')
    appointment = get_appointment_by_id(appointment_id)
    await callback.bot.send_message(
        appointment['telegram_id'],
        f"❌ Ваша запись на {appointment['service']} ({appointment['date']} {appointment['time']}) отменена.")
    await callback.answer("Запись отменена.")
    await callback.message.edit_reply_markup(reply_markup=None)


@router.message(F.text == "/appointments")
async def show_appointments(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У тебя нет доступа.")
        return
    
    appointments = get_all_appointments()
    if not appointments:
        await message.answer("📭 Записей пока нет.")
        return
    
    for app in appointments:
        # Кнопки для каждой записи
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{app['id']}")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_{app['id']}")]
        ])
        
        status_text = "ожидает" if app['status'] == 'pending' else "подтверждена" if app['status'] == 'confirmed' else "отменена"
        phone_str = f"\n📞 Телефон: {app['phone']}" if app.get('phone') else ""
        text = (f"📋 Запись #{app['id']}\n"
        f"👤 Клиент: [{app['name']}](tg://user?id={app['telegram_id']}){phone_str}\n"
        f"💅 Услуга: {app['service']}\n"
        f"📅 Дата: {app['date']}\n"
        f"⏰ Время: {app['time']}\n"
        f"🏷 Статус: {status_text}")
        
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")




async def send_appointments_page(message, page, appointments, total):
    total_pages = (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    text = f"📋 *Записи — страница {page} из {total_pages}*\n\n"
    
    for app in appointments:
        status_text = "ожидает" if app['status'] == 'pending' else "подтверждена" if app['status'] == 'confirmed' else "отменена"
        phone_str = f" — {app['phone']}" if app.get('phone') else ""
        text += f"• {app['date']} {app['time']} — {app['service']} — [{app['name']}](tg://user?id={app['telegram_id']}){phone_str} ({status_text})\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    nav_buttons = []
    
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="◀ Назад", callback_data=f"list_page_{page - 1}"))
    if page * ITEMS_PER_PAGE < total:
        nav_buttons.append(InlineKeyboardButton(text="Вперёд ▶", callback_data=f"list_page_{page + 1}"))
    
    if nav_buttons:
        keyboard.inline_keyboard.append(nav_buttons)
    
    await message.answer(text, parse_mode="Markdown", reply_markup=keyboard if nav_buttons else None)


async def show_list(message: Message, state: FSMContext):
    """Команда /list"""
    await state.clear()
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Нет доступа.")
        return
    
    page = 1
    appointments, total = get_appointments_page(page, ITEMS_PER_PAGE)
    
    if not appointments:
        await message.answer("📭 Записей нет.")
        return
    
    await send_appointments_page(message, page, appointments, total)

# Обработчик команды /list
@router.message(F.text == "/list")
async def list_command(message: Message, state: FSMContext):
    await show_list(message, state)

# Обработчик кнопки
@router.message(F.text == "📋 Список записей")
async def list_button(message: Message, state: FSMContext):
    await show_list(message, state)

# ========== ОБРАБОТЧИК КНОПОК ПАГИНАЦИИ ==========
@router.callback_query(lambda c: c.data.startswith('list_page_'))
async def list_page_callback(callback: CallbackQuery):
    page = int(callback.data.split('_')[2])
    appointments, total = get_appointments_page(page, ITEMS_PER_PAGE)
    
    await callback.message.edit_text("Загрузка...", reply_markup=None)
    await send_appointments_page(callback.message, page, appointments, total)
    await callback.answer()

# ОСТАЛЬНЫЕ АДМИН-КОМАНДЫ
# (show_appointments, simple_list, confirm_appointment, cancel_appointment и т.д.)
@router.message(F.text == "📋 Записи с кнопками")
async def appointments_with_buttons(message: Message, state: FSMContext):
    await state.clear()
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Нет доступа.")
        return
    
    appointments = get_all_appointments()
    if not appointments:
        await message.answer("📭 Записей пока нет.")
        return
    
    for app in appointments:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{app['id']}")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_{app['id']}")]
        ])
        
        status_text = "ожидает" if app['status'] == 'pending' else "подтверждена" if app['status'] == 'confirmed' else "отменена"
        phone_str = f"\n📞 Телефон: {app['phone']}" if app.get('phone') else ""
        text = (f"📋 Запись #{app['id']}\n"
        f"👤 Клиент: [{app['name']}](tg://user?id={app['telegram_id']}){phone_str}\n"
        f"💅 Услуга: {app['service']}\n"
        f"📅 Дата: {app['date']}\n"
        f"⏰ Время: {app['time']}\n"
        f"🏷 Статус: {status_text}")
        
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")



# ====================== СЛОТЫ (Добавление, удаление) ======================================

def get_cancel_keyboard():
    buttons = [[KeyboardButton(text="❌ Отменить добавление")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

@router.message(F.text == "➕ Добавить слот")
async def add_slot_start(message: Message, state: FSMContext):
    """Обработчик 'Добавить слот'"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Нет доступа.")
        return
    await state.set_state(AddSlot.waiting_for_date)
    await message.answer(
        "📅 Введи дату в формате ДД.ММ (например, 15.04)\n\n"
        "Или нажми «Отменить добавление», чтобы выйти.",
        reply_markup=get_cancel_keyboard())
    
@router.message(F.text == "❌ Отменить добавление")
async def cancel_add_slot(message: Message, state: FSMContext):
    """Обработчик отмены добавления слоа"""
    keyboard = get_admin_keyboard()
    await message.answer("❌ Добавление слотов отменено.", reply_markup=keyboard)
    await state.clear()

@router.message(AddSlot.waiting_for_date)
async def add_slot_date(message: Message, state: FSMContext):
    """Обработчик выбора даты при добавлении слота"""
    date_str = message.text.strip()
    
    # Проверка формата ДД.ММ
    if len(date_str) != 5 or date_str[2] != '.':
        await message.answer("❌ Неверный формат. Введи дату как ДД.ММ")
        return
    
    try:
        day, month = map(int, date_str.split('.'))
        # Проверка, что дата реальна
        datetime(2000, month, day)  # год любой (2000 високосный)
    except ValueError:
        await message.answer("❌ Неверная дата. Например: 15.04")
        return
    
    await state.update_data(date=date_str)
    
    await state.set_state(AddSlot.waiting_for_time)
    keyboard = get_cancel_keyboard()
    await message.answer("⏰ Введи время в формате ЧЧ:ММ (например, 14:00)", reply_markup=keyboard)

@router.message(F.text == "➕ Добавить ещё на эту дату")
async def add_more_same_date(message: Message, state: FSMContext):
    """Обработчик 'Добавить ещё на эту дату (слоты)'"""
    data = await state.get_data()
    date = data.get('date')
    if not date:
        await message.answer("❌ Ошибка: дата не найдена. Начни заново.")
        await state.clear()
        return
    
    await state.set_state(AddSlot.waiting_for_time)
    await message.answer(
        f"📅 Введи время для {date} в формате ЧЧ:ММ (например, 14:00)",
        reply_markup=get_cancel_keyboard()
    )

@router.message(F.text == "📅 Добавить на другую дату")
async def add_other_date(message: Message, state: FSMContext):
    await state.set_state(AddSlot.waiting_for_date)
    await message.answer(
        "📅 Введи новую дату в формате ДД.ММ (например, 15.04)",
        reply_markup=get_cancel_keyboard()
        )

@router.message(F.text == "❌ Закончить добавление")
async def finish_adding_slots(message: Message, state: FSMContext):
    keyboard = get_admin_keyboard()
    await message.answer("✅ Возврат в админ-панель.", reply_markup=keyboard)
    await state.clear()

# ОБРАБОТЧИК ВРЕМЕНИ
@router.message(AddSlot.waiting_for_time)
async def add_slot_time(message: Message, state: FSMContext):
    time_str = message.text.strip()
    
    if len(time_str) != 5 or time_str[2] != ':':
        await message.answer("❌ Неверный формат. Введи время как ЧЧ:ММ")
        return
    
    try:
        hours, minutes = map(int, time_str.split(':'))
        if not (0 <= hours <= 23 and 0 <= minutes <= 59):
            raise ValueError
    except ValueError:
        await message.answer("❌ Неверное время. Часы от 00 до 23, минуты от 00 до 59")
        return
    
    data = await state.get_data()
    add_work_slot(data['date'], time_str)
    
    # Кнопки выбора следующего действия
    
    keyboard = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Добавить ещё на эту дату")],
        [KeyboardButton(text="📅 Добавить на другую дату")],
        [KeyboardButton(text="❌ Закончить добавление")]
    ], resize_keyboard=True)
    
    await message.answer(
        f"✅ Слот {data['date']} {time_str} добавлен!\n\nЧто дальше?",
        reply_markup=keyboard)
    # Не очищаем state, остаёмся в FSM
# ========================================================================================================

@router.message(F.text == "📋 Список слотов")
async def list_slots(message: Message, state: FSMContext):
    """ОБРАБОТЧИК КНОПКИ "СПИСОК СЛОТОВ"""
    await state.clear()                  # Стираем состояние (предохраняемся)
    if message.from_user.id != ADMIN_ID: # Если не админ - нет доступа
        await message.answer("⛔ Нет доступа.")
        return                           # Офаем функцию
    
    dates = get_available_dates()
    if not dates:
        await message.answer("📭 Нет добавленных слотов.")
        return
    
    for date in dates:
        times = get_available_times(date)
        times_str = ', '.join(times)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Удалить всё на эту дату", callback_data=f"delete_date_{date}")]
        ])
        
        await message.answer(f"📅 {date} ⌛{times_str}", reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith('delete_date_'))
async def delete_date_slots(callback: CallbackQuery):
    """Обработчик УДАЛЕНИЯ СЛОТОВ"""
    date = callback.data.split('_')[2]
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM work_slots WHERE date = ?", (date,))
    conn.commit() # Сохраняем изменения в БД
    conn.close() # Закрываем соединение с БД
     
    await callback.answer(f"✅ Все слоты на {date} удалены.")
    await callback.message.delete() # Удаляет сообщение со списком слотов и кнопкой 

# ======================================= EXCEL =================================================
@router.message(F.text == "/export")
async def export_to_excel(message: Message):
    """ОБРАБОТЧИК КОМАНДЫ /EXPORT"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Нет доступа.")
        return
    
    data = get_all_appointments_for_export()
    if not data:
        await message.answer("📭 Нет данных для экспорта.")
        return
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Записи"
    ws.append(["Дата", "Время", "Услуга", "Статус", "Имя клиента", "Телефон"])
    
    for row in data:
        ws.append(list(row))
    
    import io
    byte_stream = io.BytesIO()
    wb.save(byte_stream)
    byte_stream.seek(0)
    
    await message.answer_document(
        BufferedInputFile(byte_stream.read(), filename="appointments.xlsx"),
        caption="📊 Экспорт записей")

@router.message(F.text == "📊 Экспорт в Excel")
async def export_button(message: Message):
    """ОБРАБОТЧИК КНОПКИ ЭКСПОРТА ЗАПИСЕЙ"""
    await export_to_excel(message)


# =============== ОБРАБОТЧИКИ УДАЛЕНИЯ ВСЕХ ЗАПИСЕЙ (ВКЛЮЧАЯ АКТИВНЫЕ) И ОТМЕНЫ УДАЛЕНИЯ ===========
@router.message(F.text == "🗑 Удалить прошедшие записи")
async def delete_expired(message: Message, state: FSMContext):
    """ОБРАБОТЧИК "УДАЛЕНИЯ ПРОШЕДШИХ ЗАПИСЕЙ"""
    await state.clear()
    if message.from_user.id != ADMIN_ID: # Если не админ, то нет доступа
        await message.answer("⛔ Нет доступа.")
        return
    
    deleted = delete_expired_appointments()
    await message.answer(f"✅ Удалено просроченных записей: {deleted}")

@router.message(F.text == "🗑 Удалить все записи")
async def clear_all_appointments(message: Message, state: FSMContext):
    """Обработчик 'удалить все записи' с Inline клавиатурой"""
    await state.clear()
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Нет доступа.")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить всё", callback_data="confirm_clear_all")],
        [InlineKeyboardButton(text="❌ Нет, отмена", callback_data="cancel_clear_all")]
    ])
    await message.answer("⚠️ Ты уверен? Это удалит ВСЕ записи без возможности восстановления.", reply_markup=keyboard)

@router.callback_query(lambda c: c.data == "confirm_clear_all")
async def confirm_clear_all(callback: CallbackQuery):
    """Обработчик подтверждения удаления всех записей"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM appointments")
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    
    await callback.message.edit_text(f"✅ Удалено всех записей: {deleted}")
    keyboard = get_admin_keyboard()
    await callback.message.answer("✅ Возврат в админ-панель.", reply_markup=keyboard)

@router.callback_query(lambda c: c.data == "cancel_clear_all")
async def cancel_clear_all(callback: CallbackQuery):
    """Обработчик отмены удаления всех записей"""
    await callback.message.edit_text("❌ Удаление отменено.")
    keyboard = get_admin_keyboard()
    await callback.message.answer("✅ Возврат в админ-панель.", reply_markup=keyboard)