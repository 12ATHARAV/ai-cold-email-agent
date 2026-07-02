import os
import google.generativeai as genai
from groq import Groq
from config import (
    PRIMARY_LLM, FALLBACK_LLM, GEMINI_MODEL, GROQ_MODEL,
    EMAIL_GENERATION_SYSTEM_PROMPT, EMAIL_TONE, RESUME_PATH,
    MY_NAME, MY_EMAIL, MY_GITHUB, MY_LINKEDIN
)
from utils.logger import setup_logger
from utils.helpers import extract_text_from_pdf

logger = setup_logger(__name__)

class EmailGenerator:
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")
        
        # Configure Gemini
        if self.gemini_key:
            genai.configure(api_key=self.gemini_key)
            
        # Configure Groq
        self.groq_client = None
        if self.groq_key:
            self.groq_client = Groq(api_key=self.groq_key)
            
        # Load resume content once on initialization
        self.resume_text = self._load_resume()

    def _load_resume(self) -> str:
        """Loads and extracts text from the resume PDF file."""
        if not RESUME_PATH.exists():
            logger.warning(f"Resume PDF not found at {RESUME_PATH}. Email generation will proceed without resume context.")
            return ""
            
        logger.info(f"Extracting text from resume PDF: {RESUME_PATH}")
        text = extract_text_from_pdf(RESUME_PATH)
        if text:
            logger.info("Resume text successfully loaded.")
        else:
            logger.warning("Failed to extract text from resume PDF or PDF was empty.")
        return text

    def generate_email_draft(self, post_data: dict, company_data: dict, github_summary: str, recipient_email: str, recipient_confidence: str) -> dict:
        """Generates a cold email based on LinkedIn post, company research, GitHub, and resume details."""
        
        # Prepare the instruction based on tone configuration
        tone_map = {
            'formal': "highly professional, formal, polite, and business-focused. Avoid casual slang.",
            'conversational': "friendly, warm, conversational, yet respectful. Write as if you are reaching out to a peer or mentor.",
            'technical': "direct, builder-focused, mentioning coding stacks, clean architectures, and engineering concepts.",
            'adaptive': "adaptive. Match the tone of the LinkedIn post: if the post is formal, write formally; if it is conversational or uses emojis, write in a friendly, enthusiastic style."
        }
        tone_instruction = tone_map.get(EMAIL_TONE, tone_map['adaptive'])

        # Build prompt
        prompt = f"""
TARGET RECIPIENT:
- Name: {post_data.get('author_name', 'LinkedIn User')}
- Headline: {post_data.get('author_headline', 'Professional')}
- Company: {company_data.get('company_name', 'Their Company')}
- Target Email: {recipient_email}

COMPANY RESEARCH DETAILS:
- Website: {company_data.get('website', 'N/A')}
- Summary: {company_data.get('summary', 'N/A')}

LINKEDIN POST CONTENT THEY WROTE:
\"\"\"
{post_data.get('post_text', '')}
\"\"\"

ATHARV'S GITHUB PORTFOLIO:
{github_summary}

ATHARV'S RESUME DETAILS (parsed from PDF):
\"\"\"
{self.resume_text if self.resume_text else "Resume details not available. Rely on GitHub projects and standard engineering skills."}
\"\"\"

Write the cold email draft now:
"""

        system_prompt = EMAIL_GENERATION_SYSTEM_PROMPT.format(tone_instruction=tone_instruction)
        
        # Try primary LLM (Gemini)
        email_text = ""
        llm_used = ""
        
        if PRIMARY_LLM == "gemini" and self.gemini_key:
            try:
                logger.info(f"Generating email draft using Gemini ({GEMINI_MODEL})...")
                model = genai.GenerativeModel(
                    model_name=GEMINI_MODEL,
                    system_instruction=system_prompt
                )
                response = model.generate_content(prompt, generation_config={"temperature": 0.7})
                if response.text:
                    email_text = response.text.strip()
                    llm_used = "Gemini 2.5 Flash"
            except Exception as e:
                logger.error(f"Gemini API call failed: {e}. Attempting fallback to Groq...")

        # Fallback to Groq
        if not email_text and self.groq_client:
            try:
                logger.info(f"Generating email draft using Groq ({GROQ_MODEL}) fallback...")
                chat_completion = self.groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    model=GROQ_MODEL,
                    temperature=0.7
                )
                content = chat_completion.choices[0].message.content
                if content:
                    email_text = content.strip()
                    llm_used = f"Groq ({GROQ_MODEL})"
            except Exception as e:
                logger.error(f"Groq API call failed: {e}")

        # Final default fallback if everything fails
        if not email_text:
            email_text = f"Subject: Reaching out regarding your recent update\n\nHi {post_data.get('author_name', 'there')},\n\nI saw your post on LinkedIn and wanted to connect. I tried to generate a draft automatically, but my AI generators were offline. Please edit this draft manually."
            llm_used = "None (offline default)"

        # Parse subject line and body
        subject = "Outreach regarding your recent update"
        body = email_text
        
        # Extract Subject if LLM formatted it as "Subject: ..."
        subject_match = re.match(r'(?:Subject|Subject Line):\s*(.+)', email_text, re.IGNORECASE)
        if subject_match:
            subject = subject_match.group(1).strip()
            # Remove the subject line from the body
            body = re.sub(r'^(?:Subject|Subject Line):\s*.+\n*', '', email_text, flags=re.IGNORECASE).strip()
        elif "subject:" in email_text.lower()[:30]:
            lines = email_text.split('\n')
            for line in lines:
                if line.lower().startswith('subject:'):
                    subject = line[8:].strip()
                    lines.remove(line)
                    body = '\n'.join(lines).strip()
                    break

        return {
            "subject": subject,
            "body": body,
            "recipient_email": recipient_email,
            "recipient_confidence": recipient_confidence,
            "llm_used": llm_used,
            "author_name": post_data.get('author_name', 'LinkedIn User'),
            "company_name": company_data.get('company_name', 'Their Company')
        }
