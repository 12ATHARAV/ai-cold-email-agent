import os
import re
import socket
import smtplib
import subprocess
import urllib.parse
import requests
from bs4 import BeautifulSoup
from utils.logger import setup_logger
from utils.helpers import extract_emails_from_text, get_domain_from_url

logger = setup_logger(__name__)

class EmailFinder:
    def __init__(self, hunter_api_key: str = None):
        self.hunter_api_key = hunter_api_key or os.getenv("HUNTER_API_KEY")

    def get_mx_records(self, domain: str) -> list[str]:
        """Finds MX records for a domain using the system's nslookup command (cross-platform, zero dependencies)."""
        if not domain:
            return []
            
        logger.info(f"Looking up MX records for domain: {domain}")
        mx_servers = []
        try:
            # Run nslookup
            if os.name == 'nt':  # Windows
                cmd = ["nslookup", "-type=mx", domain]
            else:  # Linux/Unix
                cmd = ["nslookup", "-query=mx", domain]
                
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            
            # Parse nslookup output
            # Look for lines like: domain.com  MX preference = 10, mail exchanger = mail.domain.com
            # or in Linux: domain.com mail exchanger = 10 mail.domain.com.
            lines = result.stdout.split('\n')
            for line in lines:
                if "mail exchanger" in line.lower() or "exchanger =" in line.lower():
                    # Extract the server name (usually the last word, stripped of trailing dots)
                    parts = line.split()
                    if parts:
                        server = parts[-1].strip('.')
                        # Validate server format
                        if '.' in server:
                            mx_servers.append(server)
            
            # Sort or deduplicate
            mx_servers = list(set(mx_servers))
            logger.info(f"MX records found: {mx_servers}")
            return mx_servers
        except Exception as e:
            logger.error(f"Error looking up MX records for {domain}: {e}")
            return []

    def verify_email_smtp(self, email: str, mx_servers: list[str]) -> bool:
        """Performs SMTP verification (RCPT TO) for a single email address."""
        if not email or not mx_servers:
            return False
            
        logger.info(f"Verifying email via SMTP: {email}")
        for server in mx_servers:
            try:
                # 1. Connect to MX server on SMTP port 25
                # Use a short timeout of 5s to avoid blocking
                host = socket.gethostbyname(server)
                smtp = smtplib.SMTP(timeout=5)
                smtp.connect(host, 25)
                
                # 2. Handshake
                smtp.helo(smtp.local_hostname)
                
                # 3. MAIL FROM (use a generic sender address)
                smtp.mail("info@gmail.com")
                
                # 4. RCPT TO
                code, message = smtp.rcpt(email)
                smtp.quit()
                
                # Code 250 means OK, recipient exists
                # Code 550 means user unknown / rejected
                if code == 250:
                    logger.info(f"SMTP Server {server} accepted recipient: {email} (Code {code})")
                    return True
                else:
                    logger.warning(f"SMTP Server {server} rejected recipient: {email} (Code {code}: {message})")
                    # If it explicitly says user unknown (550), it is a invalid email
                    if code == 550:
                        return False
            except Exception as e:
                logger.debug(f"SMTP verification failed on server {server}: {e}")
                continue
                
        return False

    def query_hunter_api(self, domain: str, first_name: str, last_name: str) -> str | None:
        """Queries the Hunter.io API if an API key is available."""
        if not self.hunter_api_key or not domain:
            return None
            
        logger.info(f"Querying Hunter.io API for {first_name} {last_name} at {domain}...")
        try:
            url = f"https://api.hunter.io/v2/email-finder"
            params = {
                "domain": domain,
                "first_name": first_name,
                "last_name": last_name,
                "api_key": self.hunter_api_key
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                email = data.get("data", {}).get("email")
                if email:
                    logger.info(f"Hunter.io found email: {email}")
                    return email
            else:
                logger.warning(f"Hunter.io API returned HTTP {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"Hunter.io API query failed: {e}")
            
        return None

    def scrape_emails_from_site(self, domain: str) -> list[str]:
        """Scrapes the company website for any email addresses."""
        if not domain:
            return []
            
        logger.info(f"Attempting to scrape emails from domain: {domain}")
        found_emails = []
        
        # Check standard contact pages
        paths = ["", "/contact", "/about", "/team", "/contact-us"]
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        for path in paths:
            url = f"https://{domain}{path}"
            try:
                response = requests.get(url, headers=headers, timeout=5)
                if response.status_code == 200:
                    emails = extract_emails_from_text(response.text)
                    if emails:
                        found_emails.extend(emails)
                        logger.info(f"Found emails on {url}: {emails}")
            except Exception:
                continue
                
        return list(set(found_emails))

    def guess_email_address(self, first_name: str, last_name: str, domain: str) -> str | None:
        """Guesses and validates the email using common corporate pattern guessing."""
        if not first_name or not last_name or not domain:
            return None
            
        f = first_name.lower().strip()
        l = last_name.lower().strip()
        
        # Generate common corporate email patterns
        patterns = [
            f"{f}.{l}@{domain}",        # john.doe@company.com
            f"{f}{l}@{domain}",          # johndoe@company.com
            f"{f[0]}{l}@{domain}",       # jdoe@company.com
            f"{f}{l[0]}@{domain}",       # johnd@company.com
            f"{f[0]}.{l}@{domain}",      # j.doe@company.com
            f"{f}_{l}@{domain}",         # john_doe@company.com
            f"{f}@{domain}"              # john@company.com
        ]
        
        # 1. Get MX records
        mx_servers = self.get_mx_records(domain)
        if not mx_servers:
            logger.warning(f"No MX records found for {domain}. Email guessing skipped.")
            return f"{f}.{l}@{domain}"  # Fallback to default guess
            
        # 2. Verify patterns using SMTP RCPT TO
        logger.info(f"Testing {len(patterns)} guessed email patterns via SMTP...")
        for pattern in patterns:
            # Check if this email pattern is valid
            if self.verify_email_smtp(pattern, mx_servers):
                logger.info(f"Guessed email verified: {pattern}")
                return pattern
                
        # If SMTP verification yields nothing, return the most common pattern as fallback
        return f"{f}.{l}@{domain}"

    def find_email(self, author_name: str, company_domain: str) -> tuple[str, str]:
        """Finds target email address. Returns tuple: (email, confidence_level)"""
        # Split author name into first and last
        name_parts = author_name.strip().split()
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        
        if not company_domain:
            return ("", "low")
            
        # 1. Try Hunter.io (High confidence)
        if self.hunter_api_key and first_name:
            email = self.query_hunter_api(company_domain, first_name, last_name)
            if email:
                return (email, "high (Hunter.io)")
                
        # 2. Try scraping website for emails (Medium/High confidence if matched)
        scraped_emails = self.scrape_emails_from_site(company_domain)
        if scraped_emails:
            # Check if any matches the author's name
            for email in scraped_emails:
                if first_name.lower() in email.lower() or (last_name and last_name.lower() in email.lower()):
                    return (email, "high (website match)")
            # Return first scraped if name split not matched but only one email exists
            if len(scraped_emails) == 1:
                return (scraped_emails[0], "medium (website contact)")

        # 3. Guess and verify via SMTP
        if first_name:
            guessed_email = self.guess_email_address(first_name, last_name, company_domain)
            if guessed_email:
                return (guessed_email, "medium (verified guess)")

        # 4. Fallback to generic corporate inbox if name guess fails
        fallback_email = f"info@{company_domain}"
        return (fallback_email, "low (default)")
