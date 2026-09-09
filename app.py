import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from pdf_staffing import process_planning_pdf

# 1. INSTANCIATION OBLIGATOIRE DE FLASK
app = Flask(__name__)
CORS(app)


# 2. ROUTE DE TEST / HEALTH CHECK
@app.route("/", methods=["GET"])
def health_check():
    return jsonify(
        {"status": "online", "service": "IdentiFid Smart Staffing Parser API"}
    )


# 3. ROUTE D'ANALYSE DU PDF
@app.route("/analyze-planning-pdf", methods=["POST"])
def analyze_pdf():
    try:
        data = request.get_json()
        if not data or "file_data" not in data:
            return jsonify(
                {"success": False, "message": "Aucun fichier transmis."}
            ), 400

        file_b64 = data.get("file_data")
        result = process_planning_pdf(file_b64)

        return jsonify({"success": True, "data": result}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
