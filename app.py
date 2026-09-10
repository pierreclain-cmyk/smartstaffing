import os
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from pdf_staffing import process_planning_pdf
from ai_agent import StaffingAutonomousAgent

app = Flask(__name__)
CORS(app)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://eilyxfhxmscuwbavkpzz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_eE-LmmezezF4l6L3O7hGBQ_hMOZL9i7")

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "online", "service": "IdentiFid Omni-Staffing API"}), 200

@app.route("/analyze-planning-pdf", methods=["POST"])
def analyze_pdf():
    try:
        data = request.get_json()
        result = process_planning_pdf(data.get("file_data"), filename=data.get("filename", "planning.pdf"))
        return jsonify({"success": True, "data": result}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/dernier-planning", methods=["GET"])
def get_dernier_planning():
    endpoint = f"{SUPABASE_URL}/rest/v1/historique_plannings_pdf?select=planning_json,equipiers_count,couverture_rush,sous_effectifs_count,gain_id_estime,semaine_iso&order=created_at.desc&limit=1"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    try:
        res = requests.get(endpoint, headers=headers, timeout=5)
        data = res.json()
        if res.status_code == 200 and len(data) > 0:
            last = data[0]
            return jsonify({
                "success": True,
                "data": {
                    "equipiersCount": last.get("equipiers_count", 0),
                    "couverture": last.get("couverture_rush", 0),
                    "sousEffectifs": last.get("sous_effectifs_count", 0),
                    "gainTotalID": f"+{last.get('gain_id_estime', 0)} %",
                    "semaine_iso": last.get("semaine_iso", ""),
                    "planning": last.get("planning_json", [])
                }
            }), 200
        return jsonify({"success": False, "message": "Aucun archivage"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/historique-plannings", methods=["GET"])
def get_historique_plannings():
    endpoint = f"{SUPABASE_URL}/rest/v1/historique_plannings_pdf?select=id,created_at,nom_fichier,semaine_iso,equipiers_count,couverture_rush,gain_id_estime&order=created_at.desc&limit=20"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    try:
        res = requests.get(endpoint, headers=headers, timeout=5)
        return jsonify({"success": True, "data": res.json()}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/agent-analyze", methods=["POST"])
def run_agent_analysis():
    try:
        data = request.get_json() or {}
        agent = StaffingAutonomousAgent(data.get("planning_data", {}), meteo_sky=data.get("meteo", "Ensoleillé"))
        return jsonify({"success": True, "rapport_agent": agent.analyser_et_decider()}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/cron/morning-briefing", methods=["GET", "POST"])
def trigger_morning_briefing():
    try:
        agent = StaffingAutonomousAgent()
        result = agent.generer_briefing_matin()
        return jsonify({"success": True, "data": result}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/cron/real-time-monitor", methods=["GET", "POST"])
def trigger_real_time_monitor():
    try:
        agent = StaffingAutonomousAgent()
        result = agent.surveiller_temps_reel()
        return jsonify({"success": True, "data": result}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
