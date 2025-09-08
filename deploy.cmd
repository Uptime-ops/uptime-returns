```batch
@echo off
echo Installing dependencies...
pip install -r requirements.txt
echo Starting application...
cd web
python enhanced_app.py
```