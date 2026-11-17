import sys
import threading
import types
from types import SimpleNamespace

import numpy as np

from app import create_app
from routes.attendance import _recognize_face
from recognition.engine import RecognitionEngine, engine
from recognition.liveness import TemporalLiveness


def test_missing_opencv_cascade_does_not_block_insightface(monkeypatch):
    class FakeFaceAnalysis:
        def __init__(self, name, providers):
            self.name = name
            self.providers = providers

        def prepare(self, ctx_id, det_size):
            self.ctx_id = ctx_id
            self.det_size = det_size

    insightface = types.ModuleType("insightface")
    app_module = types.ModuleType("insightface.app")
    app_module.FaceAnalysis = FakeFaceAnalysis
    monkeypatch.setitem(sys.modules, "insightface", insightface)
    monkeypatch.setitem(sys.modules, "insightface.app", app_module)

    class FakeCv2:
        data = types.SimpleNamespace(haarcascades="")
        error = RuntimeError

        @staticmethod
        def CascadeClassifier(*_args, **_kwargs):
            raise RuntimeError("cascade unavailable")

    monkeypatch.setattr("recognition.engine.cv2", FakeCv2)

    engine = RecognitionEngine()
    engine.start_loading()
    engine._loader_thread.join(timeout=2)

    assert engine.status == "InsightFace model loaded"
    assert engine.using_insightface is True
    assert engine.load_error is None


def test_liveness_accepts_a_moving_face_on_second_frame():
    checker = TemporalLiveness()

    assert checker.observe(1, 0, (0, 0, 20, 20)) is False
    assert checker.observe(1, 0, (2, 0, 22, 20)) is True


def test_model_status_starts_loading_without_blocking(monkeypatch):
    entered_loader = threading.Event()
    allow_load_to_finish = threading.Event()

    class FakeFaceAnalysis:
        def __init__(self, name, providers):
            entered_loader.set()
            allow_load_to_finish.wait(timeout=2)

        def prepare(self, ctx_id, det_size):
            self.ctx_id = ctx_id
            self.det_size = det_size

    insightface = types.ModuleType("insightface")
    app_module = types.ModuleType("insightface.app")
    app_module.FaceAnalysis = FakeFaceAnalysis
    monkeypatch.setitem(sys.modules, "insightface", insightface)
    monkeypatch.setitem(sys.modules, "insightface.app", app_module)

    engine = RecognitionEngine()
    status = engine.status
    try:
        assert status == "InsightFace model loading"
        assert entered_loader.wait(timeout=1)
    finally:
        allow_load_to_finish.set()
        engine._loader_thread.join(timeout=1)

    assert engine.status == "InsightFace model loaded"


def test_fallback_recognizes_consistent_stored_embeddings(monkeypatch):
    app = create_app(test_db_uri="sqlite:///:memory:")
    monkeypatch.setattr(engine, "_model", None)
    monkeypatch.setattr(engine, "_load_error", "test fallback")

    matching_embeddings = [
        SimpleNamespace(embedding=RecognitionEngine.serialize_embedding(np.array([1.0, 0.0])), dimension=2)
        for _ in range(4)
    ]
    other_embeddings = [
        SimpleNamespace(embedding=RecognitionEngine.serialize_embedding(np.array([0.0, 1.0])), dimension=2)
        for _ in range(4)
    ]
    students = [
        SimpleNamespace(name="Matching Student", embeddings=matching_embeddings),
        SimpleNamespace(name="Other Student", embeddings=other_embeddings),
    ]

    with app.app_context():
        face = SimpleNamespace(embedding=np.array([1.0, 0.0], dtype=np.float32))
        student, score, recognized = _recognize_face(face, students)

    assert recognized is True
    assert student.name == "Matching Student"
    assert score == 1.0
