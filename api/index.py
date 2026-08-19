import sys
import os
import traceback

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from api.main import app
except Exception as e:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    app = FastAPI()
    error_detail = traceback.format_exc()

    @app.get("/{full_path:path}")
    def fallback(full_path: str):
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to initialize API in Vercel Serverless",
                "detail": error_detail
            }
        )
