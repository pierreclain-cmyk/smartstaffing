import base64
import io
import os
import re
import requests
from PIL import Image

# 🔥 Sécurité : Vérifie que tes variables d'environnement sont bien renseignées sur Render
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://eilyxfhxmscuwbavkpzz.supabase.co").rstrip('/')
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_eE-LmmezezF4l6L3O7hGBQ_hMOZL9i7")

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
    
    # Remplacement des tabulations générées par le mode Tableau
    extracted_text = extracted_text.replace('\t', ' ')
    
    semaine_match = re.search(r"\bS(\d{2})\b", extracted_text, re.IGNORECASE)
    semaine_iso = f"2026-S{semaine_match.group(1)}" if semaine_match else "S-INCONNUE"

    lines = [line.strip() for line in extracted_text.split("\n") if line.strip()]
    
    planning_realise = []
    collaborateurs = set()
    staff_en_rush = 0
    nom_courant = "Inconnu"
    
    mots_exclus_noms = [
        "DECATHLON", "PLANNING", "TOTAL", "WELLNES", "FITNESS", "CYCLE", 
        "MONTAGNE", "WORKSHOP", "ATELIER", "CAISSE", "ACCUEIL", "RH", 
        "REPOS", "SERVICES", "GENERAL", "MANAGER", "EQUIPE", "HEURE", 
        "CIBLE", "EMPLOYES", "REC", "PÉRIODE", "FUTUR", "SEPTEMBRE", "OCTOBRE", "AOUT"
    ]
    
    for line in lines:
        nom_match = re.search(r"([A-ZÀ-Ÿ]{3,}[\s\-]+[A-ZÀ-Ÿa-zà-ÿ]{3,})", line)
        
        if nom_match:
            nom_potentiel = nom_match.group(1).strip()
            if not any(k in nom_potentiel.upper() for k in mots_exclus_noms) and not re.search(r"\d", nom_potentiel):
                nom_courant = nom_potentiel
                
        # 🔥 Regex Ultra-Permissive : Capte 09.00, 9h00, 09:00 - 13.00, 09h00 à 13h00
        time_match = re.search(r"(\d{1,2})[\.\:hH](\d{2})\s*[-|à|a]\s*(\d{1,2})[\.\:hH](\d{2})(.*)", line)
        
        if time_match:
            h_start, m_start, h_end, m_end, rest = time_match.groups()
            creneau = f"{h_start.zfill(2)}:{m_start} - {h_end.zfill(2)}:{m_end}"
            infos_supp = rest.upper() if rest else "GENERAL"
            
            rayon_detecte = "Général"
            activite = "Vente"
            if "WELLNES" in infos_supp or "FITNESS" in infos_supp: rayon_detecte = "Fitness"
            elif "CYCLE" in infos_supp or "MONT" in infos_supp: rayon_detecte = "Cycle / Montagne"
            elif "WORKSHOP" in infos_supp or "ATELIER" in infos_supp: rayon_detecte = "Workshop"
            elif "CAISSE" in infos_supp or "ACCUEIL" in infos_supp: rayon_detecte = "Ligne de Caisse"
            elif "RH" in infos_supp or "REPOS" in infos_supp: 
                activite = "Repos"
                creneau = "00:00 - 00:00"

            if nom_courant != "Inconnu":
                collaborateurs.add(nom_courant)
                
            planning_realise.append({
                "nom": nom_courant,
                "jour": "Jour Détecté",
                "creneau": creneau,
                "activite": activite,
                "rayon_cible": rayon_detecte,
                "profil": "En apprentissage ML",
                "status": "Planifié OCR" if activite != "Repos" else "Repos"
            })
            
            if activite != "Repos":
                try:
                    if int(h_start) <= 15 and int(h_end) >= 17:
                        staff_en_rush += 1
                except: pass

    couverture_calculee = min(100, int((staff_en_rush / 4) * 100)) if staff_en_rush > 0 else 45
    sous_effectif_calc = max(0, 4 - staff_en_rush)

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
    
    # 🔥 Log d'erreur détaillé pour Supabase
    try: 
        res_db = requests.post(f"{SUPABASE_URL}/rest/v1/historique_plannings_pdf", json=payload_db, headers=headers, timeout=5)
        if res_db.status_code not in (200, 201):
            print(f"⚠️ ERREUR SUPABASE ({res_db.status_code}): {res_db.text}")
    except Exception as e: 
        print(f"⚠️ ERREUR RÉSEAU SUPABASE: {str(e)}")

    return {
        "equipe": "Équipe Magasin",
        "semaine_iso": semaine_iso,
        "equipiersCount": len(collaborateurs),
        "couverture": couverture_calculee,
        "sousEffectifs": sous_effectif_calc,
        "planning": planning_realise
    }
