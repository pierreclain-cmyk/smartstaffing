import base64
import io
import pandas as pd
from datetime import datetime

# Référentiel pour catégoriser les intérimaires (sinon "Polyvalent" par défaut)
REFERENTIEL_INTERIM = {
    "Tharkoya": {"profil": "Sprinter VMA", "gain_id": 2.8, "rayon": "Caisse"},
    "Imane": {"profil": "Expert Rush", "gain_id": 2.5, "rayon": "Caisse"},
    "Clara": {"profil": "Polyvalent", "gain_id": 2.0, "rayon": "Caisse"}
}

def clean_time(time_str):
    """Transforme '9h00' en '09:00' et gère les erreurs."""
    try:
        t = str(time_str).lower().replace('h', ':')
        if len(t.split(':')[0]) == 1:
            t = '0' + t
        if len(t.split(':')) == 1 or t.split(':')[1] == '':
            t += '00'
        return t
    except:
        return "00:00"

def process_interim_csv(file_b64):
    file_bytes = base64.b64decode(file_b64)
    
    # Le vrai tableau commence à la ligne 2 (header=1)
    df = pd.read_csv(io.BytesIO(file_bytes), header=1)
    
    planning_interim = []
    
    for index, row in df.iterrows():
        if pd.isna(row['Prénom']):
            continue
            
        prenom = str(row['Prénom']).strip()
        nom = str(row['Nom']).strip()
        nom_complet = f"{nom.upper()} {prenom.capitalize()}"
        
        heure_debut = clean_time(row['Heure de début'])
        heure_fin = clean_time(row['Heure de fin'])
        creneau = f"{heure_debut} - {heure_fin}"
        
        date_mission = str(row['Date'])
        
        # Chercher dans le référentiel par prénom (très courant en intérim)
        profil_info = REFERENTIEL_INTERIM.get(prenom, {"profil": "Renfort Intérim", "gain_id": 1.0, "rayon": "Caisse"})
        
        planning_interim.append({
            "nom": nom_complet,
            "jour": date_mission,
            "creneau": creneau,
            "activite": "Caisse", # Par défaut pour l'intérim, modifiable
            "rayon_cible": profil_info["rayon"],
            "profil": profil_info["profil"],
            "status": "Intérim Confirmé",
            "trafic_prevu": "180 pass/h",
            "gain_id": f"+{profil_info['gain_id']} % ID",
            "action": "Renfort Actif"
        })

    return {
        "equipe": "Renforts Intérim",
        "semaine": "N/A",
        "semaine_iso": "2026-INTERIM",
        "equipiersCount": len(df),
        "couverture": 100,
        "sousEffectifs": 0,
        "gainTotalID": "+Variable",
        "planning": planning_interim
    }
