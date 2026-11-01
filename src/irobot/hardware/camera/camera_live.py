import os
import sys

if not os.environ.get("DISPLAY"):
    sys.exit("Erreur : Aucun serveur d'affichage X11 détecté (variable DISPLAY absente).")

os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

import cv2
from picamera2 import Picamera2

from irobot.config.settings import load_runtime_settings
from irobot.hardware.camera.frame_enhancer import FrameEnhancer, configure_exposure

CAMERA_INDEX = 0

def main():
    info = Picamera2.global_camera_info()
    print(f"{len(info)} camera(s) détectée(s)")
    if not info:
        print("Erreur: aucune caméra détectée. Vérifiez le câble CSI et l'alimentation.")
        return
    if CAMERA_INDEX >= len(info):
        print(f"Erreur: index de caméra {CAMERA_INDEX} invalide (0 à {len(info)-1})")
        return

    print(f"Utilisation de la caméra: {info[CAMERA_INDEX]['Model']}")
    settings = load_runtime_settings()
    enhancer = FrameEnhancer(settings)
    picam2 = Picamera2(CAMERA_INDEX)
    started = False

    print("Appuyez sur 'q' pour quitter")

    try:
        config = picam2.create_preview_configuration(main={"format": "BGR888"})
        picam2.configure(config)
        configure_exposure(picam2, settings)
        picam2.start()
        started = True
        while True:
            frame = picam2.capture_array()
            rotated_frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            rotated_frame = enhancer.apply(rotated_frame)
            rotated_frame = cv2.cvtColor(rotated_frame, cv2.COLOR_RGB2BGR)
            cv2.imshow("Camera 1 - Live", rotated_frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    except KeyboardInterrupt:
        print("\nDiagnostic interrompu par l'utilisateur.", flush=True)
        return 130
    finally:
        try:
            if started:
                picam2.stop()
        finally:
            picam2.close()
            cv2.destroyAllWindows()

if __name__ == "__main__":
    main()