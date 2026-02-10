from flask import Flask, request, jsonify
from flask_cors import CORS
import json

app = Flask(__name__)
CORS(app)  

@app.route("/points", methods=["POST"])
def receive_points():
    data = request.json

    print(data)

    with open("simulation_settings.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(port=5000)
