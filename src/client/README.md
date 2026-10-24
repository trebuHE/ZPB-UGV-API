# UGV API Client

This directory contains code for UGV API Client

## Getting started

Create venv, source and install dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
Update config.yaml by placing proper API ip.
```yaml
api:
  base_url: "http://localhost:8000" # Replace with your API host IP if running remotely
```
Run the app using:
```bash
python3 main.py
```