import re
from pathlib import Path
from urllib.parse import urlparse
import PyPDF2
from utils.logger import setup_logger

logger = setup_logger(__name__)

def is_valid_linkedin_url(url: str) -> bool:
    """Validates if a URL is a LinkedIn post or profile/feed update URL."""
    if not url:
        return False
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    # Must be a linkedin.com domain
    if 'linkedin.com' not in domain:
        return False
        
    path = parsed.path.lower()
    # Accept /posts/, /feed/update/, /pulse/, etc.
    valid_patterns = [
        r'/posts/',
        r'/feed/update/',
        r'/pulse/',
        r'/in/'
    ]
    
    for pattern in valid_patterns:
        if re.search(pattern, path):
            return True
            
    return False

def clean_text(text: str) -> str:
    """Cleans up raw text, resolving double spaces, strange characters, etc."""
    if not text:
        return ""
    # Normalize whitespaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extracts all text from a local PDF file (like a resume)."""
    if not pdf_path.exists():
        logger.warning(f"PDF file does not exist: {pdf_path}")
        return ""
        
    try:
        text = ""
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page_num in range(len(reader.pages)):
                page_text = reader.pages[page_num].extract_text()
                if page_text:
                    text += page_text + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"Error reading PDF from {pdf_path}: {e}")
        return ""

def extract_emails_from_text(text: str) -> list[str]:
    """Finds all email addresses in a block of text using regular expressions."""
    if not text:
        return []
    # Standard email regex
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    found = re.findall(email_pattern, text)
    # Return unique emails lowercased
    return list(set(email.lower() for email in found))

def get_domain_from_url(url: str) -> str:
    """Extracts the base domain name from a URL, e.g. https://www.google.com -> google.com."""
    if not url:
        return ""
    try:
        # Standardize prefix if missing scheme
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove www.
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except Exception:
        return ""
