import time
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from utils.logger import setup_logger
from utils.helpers import is_valid_linkedin_url
from config import MY_NAME, MY_EMAIL, MY_GITHUB, MY_LINKEDIN
from agents.linkedin_scraper import LinkedInScraper
from agents.company_researcher import CompanyResearcher
from agents.email_finder import EmailFinder
from agents.email_generator import EmailGenerator
from agents.email_sender import EmailSender
from agents.github_reader import GitHubReader

logger = setup_logger(__name__)

# Start time for uptime calculations
START_TIME = time.time()

# Stats counters
STATS = {
    "scrapes": 0,
    "emails_sent": 0,
    "errors": 0
}

# Conversation States for Redrafting
AWAITING_REDRAFT_FEEDBACK = 1

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message to the user."""
    welcome_text = (
        f"👋 *Welcome to LinkedIn Cold Outreach Bot!*\n\n"
        f"I am initialized and ready to draft customized emails on your behalf.\n\n"
        f"👤 *Sender Profile:*\n"
        f"• Name: {MY_NAME}\n"
        f"• Email: {MY_EMAIL}\n"
        f"• GitHub: {MY_GITHUB}\n"
        f"• LinkedIn: {MY_LINKEDIN}\n\n"
        f"🔗 *How to use:*\n"
        f"Simply send me any LinkedIn post URL (e.g. `https://www.linkedin.com/posts/...` or `https://www.linkedin.com/feed/update/...`).\n\n"
        f"I will fetch the post, research the company, lookup contact emails, and generate a draft cold email for your review!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", disable_web_page_preview=True)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays bot statistics and uptime."""
    uptime_seconds = int(time.time() - START_TIME)
    days, remainder = divmod(uptime_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
    
    status_text = (
        f"📊 *Bot Status Report:*\n"
        f"• *Uptime:* {uptime_str}\n"
        f"• *LinkedIn Posts Scraped:* {STATS['scrapes']}\n"
        f"• *Emails Sent Successfully:* {STATS['emails_sent']}\n"
        f"• *Errors Encountered:* {STATS['errors']}\n"
        f"• *Host:* Serv00 Cloud Server"
    )
    await update.message.reply_text(status_text, parse_mode="Markdown")

async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simple ping-pong health check."""
    await update.message.reply_text("💚 Bot is online and running 24/7!")

async def process_linkedin_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main workflow triggered when a LinkedIn URL is sent."""
    url = update.message.text.strip()
    
    if not is_valid_linkedin_url(url):
        await update.message.reply_text("❌ Invalid LinkedIn URL. Please provide a valid LinkedIn post link.")
        return

    status_message = await update.message.reply_text("⏳ *Starting outreach pipeline...*\n• Scraping LinkedIn post...", parse_mode="Markdown")
    STATS["scrapes"] += 1
    
    try:
        # 1. Scrape LinkedIn post
        scraper = LinkedInScraper()
        post_data = scraper.scrape_post(url)
        
        if post_data.get("error") and not post_data.get("post_text"):
            await status_message.edit_text(f"❌ *Scraping Failed:*\n{post_data['error']}", parse_mode="Markdown")
            STATS["errors"] += 1
            return
            
        # 2. Update status and Research company
        await status_message.edit_text("⏳ *Pipeline Progress:*\n✅ Scraped post\n• Researching company...", parse_mode="Markdown")
        company_name = post_data.get("company_name")
        if not company_name:
            company_name = "Target Company"
            
        researcher = CompanyResearcher()
        company_data = researcher.research_company(company_name)
        company_domain = company_data.get("domain")
        
        # 3. Update status and Find email
        await status_message.edit_text("⏳ *Pipeline Progress:*\n✅ Scraped post\n✅ Researched company\n• Finding contact email...", parse_mode="Markdown")
        finder = EmailFinder()
        recipient_email, confidence = finder.find_email(post_data.get("author_name", ""), company_domain)
        
        # 4. Update status and Fetch GitHub repos
        await status_message.edit_text("⏳ *Pipeline Progress:*\n✅ Scraped post\n✅ Researched company\n✅ Found contact email\n• Fetching your GitHub projects...", parse_mode="Markdown")
        github = GitHubReader()
        github_summary = github.get_formatted_summary(limit=5)
        
        # 5. Update status and Generate email draft
        await status_message.edit_text("⏳ *Pipeline Progress:*\n✅ Scraped post\n✅ Researched company\n✅ Found contact email\n✅ Fetched GitHub\n• Generating cold email draft...", parse_mode="Markdown")
        generator = EmailGenerator()
        draft = generator.generate_email_draft(post_data, company_data, github_summary, recipient_email, confidence)
        
        # Store draft details in user_data for the approval/redraft callback handlers
        context.user_data["current_draft"] = draft
        context.user_data["post_data"] = post_data
        context.user_data["company_data"] = company_data
        context.user_data["github_summary"] = github_summary
        
        # 6. Send draft preview with buttons
        await status_message.delete()  # Delete the progress message
        
        preview_text = (
            f"📧 *Cold Email Draft Generated!*\n\n"
            f"👤 *To:* {draft['author_name']} ({draft['recipient_email']})\n"
            f"🏢 *Company:* {draft['company_name']}\n"
            f"🎯 *Email Confidence:* `{draft['recipient_confidence']}`\n"
            f"🤖 *Generator:* {draft['llm_used']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 *Subject:* {draft['subject']}\n\n"
            f"{draft['body']}\n"
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
        logger.error(f"Pipeline failed: {e}")
        await status_message.edit_text(f"❌ *Pipeline Error:* An unexpected error occurred: {html.escape(str(e))}", parse_mode="HTML")
        STATS["errors"] += 1
