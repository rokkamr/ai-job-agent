import os
import json
import logging
import asyncio
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from app.database.database import get_db, init_db
from app.database.models import Job, Application, ResumeVersion, AgentRun, AgentLog
from app.scheduler.daily_job import execute_daily_workflow, start_scheduler

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

init_db()

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    logger.info("FastAPI backend & APScheduler started successfully.")
    yield

app = FastAPI(title="AI Job Application Agent Dashboard", version="1.0.0", lifespan=lifespan)

@app.get("/api/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_found = db.query(Job).count()
    qualified = db.query(Job).filter(Job.status.in_(["QUALIFIED", "TAILORED", "APPLIED"])).count()
    submitted = db.query(Job).filter(Job.status == "APPLIED").count()
    manual_review = db.query(Job).filter(Job.status == "MANUAL_ACTION_REQUIRED").count()
    failed = db.query(Job).filter(Job.status == "FAILED").count()

    latest_run = db.query(AgentRun).order_by(AgentRun.id.desc()).first()

    return {
        "total_found": total_found,
        "qualified": qualified,
        "submitted": submitted,
        "manual_review": manual_review,
        "failed": failed,
        "latest_run": {
            "id": latest_run.id if latest_run else None,
            "status": latest_run.status if latest_run else "N/A",
            "date": latest_run.run_date if latest_run else "N/A"
        }
    }

@app.get("/api/jobs")
def get_jobs(status: str = None, db: Session = Depends(get_db)):
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == status)
    jobs = query.order_by(Job.id.desc()).all()
    
    res = []
    for j in jobs:
        details = json.loads(j.match_details) if j.match_details else {}
        res.append({
            "id": j.id,
            "title": j.title,
            "company": j.company,
            "location": j.location,
            "source": j.source,
            "url": j.url,
            "match_score": j.match_score,
            "status": j.status,
            "match_details": details,
            "created_at": j.created_at.strftime("%Y-%m-%d %H:%M") if j.created_at else ""
        })
    return res

@app.get("/api/jobs/{job_id}")
def get_job_detail(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    resume_ver = db.query(ResumeVersion).filter(ResumeVersion.job_id == job.id).first()
    app_rec = db.query(Application).filter(Application.job_id == job.id).first()

    return {
        "job": {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "source": job.source,
            "url": job.url,
            "description": job.description,
            "match_score": job.match_score,
            "status": job.status,
            "match_details": json.loads(job.match_details) if job.match_details else {}
        },
        "resume_version": {
            "docx": resume_ver.file_path_docx if resume_ver else None,
            "pdf": resume_ver.file_path_pdf if resume_ver else None,
            "truth_verified": resume_ver.truth_verified if resume_ver else True
        } if resume_ver else None,
        "application": {
            "status": app_rec.status if app_rec else "N/A",
            "applied_at": app_rec.applied_at.strftime("%Y-%m-%d %H:%M") if app_rec and app_rec.applied_at else None,
            "error_message": app_rec.error_message if app_rec else None
        } if app_rec else None
    }

@app.post("/api/run-now")
async def trigger_run_now():
    logger.info("Manual trigger received from dashboard UI! Executing daily workflow...")
    asyncio.create_task(execute_daily_workflow())
    return {"status": "SUCCESS", "message": "Daily Job Agent workflow triggered!"}

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>AI Job Application Agent Dashboard</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
      <style>
        body { background-color: #0f172a; color: #f8fafc; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .card-stat { background: #1e293b; border: 1px solid #334155; border-radius: 12px; }
        .stat-val { font-size: 2.2rem; font-weight: 700; color: #38bdf8; }
        .table-custom { background: #1e293b; color: #f8fafc; border-radius: 8px; overflow: hidden; }
        .table-custom th { background: #334155; color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 0.75rem; }
        .badge-applied { background-color: #166534; color: #4ade80; }
        .badge-review { background-color: #854d0e; color: #fde047; }
        .badge-qualified { background-color: #1e40af; color: #93c5fd; }
        .badge-failed { background-color: #991b1b; color: #fca5a5; }
        .btn-run { background: linear-gradient(135deg, #0284c7, #2563eb); border: none; font-weight: 600; }
      </style>
    </head>
    <body class="p-4">
      <div class="container-fluid">
        <div class="d-flex justify-content-between align-items-center mb-4">
          <div>
            <h1 class="h3 font-weight-bold text-white mb-0">🤖 AI Job Application Agent</h1>
            <p class="text-secondary small mb-0">Autonomous Daily Worker • Schedule: 12:00 AM Asia/Kolkata</p>
          </div>
          <button id="run-btn" onclick="triggerRun()" class="btn btn-run text-white px-4 py-2 rounded-pill shadow">▶ Run Agent Now</button>
        </div>

        <!-- Banner Alert -->
        <div id="status-banner" class="alert alert-info border-0 shadow-sm d-none mb-4" style="background: #1e293b; color: #38bdf8; border-left: 4px solid #0284c7 !important;">
          <strong>⚡ Agent Run Active:</strong> Harvesting, deduplicating, evaluating, tailoring & applying to QA jobs... Live updating below!
        </div>

        <!-- Metrics Row -->
        <div class="row g-3 mb-4">
          <div class="col-md-2">
            <div class="card-stat p-3 text-center">
              <div class="text-secondary small">Total Found</div>
              <div class="stat-val" id="stat-found">0</div>
            </div>
          </div>
          <div class="col-md-2">
            <div class="card-stat p-3 text-center">
              <div class="text-secondary small">Matched (70%+)</div>
              <div class="stat-val" id="stat-matched">0</div>
            </div>
          </div>
          <div class="col-md-2">
            <div class="card-stat p-3 text-center">
              <div class="text-secondary small">Applications</div>
              <div class="stat-val text-success" id="stat-applied">0</div>
            </div>
          </div>
          <div class="col-md-3">
            <div class="card-stat p-3 text-center">
              <div class="text-secondary small">Manual Review</div>
              <div class="stat-val text-warning" id="stat-review">0</div>
            </div>
          </div>
          <div class="col-md-3">
            <div class="card-stat p-3 text-center">
              <div class="text-secondary small">Failed</div>
              <div class="stat-val text-danger" id="stat-failed">0</div>
            </div>
          </div>
        </div>

        <!-- Recent Applications Table -->
        <div class="card-stat p-4">
          <h5 class="mb-3 text-white">Recent Discovered & Applied Jobs</h5>
          <div class="table-responsive">
            <table class="table table-dark table-hover table-custom mb-0">
              <thead>
                <tr>
                  <th>Job Title</th>
                  <th>Company</th>
                  <th>Location</th>
                  <th>Source</th>
                  <th>Match Score</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody id="jobs-tbody">
                <tr><td colspan="7" class="text-center text-muted">Loading job records...</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <script>
        let isPollingFast = false;

        async function loadStats() {
          const res = await fetch('/api/dashboard/stats');
          const data = await res.json();
          document.getElementById('stat-found').innerText = data.total_found;
          document.getElementById('stat-matched').innerText = data.qualified;
          document.getElementById('stat-applied').innerText = data.submitted;
          document.getElementById('stat-review').innerText = data.manual_review;
          document.getElementById('stat-failed').innerText = data.failed;
        }

        async function loadJobs() {
          const res = await fetch('/api/jobs');
          const jobs = await res.json();
          const tbody = document.getElementById('jobs-tbody');
          if (jobs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No jobs discovered yet. Click "Run Agent Now" to start!</td></tr>';
            return;
          }
          tbody.innerHTML = jobs.map(j => `
            <tr>
              <td><strong>${j.title}</strong></td>
              <td>${j.company}</td>
              <td>${j.location}</td>
              <td><span class="badge bg-secondary">${j.source}</span></td>
              <td><span class="fw-bold text-info">${j.match_score}%</span></td>
              <td><span class="badge ${getStatusBadge(j.status)}">${j.status}</span></td>
              <td><a href="${j.url}" target="_blank" class="btn btn-sm btn-outline-info">Open URL</a></td>
            </tr>
          `).join('');
        }

        function getStatusBadge(st) {
          if (st === 'APPLIED') return 'badge-applied';
          if (st === 'MANUAL_ACTION_REQUIRED') return 'badge-review';
          if (st === 'QUALIFIED' || st === 'TAILORED') return 'badge-qualified';
          return 'badge-failed';
        }

        async function triggerRun() {
          const btn = document.getElementById('run-btn');
          const banner = document.getElementById('status-banner');
          btn.disabled = true;
          btn.innerText = '⏳ Running Agent...';
          banner.classList.remove('d-none');

          try {
            await fetch('/api/run-now', { method: 'POST' });
          } catch(e) {
            console.error(e);
          }

          // Fast poll every 2 seconds for live progress updates
          const pollInterval = setInterval(async () => {
            await loadStats();
            await loadJobs();
          }, 2000);

          // Stop fast poll after 30 seconds
          setTimeout(() => {
            clearInterval(pollInterval);
            btn.disabled = false;
            btn.innerText = '▶ Run Agent Now';
            banner.classList.add('d-none');
          }, 30000);
        }

        loadStats();
        loadJobs();
        setInterval(() => { loadStats(); loadJobs(); }, 8000);
      </script>
    </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8080"))
    logger.info(f"Starting dashboard server at http://{host}:{port}")
    uvicorn.run("app.main:app", host=host, port=port, reload=True)

