from aiogram.fsm.state import State, StatesGroup


class AdminAddWorkbook(StatesGroup):
    waiting_file = State()
    waiting_title = State()


class AdminDeleteWorkbook(StatesGroup):
    waiting_serial = State()


class AdminAddCurator(StatesGroup):
    waiting_telegram_id = State()
    waiting_name = State()


class AdminAddStudent(StatesGroup):
    waiting_telegram_id = State()
    waiting_name = State()
    waiting_curator = State()
    waiting_group = State()


class AdminGrantAccess(StatesGroup):
    waiting_telegram_id = State()


class AdminRevokeAccess(StatesGroup):
    waiting_telegram_id = State()


class AdminAddGroup(StatesGroup):
    waiting_title = State()
    waiting_curator = State()


class AdminAddChecklist(StatesGroup):
    waiting_file = State()
    waiting_title = State()


class AdminDeleteChecklist(StatesGroup):
    waiting_serial = State()


class SubmitWorkbook(StatesGroup):
    waiting_full_name = State()
    collecting_photos = State()


class CuratorAddStudent(StatesGroup):
    waiting_telegram_id = State()
    waiting_name = State()
    waiting_group = State()


class CuratorAddGroup(StatesGroup):
    waiting_title = State()


class CuratorCreateSlots(StatesGroup):
    waiting_date = State()
    waiting_start_time = State()
    waiting_end_time = State()
    waiting_duration = State()
    waiting_meet_link = State()


class StudentBookSlot(StatesGroup):
    waiting_full_name = State()
    choosing_slot = State()
