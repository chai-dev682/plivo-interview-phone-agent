from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn


from app.routers.interview import router as interview_router
from app.routers.call import router as call_router
from app.services.mysql import mysql_service
from app.admin.admin import router as admin_router

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

app.include_router(interview_router)
app.include_router(call_router)
app.include_router(admin_router)

@app.get("/")
async def health_check():
    return {"status": "success", "description": "API for managing automated phone interviews"}

if __name__ == "__main__":
    uvicorn.run("manage:app", host="0.0.0.0", port=5000, reload=True)
