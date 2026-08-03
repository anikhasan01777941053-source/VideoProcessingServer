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

    try:
        r = requests.get(stream_url, stream=True, timeout=30)

        print(f"[INFO] HTTP Status: {r.status_code}")
        print(f"[INFO] Content-Type: {r.headers.get('Content-Type')}")
        print(f"[INFO] Content-Length: {r.headers.get('Content-Length')}")

        r.close()

    except Exception as e:
        print(f"[ERROR] Request Failed: {e}")

    # ১. ৪টি রেজুলেশনের আলাদা HLS (.m3u8) জেনারেট করা
    print(f"[INFO] [{title}] Generating 1080p, 720p, 480p, 360p HLS Variants...")
       result = subprocess.run(
        f'ffmpeg -y -i "{stream_url}" -vf scale=1920:1080 -c:v libx264 -b:v 5000k -c:a aac -b:a 192k -f hls -hls_time 6 -hls_playlist_type vod "{hls_dir}/1080p.m3u8"',
        shell=True,
        capture_output=True,
        text=True
    )

    print("Return code:", result.returncode)
    print(result.stderr)

    subprocess.run(
        f'ffmpeg -y -i "{stream_url}" -vf scale=1280:720 -c:v libx264 -b:v 2500k -c:a aac -b:a 128k -f hls -hls_time 6 -hls_playlist_type vod "{hls_dir}/720p.m3u8"',
        shell=True
    )

    subprocess.run(
        f'ffmpeg -y -i "{stream_url}" -vf scale=854:480 -c:v libx264 -b:v 1200k -c:a aac -b:a 96k -f hls -hls_time 6 -hls_playlist_type vod "{hls_dir}/480p.m3u8"',
        shell=True
    )

    subprocess.run(
        f'ffmpeg -y -i "{stream_url}" -vf scale=640:360 -c:v libx264 -b:v 800k -c:a aac -b:a 64k -f hls -hls_time 6 -hls_playlist_type vod "{hls_dir}/360p.m3u8"',
        shell=True
    )
    # ২. মূল Multi-Variant Master Playlist (master.m3u8) ফাইলটি তৈরি করা
    master_content = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080,NAME="1080p"
1080p.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=2500000,RESOLUTION=1280x720,NAME="720p"
720p.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=1200000,RESOLUTION=854x480,NAME="480p"
480p.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360,NAME="360p"
360p.m3u8
"""
    with open(os.path.join(hls_dir, "master.m3u8"), "w") as f:
        f.write(master_content)

    print(f"[SUCCESS] [{title}] Multi-Variant Master Playlist (1080p, 720p, 480p, 360p) Created!")

    # ৩. অডিও অনুযায়ী MKV বা MP4 ডাউনলোড ফাইল জেনারেট করা
    if audio_count > 1:
        mkv_dir = os.path.join(title_dir, "mkv")
        os.makedirs(mkv_dir, exist_ok=True)
        subprocess.run(f'ffmpeg -y -i "{stream_url}" -map 0:v -map 0:a -vf scale=1920:1080 -c:v libx264 -c:a copy {mkv_dir}/{title}_1080p.mkv', shell=True)
        subprocess.run(f'ffmpeg -y -i "{stream_url}" -map 0:v -map 0:a -vf scale=1280:720 -c:v libx264 -c:a copy {mkv_dir}/{title}_720p.mkv', shell=True)
        subprocess.run(f'ffmpeg -y -i "{stream_url}" -map 0:v -map 0:a -vf scale=854:480 -c:v libx264 -c:a copy {mkv_dir}/{title}_480p.mkv', shell=True)
        subprocess.run(f'ffmpeg -y -i "{stream_url}" -map 0:v -map 0:a -vf scale=640:360 -c:v libx264 -c:a copy {mkv_dir}/{title}_360p.mkv', shell=True)
    else:
        mp4_dir = os.path.join(title_dir, "mp4")
        os.makedirs(mp4_dir, exist_ok=True)
        subprocess.run(f'ffmpeg -y -i "{stream_url}" -map 0:v:0 -map 0:a:0 -vf scale=1920:1080 -c:v libx264 -c:a aac {mp4_dir}/{title}_1080p.mp4', shell=True)
        subprocess.run(f'ffmpeg -y -i "{stream_url}" -map 0:v:0 -map 0:a:0 -vf scale=1280:720 -c:v libx264 -c:a aac {mp4_dir}/{title}_720p.mp4', shell=True)
        subprocess.run(f'ffmpeg -y -i "{stream_url}" -map 0:v:0 -map 0:a:0 -vf scale=854:480 -c:v libx264 -c:a aac {mp4_dir}/{title}_480p.mp4', shell=True)
        subprocess.run(f'ffmpeg -y -i "{stream_url}" -map 0:v:0 -map 0:a:0 -vf scale=640:360 -c:v libx264 -c:a aac {mp4_dir}/{title}_360p.mp4', shell=True)
   
    fmt = "mkv" if audio_count > 1 else "mp4"
    base_url = f"{BASE_URL}/static"

    PROCESS_STATUS[title] = {
        "status": "completed",
        "download_format": fmt,
        "hls_stream_link": f"{base_url}/{title}/hls/master.m3u8",
        "download_links": {
            "1080p": f"{base_url}/{title}/{fmt}/{title}_1080p.{fmt}",
            "720p": f"{base_url}/{title}/{fmt}/{title}_720p.{fmt}",
            "480p": f"{base_url}/{title}/{fmt}/{title}_480p.{fmt}",
            "360p": f"{base_url}/{title}/{fmt}/{title}_360p.{fmt}"
        }
    }

    print(f"[SUCCESS] [{title}] All Transcoding Jobs Completed Successfully!\n")

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
