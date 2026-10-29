"""Détection de balles ou objets rouge/jaune avec une caméra Raspberry Pi.

Ce module utilise Picamera2 + OpenCV pour détecter en temps réel les contours
rouges ou jaunes dans le flux vidéo. Il classe les candidats en :
- balle : forme suffisamment circulaire/compacte pour ressembler à une balle
- objet : couleur détectée mais forme trop irrégulière pour être une balle
- rien : aucune zone suffisamment compatible détectée

Modes disponibles :
- standard : messages lisibles pour un humain
- robotique : sorties compactes comme `BALL_RED_CENTER`, `OBJECT_YELLOW_LEFT`, `NONE`

Usage :
    uv run balle-rouge
    uv run balle-rouge --color red
    uv run balle-rouge --color yellow
    uv run balle-rouge --debug
    uv run balle-rouge --robotic

Le mode robotique est pensé pour un usage embarqué : il retourne un verdict en
une seule ligne sans logs de debug ni détails inutiles.
"""

import argparse
import os
import sys

if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
else:
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

import cv2
import numpy as np

try:
    from picamera2 import Picamera2
except ModuleNotFoundError:  # pragma: no cover - environnements hors Raspberry Pi
    Picamera2 = None

CAMERA_INDEX = 0

LABEL = "OBJET DETECTE"
BOX_COLOR = (0, 255, 0)
HAS_GUI = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

MIN_AREA = 300
MAX_AREA_RATIO = 0.25
BORDER_MARGIN = 10

COLOR_CONFIG = {
    "red": {
        "hsv_min": np.array((0, 150, 80)),
        "hsv_max": np.array((12, 255, 255)),
        "hsv_min_2": np.array((165, 150, 80)),
        "hsv_max_2": np.array((180, 255, 255)),
        "min_area": 800,
        "min_circularity": 0.35,
        "min_extent": 0.35,
        "min_solidity": 0.55,
        "aspect_min": 0.55,
        "aspect_max": 1.70,
    },
    "yellow": {
        "hsv_min": np.array((18, 100, 80)),
        "hsv_max": np.array((40, 255, 255)),
        "min_area": 700,
        "min_circularity": 0.30,
        "min_extent": 0.30,
        "min_solidity": 0.45,
        "aspect_min": 0.55,
        "aspect_max": 1.70,
    },
}


def safe_print(message):
    """Affiche un message en protégeant l'application contre une pipe fermée.

    Utilisé notamment avec `| head` lors de débogage en ligne de commande.
    """
    try:
        print(message)
    except BrokenPipeError:
        sys.exit(0)


def build_mask_for_color(hsv, color_name):
    """Construit un masque binaire pour une couleur donnée dans l'espace HSV.

    Le rouge est traité avec deux plages HSV (rouge autour de 0° et 180°),
    tandis que le jaune utilise une plage unique.
    """
    cfg = COLOR_CONFIG[color_name]

    if color_name == "red":
        mask1 = cv2.inRange(hsv, cfg["hsv_min"], cfg["hsv_max"])
        mask2 = cv2.inRange(hsv, cfg["hsv_min_2"], cfg["hsv_max_2"])
        return cv2.bitwise_or(mask1, mask2)

    if color_name == "yellow":
        return cv2.inRange(hsv, cfg["hsv_min"], cfg["hsv_max"])

    raise ValueError(f"Couleur non supportée : {color_name}")


def classify_colored_contour(contour, frame, color_name, debug=False):
    """Classe un contour détecté comme balle, objet ou rien.

    Les critères sont basés sur la zone, la circularité, l'aspect, l'extent et
    la solidité. Cela permet de distinguer une vraie balle sphérique d'un objet
    rouge/jaune irrégulier.
    """
    area = cv2.contourArea(contour)
    if area < MIN_AREA:
        return None

    x, y, w, h = cv2.boundingRect(contour)
    if x <= BORDER_MARGIN or y <= BORDER_MARGIN:
        return None
    if x + w >= frame.shape[1] - BORDER_MARGIN or y + h >= frame.shape[0] - BORDER_MARGIN:
        return None

    if area > frame.shape[0] * frame.shape[1] * MAX_AREA_RATIO:
        return None

    perimeter = cv2.arcLength(contour, True)
    if perimeter == 0:
        return None

    circularity = (4 * np.pi * area) / (perimeter * perimeter)
    aspect = w / h if h else 0.0
    extent = area / (w * h) if w * h else 0.0

    hull = cv2.convexHull(contour)
    hull_area = cv2.contourArea(hull)
    solidity = area / hull_area if hull_area > 0 else 0.0

    cfg = COLOR_CONFIG[color_name]
    if debug:
        safe_print(
            f"[DEBUG] {color_name.upper()} "
            f"area={area:.1f}, circularity={circularity:.3f}, "
            f"aspect={aspect:.2f}, extent={extent:.3f}, solidity={solidity:.3f}"
        )

    is_ball = (
        area >= cfg["min_area"]
        and circularity >= cfg["min_circularity"]
        and cfg["aspect_min"] <= aspect <= cfg["aspect_max"]
        and extent >= cfg["min_extent"]
        and solidity >= cfg["min_solidity"]
    )

    if is_ball:
        return "ball"

    if area >= MIN_AREA:
        return "object"

    return None


def detect_colored_objects(frame, color_name="red", debug=False, is_rgb=False):
    """Retourne les contours détectés pour une couleur donnée.

    Chaque candidat est classé avec `kind` = "ball", "object" ou ignoré, et
    expose `bbox`, `area` et `diameter_px` (diamètre du cercle de même aire,
    invariant à la rotation de l'image).
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV if is_rgb else cv2.COLOR_BGR2HSV)
    mask = build_mask_for_color(hsv, color_name)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))

    if debug:
        safe_print(f"[DEBUG] {color_name.upper()} pixels={int(mask.sum() // 255)}")

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for contour in contours:
        kind = classify_colored_contour(contour, frame, color_name, debug=debug)
        if kind is None:
            continue

        x, y, w, h = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        candidates.append({
            "kind": kind,
            "bbox": (x, y, w, h),
            "area": area,
            "diameter_px": float(np.sqrt(4.0 * area / np.pi)),
        })

    if debug:
        safe_print(f"[DEBUG] {color_name.upper()} candidats={len(candidates)}")
    return candidates


def annotate(frame, balls):
    if not balls:
        return frame

    x, y, w, h = max(balls, key=lambda b: b[2] * b[3])
    cv2.rectangle(frame, (x, y), (x + w, y + h), BOX_COLOR, 3)
    (tw, th), _ = cv2.getTextSize(LABEL, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)
    cv2.rectangle(frame, (x, y - th - 12), (x + tw + 12, y), BOX_COLOR, -1)
    cv2.putText(
        frame,
        LABEL,
        (x + 6, y - 6),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )
    return frame


def parse_args():
    parser = argparse.ArgumentParser(description="Détecte une balle ou un objet rouge/jaune et retourne le verdict.")
    parser.add_argument("--debug", action="store_true", help="affiche les détails de détection par frame")
    parser.add_argument(
        "--color",
        choices=["red", "yellow", "both"],
        default="both",
        help="couleur à détecter (par défaut: both)",
    )
    parser.add_argument(
        "--robotic",
        action="store_true",
        help="sortie compacte pour le robot: BALL_RED_CENTER / OBJECT_YELLOW_LEFT / NONE",
    )
    return parser.parse_args()


def choose_best_result(candidates, color_name, frame_shape, robotic=False):
    """Extrait le meilleur résultat parmi les candidats détectés.

    La logique privilégie en premier lieu les balles puis les objets.
    En mode robotique, la sortie est réduite à un verdict compact.
    """
    return choose_best_result_with_metrics(candidates, color_name, frame_shape, robotic=robotic)[0]


def choose_best_result_with_metrics(candidates, color_name, frame_shape, robotic=False):
    """Comme `choose_best_result`, mais retourne `(verdict, métriques)`.

    Les métriques (`kind`, `bbox`, `area`, `diameter_px`) sont celles du
    candidat retenu, ou None si rien n'a été détecté.
    """
    if not candidates:
        return None, None

    ball_candidates = [c for c in candidates if c["kind"] == "ball"]
    if ball_candidates:
        ball = max(ball_candidates, key=lambda c: c["area"])
        x, y, w, h = ball["bbox"]
        position = get_object_position(ball["bbox"], frame_shape)
        if robotic:
            return f"BALL_{color_name.upper()}_{position}", ball
        return f"RESULTAT: BALLE_{color_name.upper()} position={position} bbox=({x},{y},{w},{h}) area={ball['area']}", ball

    object_candidates = [c for c in candidates if c["kind"] == "object"]
    if object_candidates:
        obj = max(object_candidates, key=lambda c: c["area"])
        x, y, w, h = obj["bbox"]
        position = get_object_position(obj["bbox"], frame_shape)
        if robotic:
            return f"OBJECT_{color_name.upper()}_{position}", obj
        return (
            f"RESULTAT: OBJET_{color_name.upper()} position={position} bbox=({x},{y},{w},{h}) "
            f"area={obj['area']} -> pas une balle"
        ), obj

    return None, None


def get_object_position(bbox, frame_shape):
    """Retourne la zone approximative où se trouve l'objet dans l'image.

    Les positions supportées sont :
    - CENTRE
    - EN_HAUT
    - EN_BAS
    - A_GAUCHE
    - A_DROITE
    - EN_HAUT_A_GAUCHE
    - EN_HAUT_A_DROITE
    - EN_BAS_A_GAUCHE
    - EN_BAS_A_DROITE

    La logique est basée sur le centre du rectangle détecté. On découpe l'image
    en trois zones verticales et horizontales, puis on combine les deux axes.
    """
    x, y, w, h = bbox
    frame_h, frame_w = frame_shape[:2]

    cx = x + w / 2.0
    cy = y + h / 2.0

    vertical = "EN_HAUT" if cy < frame_h / 3.0 else "EN_BAS" if cy > (2.0 * frame_h) / 3.0 else "CENTRE"
    horizontal = "A_GAUCHE" if cx < frame_w / 3.0 else "A_DROITE" if cx > (2.0 * frame_w) / 3.0 else "CENTRE"

    if vertical == "CENTRE" and horizontal == "CENTRE":
        return "CENTRE"
    if vertical == "CENTRE":
        return horizontal
    if horizontal == "CENTRE":
        return vertical

    if vertical == "EN_HAUT" and horizontal == "A_GAUCHE":
        return "EN_HAUT_A_GAUCHE"
    if vertical == "EN_HAUT" and horizontal == "A_DROITE":
        return "EN_HAUT_A_DROITE"
    if vertical == "EN_BAS" and horizontal == "A_GAUCHE":
        return "EN_BAS_A_GAUCHE"
    if vertical == "EN_BAS" and horizontal == "A_DROITE":
        return "EN_BAS_A_DROITE"

    return "CENTRE"


def main():
    """Boucle principale de détection.

    En mode robotique, le script renvoie un verdict compact pour la logique du robot.
    """
    args = parse_args()
    debug = args.debug
    robotic = args.robotic
    requested_color = args.color
    colors_to_check = ["red", "yellow"] if requested_color == "both" else [requested_color]

    info = Picamera2.global_camera_info()
    if not robotic:
        safe_print(f"{len(info)} camera(s) détectée(s)")
    if not info:
        safe_print("Erreur: aucune caméra détectée. Vérifiez le câble CSI et l'alimentation.")
        return
    if CAMERA_INDEX >= len(info):
        safe_print(f"Erreur: index de caméra {CAMERA_INDEX} invalide (0 à {len(info)-1})")
        return

    if not robotic:
        safe_print(f"Utilisation de la caméra: {info[CAMERA_INDEX]['Model']}")
    picam2 = Picamera2(CAMERA_INDEX)
    config = picam2.create_preview_configuration()
    picam2.configure(config)
    picam2.start()

    if not HAS_GUI and not robotic:
        safe_print("Mode headless: détection uniquement via logs.")
    if debug and not robotic:
        safe_print(f"Mode DEBUG activé pour la couleur: {requested_color}")

    try:
        while True:
            frame = picam2.capture_array()
            rotated_frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            rotated_frame = cv2.cvtColor(rotated_frame, cv2.COLOR_RGB2BGR)

            best_result = None
            for color_name in colors_to_check:
                candidates = detect_colored_objects(rotated_frame, color_name=color_name, debug=debug)
                result = choose_best_result(candidates, color_name, rotated_frame.shape, robotic=robotic)
                if result is not None and best_result is None:
                    best_result = result

            if best_result is not None:
                safe_print(best_result)
                if HAS_GUI:
                    cv2.imshow("Camera 1 - Live", rotated_frame)
                    cv2.waitKey(250)
                break

            if debug and not robotic:
                safe_print(f"[DEBUG] RESULTAT: RIEN_DETECTE ({requested_color})")
            elif robotic:
                safe_print("NONE")

            if HAS_GUI:
                cv2.imshow("Camera 1 - Live", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
    finally:
        picam2.stop()
        if HAS_GUI:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()