import asyncio
import os
import random

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

games = {}


def make_button(text, data):
    return {"text": text, "callback_data": data}


def alive_players(game):
    return game["alive"]


@router.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "👑 SUPER MAFIA BOT\n\n"
        "🎮 Buyruqlar:\n"
        "/newgame - Yangi o'yin\n"
        "/join - O'yinga qo'shilish\n"
        "/startgame - Boshlash\n"
        "/players - O'yinchilar\n"
        "/cancel - O'yinni bekor qilish"
    )


@router.message(Command("newgame"))
async def newgame(message: Message):
    chat_id = message.chat.id

    games[chat_id] = {
        "players": {},
        "roles": {},
        "alive": [],
        "votes": {},
        "night": {},
        "phase": "waiting"
    }

    await message.answer(
        "🎮 YANGI MAFIA O'YINI!\n\n"
        "O'yinga qo'shilish uchun /join yozing.\n"
        "Kamida 5 o'yinchi kerak."
    )


@router.message(Command("join"))
async def join(message: Message):
    chat_id = message.chat.id

    if chat_id not in games:
        await message.answer("Avval /newgame yozing!")
        return

    game = games[chat_id]

    if game["phase"] != "waiting":
        await message.answer("O'yin boshlangan!")
        return

    user = message.from_user

    if user.id in game["players"]:
        await message.answer("Siz allaqachon qo'shilgansiz!")
        return

    game["players"][user.id] = user.full_name

    await message.answer(
        f"✅ {user.full_name} qo'shildi!\n"
        f"👥 Jami: {len(game['players'])}"
    )


@router.message(Command("players"))
async def players(message: Message):
    game = games.get(message.chat.id)

    if not game:
        await message.answer("O'yin mavjud emas.")
        return

    names = "\n".join(
        f"👤 {name}"
        for uid, name in game["players"].items()
    )

    await message.answer(
        f"👥 O'YINCHILAR:\n\n{names}"
    )


@router.message(Command("cancel"))
async def cancel(message: Message):
    games.pop(message.chat.id, None)
    await message.answer("❌ O'yin bekor qilindi.")


@router.message(Command("startgame"))
async def startgame(message: Message):
    chat_id = message.chat.id

    game = games.get(chat_id)

    if not game:
        await message.answer("Avval /newgame yozing!")
        return

    if game["phase"] != "waiting":
        await message.answer("O'yin allaqachon boshlangan!")
        return

    players = list(game["players"].keys())

    if len(players) < 5:
        await message.answer("Kamida 5 o'yinchi kerak!")
        return

    mafia_count = max(1, len(players) // 5)

    roles = (
        ["mafia"] * mafia_count
        + ["doctor", "detective"]
    )

    roles += ["citizen"] * (len(players) - len(roles))

    random.shuffle(roles)

    game["roles"] = dict(zip(players, roles))
    game["alive"] = players
    game["phase"] = "night"

    role_names = {
        "mafia": "🔪 MAFIA",
        "doctor": "👨‍⚕️ DOKTOR",
        "detective": "🕵️ DETEKTIV",
        "citizen": "👨‍🌾 FUQARO"
    }

    failed = []

    for uid in players:
        try:
            await bot.send_message(
                uid,
                f"🎭 SIZNING ROLINGIZ:\n\n"
                f"{role_names[game['roles'][uid]]}"
            )
        except Exception:
            failed.append(game["players"][uid])

    if failed:
        game["phase"] = "waiting"
        game["roles"] = {}
        game["alive"] = []

        await message.answer(
            "❌ Quyidagi o'yinchilar botga shaxsiy "
            "xabar orqali /start yozishi kerak:\n\n"
            + "\n".join(failed)
            + "\n\nKeyin /startgame ni qayta bosing."
        )
        return

    await message.answer(
        "🎮 MAFIA BOSHLANDI!\n\n"
        f"👥 O'yinchilar: {len(players)}\n"
        "🌙 KECHA BOSHLANDI!"
    )

    await start_night(chat_id)


async def start_night(chat_id):
    game = games[chat_id]

    game["phase"] = "night"
    game["night"] = {
        "mafia": {},
        "doctor": None,
        "detective": None
    }

    for uid in game["alive"]:
        role = game["roles"][uid]

        if role not in ("mafia", "doctor", "detective"):
            continue

        builder = InlineKeyboardBuilder()

        for target in game["alive"]:
            if target == uid:
                continue

            name = game["players"][target]

            builder.button(
                text=name,
                callback_data=f"night:{chat_id}:{target}"
            )

        builder.adjust(1)

        try:
            await bot.send_message(
                uid,
                "🌙 KECHA!\n\n"
                "Kimni tanlaysiz?",
                reply_markup=builder.as_markup()
            )
        except Exception:
            pass


async def check_night(chat_id):
    game = games[chat_id]

    mafia = [
        uid for uid in game["alive"]
        if game["roles"][uid] == "mafia"
    ]

    doctor = [
        uid for uid in game["alive"]
        if game["roles"][uid] == "doctor"
    ]

    detective = [
        uid for uid in game["alive"]
        if game["roles"][uid] == "detective"
    ]

    night = game["night"]

    if any(uid not in night["mafia"] for uid in mafia):
        return

    if doctor and night["doctor"] is None:
        return

    if detective and night["detective"] is None:
        return

    targets = list(night["mafia"].values())

    if targets:
        counts = {}

        for target in targets:
            counts[target] = counts.get(target, 0) + 1

        max_votes = max(counts.values())

        winners = [
            uid for uid, count in counts.items()
            if count == max_votes
        ]

        victim = winners[0] if len(winners) == 1 else None
    else:
        victim = None

    saved = night["doctor"]

    if victim is not None and victim != saved:
        game["alive"].remove(victim)

        await bot.send_message(
            chat_id,
            f"🌅 TONG O TDI!\n\n"
            f"🚫 {game['players'][victim]} "
            "o'yindan chiqdi."
        )
    else:
        await bot.send_message(
            chat_id,
            "🌅 TONG O TDI!\n\n"
            "🎉 Bu kecha hech kim o'yindan chiqmadi!"
        )

    result = await check_winner(chat_id)

    if result:
        return

    await start_day(chat_id)


@router.callback_query(F.data.startswith("night:"))
async def night_action(callback: CallbackQuery):
    _, chat, target = callback.data.split(":")
    chat = int(chat)
    target = int(target)

    game = games.get(chat)

    if not game or game["phase"] != "night":
        await callback.answer("Bu bosqich tugagan!", show_alert=True)
        return

    uid = callback.from_user.id

    if uid not in game["alive"] or target not in game["alive"]:
        await callback.answer("Noto'g'ri tanlov!", show_alert=True)
        return

    role = game["roles"][uid]

    if role == "mafia":
        game["night"]["mafia"][uid] = target

    elif role == "doctor":
        game["night"]["doctor"] = target

    elif role == "detective":
        game["night"]["detective"] = target

        target_role = game["roles"][target]

        result = "🔪 Mafia!" if target_role == "mafia" else "✅ Mafia emas!"

        await bot.send_message(
            uid,
            f"🕵️ Tekshiruv natijasi:\n\n{result}"
        )

    else:
        await callback.answer("Sizda tungi vazifa yo'q!")
        return

    await callback.answer("Tanlov qabul qilindi! ✅")

    await check_night(chat)


async def start_day(chat_id):
    game = games[chat_id]

    game["phase"] = "day"
    game["votes"] = {}

    builder = InlineKeyboardBuilder()

    for uid in game["alive"]:
        builder.button(
            text=game["players"][uid],
            callback_data=f"vote:{chat_id}:{uid}"
        )

    builder.adjust(1)

    await bot.send_message(
        chat_id,
        "☀️ KUN BOSHLANDI!\n\n"
        "🗳 Kimni o'yindan chiqaramiz?",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("vote:"))
async def vote(callback: CallbackQuery):
    _, chat, target = callback.data.split(":")
    chat = int(chat)
    target = int(target)

    game = games.get(chat)

    if not game or game["phase"] != "day":
        await callback.answer("Ovoz berish tugagan!")
        return

    uid = callback.from_user.id

    if uid not in game["alive"]:
        await callback.answer("Siz o'yinda emassiz!")
        return

    if target not in game["alive"]:
        await callback.answer("Bu o'yinchi o'yinda emas!")
        return

    if uid == target:
        await callback.answer(
            "O'zingizga ovoz bera olmaysiz!",
            show_alert=True
        )
        return

    game["votes"][uid] = target

    await callback.answer("Ovoz qabul qilindi! ✅")

    if len(game["votes"]) < len(game["alive"]):
        return

    counts = {}

    for target_id in game["votes"].values():
        counts[target_id] = counts.get(target_id, 0) + 1

    max_votes = max(counts.values())

    winners = [
        uid for uid, count in counts.items()
        if count == max_votes
    ]

    if len(winners) == 1:
        eliminated = winners[0]

        game["alive"].remove(eliminated)

        await bot.send_message(
            chat,
            f"🚫 {game['players'][eliminated]} "
            "ovoz bilan chiqarildi!"
        )
    else:
        await bot.send_message(
            chat,
            "🤝 Ovozlar teng! Hech kim chiqarilmadi."
        )

    result = await check_winner(chat)

    if result:
        return

    await start_night(chat)


async def check_winner(chat_id):
    game = games[chat_id]

    mafia = sum(
        1 for uid in game["alive"]
        if game["roles"][uid] == "mafia"
    )

    citizens = len(game["alive"]) - mafia

    if mafia == 0:
        winner = "🏆 FUQAROLAR G'ALABA QOZONDI!"
    elif mafia >= citizens:
        winner = "🔪 MAFIA G'ALABA QOZONDI!"
    else:
        return False

    game["phase"] = "finished"

    await bot.send_message(
        chat_id,
        f"🎮 O'YIN TUGADI!\n\n{winner}"
    )

    return True


async def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN mavjud emas!")

    dp.include_router(router)

    print("SUPER MAFIA BOT ISHLAMOQDA!")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
