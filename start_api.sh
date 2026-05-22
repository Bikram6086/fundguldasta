#!/bin/bash
cd /home/hpbikram6086/fundguldasta
source venv/bin/activate
exec python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000
