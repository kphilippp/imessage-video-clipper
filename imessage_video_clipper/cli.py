import argparse
import os
import sys

from . import __version__
from .extractor import FrameExtractor
from .scroll import ScrollAccumulator, ScrollDetector


def main():
    parser = argparse.ArgumentParser(
        prog="imessage-video-clipper",
        description="Split a screen recording of a text message conversation into sequential, non-overlapping screenshots.",
    )
    parser.add_argument("video", help="Path to the input video file")
    parser.add_argument("-o", "--output", default="./output", help="Output directory (default: ./output)")
    parser.add_argument(
        "--overlap",
        type=float,
        default=0.15,
        help="Fraction of overlap between consecutive screenshots (default: 0.15, range: 0.0-0.5)",
    )
    parser.add_argument("--top-crop", type=float, default=0.15, help="Fraction of frame to exclude from top (default: 0.15)")
    parser.add_argument(
        "--bottom-crop", type=float, default=0.15, help="Fraction of frame to exclude from bottom (default: 0.15)"
    )
    parser.add_argument("--frame-skip", type=int, default=1, help="Process every Nth frame for speed (default: 1)")
    parser.add_argument("--min-confidence", type=float, default=0.05, help="Minimum phase correlation confidence (default: 0.05)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show per-frame scroll measurements")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    args = parser.parse_args()

    if not os.path.isfile(args.video):
        print(f"Error: Video file not found: {args.video}", file=sys.stderr)
        sys.exit(1)

    if not 0.0 <= args.overlap <= 0.5:
        print("Error: --overlap must be between 0.0 and 0.5", file=sys.stderr)
        sys.exit(1)

    import cv2

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"Error: Cannot open video: {args.video}", file=sys.stderr)
        sys.exit(1)
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    content_height = frame_height * (1.0 - args.top_crop - args.bottom_crop)
    capture_threshold = content_height * (1.0 - args.overlap)

    detector = ScrollDetector(
        top_crop=args.top_crop,
        bottom_crop=args.bottom_crop,
        min_confidence=args.min_confidence,
    )

    accumulator = ScrollAccumulator(capture_threshold=capture_threshold)

    extractor = FrameExtractor(
        video_path=args.video,
        output_dir=args.output,
        scroll_detector=detector,
        scroll_accumulator=accumulator,
        frame_skip=args.frame_skip,
        verbose=args.verbose,
    )

    print(f"iMessage Video Clipper v{__version__}")
    print(f"Capture threshold: {capture_threshold:.0f}px ({args.overlap:.0%} overlap)")
    print()

    saved = extractor.run()

    print()
    print(f"Done! {len(saved)} screenshots saved to: {os.path.abspath(args.output)}")


if __name__ == "__main__":
    main()
