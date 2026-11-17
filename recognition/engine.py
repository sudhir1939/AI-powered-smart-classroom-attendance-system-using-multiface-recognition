import base64
import io
import threading
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class DetectedFace:
    box: tuple[int, int, int, int]
    embedding: np.ndarray | None
    similarity: float | None = None
    name: str = "Unknown"
    student_id: str | None = None
    quality_score: float | None = None
    quality_flags: tuple[str, ...] = ()


class RecognitionModelLoading(RuntimeError):
    pass


class RecognitionEngine:
    def __init__(self):
        self._model = None
        self._load_error = None
        self._loading = False
        self._loader_thread = None
        self._cascade_error = None
        self._lock = threading.Lock()
        self._cascade = None
        try:
            self._cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        except (AttributeError, cv2.error):
            self._cascade_error = "OpenCV face detector is unavailable."

    def start_loading(self):
        with self._lock:
            if self._model is not None or self._load_error is not None or self._loading:
                return
            self._loading = True
            self._loader_thread = threading.Thread(target=self._load_model, name="face-model-loader", daemon=True)
            self._loader_thread.start()

    def _load_model(self):
        try:
            from insightface.app import FaceAnalysis
            model = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
            model.prepare(ctx_id=0, det_size=(640, 640))
            self._model = model
        except Exception as exc:
            self._load_error = str(exc)
        finally:
            self._loading = False

    @property
    def status(self):
        if self._model:
            return "InsightFace model loaded"
        if self._load_error:
            return f"InsightFace unavailable; OpenCV fallback active ({self._load_error})"
        self.start_loading()
        if self._loading:
            return "InsightFace model loading"
        if self._model:
            return "InsightFace model loaded"
        if self._load_error:
            return f"InsightFace unavailable; OpenCV fallback active ({self._load_error})"
        if self._cascade_error:
            return f"InsightFace unavailable; OpenCV fallback active ({self._cascade_error})"
        return "InsightFace model not loaded"

    @property
    def load_error(self):
        return self._load_error

    @property
    def using_insightface(self):
        return self._model is not None

    @staticmethod
    def decode_image(data_url: str):
        if not data_url or "," not in data_url:
            raise ValueError("Invalid image payload.")
        encoded = data_url.split(",", 1)[1]
        try:
            raw = base64.b64decode(encoded)
            image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        except Exception as exc:
            raise ValueError("Image could not be decoded.") from exc
        if image is None:
            raise ValueError("Image could not be decoded.")
        return image

    @staticmethod
    def decode_bytes(raw: bytes):
        if not raw:
            raise ValueError("The uploaded image is empty.")
        image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("The uploaded file is not a valid image.")
        return image

    def detect(self, image) -> list[DetectedFace]:
        model = self._model
        if model is None and self._load_error is None:
            self.start_loading()
            if self._loading:
                raise RecognitionModelLoading("Face recognition model is loading. Scanning will start automatically.")
            model = self._model
        if model is not None:
            faces = model.get(image)
            return [
                DetectedFace(
                    box=tuple(int(value) for value in face.bbox),
                    embedding=self._normalize(face.embedding),
                    quality_score=self.face_quality(image, tuple(int(value) for value in face.bbox))[0],
                    quality_flags=self.face_quality(image, tuple(int(value) for value in face.bbox))[1],
                )
                for face in faces
                if face.embedding is not None
            ]

        if self._cascade is None:
            return []
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        candidates = list(self._cascade.detectMultiScale(enhanced, scaleFactor=1.08, minNeighbors=5, minSize=(45, 45)))
        enlarged = cv2.resize(enhanced, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
        enlarged_boxes = self._cascade.detectMultiScale(enlarged, scaleFactor=1.08, minNeighbors=4, minSize=(60, 60))
        candidates.extend((int(x / 1.5), int(y / 1.5), int(width / 1.5), int(height / 1.5)) for x, y, width, height in enlarged_boxes)
        boxes = self._deduplicate_boxes(candidates)
        detected = []
        for x, y, width, height in boxes:
            box = (int(x), int(y), int(x + width), int(y + height))
            quality_score, quality_flags = self.face_quality(image, box)
            detected.append(DetectedFace(box, self._fallback_embedding(image, box), quality_score=quality_score, quality_flags=quality_flags))
        return detected

    @staticmethod
    def face_quality(image, box):
        x1, y1, x2, y2 = box
        height, width = image.shape[:2]
        crop = image[max(0, y1):min(height, y2), max(0, x1):min(width, x2)]
        if crop.size == 0:
            return 0.0, ("face_not_visible",)
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray))
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        area_ratio = (crop.shape[0] * crop.shape[1]) / max(1, height * width)
        flags = []
        if brightness < 45:
            flags.append("too_dark")
        if brightness > 220:
            flags.append("too_bright")
        if sharpness < 20:
            flags.append("blurry")
        if area_ratio < 0.015:
            flags.append("face_too_small")
        score = max(0.0, min(1.0, (min(brightness, 255 - brightness) / 127.5) * 0.4 + min(sharpness / 120, 1) * 0.4 + min(area_ratio / 0.08, 1) * 0.2))
        return round(score, 3), tuple(flags)

    @staticmethod
    def _deduplicate_boxes(boxes):
        selected = []
        for box in sorted(boxes, key=lambda item: item[2] * item[3], reverse=True):
            x, y, width, height = box
            current = (x, y, x + width, y + height)
            overlaps = False
            for existing in selected:
                ex, ey, ew, eh = existing
                ix = max(0, min(current[2], ex + ew) - max(current[0], ex))
                iy = max(0, min(current[3], ey + eh) - max(current[1], ey))
                intersection = ix * iy
                if intersection / max(1, min(width * height, ew * eh)) > 0.35:
                    overlaps = True
                    break
            if not overlaps:
                selected.append((x, y, width, height))
        return selected

    @staticmethod
    def _fallback_embedding(image, box):
        """Create a lightweight local feature vector when InsightFace is unavailable."""
        x1, y1, x2, y2 = box
        height, width = image.shape[:2]
        crop = image[max(0, y1):min(height, y2), max(0, x1):min(width, x2)]
        if crop.size == 0:
            return None
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        normalized = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        resized = cv2.resize(normalized, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        edges_x = cv2.Sobel(normalized, cv2.CV_32F, 1, 0, ksize=3)
        edges_y = cv2.Sobel(normalized, cv2.CV_32F, 0, 1, ksize=3)
        edge_strength = cv2.magnitude(edges_x, edges_y)
        edge_strength = cv2.normalize(edge_strength, None, 0, 1, cv2.NORM_MINMAX)
        structure = cv2.resize(edge_strength, (32, 32), interpolation=cv2.INTER_AREA)
        appearance = (resized * 0.65) + (structure * 0.35)
        histogram = cv2.calcHist([normalized], [0], None, [32], [0, 256]).flatten().astype(np.float32)
        vector = np.concatenate((appearance.flatten(), histogram / max(histogram.sum(), 1.0)))
        return RecognitionEngine._normalize(vector)

    @staticmethod
    def _normalize(embedding):
        vector = np.asarray(embedding, dtype=np.float32)
        norm = np.linalg.norm(vector)
        return vector / norm if norm else vector

    @staticmethod
    def similarity(first, second):
        first = RecognitionEngine._normalize(first)
        second = RecognitionEngine._normalize(second)
        return float(np.dot(first, second))

    @staticmethod
    def serialize_embedding(embedding):
        return RecognitionEngine._normalize(embedding).astype(np.float32).tobytes()

    @staticmethod
    def deserialize_embedding(value, dimension):
        return np.frombuffer(value, dtype=np.float32, count=dimension)


engine = RecognitionEngine()
