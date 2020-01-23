:: Install/Upgrade pip
python -m pip install --upgrade pip --user

:: Create a Python virtual environment as a folder '.env'
python -m venv .env

:: Activate the virtual environment
call .\.env\Scripts\activate.bat

:: Install/Upgrade pip in that virtual environment
python -m pip install --upgrade pip

:: Install the dependencies
pip install -e .