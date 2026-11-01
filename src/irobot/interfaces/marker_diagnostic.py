"""Live, non-recording diagnostic for the selected static ArUco test marker."""

from __future__ import annotations

from irobot.config.settings import MarkerIdentity
from irobot.hardware.camera.distance_estimator import (
    MARKER_FOCAL_PX,
    MARKER_ORIENTED_SIZE_PX,
    MARKER_SIDE_CM,
    estimate_marker_distance_cm,
)
from irobot.interfaces.aruco_marker_decoder import (
    ArucoFrameDetection,
    ObservationDisposition,
    OpenCVArucoMarkerDecoder,
)


TEST_MARKER_IDENTITY = MarkerIdentity("aruco", "DICT_4X4_50", "1")
EXPECTED_CAMERA_MODEL = "ov5647"
PREVIEW_SIZE_PX = (640, 480)
ORIENTED_SIZE_PX = MARKER_ORIENTED_SIZE_PX


def compute_marker_distance_cm(
    detection: ArucoFrameDetection,
    frame_size_px: tuple[int, int] = ORIENTED_SIZE_PX,
) -> float | None:
    """Estimate direct range from pose, assuming centred optics without distortion."""
    corners = detection.corners_px
    if not _is_selected_detection(detection) or corners is None:
        return None
    return estimate_marker_distance_cm(corners, frame_size_px)


def format_detection_status(
    detection: ArucoFrameDetection,
    frame_size_px: tuple[int, int] = ORIENTED_SIZE_PX,
) -> str:
    if _is_selected_detection(detection):
        corners = detection.corners_px
        distance_cm = compute_marker_distance_cm(detection, frame_size_px)
        distance_text = (
            f"{distance_cm:.1f} cm" if distance_cm is not None else "indisponible"
        )
        return f"ID 1: detected; distance={distance_text}; corners_px={corners}"
    if detection.disposition is ObservationDisposition.VALID:
        return "ID 1: invalid detector result (identity or corners unavailable)"
    if detection.disposition is ObservationDisposition.ABSENT:
        return "ID 1: absent"
    if detection.disposition is ObservationDisposition.AMBIGUOUS:
        return f"ID 1: ambiguous; reason={detection.reason or 'unspecified'}"
    return (
        f"ID 1: {detection.disposition.value}; "
        f"reason={detection.reason or 'unspecified'}"
    )


def _is_selected_detection(detection: ArucoFrameDetection) -> bool:
    return (
        detection.disposition is ObservationDisposition.VALID
        and detection.identity == TEST_MARKER_IDENTITY
        and detection.corners_px is not None
    )


def _draw_detection(
    frame: object,
    detection: ArucoFrameDetection,
    cv2_api: object,
    frame_size_px: tuple[int, int] = ORIENTED_SIZE_PX,
) -> None:
    corners = detection.corners_px
    selected = _is_selected_detection(detection)
    if selected:
        points = tuple((round(x), round(y)) for x, y in corners)
        for start, end in zip(points, (*points[1:], points[0])):
            cv2_api.line(frame, start, end, (0, 255, 0), 2)
        for point in points:
            cv2_api.circle(frame, point, 4, (0, 0, 255), -1)

    if selected:
        distance_cm = compute_marker_distance_cm(detection, frame_size_px)
        text = (
            f"ID 1 DETECTED ~{distance_cm:.1f} cm"
            if distance_cm is not None
            else "ID 1 DETECTED - DISTANCE UNAVAILABLE"
        )
    elif detection.disposition is ObservationDisposition.VALID:
        text = "ID 1 INVALID RESULT"
    else:
        text = f"ID 1 {detection.disposition.value.upper()}"
    cv2_api.putText(
        frame,
        text,
        (12, 30),
        cv2_api.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0) if selected else (0, 165, 255),
        2,
    )


def main() -> int:
    import os
    import sys

    if not os.environ.get("DISPLAY"):
        print("Erreur : aucun affichage X11 détecté (variable DISPLAY absente).", file=sys.stderr)
        return 2

    import cv2
    from picamera2 import Picamera2

    camera_info = Picamera2.global_camera_info()
    if not camera_info:
        print("Erreur : aucune caméra détectée.", file=sys.stderr)
        return 2
    model = str(camera_info[0].get("Model", "")).lower()
    if model != EXPECTED_CAMERA_MODEL:
        print(
            f"Erreur : caméra 0 = {model or 'modèle inconnu'}, "
            f"OV5647 attendu ; aucune caméra ouverte.",
            file=sys.stderr,
        )
        return 2

    decoder = OpenCVArucoMarkerDecoder(TEST_MARKER_IDENTITY)
    camera = Picamera2(0)
    started = False
    last_status: tuple[ObservationDisposition, str | None] | None = None
    print(
        "Diagnostic ArUco statique : DICT_4X4_50 / ID 1. "
        f"Distance directe estimée par pose (côté {MARKER_SIDE_CM:g} cm, "
        f"focale {MARKER_FOCAL_PX:g} px) ; "
        "objectif non calibré, distorsion non corrigée. "
        "Aucune image n'est enregistrée. Appuyez sur q pour quitter.",
        flush=True,
    )
    try:
        camera.configure(camera.create_preview_configuration(main={"size": PREVIEW_SIZE_PX}))
        camera.start()
        started = True
        while True:
            frame_rgb = camera.capture_array()
            rotated_rgb = cv2.rotate(frame_rgb, cv2.ROTATE_90_CLOCKWISE)
            grayscale = cv2.cvtColor(rotated_rgb, cv2.COLOR_RGB2GRAY)
            detection = decoder.detect(grayscale)
            display_frame = cv2.cvtColor(rotated_rgb, cv2.COLOR_RGB2BGR)
            frame_size_px = (rotated_rgb.shape[1], rotated_rgb.shape[0])
            _draw_detection(display_frame, detection, cv2, frame_size_px)
            cv2.imshow("ArUco DICT_4X4_50 - ID 1", display_frame)

            status_key = (detection.disposition, detection.reason)
            if status_key != last_status:
                print(format_detection_status(detection, frame_size_px), flush=True)
                last_status = status_key

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    except KeyboardInterrupt:
        print("\nDiagnostic interrompu par l'utilisateur.", flush=True)
        return 130
    finally:
        try:
            if started:
                camera.stop()
        finally:
            cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
