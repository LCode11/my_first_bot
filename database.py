import sqlite3
#import os
from datetime import datetime, timedelta, timezone
import pytz

# DB_NAME = os.path.join("/data", "bookings.db") if os.path.exists("/data") else "bookings.db" # временно
DB_NAME = "bookings.db"

def get_connection():
    """Возвращает соединение с БД"""
    return sqlite3.connect(DB_NAME)

# ========== КЛИЕНТЫ ==========
def init_db():
    """Создаёт таблицы, если их нет"""
    conn = get_connection()
    cursor = conn.cursor()

    # Таблица клиентов. ХРАНИТ ИНФУ О ВСЕХ ПОЛЬЗОВАТЕЛЯХ БОТА
    # telegram_id — уникальный идентификатор Telegram (первичный ключ)
    # name — имя клиента (которое он ввёл при записи)
    # phone — номер телефона клиента
    # created_at — дата и время первого обращения (заполняется автоматически)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            telegram_id INTEGER PRIMARY KEY,
            name TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
    """)

    # Таблица записей (appointments)
    # Хранит все записи клиентов к мастеру
    # id — уникальный номер записи (автоинкремент)
    # client_id — ссылка на клиента из таблицы clients (кто записался)
    # service — название услуги (Маникюр, Педикюр и т.д.)
    # date — дата записи (формат ДД.ММ)
    # time — время записи (формат ЧЧ:ММ)
    # status — статус записи: 'pending' (ожидает), 'confirmed' (подтверждена), 'cancelled' (отменена)
    # created_at — когда была создана запись
    # FOREIGN KEY — связь: client_id ссылается на telegram_id из таблицы clients
    # reminded_24h INTEGER DEFAULT 0 — напоминалка за 24 часа, напоминание отправляется
    # confirmed_2h INTEGER DEFAULT 0 — напоминалка за 2 часа, подтверждение
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            service TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL, 
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients (telegram_id)    )

    """)
    # Добавляем новые колонки, если их нет (для старых БД)
    try:
        cursor.execute("ALTER TABLE appointments ADD COLUMN reminded_24h INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # колонка уже есть

    try:
        cursor.execute("ALTER TABLE appointments ADD COLUMN confirmed_2h INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # колонка уже есть

    # ТАБЛИЦА НАСТРОЕК(settings)
    # Хранит пары "ключ-значение" для различных настроек бота
    # key — название настройки (например, 'work_hours')
    # value — значение настройки (например, '10:00,11:00,12:00')
    # Используется для хранения рабочих часов, дней и других параметров
    # Позволяет менять настройки без перезапуска бота
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT)
    """)

    # ТАБЛИЦА РАБОЧИХ СЛОТОВ
    # Хранит даты и время, которые админ добавил как доступные для записи
        # date — дата в формате ДД.ММ
    # time — время в формате ЧЧ:ММ
    # UNIQUE(date, time) — запрещает дублирование (нельзя добавить один и тот же слот дважды)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS work_slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        UNIQUE(date, time))
    """)
    conn.commit()
    conn.close()

def check_id_in_BD(tg_id):
    """Проверят id telegram в БД"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id FROM clients WHERE telegram_id = ?", (tg_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None        

def add_client(tg_id, tg_name, phone=None, name=None):
    """Добавляет нового клиента в БД. Если name не указан, берёт tg_name."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO clients (telegram_id, name, phone) VALUES (?, ?, ?)",
        (tg_id, name or tg_name, phone)  # если name нет — берём tg_name
    )
    conn.commit()
    conn.close()
    return tg_id

def update_client_name(tg_id, name):
    """При каждой новой записи обновляет имя клиента на актуальное, если не ввёл, то tg_name"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE clients SET name = ? WHERE telegram_id = ?",
        (name, tg_id)
    )
    conn.commit()
    conn.close()

def update_client_phone(tg_id, phone):
    """При каждой новой записи обновляет телефон клиента на актуальный, если не ввёл, то None"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE clients SET phone = ? WHERE telegram_id = ?",
        (phone, tg_id)
    )
    conn.commit()
    conn.close()


# ========================================== ЗАПИСИ ====================================================
def save_appointment(client_id, service, date, time):
    """Добавляем инфу о записи в БД"""
    # client_id — это просто tg_id
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO appointments (client_id, service, date, time, status)
        VALUES (?, ?, ?, ?, 'pending')
    """, (client_id, service, date, time))
    conn.commit()
    conn.close()
    
def get_all_appointments():
    """Возвращает записи клиентов"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT a.id, a.date, a.time, a.service, a.status, c.name, c.telegram_id, c.phone
        FROM appointments a
        JOIN clients c ON a.client_id = c.telegram_id
        WHERE a.status != 'cancelled'
        ORDER BY a.date, a.time
    """)
    rows = cursor.fetchall()
    conn.close()
    
    return [{"id": r[0], "date": r[1], "time": r[2], "service": r[3], "status": r[4], 
             "name": r[5], "telegram_id": r[6], "phone": r[7]} for r in rows]

def update_appointment_status(appointment_id, status):
    """Обновляет статус записи"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE appointments SET status = ? WHERE id = ?",
        (status, appointment_id)
    )
    conn.commit()
    conn.close()

def get_appointment_by_id(appointment_id):
    """Получает всю информацию о каждой записи (для админа на подтверждение)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.service, a.date, a.time, a.status, c.telegram_id, c.name
        FROM appointments a
        JOIN clients c ON a.client_id = c.telegram_id
        WHERE a.id = ?
    """, (appointment_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {"id": row[0], "service": row[1], "date": row[2], "time": row[3],
                "status": row[4], "telegram_id": row[5], "name": row[6]}
    return None

def get_client_bookings(tg_id):
    """Получение актуальных записей клиента (для клиента) """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, date, time, service, status
        FROM appointments
        WHERE client_id = ? AND status NOT IN ('cancelled', 'done') 
        ORDER BY date, time
    """, (tg_id,))
    rows = cursor.fetchall()
    conn.close()
    
    return [{"id": r[0], "date": r[1], "time": r[2], "service": r[3], "status": r[4]} for r in rows]

def cancel_booking_by_id(booking_id):
    """Отменяет запись (меняет статус на 'cancelled')"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE appointments SET status = 'cancelled' WHERE id = ?",
        (booking_id,)
    )
    conn.commit()
    conn.close()

def get_booking_by_id(booking_id):
    """ПОЛУЧАЕТ ВСЕ ДАННЫЕ О ЗАПИСИ ПО ЕЁ ID (ID ЗАПИСИ)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.client_id, a.service, a.date, a.time, a.status, c.name
        FROM appointments a
        JOIN clients c ON a.client_id = c.telegram_id
        WHERE a.id = ?
    """, (booking_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "id": row[0],
            "client_id": row[1], # id клиента (тг id)
            "service": row[2], # услуга
            "date": row[3], # дата
            "time": row[4], # время
            "status": row[5], # статус
            "client_name": row[6]  # имя клиента
        }
    return None

def has_appointment_on_date(tg_id, date):
    """Проверяет, есть ли у клиента активная запись на указанную дату"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM appointments 
        WHERE client_id = ? AND date = ? AND status NOT IN ('cancelled', 'done')
    """, (tg_id, date))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def get_appointments_page(page=1, per_page=10):
    conn = get_connection()
    cursor = conn.cursor()
    
    offset = (page - 1) * per_page
    
    cursor.execute("""
        SELECT a.id, a.date, a.time, a.service, a.status, c.name, c.telegram_id, c.phone
        FROM appointments a
        JOIN clients c ON a.client_id = c.telegram_id
        WHERE a.status != 'cancelled'
        ORDER BY a.date, a.time
        LIMIT ? OFFSET ?
    """, (per_page, offset))
    
    rows = cursor.fetchall()
    
    cursor.execute("SELECT COUNT(*) FROM appointments")
    total = cursor.fetchone()[0]
    
    conn.close()
    
    appointments = [{"id": r[0], "date": r[1], "time": r[2], "service": r[3], "status": r[4], 
                     "name": r[5], "telegram_id": r[6], "phone": r[7]} for r in rows]
    return appointments, total

def get_client_by_tg_id(tg_id):
    """
    Возвращает данные клиента по telegram_id
    для будущей проверки в БД и предложения оставить текущие данные
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, phone FROM clients WHERE telegram_id = ?", (tg_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {"name": row[0], "phone": row[1]}
    return None

# ================ НАСТРОЙКА СЛОТОВ (РАБОЧИХ ЧАСОВ И ДНЕЙ) ДЛЯ АДМИНА============
def get_setting(key, default=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key, value):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value)
    )
    conn.commit()
    conn.close()

# ================= РАБОТА СО СЛОТАМИ (РАБОЧИЕ ЧАСЫ) (ДОБАВЛЕНИЕ/УДАЛЕНИЕ) ==============
def add_work_slot(date, time):
    """Принимает дату и время. Добавляет рабочий слот"""
    conn = get_connection()
    cursor = conn.cursor()
    try: # Попытка добавить дату и время
        cursor.execute(
            "INSERT INTO work_slots (date, time) VALUES (?, ?)", 
            (date, time) # Если дубля нет, добавляем дату и время
        )
        conn.commit() # Сохраняем изменения
    except sqlite3.IntegrityError: # Если дубль есть ловим ошибку и дальше ничего
        pass  # уже есть
    finally:
        conn.close()

def delete_work_slot(date, time):
    """Удаляем слот"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM work_slots WHERE date = ? AND time = ?",
        (date, time)
    )
    conn.commit() # Сохраняем изменения
    conn.close()

def get_available_dates():
    """Возвращает уникальные даты"""
    conn = get_connection()
    cursor = conn.cursor()
    # DISTINCT отсекает дубли, берём колонку date из таблица work_slots сортируем по дате (по возрастанию)
    cursor.execute("SELECT DISTINCT date FROM work_slots ORDER BY date")
    rows = cursor.fetchall() # Возвращает список кортежей
    conn.close() # Отключаемся от БД
    return [r[0] for r in rows] # Распаковываем каждый кортеж (доставая первое и единственное значение)

def get_available_times(date):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT time FROM work_slots WHERE date = ? ORDER BY time", (date,))
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]


# ========== ЭКСПОРТ / УДАЛЕНИЕ EXCEL===============================
def get_all_appointments_for_export():
    """ВОЗВРАЩАЕТ СПИСОК ВСЕХ ЗАПИСЕЙ ДЛЯ ЭКСПОРТА """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.date, a.time, a.service, a.status, c.name, c.phone
        FROM appointments a
        JOIN clients c ON a.client_id = c.telegram_id
        WHERE a.status != 'cancelled'
        ORDER BY a.date, a.time
    """)
    rows = cursor.fetchall() #ЗАБИРАЕТ РЕЗУЛЬТАТЫ ПОИСКА В ВИДЕ СПИСКА КОРТЕЖЕЙ
    conn.close()
    return rows # Передаёт данные в обработчик /export

def delete_expired_appointments():
    """УДАЛЯЕТ ПРОШЕДШИЕ ЗАПИСИ ВОЗВРАЩАЕТ ОБЩЕЕЕ КОЛИЧЕСТВО УДАЛЁННЫХ ЗАПИСЕЙ"""
    conn = get_connection()
    cursor = conn.cursor()
    
    today = datetime.now().strftime("%d.%m") # ГРАНИЦА ДАТЫ
    now_time = datetime.now().strftime("%H:%M") # ГРАНИЦА ВРЕМЕНИ
    # ВСЁ ЧТО МЕНЬШЕ TODAY УДАЛЯЕМ (СРАВНЕНИЕ ИДЁТ ПО-СИМВОЛЬНО)
    cursor.execute("DELETE FROM appointments WHERE date < ?", (today,)) 
    deleted1 = cursor.rowcount # КОЛИЧЕСТВО СТРОК ЗАТРОНУТЫХ ПОСЛЕДНИМ SQL ЗАПРОСОМ
    # ВСЁ ЧТО РАВНО TODAY, НО МЕНЬШЕ NOW_TIME УДАЛЯЕМ
    cursor.execute("DELETE FROM appointments WHERE date = ? AND time < ?", (today, now_time))
    deleted2 = cursor.rowcount # КОЛИЧЕСТВО СТРОК ЗАТРОНУТЫХ ПОСЛЕДНИМ SQL ЗАПРОСОМ
    conn.commit()
    
    conn.close()
    
    return deleted1 + deleted2 # ВОЗВРАЩАЕТ ЧИСЛО

# ======================================= НАПОМИНАЛКА ===========================================
def get_appointments_for_reminder(hours_before):
    """Возвращает записи, которые будут через hours_before часов"""
    conn = get_connection()
    cursor = conn.cursor()
    
    tz = pytz.timezone('Europe/Moscow')
    now = datetime.now(tz)
    remind_time = now + timedelta(hours=hours_before)
    
    target_date = remind_time.strftime("%d.%m")
    target_time = remind_time.strftime("%H:%M")
    
    reminded_col = "reminded_24h" if hours_before == 24 else "reminded_2h"
    
    cursor.execute(f"""
        SELECT a.id, a.client_id, a.service, a.date, a.time, c.name, c.telegram_id
        FROM appointments a
        JOIN clients c ON a.client_id = c.telegram_id
        WHERE a.date = ? AND a.time = ? AND a.status = 'confirmed' AND {reminded_col} = 0
    """, (target_date, target_time))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [{"id": r[0], "client_id": r[1], "service": r[2], "date": r[3], "time": r[4], "name": r[5], "telegram_id": r[6]} for r in rows]

def mark_reminder_sent(appointment_id, hours_before):
    """Помечает, что напоминание отправлено"""
    conn = get_connection()
    cursor = conn.cursor()
    reminded_col = "reminded_24h" if hours_before == 24 else "reminded_2h"
    cursor.execute(f"UPDATE appointments SET {reminded_col} = 1 WHERE id = ?", (appointment_id,))
    conn.commit()
    conn.close()

def get_appointments_for_confirmation():
    """Возвращает записи через 2 часа, которые ещё не подтверждены клиентом"""
    from datetime import datetime, timedelta
    conn = get_connection()
    cursor = conn.cursor()
    
    tz = pytz.timezone('Europe/Moscow')
    now = datetime.now(tz)
    remind_time = now + timedelta(hours=2)
    
    target_date = remind_time.strftime("%d.%m")
    target_time = remind_time.strftime("%H:%M")
    
    cursor.execute("""
        SELECT a.id, a.client_id, a.service, a.date, a.time, c.name, c.telegram_id
        FROM appointments a
        JOIN clients c ON a.client_id = c.telegram_id
        WHERE a.date = ? AND a.time = ? AND a.status = 'confirmed' AND a.confirmed_2h = 0
    """, (target_date, target_time))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [{"id": r[0], "client_id": r[1], "service": r[2], "date": r[3], "time": r[4], "name": r[5], "telegram_id": r[6]} for r in rows]

def set_confirmed_2h(appointment_id):
    """Помечает, что клиент подтвердил запись за 2 часа"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE appointments SET confirmed_2h = 1 WHERE id = ?", (appointment_id,))
    conn.commit()
    conn.close()