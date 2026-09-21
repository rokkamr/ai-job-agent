from app.database.database import SessionLocal
from app.database.models import Job
from app.agents.resume_agent import ResumeAgent
from app.agents.matching_agent import MatchingAgent
from app.agents.resume_tailor_agent import ResumeTailorAgent

def main():
    db = SessionLocal()
    kb = ResumeAgent().process_master_resume()

    # Reset job statuses to DISCOVERED to re-evaluate with calibrated scorer
    jobs = db.query(Job).all()
    for j in jobs:
        j.status = "DISCOVERED"
    db.commit()

    print(f"Reset {len(jobs)} jobs to DISCOVERED. Running MatchingAgent...")
    matching_agent = MatchingAgent(db, kb, min_score=70.0)
    res = matching_agent.evaluate_discovered_jobs()
    print(f"Qualified Jobs: {res['qualified_count']}")

    print("Tailoring resumes for qualified jobs...")
    tailor_agent = ResumeTailorAgent(db, kb)
    for q_job in res['qualified_jobs']:
        tailor_res = tailor_agent.tailor_resume_for_job(q_job.id)
        print(f"  -> Tailored Job {q_job.id} ({q_job.title} at {q_job.company}): Match Score = {q_job.match_score}%")

    db.close()

if __name__ == "__main__":
    main()
