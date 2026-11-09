"""Galerie de visages connus (YuNet + SFace) : un fichier image = un prénom (ex. Mathieu.jpg)."""

from __future__ import annotations

import logging
import unicodedata
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

from irobot.app.config.settings import RuntimeSettings

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png"})
_MAX_IMAGE_SIDE_PX = 1024


def normalize_name(name: str) -> str:
    """Clé de comparaison des prénoms : sans accents, sans casse, sans espaces superflus."""
    decomposed = unicodedata.normalize("NFD", name.strip().casefold())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


class FaceEmbedder:
    """Embedding SFace (128 valeurs) d'un visage déjà localisé par YuNet."""

    def __init__(self, settings: RuntimeSettings) -> None:
        model = Path(settings.camera_face_recognition_model_path)
        if not model.is_file():
            raise FileNotFoundError(f"Modèle SFace introuvable : {model}")
        self._recognizer = cv2.FaceRecognizerSF.create(str(model), "")
        self._threshold = settings.camera_face_match_threshold

    def embed(self, frame_bgr: NDArray[np.uint8], face: NDArray[np.float32]) -> NDArray[np.float32]:
        aligned = self._recognizer.alignCrop(frame_bgr, face)
        return np.array(self._recognizer.feature(aligned), dtype=np.float32, copy=True)

    def similarity(self, first: NDArray[np.float32], second: NDArray[np.float32]) -> float:
        return float(self._recognizer.match(first, second, cv2.FaceRecognizerSF_FR_COSINE))

    def is_match(self, score: float) -> bool:
        return score >= self._threshold


class FaceGallery:
    """Embeddings chargés une fois au démarrage depuis `camera_face_gallery_dir`."""

    def __init__(self, embeddings: dict[str, NDArray[np.float32]], embedder: FaceEmbedder | None = None) -> None:
        self._embeddings = dict(embeddings)
        self._by_key = {normalize_name(name): name for name in self._embeddings}
        self.embedder = embedder

    @classmethod
    def load(cls, settings: RuntimeSettings) -> FaceGallery:
        directory = Path(settings.camera_face_gallery_dir)
        if not directory.is_dir():
            logger.warning("Répertoire de galerie de visages introuvable : %s", directory)
            return cls({})
        embedder = FaceEmbedder(settings)
        model = Path(settings.camera_face_model_path)
        if not model.is_file():
            raise FileNotFoundError(f"Modèle YuNet introuvable : {model}")
        detector = cv2.FaceDetectorYN.create(
            str(model), "", (300, 300), score_threshold=settings.camera_face_score_threshold,
            nms_threshold=0.3, top_k=5000,
        )
        embeddings: dict[str, NDArray[np.float32]] = {}
        files = sorted(p for p in directory.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)
        for path in files:
            embedding = _embed_photo(path, detector, embedder)
            if embedding is None:
                continue
            if normalize_name(path.stem) in {normalize_name(name) for name in embeddings}:
                logger.warning("Photo %s ignorée : prénom déjà présent dans la galerie.", path.name)
                continue
            embeddings[path.stem] = embedding
        logger.info("Galerie de visages : %d personne(s) %s", len(embeddings), sorted(embeddings))
        return cls(embeddings, embedder)

    def names(self) -> list[str]:
        return sorted(self._embeddings)

    def resolve(self, name: str) -> str | None:
        """Prénom canonique (nom du fichier) ou None si la personne est inconnue."""
        return self._by_key.get(normalize_name(name))

    def get(self, name: str) -> NDArray[np.float32] | None:
        canonical = self.resolve(name)
        return None if canonical is None else self._embeddings[canonical]

    def identify(self, frame_bgr: NDArray[np.uint8], face: NDArray[np.float32]) -> str | None:
        """Identifie le visage parmi les photos chargées, avec le seuil SFace configuré."""
        if not self._embeddings:
            return None
        if self.embedder is None:
            raise RuntimeError("Galerie de visages sans modèle de reconnaissance.")
        embedding = self.embedder.embed(frame_bgr, face)
        name, score = max(
            ((name, self.embedder.similarity(reference, embedding))
             for name, reference in self._embeddings.items()),
            key=lambda item: item[1],
        )
        return name if self.embedder.is_match(score) else None


def _embed_photo(
    path: Path, detector: cv2.FaceDetectorYN, embedder: FaceEmbedder,
) -> NDArray[np.float32] | None:
    image = cv2.imread(str(path))
    if image is None:
        logger.warning("Photo %s ignorée : image illisible.", path.name)
        return None
    scale = _MAX_IMAGE_SIDE_PX / max(image.shape[:2])
    if scale < 1:
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    detector.setInputSize((image.shape[1], image.shape[0]))
    _, faces = detector.detect(image)
    count = 0 if faces is None else len(faces)
    if count != 1:
        logger.warning("Photo %s ignorée : %d visage(s) détecté(s), un seul attendu.", path.name, count)
        return None
    return embedder.embed(image, faces[0])
