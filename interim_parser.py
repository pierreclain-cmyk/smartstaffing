import base64
import io
import os
import requests
import pandas as pd
from datetime import datetime

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://eilyxfhxmscuwbavkpzz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_eE-LmmezezF4l6L3O7hGBQ_hMOZL9i7")

REFERENTIEL_INTERIM = {
    "Tharkoya": {"profil": "Sprinter VMA", "gain_id": 2.8, "rayon": "Caisse"},
    "Imane": {"profil": "Expert Rush", "gain_id": 2.5, "rayon": "Caisse"},
    "Clara": {"profil": "Polyvalent", "gain_id": 2.0, "rayon": "Caisse"}
}

def clean_time(time_str):
    try:
        t = str(time_str).lower().replace('h', ':')
        if len(t.split(':')[0]) == 1: t = '0' + t
        if len(t.split(':')) == 1 or t.split(':')[1] == '': t += '00'
        return t
    except:
        return "00:00"

def process_interim_csv(file_b64):
    file_bytes = base64.b64decode(file_b64)
    df = pd.read_csv(io.BytesIO(file_bytes), header=1)
    
    planning_interim = []
    
    for index, row in df.iterrows():
        if pd.isna(row['Prénom']): continue
            
        prenom = str(row['Prénom']).strip()
        nom = str(row['Nom']).strip()
        nom_complet = f"{nom.upper()} {prenom.capitalize()}"
        
        creneau = f"{clean_time(row['Heure de début'])} - {clean_time(row['Heure de fin'])}"
        date_mission = str(row['Date'])
        
        profil_info = REFERENTIEL_INTERIM.get(prenom, {"profil": "Renfort Intérim", "gain_id": 1.0, "rayon": "Caisse"})
        
        planning_interim.append({
            "nom": nom_complet,
            "jour": date_mission,
            "creneau": creneau,
            "activite": "Caisse",
            "rayon_cible": profil_info["rayon"],
            "profil": profil_info["profil"],
            "status": "Intérim Confirmé",
            "trafic_prevu": "180 pass/h",
            "gain_id": f"+{profil_info['gain_id']} % ID",
            "action": "Renfort Actif"
        })

    # 🔥 INJECTION DANS SUPABASE
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
    payload = {
        "nom_fichier": "export_interim.csv",
        "semaine_iso": "2026-INTERIM",
        "nom_equipe": "Renforts Intérim",
        "equipiers_count": len(planning_interim),
        "couverture_rush": 100,
        "sous_effectifs_count": 0,
        "gain_id_estime": 0,
        "planning_json": planning_interim,
        "status_execution": "ARCHIVE_INTERIM"
    }
    try:
        requests.post(f"{SUPABASE_URL}/rest/v1/historique_plannings_pdf", json=payload, headers=headers, timeout=5)
    except:
        pass

    return {
        "equipe": "Renforts Intérim",
        "semaine": "N/A",
        "semaine_iso": "2026-INTERIM",
        "equipiersCount": len(planning_interim),
        "couverture": 100,
        "sousEffectifs": 0,
        "gainTotalID": "+Variable",
        "planning": planning_interim
    }
