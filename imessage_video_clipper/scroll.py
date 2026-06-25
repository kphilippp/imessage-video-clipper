from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class ScrollMeasurement:
    displacement: float
    confidence: float
    frame_index: int


class ScrollDetector:
    def __init__(
        self,
        top_crop: float = 0.15,
        bottom_crop: float = 0.15,
        left_crop: float = 0.05,
        right_crop: float = 0.05,
        min_confidence: float = 0.05,
        noise_threshold: float = 1.0,
    ):
        self.top_crop = top_crop
        self.bottom_crop = bottom_crop
        self.left_crop = left_crop
        self.right_crop = right_crop
        self.min_confidence = min_confidence
        self.noise_threshold = noise_threshold

        self._roi_bounds = None
        self._hann_window = None

    def setup(self, frame_height: int, frame_width: int):
        y1 = int(frame_height * self.top_crop)
        y2 = int(frame_height * (1.0 - self.bottom_crop))
        x1 = int(frame_width * self.left_crop)
        x2 = int(frame_width * (1.0 - self.right_crop))
        self._roi_bounds = (y1, y2, x1, x2)

        roi_h = y2 - y1
        roi_w = x2 - x1
        self._hann_window = cv2.createHanningWindow((roi_w, roi_h), cv2.CV_64F)

    def measure(self, prev_frame: np.ndarray, curr_frame: np.ndarray, frame_index: int) -> ScrollMeasurement:
        y1, y2, x1, x2 = self._roi_bounds

        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)

        prev_roi = prev_gray[y1:y2, x1:x2].astype(np.float64)
        curr_roi = curr_gray[y1:y2, x1:x2].astype(np.float64)

        (dx, dy), response = cv2.phaseCorrelate(prev_roi, curr_roi, self._hann_window)

        # dy < 0 means content moved up on screen = user scrolled down
        scroll_amount = -dy

        if response < self.min_confidence:
            return ScrollMeasurement(displacement=0.0, confidence=response, frame_index=frame_index)

        if abs(scroll_amount) < self.noise_threshold:
            scroll_amount = 0.0

        return ScrollMeasurement(displacement=scroll_amount, confidence=response, frame_index=frame_index)


class ScrollAccumulator:
    def __init__(
        self,
        capture_threshold: float,
        settle_threshold: float = 3.0,
        max_settle_wait: int = 30,
        final_frame_ratio: float = 0.20,
    ):
        self.capture_threshold = capture_threshold
        self.settle_threshold = settle_threshold
        self.max_settle_wait = max_settle_wait
        self.final_frame_ratio = final_frame_ratio

        self.accumulated = 0.0
        self._pending = False
        self._frames_since_pending = 0

    def update(self, measurement: ScrollMeasurement) -> bool:
        if measurement.displacement > 0:
            self.accumulated += measurement.displacement

        if self.accumulated >= self.capture_threshold:
            if not self._pending:
                self._pending = True
                self._frames_since_pending = 0

        if self._pending:
            self._frames_since_pending += 1
            if abs(measurement.displacement) < self.settle_threshold or self._frames_since_pending > self.max_settle_wait:
                self._pending = False
                self.accumulated = 0.0
                return True

        return False

    def should_capture_final(self) -> bool:
        return self.accumulated > self.capture_threshold * self.final_frame_ratio
