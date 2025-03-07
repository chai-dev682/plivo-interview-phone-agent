from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from app.routers.interview import router as interview_router
from app.services.mysql import mysql_service
from app.services.Plivo import plivo_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize services
    mysql_service.initialize()
    yield
    # Shutdown: Clean up resources if needed
    pass

# Create FastAPI app
app = FastAPI(
    title="Interview API",
    description="API for managing automated phone interviews",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    # In production, replace with specific origins
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include HTTP routers
app.include_router(interview_router)

# WebSocket endpoint for Plivo
@app.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket):
    print('Plivo connection incoming')
    await plivo_service.plivo_receiver(websocket)

@app.get("/")
async def health_check():
    return {"status": "success", "description": "API for managing automated phone interviews"}

if __name__ == "__main__":
    uvicorn.run("manage:app", host="0.0.0.0", port=5000, reload=True)
