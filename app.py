import os
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

# Imports des modules métiers
from pdf_staffing import process_planning_pdf
from ai_agent import StaffingAutonomousAgent
from planning_generator import PlanningGenerator

# 1. INITIALISATION
app = Flask(__name__)
CORS(app)

# Configuration Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://eilyxfhxmscuwbavkpzz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_eE-LmmezezF4l6L3O7hGBQ_hMOZL9i7")


# ==========================================
# 2. ROUTES DE DIAGNOSTIC (PDF)
# ==========================================

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({
        "status": "online",
        "service": "IdentiFid Omni-Staffing API",
        "mode": "PDF Parser + Generative AI"
    }), 200

@app.route("/analyze-planning-pdf", methods=["POST"])
def analyze_pdf():
    try:
        data = request.get_json()
        if not data or "file_data" not in data:
            return jsonify({"success": False, "message": "Aucun fichier transmis."}), 400

        result = process_planning_pdf(
            data.get("file_data"), 
            filename=data.get("filename", "planning.pdf")
        )
        return jsonify({"success": True, "data": result}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ==========================================
# 3. ROUTES SUPABASE (HISTORIQUE)
# ==========================================

@app.route("/dernier-planning", methods=["GET"])
def get_dernier_planning():
    endpoint = f"{SUPABASE_URL}/rest/v1/historique_plannings_pdf?select=planning_json,equipiers_count,couverture_rush,sous_effectifs_count,gain_id_estime,semaine_iso&order=created_at.desc&limit=1"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
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
        else:
            return jsonify({"success": False, "message": "Aucun archivage trouvé"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/historique-plannings", methods=["GET"])
def get_historique_plannings():
    endpoint = f"{SUPABASE_URL}/rest/v1/historique_plannings_pdf?select=id,created_at,nom_fichier,semaine_iso,equipiers_count,couverture_rush,gain_id_estime&order=created_at.desc&limit=20"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    try:
        res = requests.get(endpoint, headers=headers, timeout=5)
        if res.status_code == 200:
            return jsonify({"success": True, "data": res.json()}), 200
        return jsonify({"success": False, "message": f"Erreur {res.status_code}"}), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ==========================================
# 4. ROUTES D'INTELLIGENCE ARTIFICIELLE
# ==========================================

@app.route("/agent-analyze", methods=["POST"])
def run_agent_analysis():
    try:
        data = request.get_json() or {}
        planning_data = data.get("planning_data", {})
        
        agent = StaffingAutonomousAgent(planning_data)
        # Note: assure-toi que la méthode s'appelle bien analyser_et_decider dans ai_agent.py
        rapport = agent.analyser_et_decider() 
        return jsonify({"success": True, "rapport_agent": rapport}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/generer-planning", methods=["POST"])
def api_generer_planning():
    try:
        data = request.get_json() or {}
        budget_heures = int(data.get("budget_heures", 350))
        
        generateur = PlanningGenerator(budget_heures=budget_heures, contraintes={})
        scenarios = generateur.generer_scenarios()
        
        return jsonify({"success": True, "scenarios": scenarios}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ==========================================
# 5. ROUTES CRON (AUTONOMIE GOOGLE CHAT)
# ==========================================

@app.route("/cron/morning-briefing", methods=["GET", "POST"])
def trigger_morning_briefing():
    try:
        agent = StaffingAutonomousAgent({})
        result = agent.generer_briefing_matin()
        return jsonify({"success": True, "data": result}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/cron/real-time-monitor", methods=["GET", "POST"])
def trigger_real_time_monitor():
    try:
        agent = StaffingAutonomousAgent({})
        result = agent.surveiller_temps_reel()
        return jsonify({"success": True, "data": result}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ==========================================
# 6. DÉMARRAGE DU SERVEUR
# ==========================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
