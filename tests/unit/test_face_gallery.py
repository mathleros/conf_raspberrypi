from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from irobot.common.config.settings import RuntimeSettings
from irobot.common.hardware.camera.detector import FaceDetector
from irobot.common.hardware.camera.detector import face_gallery
from irobot.common.hardware.camera.detector.face_gallery import FaceGallery, normalize_name


def test_resolve_ignores_case_and_accents():
    gallery = FaceGallery({"Mathieu": np.zeros(1), "Élodie": np.zeros(1)})
    assert gallery.resolve("mathieu") == "Mathieu"
    assert gallery.resolve("elodie") == "Élodie"
    assert gallery.resolve("Bob") is None
    assert gallery.get("Bob") is None
    assert gallery.names() == ["Mathieu", "Élodie"]
    assert normalize_name(" ÉLodie ") == "elodie"


def test_load_keeps_only_single_face_photos(tmp_path, monkeypatch):
    for name in ("Mathieu.jpg", "QUENTIN.PNG", "Deux.jpeg", "Aucun.jpg", "notes.txt"):
        (tmp_path / name).write_bytes(b"x")
    (tmp_path / "Moi.jpg").write_bytes(b"x")
    model = tmp_path / "m.onnx"
    model.touch()
    settings = RuntimeSettings(
        camera_face_gallery_dir=str(tmp_path), camera_face_model_path=str(model),
        camera_face_recognition_model_path=str(model),
    )
    counts = {"Deux": 2, "Aucun": 0}

    class Yunet:
        current = ""

        def setInputSize(self, size):
            pass

        def detect(self, image):
            count = counts.get(self.current, 1)
            return 1, (np.zeros((count, 15), np.float32) if count else None)

    yunet = Yunet()
    monkeypatch.setattr(cv2, "FaceDetectorYN", SimpleNamespace(create=lambda *a, **k: yunet))
    monkeypatch.setattr(cv2, "imread", lambda path: (setattr(yunet, "current", path.rsplit("/", 1)[-1].split(".")[0]),
                                                      np.zeros((10, 10, 3), np.uint8))[1])
    monkeypatch.setattr(face_gallery, "FaceEmbedder", lambda s: SimpleNamespace(
        embed=lambda image, face: np.ones(3, np.float32)))
    gallery = FaceGallery.load(settings)
    assert gallery.names() == ["Mathieu", "Moi", "QUENTIN"]


def test_load_without_directory_gives_empty_gallery(tmp_path):
    assert FaceGallery.load(RuntimeSettings(camera_face_gallery_dir=str(tmp_path / "absent"))).names() == []


class _Embedder:
    """Embedding = 3e valeur de la ligne YuNet (id de personne)."""

    def embed(self, frame, face):
        return np.array([face[4]], np.float32)

    def similarity(self, first, second):
        return 1.0 if first[0] == second[0] else 0.0

    def is_match(self, score):
        return score >= 0.363


@pytest.fixture
def detector(tmp_path, monkeypatch):
    model = tmp_path / "m.onnx"
    model.touch()
    settings = RuntimeSettings(
        camera_face_model_path=str(model), camera_face_grace_frames=1, camera_face_recognition_every_n=3,
        camera_clahe_enabled=False, camera_exposure_value=0.0,
    )
    net = SimpleNamespace(faces=None, setInputSize=lambda size: None)
    net.detect = lambda frame: (1, net.faces)
    monkeypatch.setattr(cv2, "FaceDetectorYN", SimpleNamespace(create=lambda *a, **k: net))
    monkeypatch.setattr("irobot.common.hardware.camera.detector.face_detector.FaceEmbedder", lambda s: _Embedder())
    return FaceDetector(settings), net


def _row(x, person, width=100, score=0.9):
    row = np.zeros(15, np.float32)
    row[:4] = (x, 50, width, width)
    row[4] = person
    row[-1] = score
    return row


FRAME = np.zeros((480, 640, 3), np.uint8)


def test_target_picks_the_right_person_not_the_largest(detector):
    face_detector, net = detector
    net.faces = np.array([_row(10, 1, width=200), _row(300, 2, width=80)])
    face_detector.set_target("Quentin", np.array([2], np.float32))
    detection = face_detector.detect(FRAME)
    assert detection.identity == "Quentin"
    assert detection.diameter_px == 80


def test_target_absent_never_falls_back_to_another_face(detector):
    face_detector, net = detector
    net.faces = np.array([_row(10, 1)])
    face_detector.set_target("Quentin", np.array([2], np.float32))
    assert face_detector.detect(FRAME) is None


def test_target_is_tracked_by_iou_between_recognitions(detector):
    face_detector, net = detector
    face_detector.set_target("Quentin", np.array([2], np.float32))
    net.faces = np.array([_row(10, 1, width=200), _row(300, 2, width=80)])
    face_detector.detect(FRAME)
    embeds = []
    real = face_detector._embedder.embed
    face_detector._embedder.embed = lambda frame, face: embeds.append(1) or real(frame, face)
    # Les ids changent mais la boîte de la cible bouge peu : pas de nouvelle reconnaissance.
    net.faces = np.array([_row(10, 1, width=200), _row(305, 9, width=80)])
    assert face_detector.detect(FRAME).diameter_px == 80
    assert embeds == []
    face_detector.detect(FRAME)
    face_detector.detect(FRAME)  # N=3 : reconnaissance, la cible n'est plus là
    assert embeds


def test_clearing_target_restores_largest_face(detector):
    face_detector, net = detector
    net.faces = np.array([_row(10, 1, width=200), _row(300, 2, width=80)])
    face_detector.set_target("Quentin", np.array([2], np.float32))
    face_detector.detect(FRAME)
    face_detector.set_target(None)
    detection = face_detector.detect(FRAME)
    assert detection.identity is None
    assert detection.diameter_px == 200


def test_target_requires_name_and_embedding(detector):
    with pytest.raises(ValueError):
        detector[0].set_target("Quentin")
