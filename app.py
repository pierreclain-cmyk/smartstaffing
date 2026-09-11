import base64
import io
import os
import re
import pdfplumber
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://eilyxfhxmscuwbavkpzz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_eE-LmmezezF4l6L3O7hGBQ_hMOZL9i7")

REFERENTIEL_RH = {
    "CEAGLIO Valerie": {"profil": "Sniper ID", "gain_id": 4.2},
    "DIBOINE Simon": {"profil": "Sprinter VMA", "gain_id": 3.8},
    "LIOTTA Clara": {"profil": "Expert Rush", "gain_id": 5.1},
    "HAMAZ Tharkoya": {"profil": "Polyvalent", "gain_id": 2.8},
    "BITOUN Clara": {"profil": "Polyvalent", "gain_id": 2.0},
    "CLARION Fabienne": {"profil": "Renfort", "gain_id": 1.5},
    "D'ORIA Christelle": {"profil": "Expert Vente", "gain_id": 0.0},
    "RAOUX HUGO": {"profil": "Renfort VMA", "gain_id": 3.0},
    "BRUN MYLENE": {"profil": "Renfort VMA", "gain_id": 2.5}
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

    nom_equipe = equipe_match.group(1).strip() if equipe_match else "Équipe Magasin"
    num_semaine = semaine_match.group(1) if semaine_match else "10"
    semaine_iso = f"2026-S{num_semaine.zfill(2)}"

    collaborateurs_trouves = set()
    planning_realise = []
    current_day = "Lundi 02/03/2026"

    for i, line in enumerate(lines):
        if any(j in line.lower() for j in ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]) and "/" in line:
            current_day = line.split("Etat")[0].strip()

        nom_trouve = None
        for ref_nom in REFERENTIEL_RH.keys():
            if ref_nom.upper() in line.upper():
                nom_trouve = ref_nom
                break
        
        if not nom_trouve and re.match(r"^[A-Z\d\'\-\s]{2,}\s+[A-Za-z]+", line):
            if not any(k in line.upper() for k in ["DECATHLON", "PLANNING", "EQUIPE", "PATRON", "INFORMATION", "ETAT"]):
                nom_trouve = line.split("V")[0].split("113")[0].strip()

        if nom_trouve and len(nom_trouve) > 3:
            collaborateurs_trouves.add(nom_trouve)
            type_activite = "Repos / RH"
            rayon_detecte = "Général"
            creneau_stricte = "00:00 - 00:00"
            
            for offset in range(1, 4):
                if i + offset < len(lines):
                    sub = lines[i + offset]
                    
                    if any(k in sub.upper() for k in ["WORKSHOP", "ATELIER", "REPARATION"]):
                        type_activite = "Atelier"
                        rayon_detecte = "Workshop"
                    elif "CAISSE" in sub.upper() or "ACCUEIL" in sub.upper():
                        type_activite = "Caisse"
                        rayon_detecte = "Ligne de Caisse"
                    elif "VENTE" in sub.upper() or "RAYON" in sub.upper():
                        type_activite = "Vente"
                        mots = sub.split()
                        if len(mots) > 1 and mots[0].upper() == "VENTE":
                            rayon_detecte = " ".join(mots[1:])
                            if "CYCLE" in rayon_detecte.upper() or "MONTAGNE" in rayon_detecte.upper():
                                rayon_detecte = "Cycle / Montagne"
                    
                    time_match = re.search(r"(\d{2}[:h]\d{2}).*?(\d{2}[:h]\d{2})", sub)
                    if time_match:
                        start = time_match.group(1).replace('h', ':')
                        end = time_match.group(2).replace('h', ':')
                        creneau_stricte = f"{start} - {end}"

            profil_info = REFERENTIEL_RH.get(nom_trouve, {"profil": "Polyvalent", "gain_id": 1.5})
            planning_realise.append({
                "nom": nom_trouve,
                "jour": current_day,
                "creneau": creneau_stricte,
                "activite": type_activite,
                "rayon_cible": rayon_detecte,
                "profil": profil_info["profil"],
                "status": "Planifié PDF" if type_activite != "Repos / RH" else "Repos",
                "action": "Conforme"
            })

    staff_en_rush = sum(1 for p in planning_realise if p["status"] != "Repos" and "-" in p["creneau"] and int(p["creneau"].split("-")[0].strip().split(":")[0]) <= 15 and int(p["creneau"].split("-")[1].strip().split(":")[0]) >= 17)
    couverture_calculee = min(100, int((staff_en_rush / 4) * 100)) if staff_en_rush > 0 else 45

    is_realise = "REALISE" in extracted_text.upper()
    type_planning = "Réalisé (Échu)" if is_realise else "Prévisionnel"
    
    ecart_perf = None
    if is_realise:
        ecart = couverture_calculee - 100
        ecart_perf = f"{ecart} pts vs Prédiction IA"

    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
    payload = {
        "nom_fichier": filename,
        "semaine_iso": semaine_iso,
        "nom_equipe": nom_equipe,
        "equipiers_count": len(collaborateurs_trouves),
        "couverture_rush": couverture_calculee,
        "sous_effectifs_count": max(0, 4 - staff_en_rush),
        "gain_id_estime": 6.1,
        "planning_json": planning_realise,
        "status_execution": "ARCHIVE"
    }
    try: requests.post(f"{SUPABASE_URL}/rest/v1/historique_plannings_pdf", json=payload, headers=headers, timeout=5)
    except: pass

    return {
        "equipe": nom_equipe,
        "semaine_iso": semaine_iso,
        "type_planning": type_planning,
        "ecart_perf": ecart_perf,
        "equipiersCount": len(collaborateurs_trouves),
        "couverture": couverture_calculee,
        "sousEffectifs": max(0, 4 - staff_en_rush),
        "planning": planning_realise
    }
