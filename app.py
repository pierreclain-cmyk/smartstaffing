import os
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

from pdf_staffing import process_planning_pdf
from interim_parser import process_interim_csv
from ai_agent import StaffingAutonomousAgent
from planning_generator import PlanningGenerator

app = Flask(__name__)
CORS(app)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://eilyxfhxmscuwbavkpzz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_eE-LmmezezF4l6L3O7hGBQ_hMOZL9i7")

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "online", "mode": "Production"}), 200

@app.route("/analyze-planning-pdf", methods=["POST"])
def analyze_pdf():
    try:
        data = request.get_json()
        if not data or "file_data" not in data:
            return jsonify({"success": False, "message": "Aucun fichier transmis."}), 400
        result = process_planning_pdf(data.get("file_data"), filename=data.get("filename", "planning.pdf"))
        return jsonify({"success": True, "data": result}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/analyze-interim-csv", methods=["POST"])
def analyze_interim():
    try:
        data = request.get_json()
        if not data or "file_data" not in data:
            return jsonify({"success": False, "message": "Aucun fichier transmis."}), 400
        result = process_interim_csv(data.get("file_data"))
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
        return jsonify({"success": False, "message": "Aucun archivage trouvé"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/historique-plannings", methods=["GET"])
def get_historique_plannings():
    endpoint = f"{SUPABASE_URL}/rest/v1/historique_plannings_pdf?select=id,created_at,nom_fichier,semaine_iso,equipiers_count,couverture_rush,gain_id_estime&order=created_at.desc&limit=20"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    try:
        res = requests.get(endpoint, headers=headers, timeout=5)
        if res.status_code == 200:
            return jsonify({"success": True, "data": res.json()}), 200
        return jsonify({"success": False, "message": f"Erreur {res.status_code}"}), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/agent-analyze", methods=["POST"])
def run_agent_analysis():
    try:
        data = request.get_json() or {}
        agent = StaffingAutonomousAgent(data.get("planning_data", {}))
        return jsonify({"success": True, "rapport_agent": agent.analyser_et_decider()}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/generer-planning", methods=["POST"])
def api_generer_planning():
    try:
        data = request.get_json() or {}
        jour_cible = data.get("jour_cible", "Samedi")
        semaine_cible = data.get("semaine_cible", "S+3")
        budget = int(data.get("budget_heures", 350))
        
        generateur = PlanningGenerator(budget_heures=budget, jour_cible=jour_cible, semaine_cible=semaine_cible)
        return jsonify({"success": True, "data": generateur.generer_scenarios()}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
        generateur = PlanningGenerator(budget_heures=budget, jour_cible=jour_cible)
        return jsonify({"success": True, "data": generateur.generer_scenarios()}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
