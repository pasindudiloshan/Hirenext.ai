# app/services/emotion_service.py
import os
import json
import base64
from io import BytesIO
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
from PIL import Image
import tensorflow as tf

try:
    import cv2  # type: ignore
except Exception:
    cv2 = None


class EmotionService:
    _instance = None

    def __init__(
        self,
        model_path: str,
        labels_path: str,
        input_size: Tuple[int, int] = (128, 128),
    ):
        self.model_path = model_path
        self.labels_path = labels_path
        self.input_size = input_size

        self.model = self._load_model(self.model_path)
        self.labels = self._load_labels(self.labels_path)

        # Optional backend face detector
        self.face_cascade = self._load_face_cascade()

    @classmethod
    def get_instance(
        cls,
        model_path: Optional[str] = None,
        labels_path: Optional[str] = None,
        input_size: Optional[Tuple[int, int]] = None,
    ) -> "EmotionService":
        if cls._instance is not None:
            return cls._instance

        base_dir = os.path.dirname(os.path.dirname(__file__))
        default_model = os.path.join(base_dir, "ml_models", "emotion_model.keras")
        default_labels = os.path.join(base_dir, "ml_models", "emotion_labels.json")

        model_path = model_path or os.environ.get("EMOTION_MODEL_PATH") or default_model
        labels_path = labels_path or os.environ.get("EMOTION_LABELS_PATH") or default_labels

        if input_size is None:
            input_size = cls._parse_input_size(
                os.environ.get("EMOTION_INPUT_SIZE", "128,128")
            )

        cls._instance = cls(
            model_path=model_path,
            labels_path=labels_path,
            input_size=input_size,
        )
        return cls._instance

    @staticmethod
    def _parse_input_size(value: str) -> Tuple[int, int]:
        try:
            parts = [int(x.strip()) for x in str(value).split(",")]
            if len(parts) != 2:
                raise ValueError
            h, w = parts
            if h <= 0 or w <= 0:
                raise ValueError
            return (h, w)
        except Exception:
            return (128, 128)

    def _load_model(self, path: str) -> tf.keras.Model:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Emotion model not found at: {path}")

        model = tf.keras.models.load_model(path, compile=False)

        dummy = np.zeros(
            (1, self.input_size[0], self.input_size[1], 3),
            dtype=np.float32
        )
        _ = model.predict(dummy, verbose=0)

        return model

    def _load_labels(self, path: str) -> List[str]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Emotion labels not found at: {path}")

        with open(path, "r", encoding="utf-8") as f:
            labels = json.load(f)

        if not isinstance(labels, list) or not all(isinstance(x, str) for x in labels):
            raise ValueError("emotion_labels.json must be a JSON list of strings (class names).")

        if len(labels) == 0:
            raise ValueError("emotion_labels.json cannot be empty.")

        return labels

    def _load_face_cascade(self):
        if cv2 is None:
            return None

        try:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            if not os.path.exists(cascade_path):
                return None

            cascade = cv2.CascadeClassifier(cascade_path)
            if cascade.empty():
                return None

            return cascade
        except Exception:
            return None

    def predict_from_base64(
        self,
        image_base64: str,
        top_k: int = 3,
        debug: bool = False
    ) -> Dict[str, Any]:
        img = self._decode_base64_to_pil(image_base64)
        return self.predict_from_pil(img, top_k=top_k, debug=debug)

    def predict_from_pil(
        self,
        img: Image.Image,
        top_k: int = 3,
        debug: bool = False
    ) -> Dict[str, Any]:
        working_img = img.convert("RGB")

        crop_info = self._detect_and_crop_face(working_img, debug=debug)
        model_img = crop_info["image"]

        x = self._preprocess_pil(model_img)
        probs = self._predict_probs(x)

        result = self._format_output(probs, top_k=top_k)
        result.update({
            "face_detected": bool(crop_info["face_detected"]),
            "face_box": crop_info["face_box"],
            "image_source": crop_info["image_source"],
        })

        if debug:
            result["debug"] = {
                "opencv_available": cv2 is not None,
                "cascade_loaded": self.face_cascade is not None,
                "input_size": list(self.input_size),
                "original_size": list(working_img.size),
                "model_input_source": crop_info["image_source"],
            }

        return result

    def _decode_base64_to_pil(self, s: str) -> Image.Image:
        if not s or not str(s).strip():
            raise ValueError("Empty image string")

        s = str(s).strip()

        if s.startswith("data:") and "," in s:
            s = s.split(",", 1)[1]

        try:
            raw = base64.b64decode(s)
        except Exception as e:
            raise ValueError(f"Invalid base64 image data: {e}")

        try:
            img = Image.open(BytesIO(raw)).convert("RGB")
        except Exception as e:
            raise ValueError(f"Could not decode image: {e}")

        return img

    def _detect_and_crop_face(
        self,
        img: Image.Image,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Detect the largest face and crop it with some padding.
        Falls back to the full image if no face detector is available or no face is found.
        """
        if self.face_cascade is None or cv2 is None:
            if debug:
                print("[EmotionService] Face cascade unavailable. Using full-frame.")
            return {
                "image": img,
                "face_detected": False,
                "face_box": None,
                "image_source": "full-frame",
            }

        try:
            rgb = np.array(img, dtype=np.uint8)
            if rgb.ndim != 3 or rgb.shape[2] != 3:
                return {
                    "image": img,
                    "face_detected": False,
                    "face_box": None,
                    "image_source": "full-frame",
                }

            gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(40, 40),
                flags=cv2.CASCADE_SCALE_IMAGE,
            )

            if faces is None or len(faces) == 0:
                if debug:
                    print("[EmotionService] No face detected. Using full-frame.")
                return {
                    "image": img,
                    "face_detected": False,
                    "face_box": None,
                    "image_source": "full-frame",
                }

            # Choose the largest face
            x, y, w, h = max(faces, key=lambda box: int(box[2]) * int(box[3]))

            # Add padding
            pad_x = int(w * 0.18)
            pad_y = int(h * 0.18)

            img_w, img_h = img.size
            x1 = max(0, int(x) - pad_x)
            y1 = max(0, int(y) - pad_y)
            x2 = min(img_w, int(x) + int(w) + pad_x)
            y2 = min(img_h, int(y) + int(h) + pad_y)

            if x2 <= x1 or y2 <= y1:
                if debug:
                    print("[EmotionService] Invalid face crop. Using full-frame.")
                return {
                    "image": img,
                    "face_detected": False,
                    "face_box": None,
                    "image_source": "full-frame",
                }

            cropped = img.crop((x1, y1, x2, y2))

            face_box = {
                "x": int(x1),
                "y": int(y1),
                "width": int(x2 - x1),
                "height": int(y2 - y1),
            }

            if debug:
                print(f"[EmotionService] Face detected. Crop box: {face_box}")

            return {
                "image": cropped,
                "face_detected": True,
                "face_box": face_box,
                "image_source": "face-crop",
            }

        except Exception as e:
            if debug:
                print(f"[EmotionService] Face detection error: {e}. Using full-frame.")
            return {
                "image": img,
                "face_detected": False,
                "face_box": None,
                "image_source": "full-frame",
            }

    def _preprocess_pil(self, img: Image.Image) -> np.ndarray:
        img = img.resize(
            (self.input_size[1], self.input_size[0]),
            Image.BILINEAR
        )

        arr = np.array(img, dtype=np.float32)

        if arr.ndim != 3 or arr.shape[2] != 3:
            raise ValueError(f"Unexpected image shape after preprocessing: {arr.shape}")

        if arr.mean() < 3:
            raise ValueError("Image appears too dark or empty for emotion prediction.")

        arr = np.expand_dims(arr, axis=0)
        return arr

    def _predict_probs(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=np.float32)

        output = self.model.predict(x, verbose=0)
        probs = np.array(output, dtype=np.float32)
        probs = np.squeeze(probs)

        if probs.ndim != 1:
            raise ValueError(f"Unexpected model output shape: {probs.shape}")

        if probs.min() < 0.0 or probs.max() > 1.0:
            probs = tf.nn.softmax(probs).numpy()

        return probs

    def _format_output(self, probs: np.ndarray, top_k: int = 3) -> Dict[str, Any]:
        probs = np.squeeze(probs)

        if probs.ndim != 1:
            raise ValueError(f"Unexpected model output shape: {probs.shape}")

        num_classes = len(self.labels)
        if probs.shape[0] != num_classes:
            raise ValueError(
                f"Model output classes ({probs.shape[0]}) != labels ({num_classes}). "
                "Check emotion_labels.json order matches training."
            )

        idx = int(np.argmax(probs))
        label = self.labels[idx]
        conf = float(probs[idx])

        top_k = max(1, min(int(top_k), num_classes))
        top_idx = np.argsort(probs)[::-1][:top_k].tolist()

        top = [
            {
                "label": self.labels[i],
                "confidence": float(probs[i]),
            }
            for i in top_idx
        ]

        return {
            "label": label,
            "confidence": conf,
            "top": top,
        }