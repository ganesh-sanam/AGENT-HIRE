"""
AgentHire AI Frontend Launcher.
Starts a simple HTTP server or uvicorn instance to serve the frontend and API.
"""

import os
import sys
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

if __name__ == "__main__":
    import uvicorn
    print("Starting AgentHire AI Web Application at http://127.0.0.1:8000 ...")
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
