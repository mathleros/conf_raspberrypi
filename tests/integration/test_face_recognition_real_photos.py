"""Reconnaissance de visages sur de vraies photos publiques (YuNet + SFace).

Photos : Wikimedia Commons (domaine public) et OpenCV samples (lena.jpg).
Le prénom de test est « Barack » (galerie `gallery/Barack.jpg`).
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from irobot.common.config.settings import RuntimeSettings
from irobot.common.hardware.camera.detector.face_gallery import FaceGallery

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "face_recognition"
_DEFAULTS = RuntimeSettings()
_MODELS_PRESENT = (
    Path(_DEFAULTS.camera_face_model_path).is_file()
    and Path(_DEFAULTS.camera_face_recognition_model_path).is_file()
)

pytestmark = pytest.mark.skipif(not _MODELS_PRESENT, reason="modèles YuNet/SFace absents")


@pytest.fixture(scope="module")
def gallery() -> FaceGallery:
    settings = RuntimeSettings(camera_face_gallery_dir=str(ASSETS / "gallery"))
    loaded = FaceGallery.load(settings)
    assert loaded.names() == ["Barack"]
    return loaded


def _best_score(gallery: FaceGallery, image: np.ndarray, name: str = "Barack") -> float | None:
    """Meilleure similarité entre la cible et les visages détectés (None si aucun visage)."""
    target = gallery.get(name)
    assert target is not None and gallery.embedder is not None
    detector = cv2.FaceDetectorYN.create(
        _DEFAULTS.camera_face_model_path, "", (image.shape[1], image.shape[0]),
        score_threshold=_DEFAULTS.camera_face_score_threshold, nms_threshold=0.3, top_k=5000,
    )
    _, faces = detector.detect(image)
    if faces is None:
        return None
    scores = [gallery.embedder.similarity(target, gallery.embedder.embed(image, face)) for face in faces]
    return max(scores)


def _read(name: str) -> np.ndarray:
    image = cv2.imread(str(ASSETS / name))
    assert image is not None, name
    return image


def test_same_person_on_other_photo_is_recognized(gallery: FaceGallery) -> None:
    score = _best_score(gallery, _read("same_person.jpg"))
    assert score is not None
    assert gallery.embedder.is_match(score), score


def test_other_face_is_not_recognized(gallery: FaceGallery) -> None:
    score = _best_score(gallery, _read("other_face.jpg"))
    assert score is None or not gallery.embedder.is_match(score), score


def test_dog_is_not_recognized(gallery: FaceGallery) -> None:
    score = _best_score(gallery, _read("dog.jpg"))
    assert score is None or not gallery.embedder.is_match(score), score


def test_target_is_found_among_several_faces(gallery: FaceGallery) -> None:
    """Deux visages côte à côte : la cible doit être reconnue parmi eux."""
    height = 480
    left = _read("other_face.jpg")
    right = _read("same_person.jpg")
    left = cv2.resize(left, (int(left.shape[1] * height / left.shape[0]), height))
    right = cv2.resize(right, (int(right.shape[1] * height / right.shape[0]), height))
    composed = cv2.hconcat([left, right])
    score = _best_score(gallery, composed)
    assert score is not None
    assert gallery.embedder.is_match(score), score


def test_unknown_name_is_not_in_gallery(gallery: FaceGallery) -> None:
    assert gallery.resolve("Quentin") is None
    assert gallery.resolve("barack") == "Barack"
