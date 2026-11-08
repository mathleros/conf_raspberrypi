import pytest

from irobot.common.hardware.runtime_factory import load_face_gallery


def test_load_face_gallery_returns_none_when_unavailable(monkeypatch, capsys):
    pytest.importorskip("cv2")
    from irobot.common.hardware.camera.detector.face_gallery import FaceGallery

    def _missing(settings):
        raise FileNotFoundError("assets/face introuvable")

    monkeypatch.setattr(FaceGallery, "load", staticmethod(_missing))

    assert load_face_gallery(object()) is None
    assert "[RUNTIME] galerie de visages indisponible" in capsys.readouterr().out


def test_load_face_gallery_returns_gallery(monkeypatch):
    pytest.importorskip("cv2")
    from irobot.common.hardware.camera.detector.face_gallery import FaceGallery

    gallery = object()
    monkeypatch.setattr(FaceGallery, "load", staticmethod(lambda settings: gallery))

    assert load_face_gallery(object()) is gallery
