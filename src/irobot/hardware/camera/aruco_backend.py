"""Lazy loading of the concrete OpenCV ArUco API."""


def load_aruco_api() -> object | None:
    import cv2

    return getattr(cv2, "aruco", None)
