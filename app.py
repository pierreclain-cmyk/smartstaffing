import os
import io
import base64
import requests
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS

from vision_staffing import process_planning_image
from interim_parser import process_interim_csv
from ml_engine import RetailMLPredictor
from planning_generator import PlanningGenerator

app = Flask(__name__)
CORS(app)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://eilyxfhxmscuwbavkpzz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_eE-LmmezezF4l6L3O7hGBQ_hMOZL9i7")

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "online", "mode": "Production OCR MLOps"}), 200

@app.route("/analyze-image", methods=["POST"])
def analyze_image():
    try:
        data = request.get_json()
        if not data or "file_data" not in data:
            return jsonify({"success": False, "message": "Aucune image transmise."}), 400
        result = process_planning_image(data.get("file_data"))
        return jsonify({"success": True, "data": result}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/analyze-interim-csv", methods=["POST"])
def analyze_interim():
    try:
        data = request.get_json()
        result = process_interim_csv(data.get("file_data"))
        return jsonify({"success": True, "data": result}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/inject-commerce", methods=["POST"])
def inject_commerce():
    try:
        data = request.get_json() or {}
        rayon = data.get("rayon", "Général")
        semaine_iso = data.get("semaine_iso", "2026-W10")
        raw_b64 = data.get("file_data", "")

        if not raw_b64:
            return jsonify({"success": False, "message": "Fichier CSV absent."}), 400

        if "," in raw_b64:
            raw_b64 = raw_b64.split(",")[1]

        file_bytes = base64.b64decode(raw_b64)

        # Lecture du CSV avec gestion des séparateurs ; et ,
        try:
            df = pd.read_csv(io.BytesIO(file_bytes), sep=",", on_bad_lines="skip")
            if len(df.columns) < 2:
                df = pd.read_csv(io.BytesIO(file_bytes), sep=";", on_bad_lines="skip")
        except Exception as e:
            return jsonify({"success": False, "message": f"Erreur lecture CSV : {str(e)}"}), 400

        df = df.fillna("")
        df.columns = df.columns.str.strip().str.replace('"', '').str.replace("'", "")

        clean_url = SUPABASE_URL.rstrip('/')
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }

        # Orientation automatique selon le type de fichier CSV
        if "volume_affaires_instore" in df.columns or "trafic_instore" in df.columns:
            # CSV de performance hebdomadaire globale
            records = df.to_dict(orient="records")
            endpoint = f"{clean_url}/rest/v1/performance_magasin_hebdo"
            res = requests.post(endpoint, json=records, headers=headers, timeout=10)
            table_cible = "performance_magasin_hebdo"
        else:
            # CSV spécifique à un rayon
            endpoint = f"{clean_url}/rest/v1/historique_ca_rayons"
            payload = {
                "rayon": rayon,
                "semaine_iso": semaine_iso,
                "donnees_financieres": df.to_dict(orient="records")
            }
            res = requests.post(endpoint, json=payload, headers=headers, timeout=10)
            table_cible = "historique_ca_rayons"

        if res.status_code in (200, 201):
            return jsonify({"success": True, "message": f"✅ {len(df)} lignes injectées dans Supabase ({table_cible})"}), 200
        else:
            print(f"⚠️ ERREUR SUPABASE COMMERCE ({res.status_code}) : {res.text}")
            return jsonify({"success": False, "message": f"Erreur Supabase ({res.status_code}) : {res.text}"}), 500

    except Exception as e:
        print(f"⚠️ CRASH INJECT COMMERCE : {str(e)}")
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
            return jsonify({"success": True, "data": {
                "equipiersCount": last.get("equipiers_count", 0),
                "couverture": last.get("couverture_rush", 0),
                "sousEffectifs": last.get("sous_effectifs_count", 0),
                "semaine_iso": last.get("semaine_iso", ""),
                "planning": last.get("planning_json", [])
            }}), 200
        return jsonify({"success": False, "message": "Aucun archivage"}), 404
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
