from pathlib import Path
from dotenv import load_dotenv

# Ensure .env is loaded before anything else
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

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

