from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logger import logger

app = FastAPI(
    title="Interview Phone Server",
    description="Interview Phone Server using Plivo",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Interview Phone Server using Plivo"}

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting server on 5000 port")
    uvicorn.run(
        "manage:app",
        host="0.0.0.0",
        port=5000,
        reload=True
    )
