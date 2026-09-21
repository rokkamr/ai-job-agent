import os
import json
from app.resume.parser import ResumeParser


class ResumeAgent:
    def __init__(self, resume_path: str = None):
        self.parser = ResumeParser(resume_path)

    def process_master_resume(self) -> dict:
        """
        Parses master resume and returns the Candidate Knowledge Base.
        """
        kb = self.parser.get_candidate_knowledge_base()
        
        # Save cache to resume/candidate_kb.json for inspection
        os.makedirs("resume", exist_ok=True)
        kb_path = os.path.join("resume", "candidate_kb.json")
        with open(kb_path, "w", encoding="utf-8") as f:
            json.dump(kb, f, indent=2)
            
        return kb
