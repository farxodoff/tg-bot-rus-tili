from aiogram.fsm.state import State, StatesGroup


class ModeState(StatesGroup):
    """Foydalanuvchi tanlagan o'rganish rejimi (chat tipidagi)."""
    chatting = State()


class QuizState(StatesGroup):
    """Test rejimi uchun bosqichlar."""
    choosing_topic = State()
    answering = State()


class SettingsState(StatesGroup):
    main = State()


# FSM data kalitlari
KEY_MODE = "mode"
KEY_QUIZ_QUESTIONS = "quiz_questions"
KEY_QUIZ_INDEX = "quiz_index"
KEY_QUIZ_SCORE = "quiz_score"
KEY_QUIZ_TOPIC = "quiz_topic"
