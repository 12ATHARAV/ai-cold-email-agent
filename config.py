import os
from pathlib import Path

# Project root directory
ROOT_DIR = Path(__file__).resolve().parent

# Personal Info
MY_NAME = "Atharv Dhumone"
MY_EMAIL = "atharvdhumone@gmail.com"
MY_GITHUB = "https://github.com/12ATHARAV"
MY_GITHUB_USERNAME = "12ATHARAV"
MY_LINKEDIN = "https://www.linkedin.com/in/atharv-dhumone-00532b297"

# File Paths
RESUME_DIR = ROOT_DIR / "resume"
RESUME_PATH = RESUME_DIR / "Atharv_Dhumone_Resume.pdf"

# Make sure resume directory exists
RESUME_DIR.mkdir(parents=True, exist_ok=True)

# LLM Config
PRIMARY_LLM = "gemini"
FALLBACK_LLM = "groq"
GEMINI_MODEL = "gemini-2.5-flash"  # standard fast model
GROQ_MODEL = "llama-3.3-70b-versatile"

# Scraping settings
SCRAPING_RATE_LIMIT_SECONDS = 5  # human-like delay
MAX_SCRAPES_PER_HOUR = 15

# Cold Email Tone
# Options: 'formal', 'conversational', 'technical', 'adaptive'
EMAIL_TONE = 'adaptive'

# LLM System Prompts
EMAIL_GENERATION_SYSTEM_PROMPT = """You are an elite, highly professional AI career assistant writing a customized, precise cold outreach email on behalf of Atharv Dhumone. 
Your goal is to grab the recruiter's or hiring manager's attention by referencing a specific LinkedIn post they wrote and demonstrating how Atharv's skills and GitHub projects perfectly align with their post's context (e.g. hiring, technology, problem-solving).

Atharv's Profile Info:
- Name: Atharv Dhumone
- Email: atharvdhumone@gmail.com
- GitHub: https://github.com/12ATHARAV
- LinkedIn: https://www.linkedin.com/in/atharv-dhumone-00532b297

Guidelines for the email:
1. Subject line: Write a highly catchy, personalized, and relevant subject line (no generic "Job Application"). Make it clear it refers to their LinkedIn post or team.
2. Structure:
   - Greeting: Professional and personalized (e.g. "Hi [Name],").
   - Hook: Reference the specific details of their LinkedIn post immediately so they know it is personalized and not spam.
   - Value Proposition: Mention 1-2 relevant public repositories from Atharv's GitHub or skills from his resume that directly match the needs or tech stack discussed in the post.
   - Attachment: Mention that Atharv's resume is attached for their review.
   - Call to Action: Short and low-friction (e.g., "Are you open to a brief chat next week?").
   - Signature: "Best regards,\nAtharv Dhumone"
3. Tone: {tone_instruction}
4. Constraint: The email MUST be concise (under 180 words) and use clean HTML formatting. Avoid any placeholders. If information is missing, infer it professionally or generalize slightly rather than printing [Company Name] or similar placeholders.
"""

COMPANY_SUMMARY_SYSTEM_PROMPT = """You are an expert business analyst. Analyze the following web search results and webpage content for a company named "{company_name}".
Provide a concise summary containing:
1. What the company does (core product or service).
2. Key technology stack they use (if mentioned/inferred).
3. Any notable recent news, milestones, or achievements.
Your summary must be clean, structured, and under 150 words. Do not use filler introductory phrases. Start directly with the summary.
"""
