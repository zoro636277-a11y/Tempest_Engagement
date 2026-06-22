import re
import sqlite3
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.types import Message, LinkPreviewOptions
from aiogram.filters import Command

TOKEN = "8696423428:AAHWlnTmlvxG5kQv6KBpaBqAcEm___-CN0M"

CHAT_ID = -1004351521726
ADMIN_ID = 7343042478
TOPICS = {
    5: 15,   # 15 Likes
    3: 30    # 30 Engagement
}

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ---------------- DATABASE ----------------

db = sqlite3.connect(
    "counter.db",
    check_same_thread=False
)

cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS topic_counter (
    thread_id INTEGER PRIMARY KEY,
    count INTEGER NOT NULL DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS user_posts (
    user_id INTEGER,
    thread_id INTEGER,
    last_count INTEGER,
    PRIMARY KEY (user_id, thread_id)
)
""")

db.commit()

db_lock = asyncio.Lock()

# ---------------- REGEX ----------------

X_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:x\.com|twitter\.com)/\S+",
    re.IGNORECASE
)

# ---------------- DB FUNCTIONS ----------------

def get_count(thread_id: int) -> int:
    cur.execute(
        "SELECT count FROM topic_counter WHERE thread_id=?",
        (thread_id,)
    )

    row = cur.fetchone()
    return row[0] if row else 0


def set_count(thread_id: int, count: int):
    cur.execute(
        """
        INSERT INTO topic_counter(thread_id, count)
        VALUES (?, ?)
        ON CONFLICT(thread_id)
        DO UPDATE SET count=excluded.count
        """,
        (thread_id, count)
    )

    db.commit()


def get_user_last(user_id: int, thread_id: int):
    cur.execute(
        """
        SELECT last_count
        FROM user_posts
        WHERE user_id=? AND thread_id=?
        """,
        (user_id, thread_id)
    )

    row = cur.fetchone()
    return row[0] if row else None


def set_user_last(
    user_id: int,
    thread_id: int,
    count: int
):
    cur.execute(
        """
        INSERT INTO user_posts(
            user_id,
            thread_id,
            last_count
        )
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, thread_id)
        DO UPDATE SET last_count=excluded.last_count
        """,
        (user_id, thread_id, count)
    )

    db.commit()

# ---------------- COMMANDS ----------------

@dp.message(Command("count"))
async def count_command(message: Message):

    thread_id = message.message_thread_id

    if thread_id not in TOPICS:
        return

    total = get_count(thread_id)

    await message.answer(
        f"Current count: {total}"
    )


@dp.message(Command("debug"))
async def debug_command(message: Message):

    await message.answer(
        f"chat_id={message.chat.id}\n"
        f"thread_id={message.message_thread_id}"
    )
@dp.message(Command("reset"))
async def reset_command(message: Message):

    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Admin only.")
        return

    try:
        cur.execute("DELETE FROM topic_counter")
        cur.execute("DELETE FROM user_posts")
        db.commit()

        await message.answer(
            "✅ Bot has been reset.\n\n"
            "• All counts cleared\n"
            "• All waiting rules cleared\n"
            "• Everyone can post again"
        )

    except Exception as e:
        await message.answer(f"❌ Error: {e}")
# ---------------- MAIN HANDLER ----------------

@dp.message()
async def handle_links(message: Message):

    if message.chat.id != CHAT_ID:
        return

    if message.from_user.is_bot:
        return

    thread_id = message.message_thread_id

    if thread_id is None:
        return

    if thread_id not in TOPICS:
        return

    text = message.text or ""

    match = X_PATTERN.search(text)

    if not match:
        return

    try:
        async with db_lock:

            required_gap = TOPICS[thread_id]

            user_id = message.from_user.id

            current_count = get_count(thread_id)

            last_count = get_user_last(
                user_id,
                thread_id
            )

            if (
                last_count is not None and
                (current_count - last_count) < required_gap
            ):

                remaining = required_gap - (
                    current_count - last_count
                )

                await message.answer(
                    f"❌ Wait for {remaining} more submissions before posting again."
                )

                try:
                    await message.delete()
                except Exception:
                    pass

                return

            new_count = current_count + 1

            set_count(
                thread_id,
                new_count
            )

            set_user_last(
                user_id,
                thread_id,
                new_count
            )

        username = (
            f"@{message.from_user.username}"
            if message.from_user.username
            else message.from_user.first_name
        )

        link = match.group(0)

        link = link.split("?")[0]

        link = re.sub(
            r"^https?://(?:www\.)?",
            "",
            link,
            flags=re.IGNORECASE
        )

        if thread_id == 5:

            status_match = re.search(
                r"/status/(\d+)",
                match.group(0)
            )

            if status_match:

                tweet_id = status_match.group(1)

                await message.answer(
                    f"#{new_count}\n"
                    f"{username}\n\n"
                    f"https://x.com/intent/like?tweet_id={tweet_id}",
                    link_preview_options=LinkPreviewOptions(
                        is_disabled=True
                    )
                )

            else:

                await message.answer(
                    f"#{new_count}\n"
                    f"{username}\n\n"
                    f"{link}",
                    link_preview_options=LinkPreviewOptions(
                        is_disabled=True
                    )
                )

        else:

            await message.answer(
                f"#{new_count}\n"
                f"{username}\n\n"
                f"{link}",
                link_preview_options=LinkPreviewOptions(
                    is_disabled=True
                )
            )

        try:
            await message.delete()
        except Exception:
            pass

    except Exception as e:
        print("ERROR:", e)

# ---------------- START ----------------

async def main():
    print("Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())