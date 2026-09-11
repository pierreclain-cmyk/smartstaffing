import base64
import io
import os
import re
import requests
from PIL import Image

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

def process_planning_image(file_b64):
    # 1. Compression de l'image pour l'API Cloud
    image_bytes = base64.b64decode(file_b64)
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=70)
    compressed_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    # 2. Appel à l'API OCR (Contourne l'absence de Tesseract sur Render)
    payload = {
        'apikey': 'helloworld',
        'base64Image': 'data:image/jpeg;base64,' + compressed_b64,
        'language': 'fre'
    }
    
    res = requests.post('https://api.ocr.space/parse/image', data=payload, timeout=20)
    if res.status_code != 200 or res.json().get('IsErroredOnProcessing'):
        raise Exception("L'API de lecture d'image est indisponible ou l'image est trop volumineuse.")
        
    extracted_text = res.json()['ParsedResults'][0]['ParsedText']
    lines = [line.strip() for line in extracted_text.split("\n") if line.strip()]
    
    planning_realise = []
    collaborateurs = set()
    staff_en_rush = 0
    nom_courant = "Inconnu"
    
    # 3. Analyse du texte extrait
    for line in lines:
        nom_match = re.search(r"([A-ZÀ-Ÿ]{2,}\s+[A-Za-zÀ-ÿ]+)", line)
        if nom_match and not any(k in line.upper() for k in ["DECATHLON", "PLANNING", "TOTAL"]):
            nom_courant = nom_match.group(1).strip()
            
        time_match = re.search(r"(\d{2}[\.\:]\d{2})\s*-\s*(\d{2}[\.\:]\d{2})\s*(.*)", line)
        if time_match:
            start = time_match.group(1).replace('.', ':')
            end = time_match.group(2).replace('.', ':')
            creneau = f"{start} - {end}"
            infos_supp = time_match.group(3).upper() if time_match.group(3) else "GENERAL"
            
            rayon_detecte = "Général"
            activite = "Vente"
            if "WELLNESS" in infos_supp or "FITNESS" in infos_supp: rayon_detecte = "Fitness"
            elif "CYCLE" in infos_supp or "MONT" in infos_supp: rayon_detecte = "Cycle / Montagne"
            elif "WORKSHOP" in infos_supp or "ATELIER" in infos_supp: rayon_detecte = "Workshop"
            elif "CAISSE" in infos_supp: rayon_detecte = "Ligne de Caisse"
            elif "RH" in infos_supp or "REPOS" in infos_supp: 
                activite = "Repos"
                creneau = "00:00 - 00:00"

            collaborateurs.add(nom_courant)
            planning_realise.append({
                "nom": nom_courant,
                "jour": "Saisie OCR",
                "creneau": creneau,
                "activite": activite,
                "rayon_cible": rayon_detecte,
                "profil": "En apprentissage ML",
                "status": "Planifié OCR" if activite != "Repos" else "Repos"
            })
            
            if activite != "Repos":
                try:
                    debut_hour = int(start.split(":")[0])
                    fin_hour = int(end.split(":")[0])
                    if debut_hour <= 15 and fin_hour >= 17:
                        staff_en_rush += 1
                except: pass

    couverture_calculee = min(100, int((staff_en_rush / 4) * 100)) if staff_en_rush > 0 else 45
    sous_effectif_calc = max(0, 4 - staff_en_rush)

    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
    payload_db = {
        "nom_fichier": "capture_horoquartz.png",
        "semaine_iso": "OCR-SCAN",
        "nom_equipe": "Équipe Magasin",
        "equipiers_count": len(collaborateurs),
        "couverture_rush": couverture_calculee,
        "sous_effectifs_count": sous_effectif_calc,
        "gain_id_estime": 6.1,
        "planning_json": planning_realise,
        "status_execution": "ARCHIVE"
    }
    try: requests.post(f"{SUPABASE_URL}/rest/v1/historique_plannings_pdf", json=payload_db, headers=headers, timeout=5)
    except: pass

    return {
        "equipe": "Équipe Magasin",
        "semaine_iso": "OCR-SCAN",
        "equipiersCount": len(collaborateurs),
        "couverture": couverture_calculee,
        "sousEffectifs": sous_effectif_calc,
        "planning": planning_realise
    }
