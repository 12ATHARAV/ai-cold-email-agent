from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from utils.logger import setup_logger
from agents.email_sender import EmailSender
from agents.email_generator import EmailGenerator
from bot.telegram_bot import STATS, AWAITING_REDRAFT_FEEDBACK

logger = setup_logger(__name__)

async def approve_send_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback when user clicks 'Approve & Send'."""
    query = update.callback_query
    await query.answer()  # Dismiss loading animation
    
    draft = context.user_data.get("current_draft")
    if not draft:
        await query.edit_message_text("❌ Error: No draft session found. Please submit the URL again.")
        return
        
    recipient = draft["recipient_email"]
    subject = draft["subject"]
    body = draft["body"]
    
    await query.edit_message_reply_markup(reply_markup=None) # Remove buttons
    status_msg = await query.message.reply_text(f"📤 Sending email to {recipient}...")
    
    try:
        sender = EmailSender()
        success = sender.send_email(recipient, subject, body)
        
        if success:
            STATS["emails_sent"] += 1
            await status_msg.edit_text(f"✅ *Email sent successfully!* \n📨 Recipient: `{recipient}`\n📌 Subject: *{subject}*", parse_mode="Markdown")
            await query.message.edit_text(
                f"{query.message.text}\n\n✅ *Approved & Sent to {recipient}*",
                parse_mode="Markdown"
            )
        else:
            await status_msg.edit_text("❌ *Failed to send email.* Check logs/credentials in .env.")
            # Put buttons back so they can retry
            keyboard = [
                [
                    InlineKeyboardButton("✅ Try Again", callback_data="approve_send"),
                    InlineKeyboardButton("🔄 Redraft", callback_data="redraft_request")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_reply_markup(reply_markup=reply_markup)
            
    except Exception as e:
        logger.error(f"Error in approve callback: {e}")
        await status_msg.edit_text(f"❌ *Sending Error:* {str(e)}")
        
    return ConversationHandler.END

async def redraft_request_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback when user clicks 'Redraft / Revise'."""
    query = update.callback_query
    await query.answer()
    
    # Prompt the user for feedback
    await query.message.reply_text(
        "📝 *Please reply to this message with your revision notes.*\n"
        "Tell me what to change (e.g. \"make it shorter\", \"focus more on my React repository\", \"make the tone more informal\").",
        parse_mode="Markdown"
    )
    
    # Transition to wait for feedback state
    return AWAITING_REDRAFT_FEEDBACK

async def process_redraft_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the user's feedback text and generates a revised draft."""
    feedback = update.message.text.strip()
    logger.info(f"Received redraft feedback: {feedback}")
    
    draft = context.user_data.get("current_draft")
    post_data = context.user_data.get("post_data")
    company_data = context.user_data.get("company_data")
    github_summary = context.user_data.get("github_summary")
    
    if not draft or not post_data or not company_data:
        await update.message.reply_text("❌ Error: Session lost. Please resubmit the LinkedIn URL.")
        return ConversationHandler.END
        
    status_message = await update.message.reply_text("🔄 *Regenerating draft based on your feedback...*", parse_mode="Markdown")
    
    try:
        # Construct updated prompt for the generator
        generator = EmailGenerator()
        
        # Inject feedback into prompt instructions
        feedback_instruction = (
            f"\n\nCRITICAL USER REQUEST: The user wants some modifications on the draft. "
            f"Please revise the email strictly adhering to this feedback: \"{feedback}\".\n"
            f"Here was the previous draft subject: \"{draft['subject']}\" and body: \"{draft['body']}\". "
            f"Generate a new, revised version based on this."
        )
        
        # Update draft
        revised_draft = generator.generate_email_draft(
            post_data, company_data, github_summary + feedback_instruction,
            draft["recipient_email"], draft["recipient_confidence"]
        )
        
        # Store new draft in session
        context.user_data["current_draft"] = revised_draft
        
        await status_message.delete()
        
        preview_text = (
            f"📧 *Revised Cold Email Draft Generated!*\n\n"
            f"👤 *To:* {revised_draft['author_name']} ({revised_draft['recipient_email']})\n"
            f"🏢 *Company:* {revised_draft['company_name']}\n"
            f"🎯 *Email Confidence:* `{revised_draft['recipient_confidence']}`\n"
            f"🤖 *Generator:* {revised_draft['llm_used']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 *Subject:* {revised_draft['subject']}\n\n"
            f"{revised_draft['body']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve & Send", callback_data="approve_send"),
                InlineKeyboardButton("🔄 Redraft / Revise", callback_data="redraft_request")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(preview_text, parse_mode="Markdown", reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Redraft failed: {e}")
        await status_message.edit_text(f"❌ *Redraft Error:* {str(e)}")
        
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gracefully cancel a conversation flow."""
    await update.message.reply_text("👍 Conversation cancelled. Send a LinkedIn URL to start over.")
    return ConversationHandler.END
