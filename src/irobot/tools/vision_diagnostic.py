"""Runnable live diagnostic for ArUco, faces and red/yellow balls."""

from __future__ import annotations

from irobot.common.config.settings import (
    MarkerIdentity,
    RuntimeSettings,
    load_runtime_settings,
)
from irobot.common.hardware.camera.detector import (
    MARKER_SIDE_CM,
    ArucoFrameDetection,
    ColorDetector,
    FaceDetector,
    FaceGallery,
    ObservationDisposition,
    OpenCVMarkerDetector,
)
from irobot.common.hardware.camera.frame_enhancer import (
    FrameEnhancer,
    configure_exposure,
)
from irobot.common.interfaces.perception_contracts import ObjectDetection

TEST_MARKER_IDENTITY = MarkerIdentity("aruco", "DICT_4X4_50", "1")
EXPECTED_CAMERA_MODEL = "ov5647"


def detect_balls(
    frame_rgb, settings: RuntimeSettings,
) -> dict[str, tuple[ObjectDetection, tuple[int, int, int, int]] | None]:
    results: dict[str, tuple[ObjectDetection, tuple[int, int, int, int]] | None] = {}
    for color in ("red", "yellow"):
        detector = ColorDetector(color, settings.camera_ball_diameter_cm, settings.camera_focal_px)
        detection = detector.detect(frame_rgb)
        if detection is None or not detection.label.endswith("_ball"):
            results[color] = None
            continue
        if detection.bbox_px is None:
            raise RuntimeError(f"{color} ball detection is missing its bounding box")
        results[color] = (detection, detection.bbox_px)
    return results


def format_object_status(name: str, detection: ObjectDetection | None, *, cached: bool = False) -> str:
    if detection is None:
        return f"{name}: absent"
    distance = f"{detection.distance_cm:.1f} cm" if detection.distance_cm is not None else "indisponible"
    state = "memorized" if cached else "detected"
    return f"{name}: {state}; {detection.position}; distance={distance}; confidence={detection.confidence:.2f}"


def format_face_identity(detection: ObjectDetection | None, *, available: bool) -> str:
    if not available:
        return "IDENTITY: unavailable"
    if detection is None:
        return "IDENTITY: no face"
    return f"IDENTITY: {detection.identity or 'unknown'}"


def _draw_face_identity(frame, text: str, cv2_api) -> None:
    import unicodedata

    text = "".join(
        char for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    ).encode("ascii", "replace").decode("ascii")
    while text and cv2_api.getTextSize(text, cv2_api.FONT_HERSHEY_SIMPLEX, 0.55, 2)[0][0] > frame.shape[1] - 12:
        text = text[:-1]
    cv2_api.putText(frame, text, (12, 150), cv2_api.FONT_HERSHEY_SIMPLEX, 0.55, (255, 200, 0), 2)


def _draw_object_status(
    frame, name: str, detection: ObjectDetection | None, row: int, color, cv2_api, *, cached: bool = False,
) -> None:
    text = f"{name} ABSENT"
    if detection is not None:
        distance = f"~{detection.distance_cm:.1f}cm" if detection.distance_cm is not None else "DIST N/A"
        state = " MEM" if cached else ""
        text = f"{name}{state} {detection.position} {distance} ({detection.confidence:.2f})"
    cv2_api.putText(frame, text, (12, 30 + row * 30), cv2_api.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)


def format_detection_status(
    detection: ArucoFrameDetection,
) -> str:
    if _is_selected_detection(detection):
        corners = detection.corners_px
        distance_cm = detection.distance_cm
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
        distance_cm = detection.distance_cm
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


def main(argv: list[str] | None = None) -> int:
    import argparse
    import os
    import sys

    parser = argparse.ArgumentParser(description="Diagnostic vision en direct.")
    parser.add_argument(
        "--preview-only",
        action="store_true",
        help="affiche le flux caméra sans exécuter les détecteurs ni ajouter d'annotations",
    )
    args = parser.parse_args(argv)

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

    settings = load_runtime_settings()
    enhancer = FrameEnhancer(settings)
    if not args.preview_only:
        try:
            gallery = FaceGallery.load(settings)
        except (FileNotFoundError, cv2.error) as exc:
            print(
                f"Reconnaissance des visages indisponible : {exc}. Détection générique maintenue.",
                file=sys.stderr, flush=True,
            )
            gallery = None
        gallery_names = gallery.names() if gallery is not None else []
        if gallery_names:
            print(f"Galerie de visages chargée : {', '.join(gallery_names)}", flush=True)
        elif gallery is not None:
            print(
                f"Reconnaissance des visages indisponible : galerie vide ou inaccessible "
                f"({settings.camera_face_gallery_dir}). Détection générique maintenue.",
                file=sys.stderr, flush=True,
            )
        marker_detector = OpenCVMarkerDetector(
            TEST_MARKER_IDENTITY,
            focal_px=settings.camera_focal_px,
            oriented_frame_size_px=settings.camera_oriented_frame_size_px,
        )
        faces = FaceDetector(settings, gallery=gallery if gallery_names else None)
    camera = Picamera2(0)
    started = False
    last_status: tuple | None = None
    if args.preview_only:
        print("Aperçu caméra uniquement. Aucune détection ni annotation. Appuyez sur q pour quitter.", flush=True)
    else:
        print(
            "Diagnostic vision : ArUco DICT_4X4_50 / ID 1, visages, balles rouge/jaune. "
            f"Distance directe estimée par pose (côté {MARKER_SIDE_CM:g} cm, "
            f"focale configurée {settings.camera_focal_px:g} px) ; "
            "objectif non calibré, distorsion non corrigée. "
            "Distances visage/balle indicatives. Visage mémorisé signalé pendant la grâce. "
            "Aucune image n'est enregistrée. Appuyez sur q pour quitter.",
            flush=True,
        )
    try:
        camera.configure(camera.create_preview_configuration(
            main={"size": settings.camera_capture_size_px, "format": "BGR888"},
        ))
        configure_exposure(camera, settings)
        camera.start()
        started = True
        while True:
            frame_rgb = camera.capture_array()
            rotated_rgb = cv2.rotate(frame_rgb, cv2.ROTATE_90_CLOCKWISE)
            rotated_rgb = enhancer.apply(rotated_rgb)
            display_frame = cv2.cvtColor(rotated_rgb, cv2.COLOR_RGB2BGR)
            if args.preview_only:
                cv2.imshow("Vision - Preview", display_frame)
            else:
                detection = marker_detector.detect(rotated_rgb)
                face = faces.detect(rotated_rgb)
                balls = detect_balls(rotated_rgb, settings)
                _draw_detection(display_frame, detection, cv2)
                statuses = [format_object_status("FACE", face, cached=faces.is_cached)]
                identity_status = format_face_identity(face, available=bool(gallery_names))
                statuses.append(identity_status)
                _draw_object_status(
                    display_frame, "FACE", face, 1, (255, 200, 0), cv2, cached=faces.is_cached,
                )
                if faces.bounding_box is not None:
                    x, y, width, height = map(round, faces.bounding_box)
                    cv2.rectangle(display_frame, (x, y), (x + width, y + height), (255, 200, 0), 2)
                for row, (color, result) in enumerate(balls.items(), start=2):
                    ball = result[0] if result else None
                    text = format_object_status(f"BALL {color.upper()}", ball)
                    statuses.append(text)
                    box_color = (0, 0, 255) if color == "red" else (0, 255, 255)
                    _draw_object_status(display_frame, f"BALL {color.upper()}", ball, row, box_color, cv2)
                    if result:
                        x, y, width, height = result[1]
                        cv2.rectangle(display_frame, (x, y), (x + width, y + height), box_color, 2)
                _draw_face_identity(display_frame, identity_status, cv2)
                cv2.imshow("Vision - ArUco / Face / Red / Yellow", display_frame)

                status_key = (detection.disposition, detection.reason, *statuses)
                if status_key != last_status:
                    print(format_detection_status(detection), flush=True)
                    print(" | ".join(statuses), flush=True)
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
            camera.close()
            cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
