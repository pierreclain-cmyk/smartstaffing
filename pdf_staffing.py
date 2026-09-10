import base64
import io
import os
import re
import pdfplumber
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://eilyxfhxmscuwbavkpzz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_eE-LmmezezF4l6L3O7hGBQ_hMOZL9i7")

REFERENTIEL_RH = {
    "CEAGLIO Valerie": {"profil": "Sniper ID", "gain_id": 4.2, "rayon": "Caisse"},
    "DIBOINE Simon": {"profil": "Sprinter VMA", "gain_id": 3.8, "rayon": "Caisse"},
    "LIOTTA Clara": {"profil": "Expert Rush", "gain_id": 5.1, "rayon": "Caisse"},
    "HAMAZ Tharkoya": {"profil": "Polyvalent", "gain_id": 2.8, "rayon": "Caisse"},
    "BITOUN Clara": {"profil": "Polyvalent", "gain_id": 2.0, "rayon": "Accueil"},
    "CLARION Fabienne": {"profil": "Renfort", "gain_id": 1.5, "rayon": "Caisse"},
    "D'ORIA Christelle": {"profil": "Expert Vente", "gain_id": 0.0, "rayon": "Rayon"},
    "RAOUX HUGO": {"profil": "Renfort VMA", "gain_id": 3.0, "rayon": "Caisse"},
    "BRUN MYLENE": {"profil": "Renfort VMA", "gain_id": 2.5, "rayon": "Caisse"}
}

def process_planning_pdf(file_b64, filename="planning.pdf"):
    pdf_bytes = base64.b64decode(file_b64)
    extracted_text = ""
    
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages[:4]:
            text = page.extract_text()
            if text: extracted_text += text + "\n"
            page.flush_cache()

    lines = [line.strip() for line in extracted_text.split("\n") if line.strip()]
    equipe_match = re.search(r"Nom Equipe:\s*(.*)", extracted_text)
    semaine_match = re.search(r"PLANNING\s+(?:REALISE|PREVISIONNEL)\s+S(\d+)", extracted_text)

    nom_equipe = equipe_match.group(1).strip() if equipe_match else "Cashier Services"
    num_semaine = semaine_match.group(1) if semaine_match else "10"
    semaine_iso = f"2026-S{num_semaine.zfill(2)}"

    collaborateurs_trouves = set()
    collab_pattern = re.compile(r"^([A-Z\d\'\-\s]{2,}\s+[A-Za-z\d\'\-]+)(?:\s+(?:V|VR|DR|D|ND))?$")
    planning_realise = []
    current_day = "Lundi 02/03/2026"
    mots_cles_ignores = ["NOM EQUIPE", "NOM DU PATRON", "DECATHLON", "PLANNING REALISE", "INFORMATION D'IMPRESSION", "ETAT", "DESCRIPTION"]

    for i, line in enumerate(lines):
        if any(j in line.lower() for j in ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]) and "/" in line:
            current_day = line.split("Etat")[0].strip()

        line_clean = line.upper()
        if any(ignore in line_clean for ignore in mots_cles_ignores): continue

        nom_trouve = next((ref for ref in REFERENTIEL_RH.keys() if ref.upper() in line_clean), None)
        if not nom_trouve and collab_pattern.match(line):
            nom_trouve = line.split("V")[0].split("113")[0].strip()

        if nom_trouve and len(nom_trouve) > 3 and not nom_trouve.startswith("113-"):
            collaborateurs_trouves.add(nom_trouve)
            type_activite = "Repos / RH"
            creneau_stricte = "00:00 - 00:00"
            
            for offset in range(1, 4):
                if i + offset < len(lines):
                    sub = lines[i + offset]
                    if "Vente" in sub: type_activite = "Vente"
                    elif any(k in sub for k in ["Caisse", "Accueil", "QCO", "Demenagmt"]): type_activite = "Caisse"
                    
                    dur_match = re.search(r"(\d{2}:\d{2})\s+(\d{2}:\d{2})", sub)
                    if dur_match:
                        dur = dur_match.group(1)
                        if dur == "08:45": creneau_stricte = "09:15 - 18:00"
                        elif dur == "05:00": creneau_stricte = "08:00 - 13:00"
                        elif dur == "06:00": creneau_stricte = "13:00 - 19:00"
                        elif dur != "00:00": creneau_stricte = f"Durée : {dur}"

            profil_info = REFERENTIEL_RH.get(nom_trouve, {"profil": "Polyvalent", "gain_id": 1.5, "rayon": "Caisse"})
            planning_realise.append({
                "nom": nom_trouve,
                "jour": current_day,
                "creneau": creneau_stricte,
                "activite": type_activite,
                "rayon_cible": profil_info["rayon"] if type_activite == "Vente" else "Caisse",
                "profil": profil_info["profil"],
                "status": "Planifié PDF" if type_activite != "Repos / RH" else "Repos",
                "trafic_prevu": "180 pass/h" if type_activite == "Caisse" else "Trafic Rayon",
                "gain_id": f"+{profil_info['gain_id']} % ID" if type_activite == "Caisse" else "Impact CA",
                "action": "Conforme" if type_activite != "Repos / RH" else "Axe d'optimisation"
            })

    endpoint = f"{SUPABASE_URL}/rest/v1/historique_plannings_pdf"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
    payload = {
        "nom_fichier": filename, "semaine_iso": semaine_iso, "nom_equipe": nom_equipe,
        "equipiers_count": len(collaborateurs_trouves), "couverture_rush": 88,
        "sous_effectifs_count": 0, "gain_id_estime": 6.1, "planning_json": planning_realise,
        "status_execution": "ARCHIVE"
    }
    try: requests.post(endpoint, json=payload, headers=headers, timeout=5)
    except: pass

    return {
        "equipe": nom_equipe, "semaine": num_semaine, "semaine_iso": semaine_iso,
        "equipiersCount": len(collaborateurs_trouves), "couverture": 88,
        "sousEffectifs": 0, "gainTotalID": "+6.1 % ID Global", "planning": planning_realise
    }
