from fastapi import FastAPI, BackgroundTasks
from fastapi.staticfiles import StaticFiles
import subprocess
import json
import os
import requests

app = FastAPI()
PROCESS_STATUS = {}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
os.makedirs(OUTPUT_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=OUTPUT_DIR), name="static")

def get_audio_track_count(video_url: str) -> int:
    cmd = f'ffprobe -v quiet -print_format json -show_streams -select_streams a "{video_url}"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    try:
        data = json.loads(result.stdout)
        return len(data.get("streams", []))
    except Exception:
        return 1

def process_video_background(stream_url: str, title: str, audio_count: int):
    title_dir = os.path.join(OUTPUT_DIR, title)
    hls_dir = os.path.join(title_dir, "hls")
    os.makedirs(hls_dir, exist_ok=True) 
 PROCESS_STATUS[title] = {
     "status": "processing"
}

print(f"\n[INFO] [{title}] Processing Started: Audio Tracks = {audio_count}")
print(f"[INFO] Testing URL: {stream_url}")

local_file = os.path.join(title_dir, "source.mp4")

print(f"[INFO] Downloading source video...")

subprocess.run(
    f'curl -L "{stream_url}" -o "{local_file}"',
    shell=True,
    check=True
)

print(f"[INFO] Source downloaded: {local_file}")

try:
    r = requests.get(stream_url, stream=True, timeout=30)

    print(f"[INFO] HTTP Status: {r.status_code}")
    print(f"[INFO] Content-Type: {r.headers.get('Content-Type')}")
    print(f"[INFO] Content-Length: {r.headers.get('Content-Length')}")

    r.close()

except Exception as e:
    print(f"[ERROR] Request Failed: {e}")
    
    # ১. ৪টি রেজুলেশনের আলাদা HLS (.m3u8) জেনারেট করা
    print(f"[INFO] [{title}] Generating 720p HLS Variant...")
    result = subprocess.run(

    print("Return code:", result.returncode)
    print(result.stderr)

    subprocess.run(
        f'ffmpeg -y -i "{local_file}" -vf scale=1280:720 -c:v libx264 -b:v 2500k -c:a aac -b:a 128k -f hls -hls_time 6 -hls_playlist_type vod "{hls_dir}/720p.m3u8"',
        shell=True
    )

    subprocess.run(

    subprocess.run(
    # ২. মূল Multi-Variant Master Playlist (master.m3u8) ফাইলটি তৈরি করা
    master_content = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080,NAME="1080p"