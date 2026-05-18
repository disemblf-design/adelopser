import os
import subprocess
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

CLI_SCRIPT = "am_downloader/cli.py"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Пришлите ссылку на артиста Apple Music, и я загружу всю дискографию.\n"
        "Пример: /download https://music.apple.com/artist/...\n"
        "После завершения пришлю лог работы."
    )

async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Укажите ссылку после /download")
        return
    url = context.args[0]
    await update.message.reply_text(f"⏳ Начинаю загрузку: {url}\nЖдите, это может занять несколько минут...")

    try:
        result = subprocess.run(
            ["python", CLI_SCRIPT, url],
            capture_output=True,
            text=True,
            timeout=600,
            env=os.environ.copy()
        )
        # Собираем вывод
        output = result.stdout + "\n" + result.stderr
        # Если вывод очень длинный, обрежем (Telegram ограничение 4096 символов)
        if len(output) > 4000:
            output = output[:4000] + "\n... (обрезано)"
        await update.message.reply_text(f"Код возврата: {result.returncode}\n\nВывод:\n{output}")
    except subprocess.TimeoutExpired:
        await update.message.reply_text("⚠️ Загрузка заняла слишком много времени, прервано.")
    except Exception as e:
        await update.message.reply_text(f"🔥 Ошибка: {str(e)}")

def main():
    if not TOKEN:
        print("FATAL: TELEGRAM_BOT_TOKEN is not set")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("download", download))
    print("Bot started polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
