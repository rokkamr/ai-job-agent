import json
from app.database.database import SessionLocal
from app.database.models import Job

def export():
    db = SessionLocal()
    jobs = db.query(Job).all()
    seed = []
    for j in jobs:
        seed.append({
            "source": j.source,
            "external_job_id": j.external_job_id,
            "title": j.title,
            "company": j.company,
            "location": j.location,
            "url": j.url,
            "description": j.description,
            "posted_date": j.posted_date,
            "match_score": j.match_score,
            "match_details": j.match_details,
            "fingerprint": j.fingerprint,
            "status": j.status
        })
    with open("app/database/seed_jobs.json", "w", encoding="utf-8") as f:
        json.dump(seed, f, indent=2)
    print(f"Exported {len(seed)} seed jobs to app/database/seed_jobs.json")
    db.close()

if __name__ == "__main__":
    export()
