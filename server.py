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

    PROCESS_STATUS[title] = {"status": "processing"}

    print(f"\n[INFO] [{title}] Processing Started: Audio Tracks = {audio_count}")
    print(f"[INFO] Testing URL: {stream_url}")

    local_file = os.path.join(title_dir, "source.mp4")
    print("[INFO] Downloading source video...")

    with requests.get(stream_url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(local_file, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

    print(f"[INFO] Source downloaded: {local_file}")

    print(f"[INFO] [{title}] Generating 1080p, 720p, 480p, 360p HLS Variants...")

    subprocess.run(
        f'ffmpeg -y -i "{local_file}" -vf scale=1920:1080 -c:v libx264 -b:v 5000k -c:a aac -b:a 192k -f hls -hls_time 6 -hls_playlist_type vod "{hls_dir}/1080p.m3u8"',
        shell=True
    )

    subprocess.run(
        f'ffmpeg -y -i "{local_file}" -vf scale=1280:720 -c:v libx264 -b:v 2500k -c:a aac -b:a 128k -f hls -hls_time 6 -hls_playlist_type vod "{hls_dir}/720p.m3u8"',
        shell=True
    )

    subprocess.run(
        f'ffmpeg -y -i "{local_file}" -vf scale=854:480 -c:v libx264 -b:v 1200k -c:a aac -b:a 96k -f hls -hls_time 6 -hls_playlist_type vod "{hls_dir}/480p.m3u8"',
        shell=True
    )

    subprocess.run(
        f'ffmpeg -y -i "{local_file}" -vf scale=640:360 -c:v libx264 -b:v 800k -c:a aac -b:a 64k -f hls -hls_time 6 -hls_playlist_type vod "{hls_dir}/360p.m3u8"',
        shell=True
    )

@app.get("/")
def home():
    return {"status": "Smart Multi-Quality Video Processing Server Active"}

@app.get("/api/process")
def process_video(stream_url: str, title: str, background_tasks: BackgroundTasks):
    try:
        audio_count = get_audio_track_count(stream_url)
        fmt = "mkv" if audio_count > 1 else "mp4"

        background_tasks.add_task(process_video_background, stream_url, title, audio_count)

        base_url = f"{BASE_URL}/static"
        
        return {
            "success": True,
            "title": title,
            "message": "Processing started in background successfully!",
            "detected_audio_tracks": audio_count,
            "download_format": fmt,
            "hls_stream_link": f"{base_url}/{title}/hls/master.m3u8",
            "download_links": {
                "1080p": f"{base_url}/{title}/{fmt}/{title}_1080p.{fmt}",
                "720p": f"{base_url}/{title}/{fmt}/{title}_720p.{fmt}",
                "480p": f"{base_url}/{title}/{fmt}/{title}_480p.{fmt}",
                "360p": f"{base_url}/{title}/{fmt}/{title}_360p.{fmt}"
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/status")
def status(title: str):
    return PROCESS_STATUS.get(title, {
        "status": "not_found"
    })

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        log_level="info"
    )
