import os
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
import google.generativeai as genai
from groq import Groq
from config import PRIMARY_LLM, FALLBACK_LLM, GEMINI_MODEL, GROQ_MODEL, COMPANY_SUMMARY_SYSTEM_PROMPT
from utils.logger import setup_logger
from utils.helpers import clean_text, get_domain_from_url

logger = setup_logger(__name__)

class CompanyResearcher:
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

    def _call_llm(self, prompt: str, system_prompt: str) -> str:
        """Helper to call LLM (Gemini with Groq fallback)."""
        # Try Gemini (Primary)
        if PRIMARY_LLM == "gemini" and self.gemini_key:
            try:
                logger.info(f"Calling Gemini ({GEMINI_MODEL}) for company summary...")
                model = genai.GenerativeModel(
                    model_name=GEMINI_MODEL,
                    system_instruction=system_prompt
                )
                response = model.generate_content(prompt, generation_config={"temperature": 0.3})
                if response.text:
                    return response.text.strip()
            except Exception as e:
                logger.error(f"Gemini API call failed: {e}. Falling back to Groq...")

        # Try Groq (Fallback)
        if self.groq_client:
            try:
                logger.info(f"Calling Groq ({GROQ_MODEL}) for company summary...")
                chat_completion = self.groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    model=GROQ_MODEL,
                    temperature=0.3
                )
                content = chat_completion.choices[0].message.content
                if content:
                    return content.strip()
            except Exception as e:
                logger.error(f"Groq API call failed: {e}")

        # Basic fallback string if both LLMs fail
        return "Company profile summary unavailable."

    def search_company_web(self, company_name: str) -> list[dict]:
        """Performs a web search via DuckDuckGo to find information about the company."""
        if not company_name:
            return []
            
        logger.info(f"Searching web for company: {company_name}")
        search_query = f"{company_name} company profile products services technology"
        
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(search_query, max_results=5))
                formatted_results = []
                for r in results:
                    formatted_results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "body": r.get("body", "")
                    })
                return formatted_results
        except Exception as e:
            logger.error(f"DuckDuckGo search failed for query '{search_query}': {e}")
            return []

    def find_company_website(self, company_name: str) -> str:
        """Finds the most likely website domain for a company name."""
        if not company_name:
            return ""
            
        logger.info(f"Finding homepage for company: {company_name}")
        search_query = f"{company_name} official website home page"
        
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(search_query, max_results=3))
                if results:
                    # Return the URL of the first search result
                    url = results[0].get("href", "")
                    return url
        except Exception as e:
            logger.error(f"DuckDuckGo website lookup failed: {e}")
            
        return ""

    def scrape_company_page(self, url: str) -> str:
        """Scrapes the raw text content of a company page (homepage, about page, etc.)."""
        if not url:
            return ""
            
        logger.info(f"Scraping company webpage: {url}")
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()
                    
                text = soup.get_text()
                return clean_text(text)[:1500]  # Get first 1500 chars to avoid token bloat
        except Exception as e:
            logger.error(f"Failed to scrape webpage {url}: {e}")
            
        return ""

    def research_company(self, company_name: str) -> dict:
        """Researches the company, scrapes pages, and generates a structured summary."""
        if not company_name:
            return {
                "company_name": "",
                "website": "",
                "domain": "",
                "summary": "No company name specified for research."
            }

        logger.info(f"Starting company research for: {company_name}")
        
        # 1. Search web
        search_results = self.search_company_web(company_name)
        
        # 2. Get website
        website = ""
        domain = ""
        
        # Look for the website in the search results first, or do a specific search
        for result in search_results:
            url = result["url"]
            if company_name.lower().replace(" ", "") in url.lower() and not any(x in url.lower() for x in ["linkedin.com", "twitter.com", "wikipedia.org"]):
                website = url
                break
                
        if not website:
            website = self.find_company_website(company_name)
            
        if website:
            domain = get_domain_from_url(website)

        # 3. Scrape website home page text
        scraped_text = ""
        if website:
            scraped_text = self.scrape_company_page(website)

        # 4. Synthesize with LLM
        prompt = f"Company Name: {company_name}\nWebsite: {website}\n\nSearch Results:\n"
        for i, r in enumerate(search_results[:3]):
            prompt += f"{i+1}. Title: {r['title']}\nURL: {r['url']}\nSnippet: {r['body']}\n\n"
            
        if scraped_text:
            prompt += f"Scraped Page Snippet:\n{scraped_text}\n"

        system_prompt = COMPANY_SUMMARY_SYSTEM_PROMPT.format(company_name=company_name)
        summary = self._call_llm(prompt, system_prompt)

        result = {
            "company_name": company_name,
            "website": website,
            "domain": domain,
            "summary": summary
        }
        
        logger.info(f"Research completed for {company_name}. Website: {website}")
        return result
