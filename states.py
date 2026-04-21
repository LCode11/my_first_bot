from aiogram.fsm.state import State, StatesGroup

class Booking(StatesGroup):
    waiting_for_service = State()
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_phone = State()
    waiting_for_name = State()
    waiting_for_name_choice = State()  # выбор: оставить имя или ввести новое
    waiting_for_phone_choice = State() # выбор: оставить телефон или ввести новый

class AddSlot(StatesGroup):
    waiting_for_date = State()
    waiting_for_time = State()