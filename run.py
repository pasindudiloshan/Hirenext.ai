# run.py

from app import create_app, mongo
from flask import jsonify

app = create_app()


# ==========================================
# Test MongoDB Connection
# ==========================================
@app.route("/test-db")
def test_db():
    try:
        collections = mongo.db.list_collection_names()
        return jsonify({
            "mongo": "connected ✅",
            "db": mongo.db.name,
            "collections": collections
        })
    except Exception as e:
        return jsonify({
            "mongo": "connection failed ❌",
            "error": str(e)
        }), 500


# ==========================================
# Test SMTP Configuration
# ==========================================
@app.route("/test-smtp")
def test_smtp():
    smtp_user = app.config.get("SMTP_USER")
    smtp_pass = app.config.get("SMTP_PASS")

    return jsonify({
        "smtp_user_set": bool(smtp_user),
        "smtp_pass_set": bool(smtp_pass),
        "smtp_host": app.config.get("SMTP_HOST"),
        "smtp_port": app.config.get("SMTP_PORT"),
        "email_enabled": app.config.get("EMAIL_ENABLED", False)
    })


# ==========================================
# Main Runner
# ==========================================
if __name__ == "__main__":
    print("🚀 HireNext.ai Server Starting...")
    print(f"📂 Database: {mongo.db.name}")
    print(f"📧 SMTP Enabled: {app.config.get('EMAIL_ENABLED', False)}")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True, use_reloader=False)