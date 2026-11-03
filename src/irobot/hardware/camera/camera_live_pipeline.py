from __future__ import annotations

import dataclasses
import logging
import threading

import cv2

try:
    from picamera2 import Picamera2
except ModuleNotFoundError:  # pragma: no cover - non-Raspberry environments
    Picamera2 = None

from irobot.config.settings import MarkerIdentity, load_runtime_settings
from irobot.hardware.camera.color_detector import (
    ColorCandidate,
    detect_colored_objects,
    select_best_candidate,
)
from irobot.hardware.camera.distance_estimator import (
    DistanceReader,
    ExponentialSmoother,
    estimate_distance_cm,
    estimate_marker_distance_cm,
    fuse_with_ultrasound,
)
from irobot.hardware.camera.frame_enhancer import FrameEnhancer, configure_exposure
from irobot.hardware.camera.face_detector import FaceDetector
from irobot.interfaces.aruco_marker_decoder import OpenCVArucoMarkerDecoder, ObservationDisposition
from irobot.interfaces.perception_pipeline import ObjectDetection, ObjectPerceptionPipeline

logger = logging.getLogger(__name__)


class CameraLivePerceptionPipeline(ObjectPerceptionPipeline):
    """Perception Picamera2 : balles, ArUco (marker/me) et YuNet (face/human).

    Sans filtre balle, ArUco est prioritaire. L'identité configurée est utilisée,
    sinon aruco/DICT_4X4_50/1 ; distance directe indicative estimée par pose
    pour un carré de 8 cm et une focale de 600 px, sans correction de distorsion.
    Les seuils horizontaux sont rapportés à une largeur de 480 px.
    """

    TARGET_FRAME_TIMEOUT_S = 1.0

    def __init__(
        self,
        *,
        camera_index: int = 0,
        default_target: str = "red",
        poll_interval_s: float = 0.05,
        ball_diameter_cm: float | None = None,
        focal_px: float | None = None,
        smoothing_alpha: float = 0.4,
        distance_reader: DistanceReader | None = None,
        fusion_enabled: bool | None = None,
        fusion_tolerance: float = 0.25,
        autostart: bool = True,
    ) -> None:
        self.camera_index = int(camera_index)
        self.default_target = (default_target or "").strip().lower()
        if self.default_target == "human":
            self.default_target = "face"
        self.poll_interval_s = max(0.0, float(poll_interval_s))

        settings = load_runtime_settings()
        self._settings = settings
        self._frame_enhancer = FrameEnhancer(settings)
        self._face_detector: FaceDetector | None = None
        self._marker_decoder = OpenCVArucoMarkerDecoder(
            settings.human_marker_identity or MarkerIdentity("aruco", "DICT_4X4_50", "1")
        )
        self.ball_diameter_cm = float(settings.camera_ball_diameter_cm if ball_diameter_cm is None else ball_diameter_cm)
        self.focal_px = float(settings.camera_focal_px if focal_px is None else focal_px)
        self.distance_reader = distance_reader
        self.fusion_enabled = bool(settings.camera_ultrasonic_fusion if fusion_enabled is None else fusion_enabled)
        self.fusion_tolerance = float(fusion_tolerance)
        self._smoother = ExponentialSmoother(smoothing_alpha)

        self._last_detection: ObjectDetection | None = None
        self._requested_target: str | None = None
        self._lock = threading.Lock()
        self._frame_condition = threading.Condition(self._lock)
        self._target_revision = 0
        self._frame_revision = -1
        self._capture_finished = False
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._capture_loop, name="camera-live-perception", daemon=False)
        if autostart:
            self._thread.start()

    def _compute_visual_distance_cm(self, detection: ObjectDetection) -> float | None:
        """Estimation visuelle lissée (thread caméra) ; aucune lecture capteur ici."""
        visual = None
        if detection.label.endswith("_ball"):
            visual = estimate_distance_cm(detection.diameter_px, self.ball_diameter_cm, self.focal_px)
        return self._smoother.update(visual)

    def _fuse_distance_cm(self, detection: ObjectDetection) -> float | None:
        """Fusion ultrason, appelée depuis le thread appelant de detect()."""
        if detection.label in {"marker_1", "face"}:
            return detection.distance_cm
        visual = detection.distance_visual_cm
        if visual is None or not self.fusion_enabled or self.distance_reader is None:
            return visual
        if detection.position != "center":
            return visual
        try:
            ultrasound = self.distance_reader()
        except Exception:
            return visual
        return fuse_with_ultrasound(visual, ultrasound, self.fusion_tolerance)

    def _detect_marker(self, frame_rgb) -> ObjectDetection | None:
        result = self._marker_decoder.detect(cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY))
        if result.disposition != ObservationDisposition.VALID:
            if result.disposition != ObservationDisposition.ABSENT:
                logger.warning("Détection ArUco non valide : %s", result.reason)
            return None
        corners = result.corners_px
        if corners is None or len(corners) != 4:
            logger.warning("Détection ArUco sans quatre coins valides.")
            return None
        distance = estimate_marker_distance_cm(
            corners, (frame_rgb.shape[1], frame_rgb.shape[0]),
        )
        if distance is None:
            logger.warning("Pose ArUco inexploitable ; distance indisponible.")
            return None
        center_x = sum(x for x, _ in corners) / 4 * 480 / frame_rgb.shape[1]
        position = "left" if center_x < 180 else "right" if center_x > 300 else "center"
        return ObjectDetection(
            label="marker_1", position=position, distance_cm=distance,
            distance_visual_cm=distance, confidence=1.0,
        )

    def _process_frame(self, frame_rgb, *, target: str | None = None) -> ObjectDetection | None:
        """Détecte la meilleure cible dans une frame déjà orientée (RGB) et renseigne la distance."""
        frame_rgb = self._frame_enhancer.apply(frame_rgb)
        if target is None:
            with self._lock:
                target = self._requested_target or self.default_target
        if target in {"face", "human"}:
            self._smoother.reset()
            if self._face_detector is None:
                self._face_detector = FaceDetector(self._settings, focal_px=self.focal_px)
            return self._face_detector.detect(frame_rgb)
        if self._face_detector is not None:
            self._face_detector.reset()
        marker_only = target in {"marker", "me"}
        ball_filter = target == "both" or any(value in target for value in ("red", "yellow", "ball"))
        if marker_only or not ball_filter:
            marker = self._detect_marker(frame_rgb)
            if marker is not None or marker_only:
                self._smoother.reset()
                return marker
        selected: tuple[str, ColorCandidate] | None = None
        for color in self._iter_colors_for_target(target, self.default_target):
            candidates = detect_colored_objects(frame_rgb, color_name=color, is_rgb=True)
            candidate = select_best_candidate(candidates)
            if candidate is None:
                continue
            if selected is None or candidate["kind"] == "ball":
                selected = (color, candidate)
            if candidate["kind"] == "ball":
                break

        if selected is None:
            self._smoother.reset()
            return None
        color, candidate = selected
        x, _, width, _ = candidate["bbox"]
        center_x = x + width / 2
        frame_width = frame_rgb.shape[1]
        position = (
            "left" if center_x < frame_width / 3
            else "right" if center_x > 2 * frame_width / 3
            else "center"
        )
        kind = candidate["kind"]
        detection = ObjectDetection(
            label=f"{color}_{kind}",
            position=position,
            distance_cm=None,
            confidence=0.95 if kind == "ball" else 0.75,
            diameter_px=candidate["diameter_px"],
        )
        detection.distance_visual_cm = self._compute_visual_distance_cm(detection)
        detection.distance_cm = detection.distance_visual_cm
        return detection

    @staticmethod
    def _iter_colors_for_target(target: str | None, default_target: str) -> list[str]:
        desired = (target or default_target or "both").strip().lower()
        if desired == "both":
            return ["red", "yellow"]
        if "yellow" in desired:
            return ["yellow", "red"]
        return ["red", "yellow"]

    def _capture_loop(self) -> None:
        if Picamera2 is None:
            logger.error("Perception caméra indisponible : Picamera2 absent.")
            with self._frame_condition:
                self._capture_finished = True
                self._frame_condition.notify_all()
            return

        camera = None
        try:
            camera = Picamera2(self.camera_index)
            # Picamera2 BGR888 fournit des octets R, G, B à _process_frame.
            config = camera.create_preview_configuration(
                main={"size": (640, 480), "format": "BGR888"}
            )
            camera.configure(config)
            configure_exposure(camera, self._settings)
            camera.start()
            processed_revision = -1

            while not self._stop_event.is_set():
                with self._lock:
                    target = self._requested_target or self.default_target
                    revision = self._target_revision
                frame_rgb = camera.capture_array()
                if revision != processed_revision:
                    if self._face_detector is not None:
                        self._face_detector.reset()
                    self._smoother.reset()
                    processed_revision = revision
                rotated_frame_rgb = cv2.rotate(frame_rgb, cv2.ROTATE_90_CLOCKWISE)
                detection = self._process_frame(rotated_frame_rgb, target=target)
                with self._frame_condition:
                    # Une image en vol ne doit pas satisfaire une nouvelle demande de cible.
                    if revision == self._target_revision:
                        self._last_detection = detection
                        self._frame_revision = revision
                    self._frame_condition.notify_all()

                if self.poll_interval_s > 0.0:
                    self._stop_event.wait(self.poll_interval_s)
        except Exception:
            logger.exception("Échec de la capture caméra.")
            with self._frame_condition:
                self._last_detection = None
                self._frame_revision = -1
        finally:
            with self._frame_condition:
                self._capture_finished = True
                self._frame_condition.notify_all()
            if camera is not None:
                try:
                    camera.stop()
                except Exception:
                    logger.exception("Échec de l'arrêt de la caméra.")
                try:
                    camera.close()
                except Exception:
                    logger.exception("Échec de la fermeture de la caméra.")

    def detect(self, *, target: str | None = None) -> ObjectDetection | None:
        expected = (target or "").strip().lower()
        if expected == "human":
            expected = "face"
        requested = "marker" if expected == "me" else expected
        with self._frame_condition:
            previous = self._requested_target or self.default_target
            previous = "marker" if previous == "me" else previous
            desired = requested or self.default_target
            desired = "marker" if desired == "me" else desired
            if desired != previous:
                self._target_revision += 1
                self._last_detection = None
            self._requested_target = requested or None
            revision = self._target_revision
            if self._thread.is_alive():
                ready = self._frame_condition.wait_for(
                    lambda: self._frame_revision == revision
                    or self._stop_event.is_set()
                    or self._capture_finished,
                    timeout=self.TARGET_FRAME_TIMEOUT_S,
                )
                if not ready:
                    logger.error("Délai dépassé en attendant une image caméra pour la cible %r.", target)
                    return None
                if self._frame_revision != revision:
                    return None
            detection = self._last_detection

        if detection is None:
            return None
        if expected:
            label = detection.label.lower()
            if expected in {"marker", "me"}:
                if label != "marker_1":
                    return None
            elif expected not in label and label not in expected:
                return None
        return dataclasses.replace(detection, distance_cm=self._fuse_distance_cm(detection))

    def close(self, timeout_s: float | None = None) -> None:
        with self._frame_condition:
            self._stop_event.set()
            self._frame_condition.notify_all()
        if self._thread.is_alive():
            self._thread.join(timeout=None if timeout_s is None else max(0.0, float(timeout_s)))
            if self._thread.is_alive():
                raise TimeoutError("Le thread caméra n'est pas arrêté.")
