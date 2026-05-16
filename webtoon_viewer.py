import os
import sys
import json
import base64
import zipfile
import shutil
import tempfile
import threading
import webview
from bottle import Bottle, request, response, static_file
from PIL import Image
import io

# 설정
APP_NAME = "JoyViewer - Webtoon Reader v3.5"
PORT = 58210
TEMP_DIR = os.path.join(tempfile.gettempdir(), "joyviewer_cache")

# 임시 디렉토리 초기화
if os.path.exists(TEMP_DIR):
    shutil.rmtree(TEMP_DIR)
os.makedirs(TEMP_DIR, exist_ok=True)

CONFIG_FILE = "joyviewer_config.json"

def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

class WebtoonApi:
    def __init__(self):
        self.library_folders = []
        self.custom_thumbnails = {}
        self.bookmarks = []
        config = self.load_config()
        if 'library_folders' in config:
            self.library_folders = config['library_folders']
        if 'custom_thumbnails' in config:
            self.custom_thumbnails = config['custom_thumbnails']
        if 'bookmarks' in config:
            self.bookmarks = config['bookmarks']
        self.current_webtoon = ""
        self.current_episode = ""

    def get_server_url(self):
        ip = get_local_ip()
        return f"http://{ip}:{PORT}"

    def load_config(self):
        try:
            import json
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def save_config(self, config_dict):
        try:
            import json
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config_dict, f, ensure_ascii=False, indent=4)
            return True
        except:
            return False

    def select_folder(self):
        result = window.create_file_dialog(webview.FOLDER_DIALOG)
        if result:
            folder = result[0]
            if folder not in self.library_folders:
                self.library_folders.append(folder)
                config = self.load_config()
                config['library_folders'] = self.library_folders
                self.save_config(config)
            return {"status": "success", "path": folder}
        return {"status": "cancel"}

    def set_custom_thumbnail(self, webtoon_path):
        result = window.create_file_dialog(
            webview.OPEN_DIALOG, 
            allow_multiple=False,
            file_types=('Image Files (*.jpg;*.jpeg;*.png;*.webp;*.gif)',)
        )
        if result:
            img_path = result[0]
            self.custom_thumbnails[webtoon_path] = img_path
            config = self.load_config()
            config['custom_thumbnails'] = self.custom_thumbnails
            self.save_config(config)
            return {"status": "success"}
        return {"status": "cancel"}

    def save_bookmark(self, bookmark_data):
        import uuid
        import datetime
        bookmark_data['id'] = str(uuid.uuid4())
        bookmark_data['date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        self.bookmarks.insert(0, bookmark_data)
        
        config = self.load_config()
        config['bookmarks'] = self.bookmarks
        self.save_config(config)
        return {"status": "success", "bookmarks": self.bookmarks}

    def get_bookmarks(self):
        return self.bookmarks

    def delete_bookmark(self, bm_id):
        self.bookmarks = [b for b in self.bookmarks if b['id'] != bm_id]
        config = self.load_config()
        config['bookmarks'] = self.bookmarks
        self.save_config(config)
        return {"status": "success", "bookmarks": self.bookmarks}

    def get_thumbnail_url(self, episode_path):
        import json
        import base64
        import zipfile
        if episode_path.lower().endswith('.cbz'):
            try:
                with zipfile.ZipFile(episode_path, 'r') as z:
                    img_files = [f for f in z.namelist() if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif'))]
                    if img_files:
                        img_files.sort()
                        payload = json.dumps({"p": episode_path, "i": img_files[0]})
                        return f"http://localhost:{PORT}/api/image/{base64.urlsafe_b64encode(payload.encode('utf-8')).decode('utf-8')}"
            except:
                pass
        else:
            try:
                img_files = [f for f in os.listdir(episode_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif'))]
                if img_files:
                    img_files.sort()
                    payload = json.dumps({"p": episode_path, "i": img_files[0]})
                    return f"http://localhost:{PORT}/api/image/{base64.urlsafe_b64encode(payload.encode('utf-8')).decode('utf-8')}"
            except:
                pass
        return ""

    def get_library(self):
        webtoons = []
        import json
        import base64
        
        def resolve_thumb(w_path, fallback_path):
            if w_path in self.custom_thumbnails and os.path.exists(self.custom_thumbnails[w_path]):
                payload = json.dumps({"f": self.custom_thumbnails[w_path]})
                encoded = base64.urlsafe_b64encode(payload.encode('utf-8')).decode('utf-8')
                return f"http://localhost:{PORT}/api/image/{encoded}"
            return self.get_thumbnail_url(fallback_path)

        for root_dir in self.library_folders:
            if not os.path.exists(root_dir):
                continue
            
            has_direct_episodes = False
            
            for item in os.listdir(root_dir):
                path = os.path.join(root_dir, item)
                
                # 1. 상위 폴더(여러 웹툰이 있는 서재)
                if os.path.isdir(path):
                    episodes = [f for f in os.listdir(path) if os.path.isdir(os.path.join(path, f)) or f.lower().endswith('.cbz')]
                    if episodes:
                        thumb = resolve_thumb(path, os.path.join(path, episodes[0]))
                        webtoons.append({
                            "name": item,
                            "path": path,
                            "count": len(episodes),
                            "thumbnail": thumb
                        })
                
                # 2. 웹툰 폴더 자체
                if item.lower().endswith('.cbz') or (os.path.isdir(path) and any(f.lower().endswith(('.jpg', '.png', '.webp')) for f in os.listdir(path))):
                    has_direct_episodes = True
                    
            if has_direct_episodes:
                folder_name = os.path.basename(root_dir)
                episodes = [f for f in os.listdir(root_dir) if f.lower().endswith('.cbz') or os.path.isdir(os.path.join(root_dir, f))]
                if episodes:
                    thumb = resolve_thumb(root_dir, os.path.join(root_dir, episodes[0]))
                    if not any(w["path"] == root_dir for w in webtoons):
                        webtoons.append({
                            "name": folder_name,
                            "path": root_dir,
                            "count": len(episodes),
                            "is_direct": True,
                            "thumbnail": thumb
                        })
        return webtoons

    def get_episodes(self, webtoon_path):
        if not os.path.exists(webtoon_path):
            return []
            
        episodes = []
        import re
        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]
            
        items = os.listdir(webtoon_path)
        items.sort(key=natural_sort_key)
        
        for item in items:
            full_path = os.path.join(webtoon_path, item)
            if item.lower().endswith('.cbz') or (os.path.isdir(full_path) and any(f.lower().endswith(('.jpg', '.png', '.webp')) for f in os.listdir(full_path))):
                ep_name = item
                if item.lower().endswith('.cbz'):
                    ep_name = item[:-4]
                episodes.append({
                    "name": ep_name,
                    "filename": item,
                    "is_cbz": item.lower().endswith('.cbz'),
                    "path": full_path
                })
        return episodes

    def get_images(self, episode_path):
        if not os.path.exists(episode_path):
            return []
        import json
        import base64
        import zipfile
        image_urls = []
        
        if episode_path.lower().endswith('.cbz'):
            with zipfile.ZipFile(episode_path, 'r') as zip_ref:
                img_files = [f for f in zip_ref.namelist() if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif'))]
                img_files.sort()
                for img_file in img_files:
                    payload = json.dumps({"p": episode_path, "i": img_file})
                    encoded = base64.urlsafe_b64encode(payload.encode('utf-8')).decode('utf-8')
                    image_urls.append(f"http://localhost:{PORT}/api/image/{encoded}")
        else:
            img_files = [f for f in os.listdir(episode_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif'))]
            img_files.sort()
            for img_file in img_files:
                payload = json.dumps({"p": episode_path, "i": img_file})
                encoded = base64.urlsafe_b64encode(payload.encode('utf-8')).decode('utf-8')
                image_urls.append(f"http://localhost:{PORT}/api/image/{encoded}")
                
        return image_urls

# WebtoonApi 인스턴스 전역 설정 (라우팅에서 접근하기 위함)
api = WebtoonApi()

# Bottle 서버 설정 (이미지 서빙용)
app = Bottle()

@app.route('/api/image/<payload>')
def serve_image(payload):
    import json
    import zipfile
    import base64
    import os
    try:
        decoded_json = base64.urlsafe_b64decode(payload.encode('utf-8')).decode('utf-8')
        data = json.loads(decoded_json)
        
        if "f" in data:
            full_path = data["f"]
            if os.path.exists(full_path):
                return static_file(os.path.basename(full_path), root=os.path.dirname(full_path))
            return "Not found"
            
        episode_path = data['p']
        img_file = data['i']
    except:
        return "Invalid payload"

    if not os.path.exists(episode_path):
        return "Not found"

    if episode_path.lower().endswith('.cbz'):
        try:
            with zipfile.ZipFile(episode_path, 'r') as zip_ref:
                with zip_ref.open(img_file) as file:
                    content = file.read()
            
            ext = os.path.splitext(img_file)[1].lower()
            if ext in ['.jpg', '.jpeg']: response.content_type = 'image/jpeg'
            elif ext == '.png': response.content_type = 'image/png'
            elif ext == '.webp': response.content_type = 'image/webp'
            elif ext == '.gif': response.content_type = 'image/gif'
            
            return content
        except Exception as e:
            return str(e)
    else:
        return static_file(img_file, root=episode_path)

@app.route('/')
def index():
    return HTML_CONTENT.replace('<head>', '<head>\n    <script>window.__IS_BOTTLE__ = true;</script>')

@app.route('/api/library')
def api_library():
    import json
    host = request.get_header('host')
    webtoons = api.get_library()
    if host:
        for w in webtoons:
            if w.get('thumbnail'):
                w['thumbnail'] = w['thumbnail'].replace(f'localhost:{PORT}', host)
    response.content_type = 'application/json'
    return json.dumps(webtoons)

@app.route('/api/episodes')
def api_episodes():
    import json
    path = request.query.path
    response.content_type = 'application/json'
    return json.dumps(api.get_episodes(path))

@app.route('/api/images')
def api_images():
    import json
    path = request.query.path
    host = request.get_header('host')
    urls = api.get_images(path)
    if host:
        urls = [url.replace(f'localhost:{PORT}', host) for url in urls]
    response.content_type = 'application/json'
    return json.dumps(urls)

@app.route('/api/bookmarks', method='GET')
def api_get_bookmarks():
    import json
    response.content_type = 'application/json'
    return json.dumps(api.get_bookmarks())

@app.route('/api/bookmarks', method='POST')
def api_save_bookmark():
    import json
    try:
        data = request.json
    except:
        import ast
        data = ast.literal_eval(request.body.read().decode('utf-8'))
    response.content_type = 'application/json'
    return json.dumps(api.save_bookmark(data))

@app.route('/api/bookmarks/<bm_id>', method='DELETE')
def api_delete_bookmark(bm_id):
    import json
    response.content_type = 'application/json'
    return json.dumps(api.delete_bookmark(bm_id))

@app.route('/api/config', method='GET')
def api_get_config():
    import json
    response.content_type = 'application/json'
    return json.dumps(api.load_config())

@app.route('/api/config', method='POST')
def api_save_config():
    import json
    try:
        data = request.json
    except:
        import ast
        data = ast.literal_eval(request.body.read().decode('utf-8'))
    response.content_type = 'application/json'
    return json.dumps({"status": "success"}) if api.save_config(data) else json.dumps({"status": "error"})

from bottle import ServerAdapter

class ThreadingServer(ServerAdapter):
    def run(self, handler):
        from wsgiref.simple_server import make_server, WSGIServer
        from socketserver import ThreadingMixIn
        
        class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
            daemon_threads = True

        server = make_server(self.host, self.port, handler, server_class=ThreadingWSGIServer)
        server.serve_forever()

def run_server():
    app.run(host='0.0.0.0', port=PORT, server=ThreadingServer, quiet=True)

# HTML/CSS/JS Template
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JoyViewer</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=Noto+Sans+KR:wght@300;400;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-dark: #0a0a0c;
            --sidebar-bg: rgba(18, 18, 22, 0.95);
            --accent: #00ffa3;
            --accent-glow: rgba(0, 255, 163, 0.3);
            --text-main: #e0e0e0;
            --text-dim: #888888;
            --glass: rgba(255, 255, 255, 0.05);
            --glass-border: rgba(255, 255, 255, 0.1);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            -webkit-user-select: none;
        }

        body {
            background: var(--bg-dark);
            color: var(--text-main);
            font-family: 'Inter', 'Noto Sans KR', sans-serif;
            overflow: hidden;
            display: flex;
            height: 100vh;
        }

        /* Sidebar */
        #sidebar {
            width: 320px;
            flex-shrink: 0;
            background: var(--sidebar-bg);
            border-right: 1px solid var(--glass-border);
            display: flex;
            flex-direction: column;
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            z-index: 100;
            backdrop-filter: blur(20px);
            overflow-x: hidden;
        }

        #sidebar.collapsed {
            margin-left: -320px;
        }

        .sidebar-header {
            padding: 24px;
            border-bottom: 1px solid var(--glass-border);
        }

        .logo {
            font-size: 24px;
            font-weight: 800;
            background: linear-gradient(135deg, #fff, var(--accent));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .btn-folder {
            width: 100%;
            padding: 12px;
            background: var(--glass);
            border: 1px solid var(--glass-border);
            color: #fff;
            border-radius: 12px;
            cursor: pointer;
            font-family: inherit;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }

        .btn-folder:hover {
            background: var(--glass-border);
            border-color: var(--accent);
            box-shadow: 0 0 15px var(--accent-glow);
        }

        .list-container {
            flex: 1;
            overflow-y: auto;
            padding: 10px;
        }

        .list-container::-webkit-scrollbar {
            width: 4px;
        }

        .list-container::-webkit-scrollbar-thumb {
            background: var(--glass-border);
            border-radius: 10px;
        }

        .section-title {
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: var(--text-dim);
            margin: 20px 0 10px 10px;
            font-weight: 600;
        }

        .item {
            padding: 14px 16px;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.2s;
            margin-bottom: 4px;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .item:hover {
            background: var(--glass);
        }

        .item.active {
            background: var(--accent-glow);
            border: 1px solid var(--accent);
        }

        .item-name {
            font-size: 14px;
            font-weight: 600;
            color: var(--text-main);
            margin-bottom: 4px;
        }

        .item-meta {
            font-size: 12px;
            color: var(--text-dim);
        }

        /* 2-column Grid for Library */
        .webtoon-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            padding: 5px 0;
        }

        .webtoon-card {
            background: var(--glass);
            border: 1px solid var(--glass-border);
            border-radius: 8px;
            overflow: hidden;
            cursor: pointer;
            transition: all 0.2s;
            position: relative;
        }

        .webtoon-card:hover, .webtoon-card.active {
            border-color: var(--accent);
            transform: translateY(-2px);
        }

        .btn-edit-thumb {
            position: absolute;
            top: 5px;
            right: 5px;
            background: rgba(0, 0, 0, 0.7);
            border: none;
            color: white;
            border-radius: 50%;
            width: 24px;
            height: 24px;
            font-size: 12px;
            cursor: pointer;
            display: none;
            z-index: 10;
        }

        .webtoon-card:hover .btn-edit-thumb {
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .webtoon-card img {
            width: 100%;
            height: 120px;
            object-fit: cover;
            border-bottom: 1px solid var(--glass-border);
        }

        .webtoon-card .info {
            padding: 8px;
        }

        .webtoon-card .title {
            font-size: 12px;
            font-weight: 600;
            color: var(--text-main);
            margin-bottom: 4px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .webtoon-card .meta {
            font-size: 11px;
            color: var(--text-dim);
        }

        .empty-state {
            padding: 40px;
            text-align: center;
            color: var(--text-dim);
        }

        /* Main Viewer */
        #main {
            flex: 1;
            position: relative;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .top-bar {
            height: 60px;
            display: flex;
            align-items: center;
            padding: 0 20px;
            background: rgba(10, 10, 12, 0.8);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid var(--glass-border);
            z-index: 10;
        }

        .btn-toggle {
            padding: 8px;
            background: none;
            border: none;
            color: var(--text-main);
            cursor: pointer;
            margin-right: 15px;
            border-radius: 8px;
        }

        .btn-toggle:hover {
            background: var(--glass);
        }

        .auto-scroll-controls {
            margin-left: auto;
            display: flex;
            align-items: center;
            gap: 15px;
            background: var(--glass);
            padding: 8px 15px;
            border-radius: 8px;
            border: 1px solid var(--glass-border);
        }

        .auto-scroll-label {
            font-size: 14px;
            font-weight: 600;
            margin-right: 5px;
        }

        .btn-ctrl {
            background: none;
            border: none;
            color: #fff;
            font-size: 16px;
            cursor: pointer;
            padding: 5px 8px;
            border-radius: 5px;
            transition: all 0.2s;
        }

        .btn-ctrl:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        .btn-play-pause.active { color: var(--accent); }

        .ctrl-select, .ctrl-input {
            background: rgba(0, 0, 0, 0.5);
            color: #fff;
            border: 1px solid var(--glass-border);
            border-radius: 4px;
            padding: 4px 8px;
            font-family: inherit;
            font-size: 13px;
            outline: none;
        }

        .ctrl-input {
            width: 60px;
            text-align: center;
        }

        .ctrl-input::-webkit-outer-spin-button,
        .ctrl-input::-webkit-inner-spin-button {
            -webkit-appearance: none;
            margin: 0;
        }

        .nav-side-btn {
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            background: rgba(0, 0, 0, 0.1);
            color: rgba(255, 255, 255, 0.2);
            border: none;
            font-size: 50px;
            padding: 50px 20px;
            cursor: pointer;
            z-index: 50;
            transition: all 0.3s;
            display: none;
            border-radius: 12px;
        }

        .nav-side-btn:hover {
            background: rgba(0, 0, 0, 0.6);
            color: rgba(255, 255, 255, 0.9);
        }

        .nav-side-btn.left {
            left: 20px;
        }

        .nav-side-btn.right {
            right: 20px;
        }

        #bookmark-btn {
            position: absolute;
            top: 70px;
            right: 20px;
            background: rgba(0, 0, 0, 0.4);
            color: rgba(255, 255, 255, 0.6);
            width: 44px;
            height: 44px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            cursor: pointer;
            z-index: 100;
            transition: all 0.3s;
            border: 1px solid var(--glass-border);
        }

        #bookmark-btn:hover {
            background: var(--sidebar-bg);
            color: var(--accent);
            border-color: var(--accent);
        }

        #btn-scroll-top {
            position: absolute;
            bottom: 30px;
            right: 20px;
            background: rgba(0, 0, 0, 0.4);
            color: rgba(255, 255, 255, 0.6);
            width: 44px;
            height: 44px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            cursor: pointer;
            z-index: 100;
            transition: all 0.3s;
            border: 1px solid var(--glass-border);
            display: none;
        }

        #btn-scroll-top:hover {
            background: var(--sidebar-bg);
            color: var(--accent);
            border-color: var(--accent);
        }

        #btn-fullscreen {
            display: none;
            position: absolute;
            bottom: 85px;
            right: 20px;
            width: 45px;
            height: 45px;
            background: rgba(0, 0, 0, 0.6);
            color: white;
            border-radius: 50%;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            z-index: 90;
            backdrop-filter: blur(5px);
            border: 1px solid var(--glass-border);
            font-size: 20px;
            transition: all 0.3s;
        }

        #btn-fullscreen:hover {
            background: var(--sidebar-bg);
            color: var(--accent);
            border-color: var(--accent);
        }

        #bookmark-panel {
            position: absolute;
            top: 125px;
            right: 20px;
            width: 320px;
            max-height: 400px;
            background: var(--sidebar-bg);
            border: 1px solid var(--glass-border);
            border-radius: 8px;
            z-index: 100;
            display: flex;
            flex-direction: column;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }

        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 15px;
            border-bottom: 1px solid var(--glass-border);
            font-weight: bold;
            font-size: 14px;
            color: var(--text-main);
        }

        #bookmark-list {
            overflow-y: auto;
            padding: 10px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            max-height: 350px;
        }

        .bookmark-item {
            background: var(--glass);
            border-radius: 6px;
            padding: 12px;
            font-size: 12px;
            cursor: pointer;
            border: 1px solid transparent;
            transition: all 0.2s;
        }

        .bookmark-item:hover {
            border-color: var(--accent);
            background: rgba(255, 255, 255, 0.1);
        }

        .bookmark-item .title {
            font-weight: 600;
            color: var(--text-main);
            margin-bottom: 4px;
            font-size: 13px;
        }

        .bookmark-item .ep-info {
            color: var(--accent);
            margin-bottom: 4px;
        }

        .bookmark-item .date {
            color: var(--text-dim);
            font-size: 11px;
        }

        .bookmark-item .actions {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 8px;
        }

        .btn-delete-bm {
            background: rgba(255, 50, 50, 0.1);
            border: 1px solid rgba(255, 50, 50, 0.3);
            color: #ffaaaa;
            border-radius: 4px;
            padding: 4px 8px;
            cursor: pointer;
            font-size: 11px;
            transition: all 0.2s;
        }

        .btn-delete-bm:hover {
            background: rgba(255, 50, 50, 0.5);
            color: white;
        }

        #auto-scroll-speed {
            width: 100px;
            cursor: pointer;
            accent-color: var(--accent);
        }

        .current-info {
            font-weight: 600;
            font-size: 16px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            flex: 1;
            margin-right: 15px;
        }

        #viewer-container {
            flex: 1;
            overflow-y: auto;
            scroll-behavior: smooth;
            background: #000;
        }

        #viewer-container::-webkit-scrollbar {
            width: 8px;
        }

        #viewer-container::-webkit-scrollbar-thumb {
            background: #333;
            border-radius: 4px;
        }

        #viewer-container::-webkit-scrollbar-thumb:hover {
            background: #444;
        }

        .webtoon-image {
            display: block;
            width: 100%;
            max-width: 800px;
            min-height: 800px; /* Lazy loading이 제대로 작동하도록 최소 높이 지정 */
            margin: 0 auto;
            height: auto;
            pointer-events: none;
            background-color: #111; /* 로딩 중 배경색 */
        }

        .viewer-footer {
            padding: 60px 0 100px 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 20px;
        }

        .btn-next {
            padding: 16px 40px;
            background: var(--accent);
            color: #000;
            border: none;
            border-radius: 30px;
            font-size: 18px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s;
            box-shadow: 0 0 20px var(--accent-glow);
        }

        .btn-next:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 30px var(--accent-glow);
        }

        /* Loading Animation */
        .loader {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            display: none;
        }

        .spinner {
            width: 40px;
            height: 40px;
            border: 4px solid var(--glass);
            border-top: 4px solid var(--accent);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: var(--text-dim);
            text-align: center;
            padding: 40px;
        }

        .empty-state h1 {
            color: #fff;
            margin-bottom: 10px;
        }

        #immersive-buttons {
            display: none;
            gap: 8px;
            margin-right: 15px;
        }

        #immersive-buttons button {
            font-weight: 800;
            color: var(--accent);
            border: 1px solid var(--accent);
            border-radius: 4px;
            padding: 4px 10px;
            font-size: 14px;
            background: rgba(0,255,163,0.1);
            cursor: pointer;
        }

        .top-bar.menu-hidden .auto-scroll-controls {
            display: none !important;
        }
        .top-bar.menu-hidden #immersive-buttons {
            display: flex !important;
        }

        /* Mobile Responsive */
        @media (max-width: 768px) {
            .top-bar {
                flex-wrap: wrap;
                height: auto;
                padding: 10px 15px;
                gap: 10px;
            }
            .current-info {
                font-size: 14px;
            }
            .auto-scroll-controls {
                width: 100%;
                margin-left: 0;
                justify-content: space-between;
                flex-wrap: wrap;
                gap: 10px;
                padding: 8px 10px;
            }
            .ctrl-select {
                max-width: 130px;
            }
            .nav-side-btn {
                padding: 15px 5px;
                font-size: 24px;
                border-radius: 8px;
            }
            .nav-side-btn.left {
                left: 0;
                border-top-left-radius: 0;
                border-bottom-left-radius: 0;
            }
            .nav-side-btn.right {
                right: 0;
                border-top-right-radius: 0;
                border-bottom-right-radius: 0;
            }
            #bookmark-btn {
                display: none !important;
            }
            #bookmark-panel {
                top: 60px;
                width: 280px;
                right: 10px;
            }
            .webtoon-image {
                min-height: 400px;
            }
        }
    </style>
</head>
<body>
    <div id="sidebar">
        <div class="sidebar-header">
            <div class="logo">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>
                JoyViewer
            </div>
            <button class="btn-folder" onclick="selectFolder()">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
                폴더 추가
            </button>
        </div>
        <div id="webtoon-list" class="list-container">
            <div class="empty-state" style="padding-top: 50px;">
                <p>우측 상단의 폴더 추가를 눌러<br>웹툰을 불러오세요.</p>
            </div>
        </div>
        <div id="episode-list" class="list-container" style="display: none; border-top: 1px solid var(--glass-border);">
            <div class="section-title">에피소드</div>
            <div id="ep-items"></div>
        </div>
    </div>

    <div id="main">
        <div class="top-bar">
            <button class="btn-toggle" onclick="toggleSidebar()">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
            </button>
            <div class="current-info" id="current-title">JoyViewer</div>
            <div id="immersive-buttons">
                <button id="btn-show-index" onclick="toggleBookmarkPanel()" title="책갈피 (Index) 열기">I</button>
                <button id="btn-show-menu" onclick="showScrollMenu()" title="스크롤 메뉴 보기">A</button>
            </div>
            
            <div class="auto-scroll-controls">
                <select id="scroll-mode" class="ctrl-select" onchange="toggleScrollModeUI()">
                    <option value="smooth">부드러운 스크롤</option>
                    <option value="step">끊어 읽기 (사람처럼)</option>
                </select>
                
                <button class="btn-ctrl btn-play-pause" id="btn-play-pause" onclick="togglePlayPause()" title="시작/일시정지">▶</button>
                <button class="btn-ctrl btn-stop" id="btn-stop" onclick="onStopBtnClick()" title="정지">⏹</button>
                
                <div id="ui-smooth" class="mode-ui" style="display: flex; align-items: center;">
                    <input type="range" id="auto-scroll-speed" min="1" max="100" value="20" title="속도 조절" oninput="updateScrollSpeed()">
                </div>
                
                <div id="ui-step" class="mode-ui" style="display: none; align-items: center; gap: 8px;">
                    <input type="number" id="step-distance" value="700" title="이동 길이(px)" class="ctrl-input"> px
                    <input type="number" id="step-pause" value="3" title="대기 시간(초)" class="ctrl-input" style="width: 45px;"> 초
                </div>
                
                <div style="width: 1px; height: 20px; background: var(--glass-border); margin: 0 5px;"></div>
                <button class="btn-ctrl" onclick="saveSettings()" title="현재 스크롤 설정 저장" style="display:flex; align-items:center;">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg>
                </button>
            </div>
        </div>

        <button id="nav-prev" class="nav-side-btn left" onclick="loadPrevEpisode()" title="이전 화 (방향키 왼쪽)">&#10094;</button>
        <button id="nav-next" class="nav-side-btn right" onclick="loadNextEpisode()" title="다음 화 (방향키 오른쪽)">&#10095;</button>

        <div id="bookmark-btn" onclick="toggleBookmarkPanel()" title="책갈피 (저장된 위치)">🔖</div>
        <div id="btn-fullscreen" onclick="toggleFullscreen()" title="전체화면 켜기/끄기">⛶</div>
        <div id="btn-scroll-top" onclick="scrollToTop()" title="최상단으로 이동">▲</div>
        <div id="bookmark-panel" style="display: none;">
            <div class="panel-header">
                <span>내 책갈피 목록</span>
                <button onclick="addBookmark()" class="btn-ctrl" style="padding: 4px 8px; font-size:12px;">+ 현재 위치 저장</button>
            </div>
            <div id="bookmark-list"></div>
        </div>

        <div id="viewer-container">
            <div id="welcome-screen" class="empty-state">
                <svg width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="var(--glass-border)" stroke-width="1" style="margin-bottom: 20px;"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>
                <h1>시작할 준비가 되었습니다</h1>
                <p>왼쪽에서 웹툰과 화차를 선택해 감상을 시작하세요.</p>
            </div>
            <div id="image-stack"></div>
            <div id="viewer-controls" class="viewer-footer" style="display: none;">
                <button class="btn-next" onclick="loadNextEpisode()">다음 화 보기</button>
                <p style="color: var(--text-dim);">마지막 페이지입니다.</p>
            </div>
        </div>

        <div class="loader" id="loader">
            <div class="spinner"></div>
        </div>
    </div>

    <script>
        let isWeb = window.__IS_BOTTLE__ === true;
        
        const ApiWrapper = {
            async get_server_url() {
                if (!isWeb) return await pywebview.api.get_server_url();
                return window.location.origin;
            },
            async get_library() {
                if (!isWeb) return await pywebview.api.get_library();
                const res = await fetch('/api/library');
                return await res.json();
            },
            async get_episodes(path) {
                if (!isWeb) return await pywebview.api.get_episodes(path);
                const res = await fetch('/api/episodes?path=' + encodeURIComponent(path));
                return await res.json();
            },
            async get_images(path) {
                if (!isWeb) return await pywebview.api.get_images(path);
                const res = await fetch('/api/images?path=' + encodeURIComponent(path));
                return await res.json();
            },
            async get_bookmarks() {
                if (!isWeb) return await pywebview.api.get_bookmarks();
                const res = await fetch('/api/bookmarks');
                return await res.json();
            },
            async save_bookmark(data) {
                if (!isWeb) return await pywebview.api.save_bookmark(data);
                const res = await fetch('/api/bookmarks', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                return await res.json();
            },
            async delete_bookmark(id) {
                if (!isWeb) return await pywebview.api.delete_bookmark(id);
                const res = await fetch('/api/bookmarks/' + id, { method: 'DELETE' });
                return await res.json();
            },
            async load_config() {
                if (!isWeb) return await pywebview.api.load_config();
                const res = await fetch('/api/config');
                return await res.json();
            },
            async save_config(config) {
                if (!isWeb) return await pywebview.api.save_config(config);
                const res = await fetch('/api/config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(config)
                });
                return await res.json();
            },
            async select_folder() {
                if (!isWeb) return await pywebview.api.select_folder();
                alert("웹 환경에서는 폴더 추가를 지원하지 않습니다. PC 뷰어에서 폴더를 추가해주세요.");
                return {status: "cancel"};
            },
            async set_custom_thumbnail(path) {
                if (!isWeb) return await pywebview.api.set_custom_thumbnail(path);
                alert("웹 환경에서는 썸네일 변경을 지원하지 않습니다. PC 뷰어에서 변경해주세요.");
                return {status: "cancel"};
            }
        };

        let currentWebtoonName = null;
        let currentWebtoonPath = null;
        let currentEpisodes = [];
        let currentEpIndex = -1;
        let pendingScrollTop = null;
        let isBookmarkPanelOpen = false;
        let bookmarks = [];

        async function selectFolder() {
            const result = await ApiWrapper.select_folder();
            if (result.status === "success") {
                loadLibrary();
            }
        }

        async function loadLibrary() {
            showLoader(true);
            const webtoons = await ApiWrapper.get_library();
            const list = document.getElementById('webtoon-list');
            list.innerHTML = '<div class="section-title">내 서재</div>';
            
            if (webtoons.length === 0) {
                list.innerHTML += '<div class="empty-state"><p>웹툰을 찾을 수 없습니다.</p></div>';
            } else {
                const grid = document.createElement('div');
                grid.className = 'webtoon-grid';
                
                webtoons.forEach((wt, index) => {
                    const card = document.createElement('div');
                    card.className = 'webtoon-card';
                    card.id = `wt-card-${index}`;
                    
                    const thumbHtml = wt.thumbnail ? `<img src="${wt.thumbnail}" alt="thumbnail">` : `<div style="height:120px; background:#222; display:flex; align-items:center; justify-content:center; color:#555; font-size:11px;">No Image</div>`;
                    
                    card.innerHTML = `
                        <button class="btn-edit-thumb" title="표지 변경">✏️</button>
                        ${thumbHtml}
                        <div class="info">
                            <div class="title" title="${wt.name}">${wt.name}</div>
                            <div class="meta">${wt.is_direct ? '단일 웹툰' : wt.count + '개의 화차'}</div>
                        </div>
                    `;
                    
                    const editBtn = card.querySelector('.btn-edit-thumb');
                    editBtn.onclick = async (e) => {
                        e.stopPropagation();
                        const res = await ApiWrapper.set_custom_thumbnail(wt.path);
                        if (res.status === 'success') {
                            loadLibrary();
                        }
                    };
                    
                    card.onclick = () => selectWebtoon(wt.path, wt.name, card);
                    grid.appendChild(card);
                });
                list.appendChild(grid);
            }
            showLoader(false);
        }

        async function selectWebtoon(path, name, element) {
            currentWebtoonName = name;
            currentWebtoonPath = path;
            
            // UI 업데이트
            document.querySelectorAll('.webtoon-card').forEach(el => el.classList.remove('active'));
            if (element) {
                element.classList.add('active');
            }
            
            showLoader(true);
            const episodes = await ApiWrapper.get_episodes(path);
            currentEpisodes = episodes;
            
            const epList = document.getElementById('episode-list');
            const epItems = document.getElementById('ep-items');
            epList.style.display = 'block';
            epItems.innerHTML = '';
            
            episodes.forEach((ep, index) => {
                const div = document.createElement('div');
                div.className = 'item';
                div.id = `ep-item-${index}`;
                div.innerHTML = `
                    <div class="item-name">${ep.name}</div>
                    <div class="item-meta">${ep.is_cbz ? 'CBZ' : 'Folder'}</div>
                `;
                div.onclick = () => loadEpisode(index);
                epItems.appendChild(div);
            });
            showLoader(false);
        }

        async function loadEpisode(index) {
            if (index < 0 || index >= currentEpisodes.length) return;
            
            currentEpIndex = index;
            const episode = currentEpisodes[index];
            
            // UI 업데이트
            document.querySelectorAll('#ep-items .item').forEach(el => el.classList.remove('active'));
            document.getElementById(`ep-item-${index}`).classList.add('active');
            document.getElementById('current-title').innerText = `${currentWebtoonName} - ${episode.name}`;
            document.getElementById('welcome-screen').style.display = 'none';
            
            showLoader(true);
            const images = await ApiWrapper.get_images(episode.path);
            
            const stack = document.getElementById('image-stack');
            stack.innerHTML = '';
            
            images.forEach(url => {
                const img = document.createElement('img');
                img.className = 'webtoon-image';
                img.src = url;
                img.loading = 'lazy';
                stack.appendChild(img);
            });
            
            if (pendingScrollTop !== null) {
                setTimeout(() => {
                    document.getElementById('viewer-container').scrollTop = pendingScrollTop;
                    pendingScrollTop = null;
                }, 100);
            } else {
                document.getElementById('viewer-container').scrollTop = 0;
            }
            
            document.getElementById('viewer-controls').style.display = 'flex';
            
            // 이전/다음 화 버튼 상태
            const nextBtn = document.querySelector('.btn-next');
            const navPrev = document.getElementById('nav-prev');
            const navNext = document.getElementById('nav-next');
            
            if (index === currentEpisodes.length - 1) {
                nextBtn.style.display = 'none';
                navNext.style.display = 'none';
            } else {
                nextBtn.style.display = 'block';
                navNext.style.display = 'block';
            }
            
            if (index === 0) {
                navPrev.style.display = 'none';
            } else {
                navPrev.style.display = 'block';
            }
            
            showLoader(false);
        }

        async function loadNextEpisode() {
            if (currentEpIndex + 1 < currentEpisodes.length) {
                await loadEpisode(currentEpIndex + 1);
            }
        }

        async function loadPrevEpisode() {
            if (currentEpIndex > 0) {
                await loadEpisode(currentEpIndex - 1);
            }
        }

        function toggleSidebar() {
            document.getElementById('sidebar').classList.toggle('collapsed');
        }

        function showLoader(show) {
            document.getElementById('loader').style.display = show ? 'block' : 'none';
        }

        function scrollToTop() {
            document.getElementById('viewer-container').scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        }

        // 스크롤 이벤트 리스너: 최상단 이동 버튼 표시/숨김
        document.getElementById('viewer-container').addEventListener('scroll', () => {
            const container = document.getElementById('viewer-container');
            const btnTop = document.getElementById('btn-scroll-top');
            if (container.scrollTop > 800) {
                btnTop.style.display = 'flex';
            } else {
                btnTop.style.display = 'none';
            }
        });

        async function toggleBookmarkPanel() {
            const panel = document.getElementById('bookmark-panel');
            isBookmarkPanelOpen = !isBookmarkPanelOpen;
            panel.style.display = isBookmarkPanelOpen ? 'flex' : 'none';
            if (isBookmarkPanelOpen) {
                bookmarks = await ApiWrapper.get_bookmarks();
                renderBookmarks();
            }
        }

        async function addBookmark() {
            if (currentEpIndex === -1 || !currentEpisodes[currentEpIndex]) {
                alert("현재 열려있는 웹툰이 없습니다.");
                return;
            }
            const container = document.getElementById('viewer-container');
            const data = {
                webtoonName: currentWebtoonName,
                webtoonPath: currentWebtoonPath,
                episodeIndex: currentEpIndex,
                episodeName: currentEpisodes[currentEpIndex].name,
                scrollTop: container.scrollTop
            };
            const res = await ApiWrapper.save_bookmark(data);
            if (res.status === 'success') {
                bookmarks = res.bookmarks;
                renderBookmarks();
            }
        }

        async function deleteBookmark(id, e) {
            e.stopPropagation();
            const res = await ApiWrapper.delete_bookmark(id);
            if (res.status === 'success') {
                bookmarks = res.bookmarks;
                renderBookmarks();
            }
        }

        async function loadBookmark(bm) {
            isBookmarkPanelOpen = false;
            document.getElementById('bookmark-panel').style.display = 'none';
            pendingScrollTop = bm.scrollTop;
            await selectWebtoon(bm.webtoonPath, bm.webtoonName, null);
            await loadEpisode(bm.episodeIndex);
        }

        function renderBookmarks() {
            const list = document.getElementById('bookmark-list');
            list.innerHTML = '';
            if (!bookmarks || bookmarks.length === 0) {
                list.innerHTML = '<div class="empty-state" style="padding:20px;"><p>저장된 책갈피가 없습니다.</p></div>';
                return;
            }
            bookmarks.forEach(bm => {
                const item = document.createElement('div');
                item.className = 'bookmark-item';
                item.onclick = () => loadBookmark(bm);
                item.innerHTML = `
                    <div class="title">${bm.webtoonName}</div>
                    <div class="ep-info">${bm.episodeName} (스크롤: ${Math.round(bm.scrollTop)}px)</div>
                    <div class="actions">
                        <span class="date">${bm.date}</span>
                        <button class="btn-delete-bm" onclick="deleteBookmark('${bm.id}', event)">삭제</button>
                    </div>
                `;
                list.appendChild(item);
            });
        }

        let currentScrollSpeed = 20;
        let isAutoScrolling = false;
        let scrollAnimationFrame = null;
        let stepTimeout = null;
        let isWaitingForNext = false;
        let autoNextTimeout = null;

        function checkAutoNext() {
            if (isWaitingForNext) return true;
            
            const container = document.getElementById('viewer-container');
            // 스크롤이 맨 아래에 도달했는지 확인 (바닥에서 10px 이내)
            // 단, scrollHeight가 clientHeight보다 클 때(스크롤이 존재할 때)만 동작하도록 강화
            const isAtBottom = container.scrollHeight > container.clientHeight && 
                               container.scrollTop + container.clientHeight >= container.scrollHeight - 10;

            if (isAtBottom) {
                if (currentEpIndex + 1 < currentEpisodes.length) {
                    isWaitingForNext = true;
                    const pauseSec = parseFloat(document.getElementById('step-pause').value) || 3;
                    
                    autoNextTimeout = setTimeout(async () => {
                        const currentContainer = document.getElementById('viewer-container');
                        // 대기 시간이 끝난 시점에도 여전히 바닥 근처인지 재확인 (이동 시 오차 고려 30px)
                        const stillAtBottom = currentContainer.scrollTop + currentContainer.clientHeight >= currentContainer.scrollHeight - 30;
                        
                        if (isAutoScrolling && stillAtBottom) {
                            await loadNextEpisode();
                            // 다음 화 로딩 후 레이아웃이 완전히 잡힐 때까지 1초간 쿨다운 (연속 점핑 방지)
                            setTimeout(() => { isWaitingForNext = false; }, 1000);
                        } else {
                            isWaitingForNext = false;
                        }
                    }, pauseSec * 1000);
                } else {
                    stopScroll();
                }
                return true;
            }
            return false;
        }

        function toggleScrollModeUI() {
            const mode = document.getElementById('scroll-mode').value;
            if (mode === 'smooth') {
                document.getElementById('ui-smooth').style.display = 'flex';
                document.getElementById('ui-step').style.display = 'none';
            } else {
                document.getElementById('ui-smooth').style.display = 'none';
                document.getElementById('ui-step').style.display = 'flex';
            }
            stopScroll();
        }

        function updateCtrlButtons() {
            const btn = document.getElementById('btn-play-pause');
            if (isAutoScrolling) {
                btn.classList.add('active');
                btn.innerText = '⏸';
            } else {
                btn.classList.remove('active');
                btn.innerText = '▶';
            }
        }

        function togglePlayPause() {
            if (isAutoScrolling) {
                pauseScroll();
            } else {
                startScroll();
            }
        }

        function showScrollMenu() {
            document.querySelector('.top-bar').classList.remove('menu-hidden');
        }

        function hideScrollMenu() {
            if (isWeb) {
                document.querySelector('.top-bar').classList.add('menu-hidden');
            }
        }

        function onStopBtnClick() {
            stopScroll();
            hideScrollMenu();
        }

        document.getElementById('viewer-container').addEventListener('click', () => {
            if (isAutoScrolling) {
                stopScroll();
            }
        });

        function startScroll() {
            if (isAutoScrolling) return;
            isAutoScrolling = true;
            updateCtrlButtons();
            hideScrollMenu();
            
            const container = document.getElementById('viewer-container');
            const mode = document.getElementById('scroll-mode').value;
            
            if (mode === 'smooth') {
                let lastTime = performance.now();
                function step(timestamp) {
                    if (!isAutoScrolling) return;
                    
                    if (checkAutoNext()) {
                        lastTime = timestamp; // 대기 시간 동안 delta time 누적 방지
                        scrollAnimationFrame = requestAnimationFrame(step);
                        return;
                    }
                    
                    const elapsed = timestamp - lastTime;
                    if (elapsed > 0) {
                        const pixelsPerMs = (currentScrollSpeed / 100) * 0.5;
                        container.scrollTop += pixelsPerMs * elapsed;
                        lastTime = timestamp;
                    }
                    scrollAnimationFrame = requestAnimationFrame(step);
                }
                scrollAnimationFrame = requestAnimationFrame(step);
            } else if (mode === 'step') {
                runStepScroll();
            }
        }

        function runStepScroll() {
            if (!isAutoScrolling) return;
            
            if (checkAutoNext()) {
                // checkAutoNext 내부에서 loadNextEpisode 후 isWaitingForNext=false가 될 때 다시 시작되도록 setTimeout 등을 걸어야 함.
                // 또는 loadNextEpisode 완료 후 startScroll 이 유지되므로 괜찮음.
                // 다만 step 스크롤 방식에서는 여기서 재귀를 잠시 끊고 기다려야 합니다.
                // isWaitingForNext가 해제되는 시점을 캐치하기 위해 폴링합니다.
                function waitStep() {
                    if (!isAutoScrolling) return;
                    if (isWaitingForNext) {
                        scrollAnimationFrame = requestAnimationFrame(waitStep);
                    } else {
                        // 대기가 끝났으므로 다음 스텝 진행
                        runStepScroll();
                    }
                }
                scrollAnimationFrame = requestAnimationFrame(waitStep);
                return;
            }
            
            const container = document.getElementById('viewer-container');
            const distance = parseInt(document.getElementById('step-distance').value) || 700;
            const pauseSec = parseFloat(document.getElementById('step-pause').value) || 3;
            
            const start = container.scrollTop;
            const change = distance;
            const duration = 500; // 0.5s animation
            let startTime = performance.now();
            
            function animateStep(timestamp) {
                if (!isAutoScrolling) return;
                
                let elapsed = timestamp - startTime;
                let progress = Math.min(elapsed / duration, 1);
                let ease = progress < 0.5 ? 2 * progress * progress : -1 + (4 - 2 * progress) * progress;
                
                container.scrollTop = start + change * ease;
                
                if (progress < 1) {
                    scrollAnimationFrame = requestAnimationFrame(animateStep);
                } else {
                    stepTimeout = setTimeout(() => {
                        if (isAutoScrolling) {
                            runStepScroll();
                        }
                    }, pauseSec * 1000);
                }
            }
            scrollAnimationFrame = requestAnimationFrame(animateStep);
        }

        function pauseScroll() {
            isAutoScrolling = false;
            if (scrollAnimationFrame) cancelAnimationFrame(scrollAnimationFrame);
            if (stepTimeout) clearTimeout(stepTimeout);
            if (autoNextTimeout) clearTimeout(autoNextTimeout);
            isWaitingForNext = false;
            updateCtrlButtons();
            showScrollMenu();
        }

        function stopScroll() {
            isAutoScrolling = false;
            if (scrollAnimationFrame) cancelAnimationFrame(scrollAnimationFrame);
            if (stepTimeout) clearTimeout(stepTimeout);
            if (autoNextTimeout) clearTimeout(autoNextTimeout);
            isWaitingForNext = false;
            updateCtrlButtons();
            showScrollMenu();
        }

        function updateScrollSpeed() {
            currentScrollSpeed = document.getElementById('auto-scroll-speed').value;
        }

        // 단축키 설정
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') {
                return; // 입력 요소에 포커스가 있을 때는 기본 동작 유지
            }

            const container = document.getElementById('viewer-container');

            if (e.code === 'Space') {
                e.preventDefault(); // 스페이스바 기본 스크롤 동작 방지
                
                if (isAutoScrolling) {
                    pauseScroll();
                } else {
                    startScroll();
                }
            } else if (e.code === 'ArrowDown') {
                e.preventDefault();
                container.scrollTop += 80;
            } else if (e.code === 'ArrowUp') {
                e.preventDefault();
                container.scrollTop -= 80;
            } else if (e.code === 'ArrowRight') {
                e.preventDefault();
                loadNextEpisode();
            } else if (e.code === 'ArrowLeft') {
                e.preventDefault();
                loadPrevEpisode();
            }
        });

        async function initApp() {
            if (isWeb) {
                document.getElementById('btn-fullscreen').style.display = 'flex';
            }
            
            try {
                const serverUrl = await ApiWrapper.get_server_url();
                const titleEl = document.getElementById('current-title');
                if (!isWeb) {
                    titleEl.innerHTML = `JoyViewer <span style="font-size:12px; color:var(--accent); font-weight:normal; margin-left:10px; opacity:0.8;">모바일 스트리밍: ${serverUrl}</span>`;
                } else {
                    titleEl.innerHTML = `JoyViewer <span style="font-size:12px; color:var(--accent); font-weight:normal; margin-left:10px; opacity:0.8;">모바일 접속 모드</span>`;
                }
            } catch (e) {}
            
            await loadSettings();
            await loadLibrary();
        }

        // 초기화
        window.addEventListener('pywebviewready', () => {
            if (window._isInit) return;
            window._isInit = true;
            isWeb = false;
            initApp();
        });

        // 웹 환경(pywebview 없음) 대비
        window.addEventListener('DOMContentLoaded', () => {
            if (isWeb && !window._isInit) {
                window._isInit = true;
                initApp();
            }
        });

        async function saveSettings() {
            const config = {
                scrollMode: document.getElementById('scroll-mode').value,
                smoothSpeed: document.getElementById('auto-scroll-speed').value,
                stepDistance: document.getElementById('step-distance').value,
                stepPause: document.getElementById('step-pause').value
            };
            
            const success = await ApiWrapper.save_config(config);
            if (success) {
                const btn = document.querySelector('button[title="현재 스크롤 설정 저장"]');
                const origColor = btn.style.color;
                btn.style.color = 'var(--accent)';
                setTimeout(() => btn.style.color = origColor, 1000);
            }
        }

        async function loadSettings() {
            const config = await ApiWrapper.load_config();
            if (config && Object.keys(config).length > 0) {
                if (config.scrollMode) document.getElementById('scroll-mode').value = config.scrollMode;
                if (config.smoothSpeed) document.getElementById('auto-scroll-speed').value = config.smoothSpeed;
                if (config.stepDistance) document.getElementById('step-distance').value = config.stepDistance;
                if (config.stepPause) document.getElementById('step-pause').value = config.stepPause;
                
                toggleScrollModeUI();
                updateScrollSpeed();
            }
        }

        function toggleFullscreen() {
            if (!document.fullscreenElement) {
                if (document.documentElement.requestFullscreen) {
                    document.documentElement.requestFullscreen();
                } else if (document.documentElement.webkitRequestFullscreen) {
                    document.documentElement.webkitRequestFullscreen();
                } else if (document.documentElement.msRequestFullscreen) {
                    document.documentElement.msRequestFullscreen();
                }
            } else {
                if (document.exitFullscreen) {
                    document.exitFullscreen();
                } else if (document.webkitExitFullscreen) {
                    document.webkitExitFullscreen();
                } else if (document.msExitFullscreen) {
                    document.msExitFullscreen();
                }
            }
        }
    </script>
</body>
</html>
"""

def reset_cache():
    if os.path.exists(TEMP_DIR):
        try:
            shutil.rmtree(TEMP_DIR)
        except:
            pass

if __name__ == "__main__":
    api = WebtoonApi()
    
    # 서버 스레드 시작
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # 웹뷰 창 생성
    window = webview.create_window(
        APP_NAME, 
        html=HTML_CONTENT, 
        js_api=api,
        width=1200, 
        height=800,
        background_color='#0a0a0c'
    )
    
    try:
        webview.start()
    finally:
        reset_cache()
