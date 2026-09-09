from pdf_staffing import process_planning_pdf


@app.route("/analyze-planning-pdf", methods=["POST"])
def analyze_pdf_route():
    try:
        data = request.get_json()
        file_b64 = data.get("file_data")
        result = process_planning_pdf(file_b64)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
