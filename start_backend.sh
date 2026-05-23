#!/bin/bash
cd /Users/bxz/Documents/projects/Argus-Invest
PYTHONPATH=/Users/bxz/Documents/projects/Argus-Invest/backend python3 -m uvicorn backend.app.main:app --reload --port 8000
