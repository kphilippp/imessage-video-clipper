import os
import shutil
import tempfile
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

    try:
        import cv2

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return jsonify({"error": "Cannot open video file"}), 400
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        content_height = frame_height * (1.0 - top_crop - bottom_crop)
        capture_threshold = content_height * (1.0 - overlap)

        detector = ScrollDetector(top_crop=top_crop, bottom_crop=bottom_crop, min_confidence=0.05)
        accumulator = ScrollAccumulator(capture_threshold=capture_threshold)
        extractor = FrameExtractor(
            video_path=video_path,
            output_dir=output_dir,
            scroll_detector=detector,
            scroll_accumulator=accumulator,
        )

        saved = extractor.run()

        screenshots = []
        for path in saved:
            filename = os.path.basename(path)
            screenshots.append(filename)

        JOBS[job_id] = {"output_dir": output_dir, "screenshots": screenshots, "job_dir": job_dir}

        return jsonify({"job_id": job_id, "screenshots": screenshots, "count": len(screenshots)})

    except Exception as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": str(e)}), 500


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
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
