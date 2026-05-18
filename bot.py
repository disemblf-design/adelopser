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
        "После завершения пришлю список ошибок (если будут)."
    )

async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Укажите ссылку после /download")
        return
    url = context.args[0]
    await update.message.reply_text(f"⏳ Начинаю загрузку: {url}\nСмотрю логи Railway...")

    # Диагностика: какие переменные окружения с токенами видны
    print("=== ENV KEYS (with TOKEN or STOREFRONT) ===")
    for k in os.environ.keys():
        if 'TOKEN' in k.upper() or 'STOREFRONT' in k.upper():
            print(f"  {k} is set")

    try:
        result = subprocess.run(
            ["python", CLI_SCRIPT, url],
            capture_output=True,
            text=True,
            timeout=600,
            env=os.environ.copy()   # передаём все переменные окружения
        )
        print("=== STDOUT ===")
        print(result.stdout)
        print("=== STDERR ===")
        print(result.stderr)
        print("=== RETURN CODE ===")
        print(result.returncode)

        if result.returncode == 0:
            await update.message.reply_text("✅ Команда выполнена. Результат в логах Railway.")
        else:
            await update.message.reply_text(f"❌ Ошибка (код {result.returncode}). Детали в логах.")
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
