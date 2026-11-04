# Phase 1: Bootstrap, Cloud Sandbox Provisioning & Gateway Scaffolding

> **Status:** Active Execution  
> **Objective:** Establish the development environment inside Docker Cloud Sandbox (`musegix-builder`), clone dependencies, scaffold the FastAPI OpenAI-compatible proxy gateway, set up GitHub Actions CI workflow, and pass the Phase 1 Certification Gate.

---

## 1. Cloud Sandbox Architecture & Execution Rules

To preserve local PC resources and prevent thermal or memory bottlenecks:
- **Sandbox Instance:** `sbx --cloud exec musegix-builder <cmd>`
- **Specs:** 8 x86_64 vCPUs, 16 GiB RAM, Docker-in-Docker capable.
- **Working Directory:** `/workspace/Musegix` inside cloud sandbox.

### Provisioning Script (`scripts/cloud_setup.sh`)
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "==> Configuring Musegix Cloud Environment on Docker Sandboxes..."
mkdir -p /workspace/Musegix
cd /workspace/Musegix

# Install Python 3.11+, C++20 toolchain, CMake, Node 20+, and pnpm
apt-get update -qq && apt-get install -y -qq \
    git curl build-essential cmake ninja-build python3-pip python3-venv \
    pkg-config libsqlite3-dev

# Install Node & pnpm for bolt.diy
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y -qq nodejs
npm install -g pnpm

# Clone component repositories for integration
mkdir -p components
git clone --depth 1 https://github.com/vishalvermauts/Ysolveth.git components/Ysolveth
git clone --depth 1 https://github.com/vishalvermauts/PolyFabric.git components/PolyFabric
git clone --depth 1 https://github.com/vishalvermauts/Veylqora.git components/Veylqora

echo "==> Cloud Environment successfully provisioned."
```

---

## 2. Gateway Core Architecture (`gateway/`)

The gateway acts as an OpenAI-compatible proxy (`POST /v1/chat/completions`) listening on port 8000.

### Directory Structure
```text
gateway/
├── __init__.py
├── app.py                     # Main FastAPI application
├── config.py                  # Environment & settings loader
├── routes.py                  # /v1/chat/completions and /v1/models endpoints
├── streaming.py               # SSE chunk generator & telemetry injector
└── schemas.py                 # Pydantic models for OpenAI request/response specs
```

### `gateway/config.py`
```python
import os
from pydantic_settings import BaseSettings

class GatewaySettings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    BASETEN_API_KEY: str = os.getenv("BASETEN_API_KEY", "")
    META_API_KEY: str = os.getenv("META_API_KEY", "")
    DEFAULT_MODEL: str = "musecontext-auto"
    YSOLVETH_ONNX_PATH: str = "components/Ysolveth/encoder_int8.onnx"
    YSOLVETH_TOKENIZER_PATH: str = "components/Ysolveth"

settings = GatewaySettings()
```

### `gateway/routes.py`
```python
import time
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from gateway.streaming import stream_chat_completion

router = APIRouter(prefix="/v1")

@router.get("/models")
async def list_models():
    return JSONResponse({
        "object": "list",
        "data": [
            {
                "id": "musecontext-auto",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "musegix-system",
            }
        ]
    })

@router.post("/chat/completions")
async def chat_completions(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    
    stream = body.get("stream", True)
    if stream:
        return StreamingResponse(
            stream_chat_completion(body),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    else:
        raise HTTPException(status_code=501, detail="Non-streaming mode not supported for IDE UI")
```

---

## 3. GitHub Actions CI Configuration (`.github/workflows/ci.yml`)

Ensures every pull request and push compiles cleanly in GitHub Actions:
```yaml
name: Musegix CI Gate

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  validate-gateway:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install Dependencies
        run: |
          pip install --upgrade pip
          pip install -r requirements.txt
      - name: Lint and Unit Tests
        run: |
          pytest tests/ -v
```

---

## 4. Phase 1 Certification Gate Checklist

To certify Phase 1 as COMPLETE, all following gates must pass:
- [ ] **Gate 1.1:** Docker Cloud Sandbox `musegix-builder` is alive, responding, and has full network access.
- [ ] **Gate 1.2:** Component repositories (`Ysolveth`, `PolyFabric`, `Veylqora`) are cloned and verified inside `/workspace/Musegix/components`.
- [ ] **Gate 1.3:** `gateway/app.py` boots cleanly with Uvicorn on port 8000 without missing module errors.
- [ ] **Gate 1.4:** `curl http://localhost:8000/v1/models` returns valid OpenAI-compatible model list JSON.
- [ ] **Gate 1.5:** GitHub repo `https://github.com/vishalvermauts/Musegix.git` has master branch initialized and passing GitHub Actions CI.
