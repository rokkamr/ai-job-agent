import os
import sys

# Add current directory to python path for Vercel
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app

# Export FastAPI instance for Vercel & ASGI servers
app = app

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("main:app", host=host, port=port, reload=True)
