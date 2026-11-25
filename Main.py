import asyncio
import os
import random

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

games = {}


@router.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "👑 SUPER MAFIA BOT\n\n"
        "/newgame - Yangi o'yin\n"
        "/join - O'yinga qo'shilish\n"
        "/startgame - O'yinni boshlash\n"
        "/top - Reyting"
    )


@router.message(Command("newgame"))
async def newgame(message: Message):
    chat_id = message.chat.id

    games[chat_id] = {
        "players": {},
        "votes": {},
        "alive": [],
        "started": False
    }

    await message.answer(
        "🎮 Yangi Mafia o'yini yaratildi!\n\n"
        "Qo'shilish uchun /join yozing."
    )


@router.message(Command("join"))
async def join(message: Message):
    chat_id = message.chat.id

    if chat_id not in games:
        await message.answer("❌ Avval /newgame yozing.")
        return

    game = games[chat_id]

    if game["started"]:
        await message.answer("O'yin allaqachon boshlangan!")
        return

    user = message.from_user

    if user.id in game["players"]:
        await message.answer("Siz allaqachon qo'shilgansiz!")
        return

    game["players"][user.id] = user.full_name

    await message.answer(
        f"✅ {user.full_name} o'yinga qo'shildi!\n"
        f"Jami: {len(game['players'])} nafar"
    )


@router.message(Command("startgame"))
async def startgame(message: Message):
    chat_id = message.chat.id

    if chat_id not in games:
        await message.answer("Avval /newgame yozing.")
        return

    game = games[chat_id]
    players = list(game["players"].keys())

    if len(players) < 5:
        await message.answer("❌ Kamida 5 ta o'yinchi kerak!")
        return

    if game["started"]:
        await message.answer("O'yin boshlangan!")
        return

    mafia_count = max(1, len(players) // 5)

    roles = (
        ["🔪 Mafia"] * mafia_count
        + ["🕵️ Detektiv", "👨‍⚕️ Doktor"]
    )

    roles += ["👨‍🌾 Fuqaro"] * (len(players) - len(roles))
    random.shuffle(roles)

    game["started"] = True
    game["alive"] = players

    for user_id, role in zip(players, roles):
        try:
            await bot.send_message(
                user_id,
                f"🎭 Sizning rolingiz: {role}"
            )
        except Exception:
            pass

    await message.answer(
        "🎮 MAFIA O'YINI BOSHLANDI!\n\n"
        f"👥 O'yinchilar: {len(players)}\n"
        "🌙 Rollar shaxsiy xabarga yuborildi.\n\n"
        "☀️ Endi ovoz berish boshlanadi."
    )

    await show_votes(chat_id)


async def show_votes(chat_id):
    game = games[chat_id]
    builder = InlineKeyboardBuilder()

    for user_id in game["alive"]:
        name = game["players"][user_id]

        builder.button(
            text=f"🗳 {name}",
            callback_data=f"vote:{chat_id}:{user_id}"
        )

    builder.adjust(1)

    await bot.send_message(
        chat_id,
        "🗳 Kimni o'yindan chiqaramiz?",
        reply_markup=builder.as_markup()
    )


@router.callback_query(lambda c: c.data.startswith("vote:"))
async def vote(callback):
    _, chat_id, target = callback.data.split(":")
    chat_id = int(chat_id)
    target = int(target)

    game = games.get(chat_id)

    if not game or not game["started"]:
        await callback.answer("O'yin tugagan!", show_alert=True)
        return

    voter = callback.from_user.id

    if voter not in game["alive"]:
        await callback.answer("Siz o'yinda emassiz!", show_alert=True)
        return

    if target not in game["alive"]:
        await callback.answer("Bu o'yinchi o'yinda emas!")
        return

    game["votes"][voter] = target

    await callback.answer("Ovozingiz qabul qilindi! ✅")

    if len(game["votes"]) == len(game["alive"]):
        counts = {}

        for voted in game["votes"].values():
            counts[voted] = counts.get(voted, 0) + 1

        eliminated = max(counts, key=counts.get)
        name = game["players"][eliminated]

        game["alive"].remove(eliminated)
        game["votes"] = {}

        await bot.send_message(
            chat_id,
            f"🚫 {name} ovoz berish orqali chiqarildi!"
        )

        if len(game["alive"]) <= 2:
            await bot.send_message(
                chat_id,
                "🏁 O'yin yakunlandi!"
            )
            game["started"] = False
        else:
            await show_votes(chat_id)


@router.message(Command("top"))
async def top(message: Message):
    await message.answer(
        "🏆 SUPER MAFIA TOP\n\n"
        "Reyting tizimi keyingi versiyada qo'shiladi."
    )


async def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN sozlanmagan!")

    dp.include_router(router)

    print("SUPER MAFIA BOT ISHLAMOQDA!")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
