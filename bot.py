import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.enums import ParseMode

from database import Database

logging.basicConfig(level=logging.INFO)

# --- SOZLAMALAR ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "SIZNING_BOT_TOKENINGIZ")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "0").split(",") if x.strip()]

db = Database("kino_bot.db")
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def is_subscribed(user_id: int) -> bool:
    channels = await db.list_channels()
    if not channels:
        return True
    for _id, username in channels:
        try:
            member = await bot.get_chat_member(username, user_id)
            if member.status in ("left", "kicked"):
                return False
        except Exception:
            # Bot kanalga admin qilinmagan yoki username xato bo'lsa, o'tkazib yuboramiz
            continue
    return True


async def not_subscribed_channels(user_id: int):
    channels = await db.list_channels()
    result = []
    for _id, username in channels:
        try:
            member = await bot.get_chat_member(username, user_id)
            if member.status in ("left", "kicked"):
                result.append(username)
        except Exception:
            continue
    return result


# --- FSM HOLATLARI ---
class AdminStates(StatesGroup):
    waiting_movie_video = State()
    waiting_movie_delete_code = State()
    waiting_broadcast = State()
    waiting_ad = State()
    waiting_channel_add = State()


# --- ADMIN PANEL KLAVIATURASI ---
def admin_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
            InlineKeyboardButton(text="🎬 Kinolar", callback_data="admin_movies"),
        ],
        [
            InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_users"),
            InlineKeyboardButton(text="📢 Xabar yuborish", callback_data="admin_broadcast"),
        ],
        [
            InlineKeyboardButton(text="🔐 Kanallar", callback_data="admin_channels"),
            InlineKeyboardButton(text="📣 Reklama", callback_data="admin_ads"),
        ],
    ])


def back_button(target: str = "admin_back") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=target)]
    ])


def movies_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kino qo'shish", callback_data="movies_add")],
        [InlineKeyboardButton(text="🗑 Kino o'chirish", callback_data="movies_delete")],
        [InlineKeyboardButton(text="📋 Ro'yxat", callback_data="movies_list")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_back")],
    ])


def channels_menu(channels) -> InlineKeyboardMarkup:
    rows = []
    for cid, username in channels:
        rows.append([InlineKeyboardButton(text=f"❌ {username}", callback_data=f"channel_del_{cid}")])
    rows.append([InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="channel_add")])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# --- FOYDALANUVCHI BUYRUQLARI ---

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await db.add_user(message.from_user.id)
    await message.answer(
        "🎬 <b>Kino Qidiruv Botiga xush kelibsiz!</b>\n\n"
        "Kino kodini (raqamini) yuboring, men sizga kinoni topib beraman.\n\n"
        "Masalan: <code>123</code>"
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    text = "ℹ️ Kino kodini raqam shaklida yuboring (masalan: 45)."
    if is_admin(message.from_user.id):
        text += "\n\nAdmin panelni ochish uchun: /admin"
    await message.answer(text)


# --- ADMIN PANELNI OCHISH ---

@dp.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("🛠 <b>Admin panel</b>", reply_markup=admin_main_menu())


@dp.callback_query(F.data == "admin_back")
async def cb_admin_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🛠 <b>Admin panel</b>", reply_markup=admin_main_menu())
    await callback.answer()


# --- STATISTIKA ---

@dp.callback_query(F.data == "admin_stats")
async def cb_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    users_count = await db.count_users()
    today = await db.users_today()
    movies_count = await db.count_movies()
    requests_count = await db.count_requests()
    top = await db.top_movies()
    top_text = "\n".join(f"  {i+1}. {code} — {cnt} marta" for i, (code, cnt) in enumerate(top)) or "  Hozircha yo'q"

    text = (
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Foydalanuvchilar: {users_count}\n"
        f"🆕 Bugun qo'shilgan: {today}\n"
        f"🎞 Kinolar soni: {movies_count}\n"
        f"🔎 Jami so'rovlar: {requests_count}\n\n"
        f"🏆 <b>Top kinolar:</b>\n{top_text}"
    )
    await callback.message.edit_text(text, reply_markup=back_button())
    await callback.answer()


# --- FOYDALANUVCHILAR ---

@dp.callback_query(F.data == "admin_users")
async def cb_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    users_count = await db.count_users()
    today = await db.users_today()
    text = (
        f"👥 <b>Foydalanuvchilar</b>\n\n"
        f"Jami: {users_count}\n"
        f"Bugun qo'shilgan: {today}"
    )
    await callback.message.edit_text(text, reply_markup=back_button())
    await callback.answer()


# --- KINOLAR ---

@dp.callback_query(F.data == "admin_movies")
async def cb_movies(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("🎬 <b>Kinolar bo'limi</b>", reply_markup=movies_menu())
    await callback.answer()


@dp.callback_query(F.data == "movies_add")
async def cb_movies_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.waiting_movie_video)
    await callback.message.edit_text(
        "🎬 Video yuboring. Captionga kino raqamini yozing (masalan: <code>101</code>).",
        reply_markup=back_button("admin_movies"),
    )
    await callback.answer()


@dp.message(StateFilter(AdminStates.waiting_movie_video), F.video)
async def process_movie_video(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    caption = (message.caption or "").strip()
    if not caption.isdigit():
        await message.answer("⚠️ Captionga faqat raqam yozing. Qayta urinib ko'ring.")
        return

    code = caption
    file_id = message.video.file_id
    title = message.video.file_name or f"Kino {code}"

    exists = await db.get_movie(code)
    if exists:
        await db.update_movie(code, file_id, title)
        await message.answer(f"✅ <b>{code}</b> raqamli kino yangilandi.", reply_markup=admin_main_menu())
    else:
        await db.add_movie(code, file_id, title)
        await message.answer(f"✅ <b>{code}</b> raqamli kino bazaga qo'shildi.", reply_markup=admin_main_menu())
    await state.clear()


@dp.callback_query(F.data == "movies_delete")
async def cb_movies_delete(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.waiting_movie_delete_code)
    await callback.message.edit_text(
        "🗑 O'chirmoqchi bo'lgan kino raqamini yuboring.",
        reply_markup=back_button("admin_movies"),
    )
    await callback.answer()


@dp.message(StateFilter(AdminStates.waiting_movie_delete_code), F.text.regexp(r"^\d+$"))
async def process_movie_delete(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    code = message.text.strip()
    deleted = await db.delete_movie(code)
    if deleted:
        await message.answer(f"🗑 <b>{code}</b> raqamli kino o'chirildi.", reply_markup=admin_main_menu())
    else:
        await message.answer(f"❌ <b>{code}</b> raqamli kino topilmadi.", reply_markup=admin_main_menu())
    await state.clear()


@dp.callback_query(F.data == "movies_list")
async def cb_movies_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    movies = await db.list_movies()
    if not movies:
        text = "Baza bo'sh."
    else:
        text = "📋 <b>Kinolar ro'yxati:</b>\n\n" + "\n".join(f"• {code} — {title}" for code, title in movies)
    if len(text) > 4000:
        text = text[:4000] + "\n..."
    await callback.message.edit_text(text, reply_markup=back_button("admin_movies"))
    await callback.answer()


# --- XABAR YUBORISH (BROADCAST) ---

@dp.callback_query(F.data == "admin_broadcast")
async def cb_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.waiting_broadcast)
    await callback.message.edit_text(
        "📢 Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yuboring (matn, rasm yoki video bo'lishi mumkin).",
        reply_markup=back_button(),
    )
    await callback.answer()


@dp.message(StateFilter(AdminStates.waiting_broadcast))
async def process_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    user_ids = await db.all_user_ids()
    sent, failed = 0, 0
    status = await message.answer(f"⏳ Yuborilmoqda... (0/{len(user_ids)})")

    for i, uid in enumerate(user_ids):
        try:
            await message.copy_to(uid)
            sent += 1
        except Exception:
            failed += 1
        if i % 25 == 0:
            try:
                await status.edit_text(f"⏳ Yuborilmoqda... ({i}/{len(user_ids)})")
            except Exception:
                pass
        await asyncio.sleep(0.05)

    await status.edit_text(f"✅ Xabar yuborildi!\n\nYuborildi: {sent}\nXato: {failed}")
    await message.answer("🛠 Admin panel", reply_markup=admin_main_menu())
    await state.clear()


# --- REKLAMA ---
# Reklama xabarni yuborish xuddi broadcast kabi ishlaydi, faqat alohida bo'lim sifatida

@dp.callback_query(F.data == "admin_ads")
async def cb_ads(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.waiting_ad)
    await callback.message.edit_text(
        "📣 Reklama xabarini (matn/rasm/video) yuboring — u barcha foydalanuvchilarga yuboriladi.",
        reply_markup=back_button(),
    )
    await callback.answer()


@dp.message(StateFilter(AdminStates.waiting_ad))
async def process_ad(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    user_ids = await db.all_user_ids()
    sent, failed = 0, 0
    status = await message.answer(f"⏳ Reklama yuborilmoqda... (0/{len(user_ids)})")

    for i, uid in enumerate(user_ids):
        try:
            await message.copy_to(uid)
            sent += 1
        except Exception:
            failed += 1
        if i % 25 == 0:
            try:
                await status.edit_text(f"⏳ Reklama yuborilmoqda... ({i}/{len(user_ids)})")
            except Exception:
                pass
        await asyncio.sleep(0.05)

    await status.edit_text(f"✅ Reklama yuborildi!\n\nYuborildi: {sent}\nXato: {failed}")
    await message.answer("🛠 Admin panel", reply_markup=admin_main_menu())
    await state.clear()


# --- KANALLAR (MAJBURIY OBUNA) ---

@dp.callback_query(F.data == "admin_channels")
async def cb_channels(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    channels = await db.list_channels()
    text = "🔐 <b>Majburiy obuna kanallari</b>\n\n"
    text += "Bosing — kanalni o'chirish uchun." if channels else "Hozircha kanal qo'shilmagan."
    await callback.message.edit_text(text, reply_markup=channels_menu(channels))
    await callback.answer()


@dp.callback_query(F.data == "channel_add")
async def cb_channel_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.waiting_channel_add)
    await callback.message.edit_text(
        "➕ Kanal username'ini yuboring (masalan: <code>@mening_kanalim</code>).\n\n"
        "⚠️ Botni o'sha kanalga admin qilib qo'shing.",
        reply_markup=back_button("admin_channels"),
    )
    await callback.answer()


@dp.message(StateFilter(AdminStates.waiting_channel_add))
async def process_channel_add(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    username = message.text.strip()
    if not username.startswith("@"):
        await message.answer("⚠️ Username @ bilan boshlanishi kerak. Masalan: @mening_kanalim")
        return
    await db.add_channel(username)
    await message.answer(f"✅ {username} qo'shildi.", reply_markup=admin_main_menu())
    await state.clear()


@dp.callback_query(F.data.startswith("channel_del_"))
async def cb_channel_delete(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    channel_id = int(callback.data.replace("channel_del_", ""))
    await db.remove_channel(channel_id)
    channels = await db.list_channels()
    await callback.message.edit_text(
        "🔐 <b>Majburiy obuna kanallari</b>\n\nKanal o'chirildi.",
        reply_markup=channels_menu(channels),
    )
    await callback.answer("O'chirildi")


# --- ASOSIY: RAQAM BO'YICHA KINO QIDIRISH ---

@dp.message(F.text.regexp(r"^\d+$"))
async def find_movie(message: Message):
    await db.add_user(message.from_user.id)

    missing = await not_subscribed_channels(message.from_user.id)
    if missing:
        text = "⚠️ Botdan foydalanish uchun quyidagi kanal(lar)ga obuna bo'ling:\n\n"
        text += "\n".join(missing)
        text += "\n\nObuna bo'lgach, raqamni qayta yuboring."
        await message.answer(text)
        return

    code = message.text.strip()
    await db.log_request(message.from_user.id, code)

    movie = await db.get_movie(code)
    if movie:
        file_id, title = movie
        await message.answer_video(file_id, caption=f"🎬 <b>{title}</b>\nKod: {code}")
    else:
        await message.answer(f"❌ <b>{code}</b> raqamli kino topilmadi.")


@dp.message()
async def fallback(message: Message):
    if is_admin(message.from_user.id):
        return
    await message.answer("Iltimos, faqat kino raqamini (masalan: <code>123</code>) yuboring.")


async def main():
    await db.init()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
