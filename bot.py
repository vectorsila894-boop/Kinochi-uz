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
    ReplyKeyboardMarkup,
    KeyboardButton,
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
    for _id, username, _link in channels:
        try:
            member = await bot.get_chat_member(username, user_id)
            if member.status in ("left", "kicked"):
                return False
        except Exception:
            # Bot kanalga admin qilinmagan yoki identifikator xato bo'lsa, o'tkazib yuboramiz
            continue
    return True


async def not_subscribed_channels(user_id: int):
    channels = await db.list_channels()
    result = []
    for _id, username, invite_link in channels:
        try:
            member = await bot.get_chat_member(username, user_id)
            if member.status in ("left", "kicked"):
                result.append((username, invite_link))
        except Exception:
            continue
    return result


# --- FSM HOLATLARI ---
class AdminStates(StatesGroup):
    waiting_movie_code = State()
    waiting_movie_video = State()
    waiting_movie_delete_code = State()
    waiting_broadcast = State()
    waiting_ad = State()
    waiting_channel_add = State()
    waiting_channel_link = State()


# --- ADMIN PANEL KLAVIATURASI (pastda doimiy ko'rinadigan tugmalar) ---
def build_reply_keyboard(rows):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t) for t in row] for row in rows],
        resize_keyboard=True,
    )


MAIN_KB = build_reply_keyboard([
    ["📊 Statistika", "👥 Foydalanuvchilar"],
    ["🎬 Kinolar", "📢 Xabar yuborish"],
    ["🔐 Kanallar", "📣 Reklama"],
])

MOVIES_KB = build_reply_keyboard([
    ["➕ Kino qo'shish", "🗑 Kino o'chirish"],
    ["📋 Ro'yxat"],
    ["⬅️ Orqaga"],
])


def channels_menu(channels) -> InlineKeyboardMarkup:
    rows = []
    for cid, username, _link in channels:
        rows.append([InlineKeyboardButton(text=f"❌ {username}", callback_data=f"channel_del_{cid}")])
    rows.append([InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="channel_add")])
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
    await message.answer("🛠 <b>Admin panel</b>", reply_markup=MAIN_KB)


# --- ASOSIY MENYU TUGMALARI ---

@dp.message(F.text == "⬅️ Orqaga")
async def menu_back(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("🛠 <b>Admin panel</b>", reply_markup=MAIN_KB)


@dp.message(F.text == "📊 Statistika")
async def menu_stats(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
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
    await message.answer(text, reply_markup=MAIN_KB)


@dp.message(F.text == "👥 Foydalanuvchilar")
async def menu_users(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    users_count = await db.count_users()
    today = await db.users_today()
    text = (
        f"👥 <b>Foydalanuvchilar</b>\n\n"
        f"Jami: {users_count}\n"
        f"Bugun qo'shilgan: {today}"
    )
    await message.answer(text, reply_markup=MAIN_KB)


# --- KINOLAR ---

@dp.message(F.text == "🎬 Kinolar")
async def menu_movies(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("🎬 <b>Kinolar bo'limi</b>", reply_markup=MOVIES_KB)


@dp.message(F.text == "➕ Kino qo'shish")
async def menu_movies_add(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.waiting_movie_code)
    await message.answer(
        "🔢 Avval kino raqamini yuboring (masalan: <code>101</code>).",
        reply_markup=MOVIES_KB,
    )


@dp.message(StateFilter(AdminStates.waiting_movie_code), F.text.regexp(r"^\d+$"))
async def process_movie_code(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    code = message.text.strip()
    await state.update_data(movie_code=code)
    await state.set_state(AdminStates.waiting_movie_video)
    await message.answer(
        f"🎬 Endi <b>{code}</b> raqami uchun videoni yuboring.",
        reply_markup=MOVIES_KB,
    )


@dp.message(StateFilter(AdminStates.waiting_movie_code))
async def process_movie_code_invalid(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("⚠️ Faqat raqam yuboring (masalan: 101).")


@dp.message(StateFilter(AdminStates.waiting_movie_video), F.video)
async def process_movie_video(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    code = data.get("movie_code")
    if not code:
        await message.answer("⚠️ Xatolik yuz berdi, qaytadan boshlang.", reply_markup=MAIN_KB)
        await state.clear()
        return

    file_id = message.video.file_id
    title = message.video.file_name or f"Kino {code}"

    exists = await db.get_movie(code)
    if exists:
        await db.update_movie(code, file_id, title)
        await message.answer(f"✅ <b>{code}</b> raqamli kino yangilandi.", reply_markup=MOVIES_KB)
    else:
        await db.add_movie(code, file_id, title)
        await message.answer(f"✅ <b>{code}</b> raqamli kino bazaga qo'shildi.", reply_markup=MOVIES_KB)
    await state.clear()


@dp.message(StateFilter(AdminStates.waiting_movie_video))
async def process_movie_video_invalid(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("⚠️ Iltimos, video fayl yuboring.")


@dp.message(F.text == "🗑 Kino o'chirish")
async def menu_movies_delete(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.waiting_movie_delete_code)
    await message.answer(
        "🗑 O'chirmoqchi bo'lgan kino raqamini yuboring.",
        reply_markup=MOVIES_KB,
    )


@dp.message(StateFilter(AdminStates.waiting_movie_delete_code), F.text.regexp(r"^\d+$"))
async def process_movie_delete(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    code = message.text.strip()
    deleted = await db.delete_movie(code)
    if deleted:
        await message.answer(f"🗑 <b>{code}</b> raqamli kino o'chirildi.", reply_markup=MOVIES_KB)
    else:
        await message.answer(f"❌ <b>{code}</b> raqamli kino topilmadi.", reply_markup=MOVIES_KB)
    await state.clear()


@dp.message(F.text == "📋 Ro'yxat")
async def menu_movies_list(message: Message):
    if not is_admin(message.from_user.id):
        return
    movies = await db.list_movies()
    if not movies:
        text = "Baza bo'sh."
    else:
        text = "📋 <b>Kinolar ro'yxati:</b>\n\n" + "\n".join(f"• {code} — {title}" for code, title in movies)
    if len(text) > 4000:
        text = text[:4000] + "\n..."
    await message.answer(text, reply_markup=MOVIES_KB)


# --- XABAR YUBORISH (BROADCAST) ---

@dp.message(F.text == "📢 Xabar yuborish")
async def menu_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.waiting_broadcast)
    await message.answer(
        "📢 Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yuboring (matn, rasm yoki video bo'lishi mumkin).",
        reply_markup=MAIN_KB,
    )


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
    await message.answer("🛠 Admin panel", reply_markup=MAIN_KB)
    await state.clear()


# --- REKLAMA ---
# Reklama xabarni yuborish xuddi broadcast kabi ishlaydi, faqat alohida bo'lim sifatida

@dp.message(F.text == "📣 Reklama")
async def menu_ads(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminStates.waiting_ad)
    await message.answer(
        "📣 Reklama xabarini (matn/rasm/video) yuboring — u barcha foydalanuvchilarga yuboriladi.",
        reply_markup=MAIN_KB,
    )


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
    await message.answer("🛠 Admin panel", reply_markup=MAIN_KB)
    await state.clear()


# --- KANALLAR (MAJBURIY OBUNA) ---

@dp.message(F.text == "🔐 Kanallar")
async def menu_channels(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    channels = await db.list_channels()
    text = "🔐 <b>Majburiy obuna kanallari</b>\n\n"
    text += "Bosing — kanalni o'chirish uchun." if channels else "Hozircha kanal qo'shilmagan."
    await message.answer(text, reply_markup=channels_menu(channels))


@dp.callback_query(F.data == "channel_add")
async def cb_channel_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.waiting_channel_add)
    await callback.message.answer(
        "➕ <b>Kanal qo'shish</b>\n\n"
        "Ochiq kanal bo'lsa — username yuboring: <code>@mening_kanalim</code>\n\n"
        "Yopiq (private) kanal bo'lsa — kanalning raqamli ID'sini yuboring, "
        "masalan: <code>-1001234567890</code>\n"
        "(ID'ni bilish uchun kanaldan istalgan xabarni @userinfobot'ga forward qiling)\n\n"
        "⚠️ Ikkala holatda ham botni o'sha kanalga <b>admin</b> qilib qo'shing.",
        reply_markup=MAIN_KB,
    )
    await callback.answer()


@dp.message(StateFilter(AdminStates.waiting_channel_add))
async def process_channel_add(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    identifier = message.text.strip()

    is_username = identifier.startswith("@")
    is_numeric_id = identifier.lstrip("-").isdigit()

    if not (is_username or is_numeric_id):
        await message.answer(
            "⚠️ Noto'g'ri format. Username (@kanal) yoki raqamli ID (-100...) yuboring."
        )
        return

    await state.update_data(channel_identifier=identifier)

    if is_username:
        # Ochiq kanal — invite link shart emas
        await db.add_channel(identifier, None)
        await message.answer(f"✅ {identifier} qo'shildi.", reply_markup=MAIN_KB)
        await state.clear()
    else:
        # Yopiq kanal — foydalanuvchilar uchun taklif havolasi kerak
        await state.set_state(AdminStates.waiting_channel_link)
        await message.answer(
            "🔗 Endi shu yopiq kanalning <b>taklif havolasini</b> yuboring "
            "(Kanal → Invite Links → havolani nusxalang).\n\n"
            "Bu havola foydalanuvchilarga \"obuna bo'ling\" xabarida ko'rsatiladi."
        )


@dp.message(StateFilter(AdminStates.waiting_channel_link))
async def process_channel_link(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    link = message.text.strip()
    if not link.startswith("http"):
        await message.answer("⚠️ Havola https:// bilan boshlanishi kerak. Qayta yuboring.")
        return

    data = await state.get_data()
    identifier = data.get("channel_identifier")
    await db.add_channel(identifier, link)
    await message.answer(f"✅ Yopiq kanal qo'shildi.\nID: {identifier}\nHavola: {link}", reply_markup=MAIN_KB)
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
        for username, invite_link in missing:
            if invite_link:
                text += f"🔗 <a href=\"{invite_link}\">Kanalga o'tish</a>\n"
            else:
                text += f"{username}\n"
        text += "\nObuna bo'lgach, raqamni qayta yuboring."
        await message.answer(text, disable_web_page_preview=True)
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
