import os
import subprocess
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отправь /download со ссылкой на артиста Apple Music")

async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Укажите ссылку после /download")
        return
    url = context.args[0]
    await update.message.reply_text(f"⏳ Загружаю {url}... (лог будет в Telegram)")

    try:
        result = subprocess.run(
            ["python", "am_downloader/cli.py", url],
            capture_output=True,
            text=True,
            timeout=600,
            env=os.environ.copy()
        )
        output = result.stdout + "\n" + result.stderr
        if len(output) > 4000:
            output = output[:4000] + "\n... (обрезано)"
        await update.message.reply_text(f"Код возврата: {result.returncode}\n\nВывод:\n{output}")
    except subprocess.TimeoutExpired:
        await update.message.reply_text("⚠️ Загрузка заняла слишком много времени, прервано.")
    except Exception as e:
        await update.message.reply_text(f"🔥 Ошибка: {str(e)}")

def main():
    if not TOKEN:
        print("Токен не задан")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("download", download))
    print("Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
