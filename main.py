import os
import sys
from dotenv import load_dotenv
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters
)
from utils.logger import setup_logger

# Load environment variables from .env file
load_dotenv()

# Setup logger
logger = setup_logger("main")

# Verify critical environment variables
def verify_env_vars():
    required = ["TELEGRAM_BOT_TOKEN", "GMAIL_USER", "GMAIL_APP_PASSWORD"]
    missing = [var for var in required if not os.getenv(var)]
    
    if missing:
        logger.error(f"Missing critical environment variables: {', '.join(missing)}")
        logger.error("Please copy .env.example to .env and fill in the values.")
        sys.exit(1)
        
    llm_keys = ["GEMINI_API_KEY", "GROQ_API_KEY"]
    if not any(os.getenv(k) for k in llm_keys):
        logger.error("You must configure at least one LLM API key: GEMINI_API_KEY or GROQ_API_KEY.")
        sys.exit(1)
        
    logger.info("Environment variables verified successfully.")

def main():
    verify_env_vars()
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    logger.info("Starting Telegram Bot Application...")
    
    # Import handlers here to prevent circular imports
    from bot.telegram_bot import (
        start_command,
        status_command,
        health_command,
        process_linkedin_url,
        AWAITING_REDRAFT_FEEDBACK
    )
    from bot.callbacks import (
        approve_send_callback,
        redraft_request_callback,
        process_redraft_feedback,
        cancel_conversation
    )
    
    # Build python-telegram-bot application
    application = Application.builder().token(token).build()
    
    # Setup conversation handler for redrafting feedback loop
    # This state machine intercepts feedback and feeds it back into the generator
    redraft_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(redraft_request_callback, pattern="^redraft_request$")
        ],
        states={
            AWAITING_REDRAFT_FEEDBACK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_redraft_feedback)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            MessageHandler(filters.COMMAND, cancel_conversation)
        ],
        per_message=False  # Handles conversation state per user
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("health", health_command))
    application.add_handler(CommandHandler("cancel", cancel_conversation))
    
    # Add the conversation handler for redrafts
    application.add_handler(redraft_conv_handler)
    
    # Approve and send handler
    application.add_handler(CallbackQueryHandler(approve_send_callback, pattern="^approve_send$"))
    
    # Text message handler to capture LinkedIn URLs
    # Matches URLs containing 'linkedin.com'
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r'linkedin\.com'),
        process_linkedin_url
    ))
    
    # Run the bot in polling mode
    logger.info("Bot is polling. Press Ctrl+C to stop.")
    application.run_polling()

if __name__ == "__main__":
    main()
