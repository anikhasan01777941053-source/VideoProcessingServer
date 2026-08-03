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

app.mount(
    "/static",
    StaticFiles(directory=OUTPUT_DIR),
    name="static"
)


def get_audio_track_count(video_url: str) -> int:
    cmd = (
        f'ffprobe -v quiet '
        f'-print_format json '
        f'-show_streams '
        f'-select_streams a '
        f'"{video_url}"'
    )

    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True
    )

    try:
        data = json.loads(result.stdout)
        return len(data.get("streams", []))
    except Exception:
        return 1


def process_video_background(
    stream_url: str,
    title: str,
    audio_count: int
):
    title_dir = os.path.join(OUTPUT_DIR, title)
    hls_dir = os.path.join(title_dir, "hls")

    os.makedirs(title_dir, exist_ok=True)
    os.makedirs(hls_dir, exist_ok=True)

    PROCESS_STATUS[title] = {
        "status": "processing"
    }

    print(f"[INFO] Processing: {title}")

    local_file = os.path.join(title_dir, "source.mp4")

    print("[INFO] Downloading source video...")

    with requests.get(
        stream_url,
        stream=True,
        timeout=(30, 600)
    ) as r:

        r.raise_for_status()

        with open(local_file, "wb") as f:

            for chunk in r.iter_content(1024 * 1024):

                if chunk:
                    f.write(chunk)

    print("[INFO] Download completed.")
    print("[INFO] Generating 720p HLS...")

    subprocess.run(
        f'ffmpeg -y '
        f'-i "{local_file}" '
        f'-vf scale=1280:720 '
        f'-c:v libx264 '
        f'-preset veryfast '
        f'-crf 23 '
        f'-c:a aac '
        f'-b:a 128k '
        f'-f hls '
        f'-hls_time 6 '
        f'-hls_playlist_type vod '
        f'"{hls_dir}/720p.m3u8"',
        shell=True,
        check=True
    )

    master_content = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-STREAM-INF:BANDWIDTH=2500000,RESOLUTION=1280x720,NAME="720p"
720p.m3u8
"""

    with open(os.path.join(hls_dir, "master.m3u8"), "w") as f:
        f.write(master_content)

    print("[INFO] 720p HLS Created.")
    fmt = "mkv" if audio_count > 1 else "mp4"

    if audio_count > 1:

        mkv_dir = os.path.join(title_dir, "mkv")
        os.makedirs(mkv_dir, exist_ok=True)

        subprocess.run(
            f'ffmpeg -y '
            f'-i "{local_file}" '
            f'-map 0:v -map 0:a '
            f'-vf scale=1280:720 '
            f'-c:v libx264 '
            f'-preset veryfast '
            f'-c:a copy '
            f'"{mkv_dir}/{title}_720p.mkv"',
            shell=True,
            check=True
        )

    else:

        mp4_dir = os.path.join(title_dir, "mp4")
        os.makedirs(mp4_dir, exist_ok=True)

        subprocess.run(
            f'ffmpeg -y '
            f'-i "{local_file}" '
            f'-map 0:v:0 -map 0:a:0 '
            f'-vf scale=1280:720 '
            f'-c:v libx264 '
            f'-preset veryfast '
            f'-c:a aac '
            f'-b:a 128k '
            f'"{mp4_dir}/{title}_720p.mp4"',
            shell=True,
            check=True
        )

    base_url = f"{BASE_URL}/static"

    PROCESS_STATUS[title] = {
        "status": "completed",
        "download_format": fmt,
        "hls_stream_link": f"{base_url}/{title}/hls/master.m3u8",
        "download_links": {
            "720p": f"{base_url}/{title}/{fmt}/{title}_720p.{fmt}"
        }
    }
    if os.path.exists(local_file):
        os.remove(local_file)

    print("[SUCCESS] Processing Completed.")
    
@app.get("/")
def home():
    return {
        "status": "720p Video Processing Server Running"
    }


@app.get("/api/process")
def process_video(
    stream_url: str,
    title: str,
    background_tasks: BackgroundTasks
):
    try:

        audio_count = get_audio_track_count(stream_url)

        fmt = "mkv" if audio_count > 1 else "mp4"

        background_tasks.add_task(
            process_video_background,
            stream_url,
            title,
            audio_count
        )

        base_url = f"{BASE_URL}/static"

        return {
            "success": True,
            "title": title,
            "message": "Processing started",
            "detected_audio_tracks": audio_count,
            "download_format": fmt,
            "hls_stream_link": f"{base_url}/{title}/hls/master.m3u8",
            "download_links": {
                "720p": f"{base_url}/{title}/{fmt}/{title}_720p.{fmt}"
            }
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/status")
def status(title: str):
    return PROCESS_STATUS.get(
        title,
        {
            "status": "not_found"
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        log_level="info"
    )    