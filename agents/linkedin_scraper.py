import os
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from linkedin_api import Linkedin
from config import PRIMARY_LLM
from utils.logger import setup_logger
from utils.helpers import clean_text

logger = setup_logger(__name__)

class LinkedInScraper:
    def __init__(self, li_at_cookie: str = None):
        self.li_at_cookie = li_at_cookie or os.getenv("LINKEDIN_LI_AT")
        self.api = None
        if self.li_at_cookie:
            try:
                # Initialize Tom Quirk's Linkedin client with session cookie
                self.api = Linkedin(cookie_li_at=self.li_at_cookie)
                logger.info("Initialized LinkedIn API client with session cookie.")
            except Exception as e:
                logger.error(f"Failed to initialize LinkedIn API with cookie: {e}")

    def extract_post_id(self, url: str) -> str | None:
        """Extracts the post activity ID/URN from a LinkedIn URL."""
        if not url:
            return None
        
        # Try to find a sequence of 19 digits (typical LinkedIn URN ID)
        match = re.search(r'activity[:-](\d{19})', url)
        if match:
            return match.group(1)
            
        # Or look for digits in path
        match = re.search(r'/posts/\w+-(\d{19})', url)
        if match:
            return match.group(1)
            
        # Try any sequence of 19 digits in URL
        match = re.search(r'(\d{19})', url)
        if match:
            return match.group(1)
            
        return None

    def scrape_post(self, url: str) -> dict:
        """Scrapes a LinkedIn post by URL, trying authenticated Voyager API first, then public HTML fallback."""
        post_id = self.extract_post_id(url)
        logger.info(f"Scraping LinkedIn post. ID extracted: {post_id} from URL: {url}")
        
        result = {
            "post_id": post_id,
            "url": url,
            "author_name": "LinkedIn User",
            "author_headline": "Professional",
            "post_text": "",
            "company_name": "",
            "error": None
        }

        # Strategy 1: Unofficial Voyager API V2 (requires cookie)
        if self.api and post_id:
            try:
                logger.info("Attempting Voyager updatesV2 query...")
                urn = f"urn:li:activity:{post_id}"
                endpoint = "/feed/updatesV2"
                params = {
                    "q": "backendUrnOrNss",
                    "urnOrNss": urn
                }
                response = self.api._fetch(endpoint, params=params)
                if response.status_code == 200:
                    data = response.json()
                    elements = data.get("elements", [])
                    if elements:
                        element = elements[0]
                        # Extract post text
                        commentary = element.get("commentary", {})
                        post_text = commentary.get("text", {}).get("text", "")
                        if not post_text:
                            # Try fallback fields
                            update_content = element.get("updateActionHeader", {})
                            post_text = update_content.get("text", {}).get("text", "")
                            
                        # Extract author info
                        actor = element.get("actor", {})
                        name = actor.get("name", {}).get("text", "")
                        headline = actor.get("description", {}).get("text", "")
                        
                        # Set fields
                        if post_text:
                            result["post_text"] = post_text
                        if name:
                            result["author_name"] = name
                        if headline:
                            result["author_headline"] = headline
                            
                        # Attempt to guess company from author headline
                        company_match = re.search(r'(?:at|@)\s+([A-Z][A-Za-z0-9\s.,&]+)', headline)
                        if company_match:
                            result["company_name"] = company_match.group(1).strip()
                            
                        logger.info("Successfully fetched post content via Voyager API.")
                        return result
                    else:
                        logger.warning("Voyager API returned empty elements list.")
                else:
                    logger.warning(f"Voyager API request failed with status: {response.status_code}")
            except Exception as e:
                logger.error(f"Error querying Voyager API: {e}")

        # Strategy 2: Fallback to public meta tag scraping (no cookies needed)
        logger.info("Falling back to public HTML scraping...")
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9"
            }
            # Add session cookies if we have them to bypass loginwall
            cookies = {}
            if self.li_at_cookie:
                cookies = {"li_at": self.li_at_cookie}
                
            response = requests.get(url, headers=headers, cookies=cookies, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract post text from og:description
                meta_desc = soup.find('meta', property='og:description')
                if meta_desc and meta_desc.get('content'):
                    result["post_text"] = clean_text(meta_desc['content'])
                else:
                    # Alternative description tags
                    meta_desc_alt = soup.find('meta', attrs={'name': 'description'})
                    if meta_desc_alt and meta_desc_alt.get('content'):
                        result["post_text"] = clean_text(meta_desc_alt['content'])
                        
                # Extract author name from title
                # Format is usually: "Author Name on LinkedIn: Post Content" or similar
                title_tag = soup.find('title')
                if title_tag:
                    title_text = title_tag.get_text()
                    if "on LinkedIn" in title_text:
                        parts = title_text.split("on LinkedIn")
                        result["author_name"] = parts[0].strip()
                        
                # If post_text was empty but we found other tags
                if not result["post_text"]:
                    # Try finding elements with specific class names
                    desc_elem = soup.find('p', class_=re.compile(r'description|content|commentary'))
                    if desc_elem:
                        result["post_text"] = clean_text(desc_elem.get_text())
                
                # Check if we got something
                if result["post_text"]:
                    logger.info("Successfully fetched post content via public HTML scraping.")
                    return result
            else:
                logger.warning(f"Public scraping returned status code {response.status_code}")
                result["error"] = f"LinkedIn returned HTTP {response.status_code}"
        except Exception as e:
            logger.error(f"Error during public scraping fallback: {e}")
            result["error"] = str(e)
            
        # Strategy 3: Parse basic info from URL if all else fails
        if not result["post_text"]:
            result["post_text"] = f"Could not fetch post content. Please copy-paste the post details or retry with a valid session cookie."
            
        return result
