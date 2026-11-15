import sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv("APP_HOST", "127.0.0.1"),
        port=int(os.getenv("APP_PORT", "8000")),
        access_log=False,
    )
