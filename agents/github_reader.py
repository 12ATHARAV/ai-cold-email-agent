import os
import json
import time
import requests
from pathlib import Path
from config import MY_GITHUB_USERNAME
from utils.logger import setup_logger

logger = setup_logger(__name__)

CACHE_FILE = Path(__file__).resolve().parent.parent / "logs" / "github_cache.json"
CACHE_EXPIRY_SECONDS = 86400  # 24 hours

class GitHubReader:
    def __init__(self, username: str = MY_GITHUB_USERNAME, token: str = None):
        self.username = username
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.headers = {
            "Accept": "application/vnd.github+json"
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def _get_cache(self) -> list | None:
        """Retrieve repos from cache if valid."""
        if not CACHE_FILE.exists():
            return None
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if time.time() - data.get("timestamp", 0) < CACHE_EXPIRY_SECONDS:
                    logger.info("Retrieved GitHub repositories from local cache.")
                    return data.get("repos")
        except Exception as e:
            logger.warning(f"Failed to read GitHub cache: {e}")
        return None

    def _set_cache(self, repos: list) -> None:
        """Save repos to cache."""
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    "timestamp": time.time(),
                    "repos": repos
                }, f, indent=4, ensure_ascii=False)
            logger.info("Saved GitHub repositories to local cache.")
        except Exception as e:
            logger.warning(f"Failed to write GitHub cache: {e}")

    def fetch_repositories(self, force_refresh: bool = False) -> list[dict]:
        """Fetches public repositories for the configured user, using cache if available."""
        if not force_refresh:
            cached = self._get_cache()
            if cached is not None:
                return cached

        logger.info(f"Fetching public repositories for GitHub user {self.username}...")
        url = f"https://api.github.com/users/{self.username}/repos"
        
        try:
            # We want to fetch repos sorted by updated time
            params = {
                "sort": "updated",
                "per_page": 30
            }
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"GitHub API returned status code {response.status_code}: {response.text}")
                # Try to use expired cache if available before failing
                expired_cache = self._read_any_cache()
                if expired_cache:
                    logger.info("GitHub API failed; falling back to expired cache.")
                    return expired_cache
                return []
                
            repos_data = response.json()
            repos = []
            for repo in repos_data:
                # Exclude forks to focus on original repositories
                if repo.get("fork"):
                    continue
                repos.append({
                    "name": repo.get("name"),
                    "description": repo.get("description") or "No description provided.",
                    "html_url": repo.get("html_url"),
                    "language": repo.get("language") or "Other",
                    "stars": repo.get("stargazers_count", 0),
                    "updated_at": repo.get("updated_at")
                })
            
            self._set_cache(repos)
            return repos
            
        except Exception as e:
            logger.error(f"Error fetching repositories from GitHub: {e}")
            expired_cache = self._read_any_cache()
            if expired_cache:
                return expired_cache
            return []

    def _read_any_cache(self) -> list | None:
        """Reads cache regardless of expiration."""
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("repos")
            except Exception:
                pass
        return None

    def get_formatted_summary(self, limit: int = 5) -> str:
        """Gets a clean markdown summary of the top repositories to pass to the LLM."""
        repos = self.fetch_repositories()
        if not repos:
            return "No GitHub repositories found."
            
        # Sort by stars, then by recency
        repos.sort(key=lambda x: (x['stars'], x['updated_at']), reverse=True)
        
        summary = "Atharv's top original GitHub projects:\n"
        for repo in repos[:limit]:
            summary += f"- **{repo['name']}** (Language: {repo['language']}, Stars: {repo['stars']}): {repo['description']} - Link: {repo['html_url']}\n"
        return summary
