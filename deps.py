import os
from datetime import datetime, timezone

from birdnetlib.analyzer import Analyzer
from dotenv import load_dotenv
from slowapi import Limiter
from slowapi.util import get_remote_address

load_dotenv()

start_time = datetime.now(timezone.utc)

EXPECTED_TOKEN = os.getenv("BIRDNET_API_KEY", "")
if not EXPECTED_TOKEN:
    raise RuntimeError("Environment variable BIRDNET_API_KEY is not set")

analyzer = Analyzer()

TMP_DIR = "/tmp/birdnet_uploads"
os.makedirs(TMP_DIR, exist_ok=True)

limiter = Limiter(key_func=get_remote_address)
