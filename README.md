# 🤖 AI Resume Job Finder

An AI agent that reads your PDF resume, searches multiple job boards daily, scores each job using Google Gemini AI, and emails you the top matches every morning.

---

## ✨ Features

- 📄 **Smart Resume Parsing** — Reads your PDF resume and extracts skills, experience, and job titles using Gemini AI
- 🔍 **Multi-Source Job Search** — Searches RemoteOK, Arbeitnow (free, no key needed), + JSearch/Adzuna (optional)
- 🤖 **AI Match Scoring** — Scores each job 0–100%, explains why you're a match, lists skill gaps
- ✍️ **Cover Letter Snippets** — Generates a personalized cover letter opener for each job
- 📧 **Email Delivery** — Sends a beautiful HTML report to your inbox every morning
- 📅 **Fully Automated** — Windows Task Scheduler runs it daily without any manual steps

---

## 🚀 Quick Start

### 1. Open a terminal in this folder

```
cd C:\Users\rajar\.gemini\antigravity\scratch\resume_agent
```

### 2. Run the setup wizard

```
python setup.py
```

The wizard will:
- Install all Python dependencies
- Ask for your Gemini API key (free: https://aistudio.google.com/app/apikey)
- Configure your Gmail for email delivery
- Set the daily run time (default: 8:00 AM)
- Register the Windows Task Scheduler task

### 3. Place your resume

Copy your PDF resume to:
```
resume\resume.pdf
```

### 4. Test it!

```
python agent.py --test
```

This runs with mock jobs (no API calls) to verify everything works. Check `output/` for the HTML report.

### 5. Full run

```
python agent.py
```

---

## 📁 Project Structure

```
resume_agent/
├── resume/
│   └── resume.pdf          ← Put your resume here!
├── output/
│   └── job_report_YYYY-MM-DD.html
├── agent.py                ← Main orchestrator
├── resume_parser.py        ← PDF parsing + Gemini extraction
├── job_searcher.py         ← Multi-source job fetching
├── job_matcher.py          ← AI scoring and ranking
├── reporter.py             ← HTML report + Gmail delivery
├── scheduler.py            ← Windows Task Scheduler
├── setup.py                ← One-time setup wizard
├── config.yaml             ← All settings
└── requirements.txt
```

---

## ⚙️ Configuration

Edit `config.yaml` to customize everything:

```yaml
job_preferences:
  location: "Hyderabad"
  job_types: [remote, hybrid]
  experience_years: 1.4
  max_jobs_to_report: 15
  min_match_score: 40      # Only show jobs above this score

email:
  enabled: true
  sender_email: your@gmail.com
  sender_password: "your-app-password"

schedule:
  time: "08:00"            # Daily run time
```

---

## 🔑 API Keys

| Service | Required | Cost | Get Key |
|---|---|---|---|
| Google Gemini | **Yes** | Free | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| JSearch (RapidAPI) | Optional | Free 200 req/mo | [rapidapi.com](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) |
| Adzuna India | Optional | Free 1000 req/mo | [developer.adzuna.com](https://developer.adzuna.com/) |
| Gmail | **Yes (for email)** | Free | [App Password Guide](https://support.google.com/accounts/answer/185833) |

> RemoteOK and Arbeitnow work with **no API key needed**!

---

## 🔧 Useful Commands

```bash
# Run the agent now
python agent.py

# Test without real job searches
python agent.py --test

# Check scheduled task status
python scheduler.py --status

# Update scheduled task time (edit config.yaml first, then:)
python scheduler.py

# Remove scheduled task
python scheduler.py --remove

# Re-run setup
python setup.py
```

---

## 📧 Gmail Setup (App Password)

1. Go to [Google Account](https://myaccount.google.com) → **Security**
2. Enable **2-Step Verification** if not already enabled
3. Go to **Security** → **App passwords**
4. Select app: **Mail**, device: **Windows Computer**
5. Copy the 16-character password
6. Paste it as `sender_password` in `config.yaml`

---

## 🛠️ Troubleshooting

**Resume not found:** Place your PDF at `resume/resume.pdf`

**Gemini API error:** Get your free key at https://aistudio.google.com/app/apikey

**Email not sending:** Make sure you're using an App Password, not your regular Gmail password

**No jobs found:** Add optional API keys (JSearch, Adzuna) for more sources

**Low match scores:** Lower `min_match_score` in config.yaml (try 30)
