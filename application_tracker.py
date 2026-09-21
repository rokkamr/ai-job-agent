"""
application_tracker.py
-----------------------
Tracks every job application to avoid duplicate submissions.
Persists data in applied_jobs.json in the project directory.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

TRACKER_FILE = "applied_jobs.json"


class ApplicationTracker:
    def __init__(self, tracker_file: str = TRACKER_FILE):
        self.tracker_file = Path(tracker_file)
        self.applied: dict = self._load()

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def _clean_str(self, text: str) -> str:
        """Normalize string for fuzzy comparison."""
        import re
        return re.sub(r'[^a-z0-9]', '', (text or "").lower())

    def _get_fingerprint(self, title: str, company: str) -> str:
        """Generate normalized fingerprint string from title and company."""
        return f"{self._clean_str(company)}:{self._clean_str(title)}"

    def already_applied(self, job_id: str, title: str = "", company: str = "", days_window: int = 30) -> bool:
        """
        Multi-tier deduplication check:
          Tier 1: Exact Job ID / URL match
          Tier 2: Normalized (Company + Title) fingerprint match within `days_window`
        """
        # Tier 1: Exact ID check
        if job_id in self.applied:
            return True

        if not title or not company:
            return False

        # Tier 2: Company + Title fingerprint check with sliding time window
        target_fp = self._get_fingerprint(title, company)
        now = datetime.now()

        for record in self.applied.values():
            rec_title = record.get("job_title", "")
            rec_comp = record.get("company", "")
            rec_fp = self._get_fingerprint(rec_title, rec_comp)

            if target_fp == rec_fp:
                # Check if applied within sliding days window
                applied_at_str = record.get("applied_at")
                if applied_at_str:
                    try:
                        applied_at = datetime.fromisoformat(applied_at_str)
                        days_diff = (now - applied_at).days
                        if days_diff <= days_window:
                            return True
                    except Exception:
                        return True
                else:
                    return True

        return False

    def mark_applied(
        self,
        job_id: str,
        job_title: str,
        company: str,
        method: str,
        status: str,
        notes: str = "",
    ):
        self.applied[job_id] = {
            "job_title": job_title,
            "company": company,
            "fingerprint": self._get_fingerprint(job_title, company),
            "method": method,   # email | web | manual
            "status": status,   # sent | submitted | partial | pending | failed
            "notes": notes,
            "applied_at": datetime.now().isoformat(),
        }
        self._save()
        log.info(f"      Tracked → {job_title} @ {company}  [{method}] [{status}]")

    def get_all(self) -> dict:
        return self.applied

    def summary(self) -> dict:
        total = len(self.applied)
        by_status = {}
        for v in self.applied.values():
            s = v.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1
        return {"total": total, "by_status": by_status}

    # ------------------------------------------------------------------ #
    #  Persistence                                                         #
    # ------------------------------------------------------------------ #

    def _load(self) -> dict:
        if self.tracker_file.exists():
            try:
                return json.loads(self.tracker_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save(self):
        self.tracker_file.write_text(
            json.dumps(self.applied, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
