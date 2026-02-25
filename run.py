from app import create_app, mongo
from flask import jsonify

app = create_app()

@app.route("/test-db")
def test_db():
    return jsonify({
        "mongo": "connected ✅",
        "db": mongo.db.name,
        "collections": mongo.db.list_collection_names()
    })

if __name__ == "__main__":
    app.run(debug=True)