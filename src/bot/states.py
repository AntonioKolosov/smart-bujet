from aiogram.fsm.state import State, StatesGroup

class OnboardingStates(StatesGroup):
    choosing_mode = State()
    uploading_statements = State()
    waiting_for_currency = State()
    waiting_for_initial_balance = State()
