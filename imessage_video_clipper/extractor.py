import os
import sys

import cv2

from .scroll import ScrollAccumulator, ScrollDetector


class FrameExtractor:
    def __init__(
        self,
        video_path: str,
        output_dir: str,
        scroll_detector: ScrollDetector,
        scroll_accumulator: ScrollAccumulator,
        frame_skip: int = 1,
        verbose: bool = False,
        progress_callback=None,
    ):
        self.video_path = video_path
        self.output_dir = output_dir
        self.scroll_detector = scroll_detector
        self.scroll_accumulator = scroll_accumulator
        self.frame_skip = frame_skip
        self.verbose = verbose
        self.progress_callback = progress_callback

    def run(self) -> list[str]:
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {self.video_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        fps = cap.get(cv2.CAP_PROP_FPS)

        print(f"Video: {frame_width}x{frame_height}, {total_frames} frames, {fps:.1f} fps")

        self.scroll_detector.setup(frame_height, frame_width)

        os.makedirs(self.output_dir, exist_ok=True)

        ret, first_frame = cap.read()
        if not ret:
            cap.release()
            raise RuntimeError("Video contains no readable frames")

        saved_paths = []
        screenshot_num = 1
        path = self._save_frame(first_frame, screenshot_num, total_frames)
        saved_paths.append(path)

        prev_frame = first_frame
        frame_index = 0
        last_frame = first_frame

        while True:
            if self.frame_skip > 1:
                frame_index += self.frame_skip
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            else:
                frame_index += 1

            ret, curr_frame = cap.read()
            if not ret:
                break

            last_frame = curr_frame

            measurement = self.scroll_detector.measure(prev_frame, curr_frame, frame_index)

            if self.verbose:
                print(
                    f"  Frame {frame_index}/{total_frames}: "
                    f"dy={measurement.displacement:+.1f}px, "
                    f"conf={measurement.confidence:.3f}, "
                    f"accum={self.scroll_accumulator.accumulated:.0f}px",
                    file=sys.stderr,
                )

            should_capture = self.scroll_accumulator.update(measurement)

            if should_capture:
                screenshot_num += 1
                path = self._save_frame(curr_frame, screenshot_num, total_frames)
                saved_paths.append(path)

            prev_frame = curr_frame

            if frame_index % 100 == 0:
                if self.progress_callback:
                    self.progress_callback(frame_index, total_frames)
                elif not self.verbose:
                    pct = frame_index / total_frames * 100 if total_frames > 0 else 0
                    print(f"  Processing... {pct:.0f}%", file=sys.stderr)

        if self.scroll_accumulator.should_capture_final():
            screenshot_num += 1
            path = self._save_frame(last_frame, screenshot_num, total_frames)
            saved_paths.append(path)

        cap.release()
        return saved_paths

    def _save_frame(self, frame, screenshot_num: int, total_frames: int) -> str:
        digits = 4 if total_frames > 9999 else 3
        filename = f"screenshot_{screenshot_num:0{digits}d}.png"
        filepath = os.path.join(self.output_dir, filename)
        cv2.imwrite(filepath, frame)
        print(f"  Saved: {filename}")
        return filepath
