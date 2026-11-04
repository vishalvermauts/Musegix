# Musegix Project Memory Summary

## High-Level Objective
Build **Musegix**, an intelligent multi-model routing, AST context pruning, and staleness-aware agent memory gateway for `bolt.diy`, submitted to the Meta Global AI Developer Hackathon.

## Integrated Engines
- **Ysolveth**: INT8 ONNX Model Complexity Classifier (<5ms CPU)
- **PolyFabric**: Tree-sitter AST Context Pruner & RRF Search
- **Veylqora**: C++20 SQLite WAL AST-bounded Agent Memory Engine
- **Frontend UI**: `bolt.diy` (Browser IDE)

## Development Environment
- Cloud execution on Docker Sandboxes: `musegix-builder` (8 CPUs, 16 GiB RAM).
- Remote Git Repo: `https://github.com/vishalvermauts/Musegix.git`
- CI/CD: GitHub Actions running automated test and certification gates.
