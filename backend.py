from flask import Flask, render_template, request, redirect, url_for, jsonify
import yt_dlp
import subprocess
import threading
import time
import os
import yaml
import queue as song_queue

app = Flask(__name__)
queue = song_queue.Queue()
now_playing = {"title": None}

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

with open('config.yml', 'r') as file:
    config = yaml.safe_load(file)

def download_song(video):
    url = video["url"]
    title = video["title"]
    video_id = video["video_id"]
    duration = video["duration"]

    ydl_opts = {
        'format': 'bestaudio',
        'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        }],
        'quiet': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url)
        filename = ydl.prepare_filename(info).replace(".webm", ".mp3")
    return filename, {"title": title, "video_id": video_id, "duration": duration, "url": url}

def download_and_play():
    next_song = queue.get()
    next_file, next_meta = download_song(next_song)

    while True:
        now_playing.update(next_meta)
        now_playing["start_time"] = time.time()

        play_proc = subprocess.Popen(['ffplay', '-nodisp', '-autoexit', next_file])

        def downloader():
            nonlocal next_song, next_file, next_meta
            next_song = queue.get()
            next_file, next_meta = download_song(next_song)

        download_thread = threading.Thread(target=downloader)
        download_thread.start()

        play_proc.wait()
        now_playing.clear()

        download_thread.join()

threading.Thread(target=download_and_play, daemon=True).start()

@app.route('/')
def index():
    return render_template('screen.html', now_playing=now_playing, queue=list(queue.queue),config=config)

@app.route('/request')
def request_page():
    return render_template('request.html')

@app.route('/search')
def search():
    query = request.args.get('q')
    ydl_opts = {'quiet': True, 'extract_flat': True, 'skip_download': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        search_results = ydl.extract_info(f"ytsearch10:{query}", download=False)['entries']
    return jsonify(results=[
        {
            "title": vid["title"],
            "id": vid["id"],
            "duration": vid.get("duration")  # seconds
        } for vid in search_results
    ])

@app.route('/add_song', methods=['POST'])
def add_song():
    if request.is_json:
        data = request.get_json()
        url = data.get('url')
    else:
        url = request.form['url']

    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        info = ydl.extract_info(url, download=False)
        title = info['title']
        duration = info.get('duration', 0)
        video_id = info['id']

    queue.put({"url": url, "title": title, "duration": duration, "video_id": video_id})
    return jsonify(success=True)

@app.route('/api/now_playing')
def api_now_playing():
    return jsonify(now_playing=now_playing, queue=list(queue.queue))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7000, debug=True)
