from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)  

OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "/output/simulation_settings.json")

@app.route("/points", methods=["POST"])
def receive_points():
    data = request.json

    print(data)
    
    current_datetime = datetime.now()
    openString = "./output/simulation_settings_" + current_datetime.strftime("%Y-%m-%d_%H:%M:%S") + ".json"

    
    
    current_datetime = datetime.now()
    openString = "output/simulation_settings_" + current_datetime.strftime("%Y-%m-%d_%H:%M:%S") + ".json"

    with open(openString, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return jsonify({"status": "ok"})

if __name__ == "__main__":
    try:
        
        app.run(port=5000, debug=False)
    except KeyboardInterrupt:
        print("\nStopping Flask server...")
