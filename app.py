import os
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from pdf_staffing import process_planning_pdf

# 1. INITIALISATION DE L'APPLICATION FLASK
app = Flask(__name__)
CORS(app)

# Configuration Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://eilyxfhxmscuwbavkpzz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_eE-LmmezezF4l6L3O7hGBQ_hMOZL9i7")


# ==========================================
# 2. AGENT IA AUTONOME (CLASSE INTERNE)
# ==========================================
class StaffingAutonomousAgent:
    def __init__(self, planning_data, meteo_sky="Ensoleillé", trafic_var=0):
        self.planning = planning_data.get("planning", [])
        self.semaine = planning_data.get("semaine_iso", "S36")
        self.meteo = meteo_sky
        self.trafic_var = trafic_var
        self.headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }

    def analyser_et_decider(self):
        actions_correctives = []
        gain_id_total = 0.0

        # Calcul du facteur de stress
        facteur_stress = 1.0
        if self.meteo in ["Pluvieux", "Orageux", "Averses"]:
            facteur_stress += 0.20
        facteur_stress += (self.trafic_var / 100.0)

        # Détection des besoins de caisse
        caisse_count = sum(1 for p in self.planning if "Caisse" in p.get("activite", ""))
        
        if caisse_count < 3 and facteur_stress > 1.1:
            actions_correctives.append({
                "type": "ALERTE_RUSH",
                "priorite": "HAUTE",
                "message": f"🚨 Risque de saturation VMA détecté pour la semaine {self.semaine}.",
                "action": "Activer le renfort automatique d'Imane et Tharkoya sur le créneau 14h-18h."
            })
            gain_id_total += 4.5

        for p in self.planning:
            if p.get("profil") == "Expert Rush" and "Repos" in p.get("activite", ""):
                actions_correctives.append({
                    "type": "OPTIMISATION_PROFIL",
                    "priorite": "MOYENNE",
                    "message": f"💡 {p.get('nom')} (Expert Rush) est positionné en Repos.",
                    "action": "Proposer une permutation de shift pour maximiser le taux d'ID."
                })
                gain_id_total += 2.3

        rapport = {
            "semaine_iso": self.semaine,
            "score_coherence": max(40, int(100 - (len(actions_correctives) * 15))),
            "facteur_stress_calcule": round(facteur_stress, 2),
            "gain_id_potentiel": round(gain_id_total, 2),
            "actions_suggerees": actions_correctives
        }

        self._archiver_decision_agent(rapport)
        return rapport

    def _archiver_decision_agent(self, rapport):
        endpoint = f"{SUPABASE_URL}/rest/v1/agent_decisions_log"
        try:
            requests.post(endpoint, json=rapport, headers=self.headers, timeout=5)
        except Exception as e:
            print(f"Erreur d'archivage Agent : {e}")


# ==========================================
# 3. ROUTES ET ENDPOINTS DE L'API
# ==========================================

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({
        "status": "online",
        "service": "IdentiFid Smart Staffing MLOps Engine",
        "version": "3.2"
    }), 200


@app.route("/analyze-planning-pdf", methods=["POST"])
def analyze_pdf():
    try:
        data = request.get_json()
        if not data or "file_data" not in data:
            return jsonify({"success": False, "message": "Aucun fichier transmis."}), 400

        file_b64 = data.get("file_data")
        filename = data.get("filename", "planning.pdf")

        # Analyse et enregistrement Supabase via pdf_staffing.py
        result = process_planning_pdf(file_b64, filename=filename)

        return jsonify({"success": True, "data": result}), 200

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
        else:
            return jsonify({"success": False, "message": f"Erreur Supabase HTTP {res.status_code}"}), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/agent-analyze", methods=["POST"])
def run_agent_analysis():
    try:
        data = request.get_json() or {}
        planning_data = data.get("planning_data", {})
        meteo = data.get("meteo", "Ensoleillé")
        trafic_var = data.get("trafic_var", 0)

        agent = StaffingAutonomousAgent(planning_data, meteo_sky=meteo, trafic_var=trafic_var)
        rapport = agent.analyser_et_decider()

        return jsonify({"success": True, "rapport_agent": rapport}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ==========================================
# 4. POINT D'ENTRÉE DU SERVEUR
# ==========================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
