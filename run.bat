@echo off
echo Activating virtual environment...
if not exist venv\Scripts\activate.bat (
    echo Virtual environment not found. Creating one...
    python -m venv venv
)
call venv\Scripts\activate.bat

echo Installing dependencies...
pip install -r requirements.txt

echo Running main.py...
python main.py
pause
