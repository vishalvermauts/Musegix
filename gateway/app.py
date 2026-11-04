from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from gateway.routes import router

app = FastAPI(
    title="Musegix Gateway",
    description="Intelligent AI IDE Router, AST Context Pruner & Agent Memory Engine for bolt.diy",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/")
async def root():
    return {
        "service": "Musegix Gateway",
        "status": "ok",
        "version": "1.0.0"
    }
