import base64
import io
import os
import re
import requests
from PIL import Image

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://eilyxfhxmscuwbavkpzz.supabase.co").rstrip('/')
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_eE-LmmezezF4l6L3O7hGBQ_hMOZL9i7")

JOURS_DEFAUT = ["Di 27", "Lu 28", "Ma 29", "Me 30", "Je 01", "Ve 02", "Sa 03"]

def process_planning_image(file_b64):
    image_bytes = base64.b64decode(file_b64)
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=70)
    compressed_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    payload = {
        'apikey': 'helloworld',
        'base64Image': 'data:image/jpeg;base64,' + compressed_b64,
        'language': 'fre',
        'isTable': 'true'
    }
    
    res = requests.post('https://api.ocr.space/parse/image', data=payload, timeout=20)
    if res.status_code != 200 or res.json().get('IsErroredOnProcessing'):
        raise Exception("L'API de lecture d'image est indisponible.")
        
    extracted_text = res.json()['ParsedResults'][0]['ParsedText']
    
    # Extraction de la semaine ISO
    semaine_match = re.search(r"\bS(\d{2})\b", extracted_text, re.IGNORECASE)
    semaine_iso = f"2026-S{semaine_match.group(1)}" if semaine_match else "2026-S40"

    # Reconstitution des 7 jours d'entête
    matches_jours = re.findall(r"\b(Di|Lu|Ma|Me|Je|Ve|Sa)\s*(\d{1,2})\b", extracted_text, re.IGNORECASE)
    if len(matches_jours) >= 7:
        jours_detectes = [f"{j[0].capitalize()} {j[1]}" for j in matches_jours[:7]]
    else:
        jours_detectes = JOURS_DEFAUT

    lines = [line.strip() for line in extracted_text.split("\n") if line.strip()]
    
    planning_realise = []
    collaborateurs = set()
    seen_entries = set()
    staff_en_rush = 0
    
    mots_exclus_noms = [
        "DECATHLON", "PLANNING", "TOTAL", "WELLNES", "FITNESS", "CYCLE", 
        "MONTAGNE", "WORKSHOP", "ATELIER", "CAISSE", "ACCUEIL", "RH", 
        "REPOS", "SERVICES", "GENERAL", "MANAGER", "EQUIPE", "HEURE", 
        "CIBLE", "EMPLOYES", "REC", "PÉRIODE", "FUTUR", "SEPTEMBRE", "OCTOBRE", "AOUT"
    ]

    nom_courant = "Inconnu"

    for line in lines:
        # Séparation par cellule grâce aux tabulations du mode Tableau OCR
        cells = [c.strip() for c in line.split('\t') if c.strip()]
        if not cells:
            cells = [line]

        # 1. Recherche d'un nom de collaborateur dans la ligne
        nom_trouve = None
        for cell in cells:
            nom_match = re.search(r"([A-ZÀ-Ÿ]{3,}[\s\-]+[A-ZÀ-Ÿa-zà-ÿ]{3,})", cell)
            if nom_match:
                candidate = nom_match.group(1).strip()
                if not any(k in candidate.upper() for k in mots_exclus_noms) and not re.search(r"\d", candidate):
                    nom_trouve = candidate
                    break

        if nom_trouve:
            nom_courant = nom_trouve
            collaborateurs.add(nom_courant)

        # 2. Analyse des cellules horaires/repos
        # On ne traite que si un nom est déjà identifié
        if nom_courant == "Inconnu":
            continue

        # Extraction de tous les créneaux ou mentions RH dans la ligne
        day_cell_idx = 0
        for cell in cells:
            # Recherche d'horaires dans la cellule
            time_matches = re.findall(r"(\d{1,2})[\.\:hH](\d{2})\s*[-|à|a]\s*(\d{1,2})[\.\:hH](\d{2})(.*)", cell)
            is_repos = bool(re.search(r"\b(RH|REPOS)\b", cell.upper())) and not time_matches

            if is_repos:
                jour_libelle = jours_detectes[day_cell_idx % len(jours_detectes)]
                unique_key = f"{nom_courant}_{jour_libelle}_REPOS"
                if unique_key not in seen_entries:
                    seen_entries.add(unique_key)
                    planning_realise.append({
                        "nom": nom_courant,
                        "jour": jour_libelle,
                        "creneau": "00:00 - 00:00",
                        "activite": "Repos",
                        "rayon_cible": "Aucun",
                        "profil": "En apprentissage ML",
                        "status": "Repos"
                    })
                day_cell_idx += 1

            elif time_matches:
                jour_libelle = jours_detectes[day_cell_idx % len(jours_detectes)]
                for tm in time_matches:
                    h_start, m_start, h_end, m_end, rest = tm
                    creneau = f"{h_start.zfill(2)}:{m_start} - {h_end.zfill(2)}:{m_end}"
                    infos_supp = rest.upper() if rest else "GENERAL"

                    rayon_detecte = "Général"
                    activite = "Vente"
                    if "WELLNES" in infos_supp or "FITNESS" in infos_supp: rayon_detecte = "Fitness"
                    elif "CYCLE" in infos_supp or "MONT" in infos_supp: rayon_detecte = "Cycle / Montagne"
                    elif "WORKSHOP" in infos_supp or "ATELIER" in infos_supp: rayon_detecte = "Workshop"
                    elif "CAISSE" in infos_supp or "ACCUEIL" in infos_supp: rayon_detecte = "Ligne de Caisse"

                    try:
                        if int(h_start) <= 15 and int(h_end) >= 17:
                            staff_en_rush += 1
                    except: pass

                    unique_key = f"{nom_courant}_{jour_libelle}_{creneau}"
                    if unique_key not in seen_entries:
                        seen_entries.add(unique_key)
                        planning_realise.append({
                            "nom": nom_courant,
                            "jour": jour_libelle,
                            "creneau": creneau,
                            "activite": activite,
                            "rayon_cible": rayon_detecte,
                            "profil": "En apprentissage ML",
                            "status": "Planifié OCR"
                        })
                day_cell_idx += 1

    couverture_calculee = min(100, int((staff_en_rush / 4) * 100)) if staff_en_rush > 0 else 45
    sous_effectif_calc = max(0, 4 - staff_en_rush)

    # Export Supabase
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
    payload_db = {
        "nom_fichier": "capture_horoquartz.png",
        "semaine_iso": semaine_iso,
        "nom_equipe": "Équipe Magasin",
        "equipiers_count": len(collaborateurs),
        "couverture_rush": couverture_calculee,
        "sous_effectifs_count": sous_effectif_calc,
        "gain_id_estime": 6.1,
        "planning_json": planning_realise,
        "status_execution": "ARCHIVE"
    }
    
    try: 
        res_db = requests.post(f"{SUPABASE_URL}/rest/v1/historique_plannings_pdf", json=payload_db, headers=headers, timeout=5)
        if res_db.status_code not in (200, 201):
            print(f"Erreur Supabase ({res_db.status_code}): {res_db.text}")
    except Exception as e: 
        print(f"Erreur réseau Supabase : {str(e)}")

    return {
        "equipe": "Équipe Magasin",
        "semaine_iso": semaine_iso,
        "equipiersCount": len(collaborateurs),
        "couverture": couverture_calculee,
        "sousEffectifs": sous_effectif_calc,
        "planning": planning_realise
    }
