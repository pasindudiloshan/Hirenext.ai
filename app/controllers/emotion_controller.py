# app/controllers/emotion_controller.py
import traceback
from flask import Blueprint, request, jsonify

from app.services.emotion_service import EmotionService


emotion_bp = Blueprint("emotion_bp", __name__, url_prefix="/emotion")


@emotion_bp.route("/health", methods=["GET"])
def health():
    """
    Simple health check for emotion service.
    """
    return jsonify({
        "ok": True,
        "service": "emotion"
    }), 200


@emotion_bp.route("/predict", methods=["POST"])
def predict():
    """
    Expects JSON:
    {
      "image": "data:image/jpeg;base64,...." OR "base64string...",
      "top_k": 3,
      "session_id": "abc123",   # optional
      "debug": false            # optional
    }

    Returns:
    {
      "ok": true,
      "session_id": "abc123",
      "label": "happy",
      "confidence": 0.82,
      "top": [
        {"label": "happy", "confidence": 0.82},
        {"label": "fear", "confidence": 0.10},
        {"label": "angry", "confidence": 0.05}
      ],
      "face_detected": true,
      "face_box": {
        "x": 12,
        "y": 20,
        "width": 90,
        "height": 90
      },
      "image_source": "face-crop"
    }
    """
    try:
        data = request.get_json(silent=True)

        if not data or not isinstance(data, dict):
            return jsonify({
                "ok": False,
                "error": "Request body must be valid JSON"
            }), 400

        img_b64 = data.get("image", "")
        top_k = data.get("top_k", 3)
        session_id = str(data.get("session_id", "") or "")
        debug = bool(data.get("debug", False))

        if not img_b64 or not str(img_b64).strip():
            return jsonify({
                "ok": False,
                "error": "Missing 'image' (base64) in request body"
            }), 400

        try:
            top_k = int(top_k)
        except (TypeError, ValueError):
            return jsonify({
                "ok": False,
                "error": "'top_k' must be an integer"
            }), 400

        top_k = max(1, min(top_k, 10))

        # Model was trained with 128x128 input
        svc = EmotionService.get_instance(input_size=(128, 128))
        result = svc.predict_from_base64(
            img_b64,
            top_k=top_k,
            debug=debug
        )

        response = {
            "ok": True,
            "session_id": session_id,
            **result
        }

        return jsonify(response), 200

    except ValueError as ve:
        print("\n[EmotionController] ValueError during prediction:")
        traceback.print_exc()
        return jsonify({
            "ok": False,
            "error": str(ve)
        }), 400

    except FileNotFoundError as fe:
        print("\n[EmotionController] FileNotFoundError during prediction:")
        traceback.print_exc()
        return jsonify({
            "ok": False,
            "error": str(fe)
        }), 500

    except Exception as e:
        print("\n[EmotionController] Unexpected error during prediction:")
        traceback.print_exc()
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500