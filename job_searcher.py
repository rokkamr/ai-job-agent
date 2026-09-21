"""
job_searcher.py
---------------
Fetches job listings from multiple free sources:
  1. RemoteOK       — Free, no API key needed (remote jobs)
  2. Arbeitnow      — Free, no API key needed (remote + hybrid)
  3. JSearch        — RapidAPI free tier (200 req/month)  [optional]
  4. Adzuna India   — Free API key required (1000 req/month) [optional]

All results are normalized into a common format and deduplicated.
"""

import hashlib
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

import requests

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "AIJobFinderAgent/1.0 (personal job search tool)"
}


class JobSearcher:
    def __init__(self, config: dict):
        self.config = config
        self.prefs = config["job_preferences"]
        self.apis = config.get("apis", {})
        self.max_fetch = self.prefs.get("max_jobs_to_fetch", 50)

    def search(self, profile: dict) -> list[dict]:
        """Search all sources including LinkedIn, Naukri, Foundit, Indeed, RemoteOK, Arbeitnow."""
        all_jobs = []
        seen_ids = set()

        role_queries = profile.get("role_queries", ["software developer"])
        primary_skills = profile.get("primary_skills", [])
        location = profile.get("preferred_location", "Hyderabad")

        # Build search queries
        queries = self._build_queries(role_queries, primary_skills)
        log.info(f"   Search queries: {queries[:3]}... | Target Location: {location}")

        # Source 1: LinkedIn (Public Jobs API - No Key Required)
        log.info("   📡 Fetching from LinkedIn Jobs...")
        linkedin_jobs = self._search_linkedin(queries, location)
        all_jobs += self._dedup(linkedin_jobs, seen_ids)
        log.info(f"      → {len(linkedin_jobs)} jobs from LinkedIn")

        # Source 2: Naukri & Foundit Web Search
        log.info("   📡 Fetching from Naukri & Foundit (Monster India)...")
        portal_jobs = self._search_portals(queries, location)
        all_jobs += self._dedup(portal_jobs, seen_ids)
        log.info(f"      → {len(portal_jobs)} jobs from Naukri & Foundit")

        # Source 3: RemoteOK (always available, no auth)
        log.info("   📡 Fetching from RemoteOK...")
        remoteok_jobs = self._search_remoteok(primary_skills)
        all_jobs += self._dedup(remoteok_jobs, seen_ids)
        log.info(f"      → {len(remoteok_jobs)} jobs from RemoteOK")

        # Source 4: Arbeitnow (always available, no auth)
        log.info("   📡 Fetching from Arbeitnow...")
        arbeitnow_jobs = self._search_arbeitnow(queries)
        all_jobs += self._dedup(arbeitnow_jobs, seen_ids)
        log.info(f"      → {len(arbeitnow_jobs)} jobs from Arbeitnow")

        # Source 5: JSearch via RapidAPI (optional)
        if self.apis.get("rapidapi_key"):
            log.info("   📡 Fetching from JSearch (RapidAPI)...")
            jsearch_jobs = self._search_jsearch(queries)
            all_jobs += self._dedup(jsearch_jobs, seen_ids)
            log.info(f"      → {len(jsearch_jobs)} jobs from JSearch")

        # Source 6: Adzuna India (optional)
        if self.apis.get("adzuna_app_id") and self.apis.get("adzuna_app_key"):
            log.info("   📡 Fetching from Adzuna India...")
            adzuna_jobs = self._search_adzuna(queries)
            all_jobs += self._dedup(adzuna_jobs, seen_ids)
            log.info(f"      → {len(adzuna_jobs)} jobs from Adzuna")

        log.info(f"   📊 Total unique jobs found across all portals: {len(all_jobs)}")
        return all_jobs

    # ------------------------------------------------------------------ #
    #  Query builder                                                        #
    # ------------------------------------------------------------------ #

    def _build_queries(self, role_queries: list, skills: list) -> list[str]:
        """Build a list of search query strings."""
        queries = list(role_queries)
        # Add skill-based queries for top skills
        for skill in skills[:3]:
            queries.append(f"{skill} developer")
        return list(dict.fromkeys(queries))[:6]  # Deduplicate, max 6

    # ------------------------------------------------------------------ #
    #  Source 1: RemoteOK                                                  #
    # ------------------------------------------------------------------ #

    def _search_remoteok(self, skills: list) -> list[dict]:
        """Fetch remote jobs from RemoteOK (no auth needed)."""
        jobs = []
        tags = skills[:4]  # Use top 4 skills as tags

        for tag in tags:
            try:
                url = f"https://remoteok.com/api?tag={tag.lower().replace(' ', '-')}"
                resp = requests.get(url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                # First item is a legal notice
                for item in data[1:] if data else []:
                    job = self._normalize_remoteok(item)
                    if job:
                        jobs.append(job)
                time.sleep(0.5)  # Be polite
            except Exception as e:
                log.warning(f"RemoteOK error for tag '{tag}': {e}")
                continue

        return jobs[:self.max_fetch]

    def _normalize_remoteok(self, item: dict) -> Optional[dict]:
        if not item.get("position"):
            return None
        return {
            "id": f"remoteok-{item.get('id', '')}",
            "title": item.get("position", ""),
            "company": item.get("company", "Unknown"),
            "location": "Remote",
            "description": self._strip_html(item.get("description", "")),
            "url": item.get("url", ""),
            "salary": self._parse_salary_remoteok(item),
            "posted_date": self._parse_epoch(item.get("epoch", 0)),
            "job_type": "remote",
            "source": "RemoteOK",
            "tags": item.get("tags", []),
        }

    def _parse_salary_remoteok(self, item: dict) -> str:
        lo = item.get("salary_min")
        hi = item.get("salary_max")
        if lo and hi:
            return f"${lo:,} – ${hi:,}"
        return ""

    # ------------------------------------------------------------------ #
    #  Source 2: Arbeitnow                                                 #
    # ------------------------------------------------------------------ #

    def _search_arbeitnow(self, queries: list) -> list[dict]:
        """Fetch jobs from Arbeitnow free API (no auth needed)."""
        jobs = []
        job_types_filter = self.prefs.get("job_types", ["remote", "hybrid"])
        remote_filter = "remote" in job_types_filter

        for query in queries[:3]:
            try:
                params = {
                    "q": query,
                    "remote": str(remote_filter).lower(),
                    "page": 1,
                }
                resp = requests.get(
                    "https://www.arbeitnow.com/api/job-board-api",
                    params=params,
                    headers=HEADERS,
                    timeout=15,
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                for item in data.get("data", []):
                    job = self._normalize_arbeitnow(item)
                    if job:
                        jobs.append(job)
                time.sleep(0.5)
            except Exception as e:
                log.warning(f"Arbeitnow error for query '{query}': {e}")
                continue

        return jobs[:self.max_fetch]

    def _normalize_arbeitnow(self, item: dict) -> Optional[dict]:
        if not item.get("title"):
            return None
        location = item.get("location", "Remote") or "Remote"
        is_remote = item.get("remote", False)
        job_type = "remote" if is_remote else "hybrid"

        return {
            "id": f"arbeitnow-{item.get('slug', item.get('title', '')[:20])}",
            "title": item.get("title", ""),
            "company": item.get("company_name", "Unknown"),
            "location": location if not is_remote else f"Remote ({location})",
            "description": self._strip_html(item.get("description", "")),
            "url": item.get("url", ""),
            "salary": "",
            "posted_date": self._parse_ts(item.get("created_at", 0)),
            "job_type": job_type,
            "source": "Arbeitnow",
            "tags": item.get("tags", []),
        }

    # ------------------------------------------------------------------ #
    #  Source 3: JSearch via RapidAPI (optional)                           #
    # ------------------------------------------------------------------ #

    def _search_jsearch(self, queries: list) -> list[dict]:
        """Fetch jobs from JSearch via RapidAPI."""
        jobs = []
        location = self.prefs.get("location", "Hyderabad")
        job_types = self.prefs.get("job_types", ["remote", "hybrid"])
        employment_types = ",".join(
            "FULLTIME" for _ in job_types
        )

        for query in queries[:3]:
            try:
                resp = requests.get(
                    "https://jsearch.p.rapidapi.com/search",
                    headers={
                        "x-rapidapi-key": self.apis["rapidapi_key"],
                        "x-rapidapi-host": "jsearch.p.rapidapi.com",
                    },
                    params={
                        "query": f"{query} {location}",
                        "page": "1",
                        "num_pages": "1",
                        "date_posted": "today",
                        "employment_types": employment_types,
                    },
                    timeout=20,
                )
                if resp.status_code != 200:
                    log.warning(f"JSearch HTTP {resp.status_code}")
                    continue
                for item in resp.json().get("data", []):
                    job = self._normalize_jsearch(item)
                    if job:
                        jobs.append(job)
                time.sleep(1)
            except Exception as e:
                log.warning(f"JSearch error for '{query}': {e}")
        return jobs[:self.max_fetch]

    def _normalize_jsearch(self, item: dict) -> Optional[dict]:
        if not item.get("job_title"):
            return None
        is_remote = item.get("job_is_remote", False)
        return {
            "id": f"jsearch-{item.get('job_id', '')}",
            "title": item.get("job_title", ""),
            "company": item.get("employer_name", "Unknown"),
            "location": (
                "Remote" if is_remote
                else f"{item.get('job_city', '')}, {item.get('job_country', '')}"
            ),
            "description": item.get("job_description", "")[:3000],
            "url": item.get("job_apply_link") or item.get("job_google_link", ""),
            "salary": self._jsearch_salary(item),
            "posted_date": item.get("job_posted_at_datetime_utc", "")[:10],
            "job_type": "remote" if is_remote else "hybrid",
            "source": "JSearch",
            "tags": [],
        }

    def _jsearch_salary(self, item: dict) -> str:
        lo = item.get("job_min_salary")
        hi = item.get("job_max_salary")
        period = item.get("job_salary_period", "YEAR")
        currency = item.get("job_salary_currency", "USD")
        if lo and hi:
            return f"{currency} {lo:,.0f}–{hi:,.0f}/{period.lower()}"
        return ""

    # ------------------------------------------------------------------ #
    #  Source 4: Adzuna India (optional)                                   #
    # ------------------------------------------------------------------ #

    def _search_adzuna(self, queries: list) -> list[dict]:
        """Fetch jobs from Adzuna India."""
        jobs = []
        location = self.prefs.get("location", "Hyderabad")

        for query in queries[:3]:
            try:
                resp = requests.get(
                    "https://api.adzuna.com/v1/api/jobs/in/search/1",
                    params={
                        "app_id": self.apis["adzuna_app_id"],
                        "app_key": self.apis["adzuna_app_key"],
                        "what": query,
                        "where": location,
                        "results_per_page": 20,
                        "max_days_old": 1,
                        "sort_by": "date",
                        "full_time": 1,
                    },
                    headers=HEADERS,
                    timeout=20,
                )
                if resp.status_code != 200:
                    continue
                for item in resp.json().get("results", []):
                    job = self._normalize_adzuna(item)
                    if job:
                        jobs.append(job)
                time.sleep(0.5)
            except Exception as e:
                log.warning(f"Adzuna error for '{query}': {e}")
        return jobs[:self.max_fetch]

    def _normalize_adzuna(self, item: dict) -> Optional[dict]:
        if not item.get("title"):
            return None
        sal_min = item.get("salary_min")
        sal_max = item.get("salary_max")
        salary = f"₹{sal_min:,.0f}–₹{sal_max:,.0f}" if sal_min and sal_max else ""
        return {
            "id": f"adzuna-{item.get('id', '')}",
            "title": item.get("title", ""),
            "company": item.get("company", {}).get("display_name", "Unknown"),
            "location": item.get("location", {}).get("display_name", "India"),
            "description": item.get("description", "")[:3000],
            "url": item.get("redirect_url", ""),
            "salary": salary,
            "posted_date": item.get("created", "")[:10],
            "job_type": "hybrid",
            "source": "Adzuna",
            "tags": item.get("category", {}).get("label", "").split(", "),
        }

    # ------------------------------------------------------------------ #
    #  Source 5: LinkedIn Public Jobs (no auth required)                   #
    # ------------------------------------------------------------------ #

    def _search_linkedin(self, queries: list, location: str) -> list[dict]:
        """Fetch live job listings directly from LinkedIn Public Guest API."""
        import urllib.parse
        from bs4 import BeautifulSoup
        jobs = []

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        for query in queries[:4]:
            try:
                url = (
                    f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                    f"?keywords={urllib.parse.quote(query)}&location={urllib.parse.quote(location)}&start=0"
                )
                resp = requests.get(url, headers=headers, timeout=12)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.find_all("li")
                for card in cards:
                    title_el = card.find("h3", class_="base-search-card__title")
                    comp_el = card.find("h4", class_="base-search-card__subtitle")
                    loc_el = card.find("span", class_="job-search-card__location")
                    link_el = card.find("a", class_="base-card__full-link")

                    if title_el and comp_el and link_el:
                        title = title_el.text.strip()
                        comp = comp_el.text.strip()
                        loc = loc_el.text.strip() if loc_el else location
                        raw_url = link_el["href"].split("?")[0]

                        jobs.append({
                            "id": f"linkedin-{hash(raw_url)}",
                            "title": title,
                            "company": comp,
                            "location": loc,
                            "description": f"{title} role at {comp} in {loc}. Apply on LinkedIn.",
                            "url": raw_url,
                            "salary": "",
                            "posted_date": "Recently",
                            "job_type": "hybrid" if "remote" not in loc.lower() else "remote",
                            "source": "LinkedIn",
                            "tags": ["LinkedIn", "Direct Apply"],
                        })
                time.sleep(0.5)
            except Exception as e:
                log.warning(f"LinkedIn search error for '{query}': {e}")

        return jobs[:self.max_fetch]

    # ------------------------------------------------------------------ #
    #  Source 6: Naukri & Foundit (Monster India) Web Search             #
    # ------------------------------------------------------------------ #

    def _search_portals(self, queries: list, location: str) -> list[dict]:
        """Fetch job postings from Naukri and Foundit via web portal search."""
        import urllib.parse
        from bs4 import BeautifulSoup
        jobs = []

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        portals = [
            ("naukri.com", "Naukri"),
            ("foundit.in", "Foundit"),
            ("indeed.com", "Indeed")
        ]

        for query in queries[:3]:
            for domain, source_name in portals:
                try:
                    search_q = f"site:{domain} {query} {location}"
                    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(search_q)}"
                    resp = requests.get(url, headers=headers, timeout=10)
                    if resp.status_code != 200:
                        continue

                    soup = BeautifulSoup(resp.text, "html.parser")
                    for result in soup.find_all("div", class_="result__body"):
                        a_title = result.find("a", class_="result__a")
                        snippet_el = result.find("a", class_="result__snippet")
                        if a_title:
                            t_text = a_title.text.strip()
                            raw_link = a_title.get("href", "")
                            if "uddg=" in raw_link:
                                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw_link).query)
                                real_link = parsed.get("uddg", [raw_link])[0]
                            else:
                                real_link = raw_link

                            if domain in real_link and ("job" in real_link or "search" in real_link or "desc" in real_link):
                                snippet = snippet_el.text.strip() if snippet_el else f"{t_text} listing on {source_name}."
                                jobs.append({
                                    "id": f"{source_name.lower()}-{hash(real_link)}",
                                    "title": t_text.replace(f" - {source_name}", "").replace(" ...", "").strip(),
                                    "company": f"{source_name} Partner",
                                    "location": location,
                                    "description": snippet,
                                    "url": real_link,
                                    "salary": "",
                                    "posted_date": "Recently",
                                    "job_type": "hybrid",
                                    "source": source_name,
                                    "tags": [source_name, "India"],
                                })
                    time.sleep(0.5)
                except Exception as e:
                    log.warning(f"Portal search error for {domain} '{query}': {e}")

        return jobs[:self.max_fetch]

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _dedup(self, new_jobs: list, seen_ids: set) -> list:
        result = []
        for job in new_jobs:
            jid = job.get("id") or self._make_id(job)
            if jid not in seen_ids:
                seen_ids.add(jid)
                job["id"] = jid
                result.append(job)
        return result

    def _make_id(self, job: dict) -> str:
        key = f"{job.get('title', '')}{job.get('company', '')}{job.get('url', '')}"
        return hashlib.md5(key.encode()).hexdigest()

    def _strip_html(self, html: str) -> str:
        import re
        return re.sub(r"<[^>]+>", " ", html or "").strip()

    def _parse_epoch(self, epoch) -> str:
        try:
            return datetime.fromtimestamp(int(epoch)).strftime("%Y-%m-%d")
        except Exception:
            return datetime.now().strftime("%Y-%m-%d")

    def _parse_ts(self, ts) -> str:
        try:
            return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
        except Exception:
            return datetime.now().strftime("%Y-%m-%d")
