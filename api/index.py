import os
import sys

# Ensure root directory is on python path for Vercel serverless environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app

# Export FastAPI instance for Vercel
app = app
