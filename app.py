import os
import io
import base64
import requests
import pandas as pd
from flask import Flask, request, jsonify
from flask_cors import CORS

# 1. Instanciation globale de l'application Flask (Requis pour gunicorn app:app)
app = Flask(__name__)
CORS(app)

# Configuration Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://eilyxfhxmscuwbavkpzz.supabase.co").rstrip('/')
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_eE-LmmezezF4l6L3O7hGBQ_hMOZL9i7")

# 2. Imports sécurisés des moteurs métiers
try:
    from pdf_staffing import process_planning_pdf
except ImportError as e:
    print(f"⚠️ Avertissement : Module pdf_staffing non chargé ({e})")
    process_planning_pdf = None

try:
    from ml_engine import RetailMLPredictor
except ImportError as e:
    print(f"⚠️ Avertissement : Module ml_engine non chargé ({e})")
    RetailMLPredictor = None


@app.route("/", methods=["GET"])
def health_check():
    """Route de contrôle de santé de l'API."""
    return jsonify({
        "status": "online",
        "service": "SmartStaffing ML Engine",
        "version": "3.1",
        "modules": {
            "pdf_staffing": process_planning_pdf is not None,
            "ml_engine": RetailMLPredictor is not None
        }
    }), 200


@app.route("/analyze-pdf", methods=["POST"])
def analyze_pdf():
    """Analyse un PDF de planning Horoquartz (Ligne de Caisse) transmis en Base64."""
    if process_planning_pdf is None:
        return jsonify({"success": False, "message": "Module pdf_staffing indisponible sur le serveur."}), 500

    try:
        data = request.get_json() or {}
        file_data = data.get("file_data", "")
        if not file_data:
            return jsonify({"success": False, "message": "Fichier PDF manquant dans la requête."}), 400
        
        result = process_planning_pdf(file_data)
        return jsonify({"success": True, "data": result}), 200

    except Exception as e:
        print(f"⚠️ Erreur /analyze-pdf : {str(e)}")
        return jsonify({"success": False, "message": f"Erreur de traitement PDF : {str(e)}"}), 500


@app.route("/inject-commerce", methods=["POST"])
def inject_commerce():
    """Injecte un fichier CSV de données commerce ou de performances hebdomadaires dans Supabase."""
    try:
        data = request.get_json() or {}
        rayon = data.get("rayon", "Ligne de Caisse")
        semaine_iso = data.get("semaine_iso", "2026-W10")
        raw_b64 = data.get("file_data", "")

        if not raw_b64:
            return jsonify({"success": False, "message": "Fichier CSV absent."}), 400

        if "," in raw_b64:
            raw_b64 = raw_b64.split(",")[1]

        file_bytes = base64.b64decode(raw_b64)

        # Lecture du CSV avec gestion des séparateurs (virgule ou point-virgule)
        try:
            df = pd.read_csv(io.BytesIO(file_bytes), sep=",", on_bad_lines="skip")
            if len(df.columns) < 2:
                df = pd.read_csv(io.BytesIO(file_bytes), sep=";", on_bad_lines="skip")
        except Exception as e:
            return jsonify({"success": False, "message": f"Erreur de lecture du CSV : {str(e)}"}), 400

        df = df.fillna("")
        df.columns = df.columns.str.strip().str.replace('"', '').str.replace("'", "")

        clean_url = SUPABASE_URL.rstrip('/')
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }

        # Détection automatique de la table cible dans Supabase
        if "volume_affaires_instore" in df.columns or "trafic_instore" in df.columns:
            records = df.to_dict(orient="records")
            endpoint = f"{clean_url}/rest/v1/performance_magasin_hebdo"
            res = requests.post(endpoint, json=records, headers=headers, timeout=10)
            table_cible = "performance_magasin_hebdo"
        else:
            endpoint = f"{clean_url}/rest/v1/historique_ca_rayons"
            payload = {
                "rayon": rayon,
                "semaine_iso": semaine_iso,
                "donnees_financieres": df.to_dict(orient="records")
            }
            res = requests.post(endpoint, json=payload, headers=headers, timeout=10)
            table_cible = "historique_ca_rayons"

        if res.status_code in (200, 201):
            return jsonify({"success": True, "message": f"✅ {len(df)} lignes importées dans {table_cible}"}), 200
        else:
            print(f"⚠️ Erreur Supabase ({res.status_code}) : {res.text}")
            return jsonify({"success": False, "message": f"Erreur Supabase ({res.status_code}) : {res.text}"}), 500

    except Exception as e:
        print(f"⚠️ Erreur /inject-commerce : {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/generate-scenarios", methods=["POST"])
def generate_scenarios():
    """Génère les propositions de plannings optimisés MLOps pour la Ligne de Caisse."""
    if RetailMLPredictor is None:
        return jsonify({"success": False, "message": "Module ml_engine indisponible sur le serveur."}), 500

    try:
        data = request.get_json() or {}
        budget = int(data.get("budget", 350))
        date_cible = data.get("date_cible", "2026-10-01")
        semaine_cible = data.get("semaine_cible", "S+3")

        predictor = RetailMLPredictor()
        scenarios = predictor.generate_proposals(budget, date_cible, semaine_cible)
        return jsonify({"success": True, "data": {"scenarios": scenarios}}), 200

    except Exception as e:
        print(f"⚠️ Erreur /generate-scenarios : {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/historique", methods=["GET"])
def get_historique():
    """Récupère l'historique des plannings enregistrés depuis Supabase."""
    try:
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        endpoint = f"{SUPABASE_URL}/rest/v1/historique_plannings_pdf?select=id,semaine_iso,nom_fichier,couverture_rush,equipiers_count,created_at&order=created_at.desc"
        res = requests.get(endpoint, headers=headers, timeout=5)
        
        if res.status_code == 200:
            return jsonify({"success": True, "data": res.json()}), 200
        
        return jsonify({"success": False, "message": f"Erreur Supabase ({res.status_code}) : {res.text}"}), 500

    except Exception as e:
        print(f"⚠️ Erreur /historique : {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
