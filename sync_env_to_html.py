"""sync_env_to_html.py — 로컬 .env의 API 키를 TrendSetter_KBeauty_Pro.html용 local_keys.js로 동기화
(local_keys.js는 .gitignore에 등록되어 Git에 절대 올라가지 않습니다.)
"""
import json
import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

payload = {
    "YOUTUBE_API_KEY": os.getenv("YOUTUBE_API_KEY", "").strip(),
    "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY", "").strip(),
}

out_path = os.path.join(BASE_DIR, "local_keys.js")
with open(out_path, "w", encoding="utf-8") as f:
    f.write("// Auto-generated from .env (gitignored — do not commit)\n")
    f.write(f"window.__LOCAL_ENV__ = {json.dumps(payload, ensure_ascii=False)};\n")

print(
    f"local_keys.js 생성 완료 "
    f"(YOUTUBE_API_KEY={'OK' if payload['YOUTUBE_API_KEY'] else 'MISSING'}, "
    f"GOOGLE_API_KEY={'OK' if payload['GOOGLE_API_KEY'] else 'MISSING'})"
)
