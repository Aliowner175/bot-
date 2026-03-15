import asyncio
import sqlite3
import random
import string
from datetime import datetime

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

TOKEN = "8737581487:AAG8QyeCTVBUg1bmrntzNMN7BmDgWfM0QT0"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# =========================
# DATABASE
# =========================
db = sqlite3.connect("bot_data.db", check_same_thread=False)
db.row_factory = sqlite3.Row
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    surname TEXT,
    phone TEXT,
    username TEXT,
    role TEXT DEFAULT 'student',
    certificate TEXT,
    teacher_id INTEGER,
    join_code TEXT,
    created_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    q_index INTEGER NOT NULL,
    answer TEXT NOT NULL,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(code, q_index)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS test_meta (
    code TEXT PRIMARY KEY,
    created_by INTEGER NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    created_at TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    score INTEGER NOT NULL,
    total INTEGER NOT NULL,
    created_at TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS student_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    q_index INTEGER NOT NULL,
    chosen_answer TEXT NOT NULL,
    correct_answer TEXT NOT NULL,
    is_correct INTEGER NOT NULL,
    created_at TEXT NOT NULL
)
""")

db.commit()

# =========================
# STATES
# =========================
class RegisterState(StatesGroup):
    waiting_name = State()
    waiting_surname = State()
    waiting_phone = State()
    waiting_role = State()


class CertificateState(StatesGroup):
    waiting_certificate = State()


class LinkTeacherState(StatesGroup):
    waiting_join_code = State()


class CreateTestState(StatesGroup):
    waiting_code = State()
    waiting_count = State()
    waiting_start_time = State()
    waiting_end_time = State()
    choosing_answers = State()


class SolveState(StatesGroup):
    waiting_code = State()
    solving = State()


class SettingsState(StatesGroup):
    waiting_name = State()


# =========================
# HELPERS
# =========================
def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_dt(text: str):
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def generate_join_code(length=6):
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def role_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Men o‘qituvchiman")],
            [KeyboardButton(text="Men o‘quvchiman")],
            [KeyboardButton(text="Ortga")]
        ],
        resize_keyboard=True
    )


def teacher_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Test yaratish")],
            [KeyboardButton(text="Umumiy natijalar"), KeyboardButton(text="Profil")],
            [KeyboardButton(text="Natijalar"), KeyboardButton(text="Sozlamalar")],
            [KeyboardButton(text="Rolni almashtirish")]
        ],
        resize_keyboard=True
    )


def student_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Test yechish"), KeyboardButton(text="Ustozga ulanish")],
            [KeyboardButton(text="Profil"), KeyboardButton(text="Natijalar")],
            [KeyboardButton(text="Sozlamalar"), KeyboardButton(text="Rolni almashtirish")]
        ],
        resize_keyboard=True
    )


def settings_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Ismni o‘zgartirish")],
            [KeyboardButton(text="Bosh menyu")]
        ],
        resize_keyboard=True
    )


def main_menu(user_id: int):
    return teacher_menu() if is_teacher(user_id) else student_menu()


def teacher_answer_keyboard(code: str, q_index: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="A", callback_data=f"tans:{code}:{q_index}:A"),
            InlineKeyboardButton(text="B", callback_data=f"tans:{code}:{q_index}:B"),
            InlineKeyboardButton(text="C", callback_data=f"tans:{code}:{q_index}:C"),
            InlineKeyboardButton(text="D", callback_data=f"tans:{code}:{q_index}:D"),
        ]]
    )


def student_answer_keyboard(code: str, q_index: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="A", callback_data=f"sans:{code}:{q_index}:A"),
            InlineKeyboardButton(text="B", callback_data=f"sans:{code}:{q_index}:B"),
            InlineKeyboardButton(text="C", callback_data=f"sans:{code}:{q_index}:C"),
            InlineKeyboardButton(text="D", callback_data=f"sans:{code}:{q_index}:D"),
        ]]
    )


def user_exists(user_id: int) -> bool:
    row = cursor.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,)).fetchone()
    return row is not None


def get_user(user_id: int):
    return cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()


def is_teacher(user_id: int) -> bool:
    row = cursor.execute("SELECT role FROM users WHERE user_id=?", (user_id,)).fetchone()
    return bool(row and row["role"] == "teacher")


def set_role(user_id: int, role: str):
    cursor.execute("UPDATE users SET role=? WHERE user_id=?", (role, user_id))
    db.commit()


def get_display_name(user_id: int) -> str:
    u = get_user(user_id)
    if not u:
        return "Noma'lum"
    full = f"{u['name'] or ''} {u['surname'] or ''}".strip()
    return full if full else "Noma'lum"


def ensure_teacher_join_code(user_id: int) -> str:
    row = cursor.execute("SELECT join_code FROM users WHERE user_id=?", (user_id,)).fetchone()
    if row and row["join_code"]:
        return row["join_code"]

    while True:
        code = generate_join_code()
        exists = cursor.execute("SELECT user_id FROM users WHERE join_code=?", (code,)).fetchone()
        if not exists:
            cursor.execute("UPDATE users SET join_code=? WHERE user_id=?", (code, user_id))
            db.commit()
            return code


def get_student_teacher_id(user_id: int):
    row = cursor.execute("SELECT teacher_id FROM users WHERE user_id=?", (user_id,)).fetchone()
    return row["teacher_id"] if row else None


def set_student_teacher(student_id: int, teacher_id: int):
    cursor.execute("UPDATE users SET teacher_id=? WHERE user_id=?", (teacher_id, student_id))
    db.commit()


def get_user_by_join_code(join_code: str):
    return cursor.execute("SELECT * FROM users WHERE join_code=?", (join_code,)).fetchone()


def save_teacher_certificate(user_id: int, file_id: str | None):
    cursor.execute("UPDATE users SET certificate=? WHERE user_id=?", (file_id, user_id))
    db.commit()


def clear_test(code: str):
    cursor.execute("DELETE FROM tests WHERE code=?", (code,))
    cursor.execute("DELETE FROM test_meta WHERE code=?", (code,))
    db.commit()


def save_test_meta(code: str, created_by: int, start_time: str, end_time: str):
    cursor.execute("""
        INSERT OR REPLACE INTO test_meta(code, created_by, start_time, end_time, created_at)
        VALUES(?,?,?,?,?)
    """, (code, created_by, start_time, end_time, now_str()))
    db.commit()


def get_test_meta(code: str):
    return cursor.execute("SELECT * FROM test_meta WHERE code=?", (code,)).fetchone()


def save_test_answer(code: str, q_index: int, answer: str, created_by: int):
    cursor.execute("""
        INSERT OR REPLACE INTO tests(code, q_index, answer, created_by, created_at)
        VALUES(?,?,?,?,?)
    """, (code, q_index, answer, created_by, now_str()))
    db.commit()


def count_questions(code: str) -> int:
    row = cursor.execute("SELECT COUNT(*) AS cnt FROM tests WHERE code=?", (code,)).fetchone()
    return row["cnt"] if row else 0


def get_correct_answer(code: str, q_index: int):
    row = cursor.execute(
        "SELECT answer FROM tests WHERE code=? AND q_index=?",
        (code, q_index)
    ).fetchone()
    return row["answer"] if row else None


def save_result(user_id: int, code: str, score: int, total: int):
    cursor.execute("""
        INSERT INTO results(user_id, code, score, total, created_at)
        VALUES(?,?,?,?,?)
    """, (user_id, code, score, total, now_str()))
    db.commit()


def clear_student_answers(user_id: int, code: str):
    cursor.execute("DELETE FROM student_answers WHERE user_id=? AND code=?", (user_id, code))
    db.commit()


def save_student_answer(user_id: int, code: str, q_index: int, chosen_answer: str, correct_answer: str, is_correct: int):
    cursor.execute("""
        INSERT INTO student_answers(
            user_id, code, q_index, chosen_answer, correct_answer, is_correct, created_at
        )
        VALUES(?,?,?,?,?,?,?)
    """, (user_id, code, q_index, chosen_answer, correct_answer, is_correct, now_str()))
    db.commit()


def get_student_answer_details(user_id: int, code: str):
    return cursor.execute("""
        SELECT q_index, chosen_answer, correct_answer, is_correct
        FROM student_answers
        WHERE user_id=? AND code=?
        ORDER BY q_index ASC
    """, (user_id, code)).fetchall()


def count_created_tests(user_id: int) -> int:
    row = cursor.execute(
        "SELECT COUNT(*) AS cnt FROM test_meta WHERE created_by=?",
        (user_id,)
    ).fetchone()
    return row["cnt"] if row else 0


def count_solved_tests(user_id: int) -> int:
    row = cursor.execute(
        "SELECT COUNT(*) AS cnt FROM results WHERE user_id=?",
        (user_id,)
    ).fetchone()
    return row["cnt"] if row else 0


def count_teacher_students(user_id: int) -> int:
    row = cursor.execute(
        "SELECT COUNT(*) AS cnt FROM users WHERE teacher_id=?",
        (user_id,)
    ).fetchone()
    return row["cnt"] if row else 0


def get_stats(user_id: int):
    row = cursor.execute("""
        SELECT
            COUNT(*) AS attempts,
            COALESCE(SUM(score), 0) AS total_correct,
            COALESCE(SUM(total), 0) AS total_questions,
            COALESCE(MAX(score), 0) AS best_score
        FROM results
        WHERE user_id=?
    """, (user_id,)).fetchone()
    return row


def get_last_results(user_id: int, limit=10):
    return cursor.execute("""
        SELECT code, score, total, created_at
        FROM results
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT ?
    """, (user_id, limit)).fetchall()


def get_teacher_results(teacher_id: int, limit=100):
    return cursor.execute("""
        SELECT
            r.user_id,
            r.code,
            r.score,
            r.total,
            r.created_at,
            u.name,
            u.surname,
            u.username,
            u.phone
        FROM results r
        JOIN test_meta tm ON r.code = tm.code
        LEFT JOIN users u ON r.user_id = u.user_id
        WHERE tm.created_by = ?
        ORDER BY r.id DESC
        LIMIT ?
    """, (teacher_id, limit)).fetchall()


async def safe_delete_message(message: types.Message):
    try:
        await message.delete()
    except Exception:
        pass


async def temp_bot_message(chat_id: int, text: str, reply_markup=None, delay: int = 6):
    sent = await bot.send_message(chat_id, text, reply_markup=reply_markup)
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, sent.message_id)
    except Exception:
        pass


async def send_main_menu(chat_id: int, user_id: int, text: str = "Bosh menyu:"):
    await bot.send_message(chat_id, text, reply_markup=main_menu(user_id))


# =========================
# START / REGISTER
# =========================
@dp.message(CommandStart())
async def start_handler(msg: types.Message, state: FSMContext):
    if user_exists(msg.from_user.id):
        await state.clear()
        await send_main_menu(msg.chat.id, msg.from_user.id, "Bosh menyu:")
        return

    await state.set_state(RegisterState.waiting_name)
    await temp_bot_message(msg.chat.id, "Ismingizni kiriting:", delay=30)


@dp.message(RegisterState.waiting_name)
async def register_name(msg: types.Message, state: FSMContext):
    name = msg.text.strip()
    if len(name) < 2:
        await temp_bot_message(msg.chat.id, "Ism juda qisqa.", delay=4)
        return

    await state.update_data(name=name)
    await safe_delete_message(msg)
    await state.set_state(RegisterState.waiting_surname)
    await temp_bot_message(msg.chat.id, "Familiyangizni kiriting:", delay=30)


@dp.message(RegisterState.waiting_surname)
async def register_surname(msg: types.Message, state: FSMContext):
    surname = msg.text.strip()
    if len(surname) < 2:
        await temp_bot_message(msg.chat.id, "Familiya juda qisqa.", delay=4)
        return

    await state.update_data(surname=surname)
    await safe_delete_message(msg)
    await state.set_state(RegisterState.waiting_phone)
    await temp_bot_message(msg.chat.id, "Telefon raqamingizni kiriting:", delay=30)


@dp.message(RegisterState.waiting_phone)
async def register_phone(msg: types.Message, state: FSMContext):
    phone = msg.text.strip()
    data = await state.get_data()

    cursor.execute("""
        INSERT INTO users(
            user_id, name, surname, phone, username, role,
            certificate, teacher_id, join_code, created_at
        )
        VALUES(?,?,?,?,?,?,?,?,?,?)
    """, (
        msg.from_user.id,
        data["name"],
        data["surname"],
        phone,
        msg.from_user.username,
        "student",
        None,
        None,
        None,
        now_str()
    ))
    db.commit()

    await safe_delete_message(msg)
    await state.set_state(RegisterState.waiting_role)
    await temp_bot_message(
        msg.chat.id,
        "Registratsiya tugadi.\n\nRolingizni tanlang:",
        reply_markup=role_menu(),
        delay=30
    )


# =========================
# ROLE
# =========================
@dp.message(F.text == "Men o‘qituvchiman")
async def set_teacher_role(msg: types.Message, state: FSMContext):
    if not user_exists(msg.from_user.id):
        await temp_bot_message(msg.chat.id, "/start bosing.", delay=4)
        return

    set_role(msg.from_user.id, "teacher")
    join_code = ensure_teacher_join_code(msg.from_user.id)

    await state.set_state(CertificateState.waiting_certificate)
    await temp_bot_message(
        msg.chat.id,
        f"Siz o‘qituvchi bo‘ldingiz.\n\n"
        f"Ustoz kodingiz: {join_code}\n\n"
        f"Iltimos sertifikat rasmini yoki faylini yuboring:",
        delay=40
    )


@dp.message(CertificateState.waiting_certificate)
async def save_certificate(msg: types.Message, state: FSMContext):
    file_id = None

    if msg.photo:
        file_id = msg.photo[-1].file_id
    elif msg.document:
        file_id = msg.document.file_id
    else:
        await temp_bot_message(msg.chat.id, "Sertifikatni rasm yoki fayl ko‘rinishida yuboring.", delay=4)
        return

    save_teacher_certificate(msg.from_user.id, file_id)
    await state.clear()
    await safe_delete_message(msg)
    await temp_bot_message(msg.chat.id, "Sertifikat saqlandi ✅", delay=6)
    await send_main_menu(msg.chat.id, msg.from_user.id)


@dp.message(F.text == "Men o‘quvchiman")
async def set_student_role(msg: types.Message, state: FSMContext):
    if not user_exists(msg.from_user.id):
        await temp_bot_message(msg.chat.id, "/start bosing.", delay=4)
        return

    set_role(msg.from_user.id, "student")
    await state.clear()
    await temp_bot_message(msg.chat.id, "Siz o‘quvchi bo‘ldingiz.", delay=6)
    await send_main_menu(msg.chat.id, msg.from_user.id)


@dp.message(F.text == "Rolni almashtirish")
async def change_role(msg: types.Message, state: FSMContext):
    await state.clear()
    await temp_bot_message(msg.chat.id, "Yangi rolingizni tanlang:", reply_markup=role_menu(), delay=30)


@dp.message(F.text == "Ortga")
async def back_from_role(msg: types.Message, state: FSMContext):
    await state.clear()
    if user_exists(msg.from_user.id):
        await send_main_menu(msg.chat.id, msg.from_user.id, "Bosh menyu:")
    else:
        await temp_bot_message(msg.chat.id, "Rolingizni tanlang:", reply_markup=role_menu(), delay=20)


# =========================
# SETTINGS / PROFILE / RESULTS
# =========================
@dp.message(F.text == "Bosh menyu")
async def back_menu(msg: types.Message, state: FSMContext):
    await state.clear()
    await send_main_menu(msg.chat.id, msg.from_user.id, "Bosh menyu:")


@dp.message(F.text == "Sozlamalar")
async def settings_handler(msg: types.Message, state: FSMContext):
    await state.clear()
    await temp_bot_message(msg.chat.id, "Sozlamalar:", reply_markup=settings_menu(), delay=20)


@dp.message(F.text == "Ismni o‘zgartirish")
async def change_name_start(msg: types.Message, state: FSMContext):
    await state.set_state(SettingsState.waiting_name)
    await temp_bot_message(msg.chat.id, "Yangi ismingizni kiriting:", delay=30)


@dp.message(SettingsState.waiting_name)
async def save_new_name(msg: types.Message, state: FSMContext):
    name = msg.text.strip()
    if len(name) < 2:
        await temp_bot_message(msg.chat.id, "Ism juda qisqa.", delay=4)
        return

    cursor.execute("UPDATE users SET name=? WHERE user_id=?", (name, msg.from_user.id))
    db.commit()
    await safe_delete_message(msg)
    await state.clear()
    await temp_bot_message(msg.chat.id, "Ism yangilandi ✅", delay=6)
    await send_main_menu(msg.chat.id, msg.from_user.id)


@dp.message(F.text == "Profil")
async def profile_handler(msg: types.Message):
    u = get_user(msg.from_user.id)
    if not u:
        await temp_bot_message(msg.chat.id, "/start bosing.", delay=4)
        return

    stats = get_stats(msg.from_user.id)
    role = u["role"] or "student"

    if role == "teacher":
        text = (
            f"👤 Profil\n\n"
            f"Ism: {u['name']}\n"
            f"Familiya: {u['surname']}\n"
            f"Telefon: {u['phone']}\n"
            f"Username: @{u['username'] if u['username'] else 'yo‘q'}\n"
            f"Rol: O‘qituvchi\n"
            f"Ustoz kodi: {u['join_code']}\n"
            f"Sertifikat: {'bor' if u['certificate'] else 'yo‘q'}\n\n"
            f"📊 Statistika\n"
            f"Yaratgan testlar soni: {count_created_tests(msg.from_user.id)}\n"
            f"Biriktirilgan o‘quvchilar soni: {count_teacher_students(msg.from_user.id)}\n"
            f"Shaxsiy ishlangan testlar: {count_solved_tests(msg.from_user.id)}\n"
            f"Urinishlar: {stats['attempts']}\n"
            f"Jami to‘g‘ri: {stats['total_correct']}\n"
            f"Jami savollar: {stats['total_questions']}\n"
            f"Eng yaxshi natija: {stats['best_score']}"
        )
    else:
        teacher_name = get_display_name(u["teacher_id"]) if u["teacher_id"] else "Biriktirilmagan"
        text = (
            f"👤 Profil\n\n"
            f"Ism: {u['name']}\n"
            f"Familiya: {u['surname']}\n"
            f"Telefon: {u['phone']}\n"
            f"Username: @{u['username'] if u['username'] else 'yo‘q'}\n"
            f"Rol: O‘quvchi\n"
            f"Biriktirilgan ustoz: {teacher_name}\n\n"
            f"📊 Statistika\n"
            f"Yechgan testlar soni: {count_solved_tests(msg.from_user.id)}\n"
            f"Urinishlar: {stats['attempts']}\n"
            f"Jami to‘g‘ri: {stats['total_correct']}\n"
            f"Jami savollar: {stats['total_questions']}\n"
            f"Eng yaxshi natija: {stats['best_score']}"
        )

    await temp_bot_message(msg.chat.id, text, delay=20)
    await send_main_menu(msg.chat.id, msg.from_user.id)


@dp.message(F.text == "Natijalar")
async def results_handler(msg: types.Message):
    rows = get_last_results(msg.from_user.id)
    if not rows:
        await temp_bot_message(msg.chat.id, "Sizda hali natijalar yo‘q.", delay=6)
        await send_main_menu(msg.chat.id, msg.from_user.id)
        return

    text = "📑 Oxirgi natijalar:\n\n"
    for i, row in enumerate(rows, start=1):
        text += (
            f"{i}) Kod: {row['code']}\n"
            f"Natija: {row['score']}/{row['total']}\n"
            f"Sana: {row['created_at']}\n\n"
        )

    await temp_bot_message(msg.chat.id, text, delay=20)
    await send_main_menu(msg.chat.id, msg.from_user.id)


@dp.message(F.text == "Umumiy natijalar")
async def teacher_results_handler(msg: types.Message):
    if not is_teacher(msg.from_user.id):
        await temp_bot_message(msg.chat.id, "Bu bo‘lim faqat o‘qituvchi uchun.", delay=6)
        await send_main_menu(msg.chat.id, msg.from_user.id)
        return

    rows = get_teacher_results(msg.from_user.id)
    if not rows:
        await temp_bot_message(msg.chat.id, "Siz yaratgan testlar bo‘yicha hali natijalar yo‘q.", delay=6)
        await send_main_menu(msg.chat.id, msg.from_user.id)
        return

    text = "📊 Umumiy natijalar:\n\n"

    for i, row in enumerate(rows, start=1):
        student_name = f"{row['name'] or ''} {row['surname'] or ''}".strip() or "Noma'lum"
        username = f"@{row['username']}" if row["username"] else "username yo‘q"
        phone = row["phone"] if row["phone"] else "telefon yo‘q"

        details = get_student_answer_details(row["user_id"], row["code"])

        correct_count = sum(1 for d in details if d["is_correct"] == 1)
        wrong_count = sum(1 for d in details if d["is_correct"] == 0)

        detail_text = ""
        if details:
            for d in details:
                status = "✅ To‘g‘ri" if d["is_correct"] == 1 else "❌ Xato"
                detail_text += (
                    f"{d['q_index']}-savol: {status} | "
                    f"Belgilagan: {d['chosen_answer']} | "
                    f"To‘g‘ri javob: {d['correct_answer']}\n"
                )
        else:
            detail_text = "Savollar bo‘yicha ma’lumot topilmadi.\n"

        part = (
            f"{i}) {student_name}\n"
            f"{username}\n"
            f"Telefon: {phone}\n"
            f"Kod: {row['code']}\n"
            f"Natija: {row['score']}/{row['total']}\n"
            f"To‘g‘ri javoblar: {correct_count}\n"
            f"Xato javoblar: {wrong_count}\n"
            f"Sana: {row['created_at']}\n"
            f"--- Savollar bo‘yicha ---\n"
            f"{detail_text}\n"
        )

        if len(text) + len(part) > 3500:
            await temp_bot_message(msg.chat.id, text, delay=25)
            text = ""

        text += part

    if text:
        await temp_bot_message(msg.chat.id, text, delay=25)

    await send_main_menu(msg.chat.id, msg.from_user.id)


# =========================
# LINK TEACHER
# =========================
@dp.message(F.text == "Ustozga ulanish")
async def link_teacher_start(msg: types.Message, state: FSMContext):
    if is_teacher(msg.from_user.id):
        await temp_bot_message(msg.chat.id, "Bu bo‘lim faqat o‘quvchilar uchun.", delay=4)
        return

    await state.set_state(LinkTeacherState.waiting_join_code)
    await temp_bot_message(msg.chat.id, "Ustoz kodini yuboring:", delay=30)


@dp.message(LinkTeacherState.waiting_join_code)
async def link_teacher_save(msg: types.Message, state: FSMContext):
    join_code = msg.text.strip().upper()

    teacher = get_user_by_join_code(join_code)
    if not teacher:
        await temp_bot_message(msg.chat.id, "Bunday ustoz kodi topilmadi.", delay=4)
        return

    if teacher["role"] != "teacher":
        await temp_bot_message(msg.chat.id, "Bu kod o‘qituvchiga tegishli emas.", delay=4)
        return

    set_student_teacher(msg.from_user.id, teacher["user_id"])
    await safe_delete_message(msg)
    await state.clear()
    await temp_bot_message(
        msg.chat.id,
        f"Siz {get_display_name(teacher['user_id'])} ustozga biriktirildingiz ✅",
        delay=6
    )
    await send_main_menu(msg.chat.id, msg.from_user.id)


# =========================
# CREATE TEST
# =========================
@dp.message(F.text == "Test yaratish")
async def create_test_start(msg: types.Message, state: FSMContext):
    if not is_teacher(msg.from_user.id):
        await temp_bot_message(msg.chat.id, "Bu bo‘lim faqat o‘qituvchi uchun.", delay=6)
        await send_main_menu(msg.chat.id, msg.from_user.id)
        return

    await state.clear()
    await state.set_state(CreateTestState.waiting_code)
    await temp_bot_message(msg.chat.id, "Test kodini kiriting:", delay=30)


@dp.message(CreateTestState.waiting_code)
async def create_test_code(msg: types.Message, state: FSMContext):
    code = msg.text.strip()

    if len(code) < 2:
        await temp_bot_message(msg.chat.id, "Kod juda qisqa.", delay=4)
        return

    await state.update_data(code=code)
    await safe_delete_message(msg)
    await state.set_state(CreateTestState.waiting_count)
    await temp_bot_message(msg.chat.id, "Savollar sonini kiriting:", delay=30)


@dp.message(CreateTestState.waiting_count)
async def create_test_count(msg: types.Message, state: FSMContext):
    text = msg.text.strip()

    if not text.isdigit():
        await temp_bot_message(msg.chat.id, "Faqat son yuboring.", delay=4)
        return

    count = int(text)
    if count <= 0:
        await temp_bot_message(msg.chat.id, "Savollar soni 1 tadan kam bo‘lmasin.", delay=4)
        return

    await state.update_data(count=count)
    await safe_delete_message(msg)
    await state.set_state(CreateTestState.waiting_start_time)
    await temp_bot_message(msg.chat.id, "Boshlanish vaqtini kiriting.\nFormat: YYYY-MM-DD HH:MM:SS", delay=30)


@dp.message(CreateTestState.waiting_start_time)
async def create_test_start_time(msg: types.Message, state: FSMContext):
    start_time = msg.text.strip()
    start_dt = parse_dt(start_time)

    if not start_dt:
        await temp_bot_message(msg.chat.id, "Vaqt noto‘g‘ri formatda.\nMasalan: 2026-03-11 18:00:00", delay=4)
        return

    await state.update_data(start_time=start_time)
    await safe_delete_message(msg)
    await state.set_state(CreateTestState.waiting_end_time)
    await temp_bot_message(msg.chat.id, "Tugash vaqtini kiriting.\nFormat: YYYY-MM-DD HH:MM:SS", delay=30)


@dp.message(CreateTestState.waiting_end_time)
async def create_test_end_time(msg: types.Message, state: FSMContext):
    end_time = msg.text.strip()
    end_dt = parse_dt(end_time)

    if not end_dt:
        await temp_bot_message(msg.chat.id, "Vaqt noto‘g‘ri formatda.\nMasalan: 2026-03-11 19:00:00", delay=4)
        return

    data = await state.get_data()
    start_dt = parse_dt(data["start_time"])

    if not start_dt:
        await temp_bot_message(msg.chat.id, "Boshlanish vaqti topilmadi. Qaytadan boshlang.", delay=4)
        await state.clear()
        await send_main_menu(msg.chat.id, msg.from_user.id)
        return

    if end_dt <= start_dt:
        await temp_bot_message(msg.chat.id, "Tugash vaqti boshlanish vaqtidan katta bo‘lishi kerak.", delay=4)
        return

    code = data["code"]
    count = data["count"]

    clear_test(code)
    save_test_meta(code, msg.from_user.id, data["start_time"], end_time)

    await state.update_data(current_q=1)
    await safe_delete_message(msg)
    await state.set_state(CreateTestState.choosing_answers)

    await msg.answer(
        f"Test kodi: {code}\n"
        f"Jami savollar: {count}\n"
        f"Boshlanish: {data['start_time']}\n"
        f"Tugash: {end_time}\n\n"
        f"1-savol uchun javobni belgilang:",
        reply_markup=teacher_answer_keyboard(code, 1)
    )


@dp.callback_query(F.data.startswith("tans:"))
async def teacher_choose_answer(call: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state != CreateTestState.choosing_answers.state:
        await call.answer("Bu tugma hozir faol emas", show_alert=True)
        return

    try:
        _, code, q_str, answer = call.data.split(":")
        q_index = int(q_str)
    except Exception:
        await call.answer("Xatolik", show_alert=True)
        return

    data = await state.get_data()
    current_q = data.get("current_q")
    count = data.get("count")
    saved_code = data.get("code")

    if not current_q or not count or not saved_code:
        await call.answer("Jarayon topilmadi", show_alert=True)
        await state.clear()
        await send_main_menu(call.message.chat.id, call.from_user.id)
        return

    if saved_code != code or current_q != q_index:
        await call.answer("Eski yoki noto‘g‘ri tugma", show_alert=True)
        return

    save_test_answer(code, q_index, answer, call.from_user.id)
    next_q = q_index + 1

    await call.answer("Saqlandi")

    if next_q > count:
        await state.clear()
        try:
            await call.message.edit_text(f"✅ Test saqlandi!\n\nKod: {code}\nSavollar soni: {count}")
            await asyncio.sleep(5)
            await safe_delete_message(call.message)
        except Exception:
            pass

        await send_main_menu(call.message.chat.id, call.from_user.id)
        return

    await state.update_data(current_q=next_q)

    try:
        await call.message.edit_text(
            f"{next_q}-savol uchun javobni belgilang:",
            reply_markup=teacher_answer_keyboard(code, next_q)
        )
    except Exception:
        pass


# =========================
# SOLVE TEST
# =========================
@dp.message(F.text == "Test yechish")
async def solve_test_start(msg: types.Message, state: FSMContext):
    if is_teacher(msg.from_user.id):
        await temp_bot_message(msg.chat.id, "Bu bo‘lim o‘quvchilar uchun.", delay=6)
        await send_main_menu(msg.chat.id, msg.from_user.id)
        return

    await state.clear()
    await state.set_state(SolveState.waiting_code)
    await temp_bot_message(msg.chat.id, "Test kodini yuboring:", delay=30)


@dp.message(SolveState.waiting_code)
async def solve_test_code(msg: types.Message, state: FSMContext):
    code = msg.text.strip()

    total = count_questions(code)
    if total == 0:
        await temp_bot_message(msg.chat.id, "Bu kod bo‘yicha test topilmadi.", delay=4)
        return

    meta = get_test_meta(code)
    if not meta:
        await temp_bot_message(msg.chat.id, "Bu test uchun vaqt ma’lumoti topilmadi.", delay=4)
        return

    teacher_id = get_student_teacher_id(msg.from_user.id)
    if not teacher_id:
        await temp_bot_message(
            msg.chat.id,
            "Siz hali ustozga biriktirilmagansiz. Avval 'Ustozga ulanish' bo‘limidan kod kiriting.",
            delay=6
        )
        return

    if meta["created_by"] != teacher_id:
        await temp_bot_message(msg.chat.id, "Bu test sizning ustozingizga tegishli emas.", delay=4)
        return

    now_dt = datetime.now()
    start_dt = parse_dt(meta["start_time"])
    end_dt = parse_dt(meta["end_time"])

    if not start_dt or not end_dt:
        await temp_bot_message(msg.chat.id, "Test vaqti noto‘g‘ri saqlangan.", delay=4)
        return

    if now_dt < start_dt:
        await temp_bot_message(msg.chat.id, f"Bu test hali boshlanmagan.\nBoshlanish: {meta['start_time']}", delay=6)
        return

    if now_dt > end_dt:
        await temp_bot_message(msg.chat.id, f"Bu test vaqti tugagan.\nTugash: {meta['end_time']}", delay=6)
        return

    clear_student_answers(msg.from_user.id, code)

    await state.update_data(code=code, current_q=1, score=0, total=total)
    await safe_delete_message(msg)
    await state.set_state(SolveState.solving)

    await msg.answer(
        f"Test boshlandi.\nTugash vaqti: {meta['end_time']}\n\n1-savol:",
        reply_markup=student_answer_keyboard(code, 1)
    )


@dp.callback_query(F.data.startswith("sans:"))
async def student_solve_answer(call: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state != SolveState.solving.state:
        await call.answer("Bu tugma hozir faol emas", show_alert=True)
        return

    try:
        _, code, q_str, chosen = call.data.split(":")
        q_index = int(q_str)
    except Exception:
        await call.answer("Xatolik", show_alert=True)
        return

    data = await state.get_data()
    current_q = data.get("current_q")
    score = data.get("score", 0)
    total = data.get("total")
    saved_code = data.get("code")

    if not current_q or not total or not saved_code:
        await call.answer("Jarayon topilmadi", show_alert=True)
        await state.clear()
        await send_main_menu(call.message.chat.id, call.from_user.id)
        return

    if saved_code != code or current_q != q_index:
        await call.answer("Eski yoki noto‘g‘ri tugma", show_alert=True)
        return

    meta = get_test_meta(code)
    if not meta:
        await call.answer("Vaqt ma’lumoti topilmadi", show_alert=True)
        await state.clear()
        await send_main_menu(call.message.chat.id, call.from_user.id)
        return

    end_dt = parse_dt(meta["end_time"])
    if not end_dt:
        await call.answer("Test tugash vaqti noto‘g‘ri", show_alert=True)
        await state.clear()
        await send_main_menu(call.message.chat.id, call.from_user.id)
        return

    if datetime.now() > end_dt:
        save_result(call.from_user.id, code, score, total)
        await state.clear()
        try:
            await call.message.edit_text("✅ Test saqlandi!")
            await asyncio.sleep(5)
            await safe_delete_message(call.message)
        except Exception:
            pass
        await call.answer()
        await send_main_menu(call.message.chat.id, call.from_user.id)
        return

    correct = get_correct_answer(code, q_index)
    if not correct:
        await call.answer("Savol topilmadi", show_alert=True)
        await state.clear()
        await send_main_menu(call.message.chat.id, call.from_user.id)
        return

    is_correct = 1 if chosen == correct else 0
    if is_correct:
        score += 1

    save_student_answer(
        call.from_user.id,
        code,
        q_index,
        chosen,
        correct,
        is_correct
    )

    await call.answer("Javob qabul qilindi ✅")

    next_q = q_index + 1

    if next_q > total:
        save_result(call.from_user.id, code, score, total)
        await state.clear()
        try:
            await call.message.edit_text("✅ Test saqlandi!")
            await asyncio.sleep(5)
            await safe_delete_message(call.message)
        except Exception:
            pass

        await send_main_menu(call.message.chat.id, call.from_user.id)
        return

    await state.update_data(current_q=next_q, score=score)

    try:
        await call.message.edit_text(
            f"{next_q}-savol:",
            reply_markup=student_answer_keyboard(code, next_q)
        )
    except Exception:
        pass


# =========================
# FALLBACK
# =========================
@dp.message()
async def fallback_handler(msg: types.Message):
    if user_exists(msg.from_user.id):
        await send_main_menu(msg.chat.id, msg.from_user.id, "Menyudan tanlang:")
    else:
        await temp_bot_message(msg.chat.id, "/start bosing.", delay=4)


# =========================
# MAIN
# =========================
async def main():
    print("Bot ishga tushyapti...")
    await bot.delete_webhook(drop_pending_updates=True)
    print("Polling boshlandi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
