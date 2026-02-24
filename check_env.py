from pathlib import Path
import os
from dotenv import load_dotenv
BASE_DIR = Path(r"c:\Users\SUBHODEEP\OneDrive\Desktop\circuit1")
env_path = BASE_DIR / "circuit-canvas" / ".env"
print('env_path exists:', env_path.exists(), env_path)
if env_path.exists():
    load_dotenv(env_path)
print('ADMIN_NAME raw:', os.getenv('ADMIN_NAME'))
print('ADMIN_PASSWORD raw:', os.getenv('ADMIN_PASSWORD'))
print('ADMIN_ENABLED:', bool(os.getenv('ADMIN_NAME') and os.getenv('ADMIN_PASSWORD')))
