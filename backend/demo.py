import os, requests
from dotenv import load_dotenv
load_dotenv()

headers = {"X-API-KEY": os.getenv("VADOO_API_KEY", "")}
payload = {
  "topic":"Custom",
  "prompt":"A calm ocean at golden hour with gentle waves.",
  "voice":"Charlie",
  "theme":"Hormozi_1",
  "style":"cinematic",          # try "anime" or "photographic" too
  "language":"English",
  "duration":"30-60",
  "aspect_ratio":"9:16",
  "use_ai":"1",
  "include_voiceover":"1"
}
r = requests.post("https://viralapi.vadoo.tv/api/generate_video", json=payload, headers=headers, timeout=60)
print(r.status_code, r.text)
