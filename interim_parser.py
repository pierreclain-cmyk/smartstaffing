import base64
import io
import os
import requests
import pandas as pd

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

REFERENTIEL_INTERIM = {
    "Tharkoya": {"profil": "Sprinter VMA", "gain_id": 2.8, "rayon": "Ligne de Caisse"},
    "Imane": {"profil": "Expert Rush", "gain_id": 2.5, "rayon": "Ligne de Caisse"},
    "Clara": {"profil": "Polyvalent", "gain_id": 2.0, "rayon": "Ligne de Caisse"}
}

def clean_time(time_str):
    try:
        t = str(time_str).lower().replace('h', ':')
        if len(t.split(':')[0]) == 1: t = '0' + t
        if len(t.split(':')) == 1 or t.split(':')[1] == '': t += '00'
        return t
    except: return "00:00"

def process_interim_csv(file_b64):
    file_bytes = base64.b64decode(file_b64)
    df = pd.read_csv(io.BytesIO(file_bytes), header=1)
    planning_interim = []
    
    for index, row in df.iterrows():
        if pd.isna(row.get('Prénom')): continue
        prenom = str(row['Prénom']).strip()
        nom = str(row['Nom']).strip()
        creneau = f"{clean_time(row['Heure de début'])} - {clean_time(row['Heure de fin'])}"
        
        profil_info = REFERENTIEL_INTERIM.get(prenom, {"profil": "Renfort Intérim", "gain_id": 1.0, "rayon": "Général"})
        planning_interim.append({
            "nom": f"{nom.upper()} {prenom.capitalize()}",
            "jour": str(row['Date']),
            "creneau": creneau,
            "activite": "Renfort",
            "rayon_cible": profil_info["rayon"],
            "profil": profil_info["profil"],
            "status": "Intérim Confirmé",
            "action": "Renfort Actif"
        })
    return {"equipe": "Renforts", "equipiersCount": len(planning_interim), "couverture": 100, "planning": planning_interim}
