import base64
import io
import os
import re
import requests
from PIL import Image

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://eilyxfhxmscuwbavkpzz.supabase.co").rstrip('/')
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_eE-LmmezezF4l6L3O7hGBQ_hMOZL9i7")

JOURS_DEFAUT = ["Di 27", "Lu 28", "Ma 29", "Me 30", "Je 01", "Ve 02", "Sa 03"]

def parse_horoquartz_cell(cell_text):
    if not cell_text or not cell_text.strip():
        return []
    
    txt = cell_text.strip()
    
    # Détection des repos
    if re.search(r"\b(RH|REPOS)\b", txt.upper()) and not re.search(r"\d{1,2}[\.\:hH]\d{1,2}", txt):
        return [{"type": "Repos", "creneau": "00:00 - 00:00", "info": "Repos"}]
        
    # Normalisation de la chaîne horaire (ex: 19. 30 -> 19.30, 19.3 -> 19.30, 19h30 -> 19.30)
    clean = txt.replace(',', '.').replace('h', '.').replace('H', '.')
    clean = re.sub(r'(\d{1,2})\.\s+(\d{1,2})', r'\1.\2', clean)
    clean = re.sub(r'(\d{1,2}\.\d{1,2})\s*[-–—|àa]\s*(\d{1,2}\.\d{1,2})', r'\1-\2', clean)
    clean = re.sub(r'(\d{1,2}\.\d{1,2})\s*[-–—|àa]\s*(\d{1,2})(?!\d|\.)', r'\1-\2.00', clean)
    
    pattern = r"(\d{1,2})\.(\d{1,2})\s*[-–—|àa]\s*(\d{1,2})\.(\d{1,2})"
    matches = re.findall(pattern, clean)
    
    results = []
    for h1, m1, h2, m2 in matches:
        if len(m1) == 1: m1 = m1 + "0"
        if len(m2) == 1: m2 = m2 + "0"
        
        c = f"{h1.zfill(2)}:{m1.zfill(2)} - {h2.zfill(2)}:{m2.zfill(2)}"
        results.append({"type": "Work", "creneau": c, "info": txt})
        
    return results

def process_planning_image(file_b64):
    try:
        image_bytes = base64.b64decode(file_b64)
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        compressed_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

        payload = {
            'apikey': 'helloworld',
            'base64Image': 'data:image/jpeg;base64,' + compressed_b64,
            'language': 'fre',
            'isTable': 'true'
        }
        
        res = requests.post('https://api.ocr.space/parse/image', data=payload, timeout=25)
        if res.status_code != 200:
            raise Exception(f"Erreur API OCR Space (HTTP {res.status_code})")
            
        res_json = res.json()
        if res_json.get('IsErroredOnProcessing'):
            err_msg = res_json.get('ErrorMessage', ['Erreur inconnue'])[0]
            raise Exception(f"Erreur OCR Space: {err_msg}")
            
        parsed_results = res_json.get('ParsedResults', [])
        if not parsed_results:
            raise Exception("Aucun résultat renvoyé par l'OCR.")
            
        extracted_text = parsed_results[0].get('ParsedText', '')

        # 1. Extraction de la Semaine ISO
        semaine_match = re.search(r"\bS(\d{2})\b", extracted_text, re.IGNORECASE)
        semaine_iso = f"2026-S{semaine_match.group(1)}" if semaine_match else "2026-S40"

        # 2. Entête des jours
        matches_jours = re.findall(r"\b(Di|Lu|Ma|Me|Je|Ve|Sa)\s*(\d{1,2})\b", extracted_text, re.IGNORECASE)
        if len(matches_jours) >= 7:
            jours_detectes = [f"{j[0].capitalize()} {j[1]}" for j in matches_jours[:7]]
        else:
            jours_detectes = JOURS_DEFAUT

        lines = extracted_text.split("\n")
        
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
            if not line.strip():
                continue

            cells = line.split('\t')
            
            # Recherche du nom (tolère DE JESUS YSILDA, BEAL Eric, etc.)
            nom_trouve = None
            for cell in cells[:3]:
                cell_txt = cell.strip()
                matches = re.findall(r"([A-ZÀ-Ÿa-zà-ÿ]{2,}(?:[\s\-]+[A-ZÀ-Ÿa-zà-ÿ]{2,})+)", cell_txt)
                for candidate in matches:
                    cand_clean = candidate.strip()
                    cand_upper = cand_clean.upper()
                    words = cand_upper.split()
                    if not any(w in mots_exclus_noms for w in words) and not re.search(r"\d", cand_clean):
                        nom_trouve = cand_clean
                        break
                if nom_trouve:
                    break

            if nom_trouve:
                nom_courant = nom_trouve
                collaborateurs.add(nom_courant)

            if nom_courant == "Inconnu":
                continue

            # Alignement strict sur les 7 colonnes de la semaine
            day_cells = cells[-7:] if len(cells) >= 7 else cells

            for day_idx, cell in enumerate(day_cells):
                if day_idx >= len(jours_detectes):
                    break
                
                jour_libelle = jours_detectes[day_idx]
                parsed_items = parse_horoquartz_cell(cell)

                for item in parsed_items:
                    if item['type'] == 'Repos':
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

                    elif item['type'] == 'Work':
                        creneau = item['creneau']
                        infos_supp = item['info'].upper()

                        rayon_detecte = "Général"
                        activite = "Vente"
                        if "WELLNES" in infos_supp or "FITNESS" in infos_supp: rayon_detecte = "Fitness"
                        elif "CYCLE" in infos_supp or "MONT" in infos_supp: rayon_detecte = "Cycle / Montagne"
                        elif "WORKSHOP" in infos_supp or "ATELIER" in infos_supp: rayon_detecte = "Workshop"
                        elif "CAISSE" in infos_supp or "ACCUEIL" in infos_supp: rayon_detecte = "Ligne de Caisse"
                        elif "ECOLE" in infos_supp or "FORMATION" in infos_supp: 
                            activite = "Formation"
                            rayon_detecte = "École Magasin"

                        # Décompte du rush (15h-17h)
                        try:
                            start_h = int(creneau.split(":")[0])
                            end_h = int(creneau.split("-")[1].strip().split(":")[0])
                            if start_h <= 15 and end_h >= 17:
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
            requests.post(f"{SUPABASE_URL}/rest/v1/historique_plannings_pdf", json=payload_db, headers=headers, timeout=5)
        except Exception as e_db:
            print(f"Erreur Supabase: {e_db}")

        return {
            "equipe": "Équipe Magasin",
            "semaine_iso": semaine_iso,
            "equipiersCount": len(collaborateurs),
            "couverture": couverture_calculee,
            "sousEffectifs": sous_effectif_calc,
            "planning": planning_realise
        }

    except Exception as e:
        print(f"⚠️ Erreur process_planning_image: {str(e)}")
        raise Exception(f"Échec de l'analyse OCR : {str(e)}")
