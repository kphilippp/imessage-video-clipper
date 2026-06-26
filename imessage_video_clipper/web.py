import os
import shutil
import tempfile
import threading
import traceback
import uuid
import zipfile

from flask import Flask, jsonify, render_template, request, send_file

from .extractor import FrameExtractor
from .scroll import ScrollAccumulator, ScrollDetector

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500MB

UPLOAD_DIR = tempfile.mkdtemp(prefix="imessage_clipper_")
JOBS = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    if "video" not in request.files:
        return jsonify({"error": "No video file provided"}), 400

    file = request.files["video"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".mov", ".mp4"):
        return jsonify({"error": "Only .mov and .mp4 files are supported"}), 400

    job_id = str(uuid.uuid4())
    job_dir = os.path.join(UPLOAD_DIR, job_id)
    os.makedirs(job_dir)

    video_path = os.path.join(job_dir, f"input{ext}")
    output_dir = os.path.join(job_dir, "output")
    os.makedirs(output_dir)

    file.save(video_path)

    overlap = float(request.form.get("overlap", 0.15))
    top_crop = float(request.form.get("top_crop", 0.15))
    bottom_crop = float(request.form.get("bottom_crop", 0.15))

    import cv2

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": "Cannot open video file"}), 400

    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()

    # Auto frame-skip: process ~10 frames per second of video, minimum 1
    frame_skip = max(1, int(fps / 10)) if fps > 0 else 1

    content_height = frame_height * (1.0 - top_crop - bottom_crop)
    capture_threshold = content_height * (1.0 - overlap)

    JOBS[job_id] = {
        "status": "processing",
        "progress": 0,
        "total_frames": total_frames,
        "output_dir": output_dir,
        "job_dir": job_dir,
        "screenshots": [],
        "error": None,
    }

    def process():
        try:
            detector = ScrollDetector(top_crop=top_crop, bottom_crop=bottom_crop, min_confidence=0.05)
            accumulator = ScrollAccumulator(capture_threshold=capture_threshold)
            extractor = FrameExtractor(
                video_path=video_path,
                output_dir=output_dir,
                scroll_detector=detector,
                scroll_accumulator=accumulator,
                frame_skip=frame_skip,
                progress_callback=lambda current, total: update_progress(job_id, current, total),
            )

            saved = extractor.run()

            screenshots = [os.path.basename(p) for p in saved]
            JOBS[job_id]["screenshots"] = screenshots
            JOBS[job_id]["status"] = "done"
            JOBS[job_id]["progress"] = 100
        except Exception as e:
            traceback.print_exc()
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"] = str(e)

    thread = threading.Thread(target=process, daemon=True)
    thread.start()

    return jsonify({"job_id": job_id, "total_frames": total_frames, "frame_skip": frame_skip})


def update_progress(job_id, current_frame, total_frames):
    if job_id in JOBS and total_frames > 0:
        JOBS[job_id]["progress"] = int(current_frame / total_frames * 100)


@app.route("/status/<job_id>")
def job_status(job_id):
    if job_id not in JOBS:
        return jsonify({"error": "Job not found"}), 404

    job = JOBS[job_id]
    return jsonify({
        "status": job["status"],
        "progress": job["progress"],
        "screenshots": job["screenshots"] if job["status"] == "done" else [],
        "count": len(job["screenshots"]) if job["status"] == "done" else 0,
        "error": job["error"],
    })


@app.route("/screenshot/<job_id>/<filename>")
def get_screenshot(job_id, filename):
    if job_id not in JOBS:
        return jsonify({"error": "Job not found"}), 404
    filepath = os.path.join(JOBS[job_id]["output_dir"], filename)
    if not os.path.isfile(filepath):
        return jsonify({"error": "Screenshot not found"}), 404
    return send_file(filepath, mimetype="image/png")


@app.route("/download/<job_id>")
def download_zip(job_id):
    if job_id not in JOBS:
        return jsonify({"error": "Job not found"}), 404

    job = JOBS[job_id]
    zip_path = os.path.join(job["job_dir"], "screenshots.zip")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename in job["screenshots"]:
            filepath = os.path.join(job["output_dir"], filename)
            zf.write(filepath, filename)

    return send_file(zip_path, as_attachment=True, download_name="screenshots.zip")


def main():
    import argparse

    parser = argparse.ArgumentParser(prog="imessage-video-clipper-web")
    parser.add_argument("--port", type=int, default=5050, help="Port to run on (default: 5050)")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    args = parser.parse_args()

    print(f"Starting iMessage Video Clipper UI at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
