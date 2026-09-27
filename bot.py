import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from database import Database

logging.basicConfig(level=logging.INFO)

# --- SOZLAMALAR ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "SIZNING_BOT_TOKENINGIZ")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "0").split(",") if x.strip()]
# Majburiy obuna kanali (ixtiyoriy). Bo'sh qoldirsangiz, tekshiruv o'chadi.
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "")  # masalan: "@mening_kanalim"

db = Database("kino_bot.db")
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def is_subscribed(user_id: int) -> bool:
    if not REQUIRED_CHANNEL:
        return True
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status not in ("left", "kicked")
    except Exception:
        return False


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
    text = (
        "ℹ️ <b>Yordam</b>\n\n"
        "Kino kodini raqam shaklida yuboring (masalan: 45).\n"
    )
    if is_admin(message.from_user.id):
        text += (
            "\n<b>Admin buyruqlari:</b>\n"
            "/add [raqam] — video yuborib, kino qo'shish\n"
            "(video yuborilganda captionga raqamni yozing)\n"
            "/delete [raqam] — kinoni o'chirish\n"
            "/list — barcha kinolar ro'yxati\n"
            "/stats — statistika\n"
        )
    await message.answer(text)


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    users_count = await db.count_users()
    movies_count = await db.count_movies()
    requests_count = await db.count_requests()
    await message.answer(
        f"📊 <b>Statistika</b>\n\n"
        f"👤 Foydalanuvchilar: {users_count}\n"
        f"🎞 Kinolar soni: {movies_count}\n"
        f"🔎 Jami so'rovlar: {requests_count}"
    )


# --- ADMIN: KINO QO'SHISH ---
# Video yuborilganda caption'da raqam bo'lishi shart: masalan caption = "101"

@dp.message(F.video)
async def add_movie_by_video(message: Message):
    if not is_admin(message.from_user.id):
        return

    caption = (message.caption or "").strip()
    if not caption.isdigit():
        await message.answer(
            "⚠️ Video yuborayotganda captionga kino raqamini yozing.\n"
            "Masalan, videoga caption sifatida: <code>101</code>"
        )
        return

    code = caption
    file_id = message.video.file_id
    title = message.video.file_name or f"Kino {code}"

    exists = await db.get_movie(code)
    if exists:
        await db.update_movie(code, file_id, title)
        await message.answer(f"✅ <b>{code}</b> raqamli kino yangilandi.")
    else:
        await db.add_movie(code, file_id, title)
        await message.answer(f"✅ <b>{code}</b> raqamli kino bazaga qo'shildi.")


@dp.message(Command("delete"))
async def cmd_delete(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer("Foydalanish: /delete [raqam]")
        return

    code = parts[1].strip()
    deleted = await db.delete_movie(code)
    if deleted:
        await message.answer(f"🗑 <b>{code}</b> raqamli kino o'chirildi.")
    else:
        await message.answer(f"❌ <b>{code}</b> raqamli kino topilmadi.")


@dp.message(Command("list"))
async def cmd_list(message: Message):
    if not is_admin(message.from_user.id):
        return

    movies = await db.list_movies()
    if not movies:
        await message.answer("Baza bo'sh.")
        return

    text = "🎞 <b>Kinolar ro'yxati:</b>\n\n"
    text += "\n".join(f"• {code} — {title}" for code, title in movies)
    # Telegram xabar uzunligi cheklovi uchun bo'lib yuborish
    for chunk_start in range(0, len(text), 4000):
        await message.answer(text[chunk_start:chunk_start + 4000])


# --- ASOSIY: RAQAM BO'YICHA KINO QIDIRISH ---

@dp.message(F.text.regexp(r"^\d+$"))
async def find_movie(message: Message):
    await db.add_user(message.from_user.id)

    if not await is_subscribed(message.from_user.id):
        await message.answer(
            f"⚠️ Botdan foydalanish uchun avval kanalimizga obuna bo'ling: {REQUIRED_CHANNEL}\n"
            "Obuna bo'lgach, raqamni qayta yuboring."
        )
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
    await message.answer(
        "Iltimos, faqat kino raqamini (masalan: <code>123</code>) yuboring."
    )


async def main():
    await db.init()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
