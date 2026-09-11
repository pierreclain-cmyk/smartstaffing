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
    img_w, img_h = img.size
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    compressed_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    # Requête avec Overlay pour obtenir les coordonnées spatiales (X, Y)
    payload = {
        'apikey': 'helloworld',
        'base64Image': 'data:image/jpeg;base64,' + compressed_b64,
        'language': 'fre',
        'isOverlayRequired': 'true',
        'isTable': 'true'
    }
    
    res = requests.post('https://api.ocr.space/parse/image', data=payload, timeout=25)
    if res.status_code != 200 or res.json().get('IsErroredOnProcessing'):
        raise Exception("L'API de lecture d'image est indisponible.")
        
    parsed_result = res.json()['ParsedResults'][0]
    extracted_text = parsed_result.get('ParsedText', '')
    
    # 1. Extraction Semaine ISO
    semaine_match = re.search(r"\bS(\d{2})\b", extracted_text, re.IGNORECASE)
    semaine_iso = f"2026-S{semaine_match.group(1)}" if semaine_match else "2026-S40"

    # 2. Reconstruction de la structure visuelle (Lignes + Mots avec X, Y)
    lines_data = []
    overlay = parsed_result.get('Overlay', {})
    if overlay and 'Lines' in overlay:
        for line in overlay['Lines']:
            line_text = " ".join([w.get('WordText', '') for w in line.get('Words', [])])
            words = line.get('Words', [])
            if words:
                min_left = min([w.get('Left', 0) for w in words])
                min_top = min([w.get('Top', 0) for w in words])
                lines_data.append({
                    'text': line_text,
                    'left': min_left,
                    'top': min_top,
                    'words': words
                })

    # 3. Détection des jours (Di 27 à Sa 03)
    matches_jours = re.findall(r"\b(Di|Lu|Ma|Me|Je|Ve|Sa)\s*(\d{1,2})\b", extracted_text, re.IGNORECASE)
    jours_detectes = [f"{j[0].capitalize()} {j[1]}" for j in matches_jours[:7]] if len(matches_jours) >= 7 else JOURS_DEFAUT

    # Calcul des 7 bandes verticales (Colonnes X)
    header_x_positions = []
    for ld in lines_data:
        for w in ld['words']:
            w_txt = w.get('WordText', '')
            if re.match(r"^(Di|Lu|Ma|Me|Je|Ve|Sa)$", w_txt, re.IGNORECASE):
                header_x_positions.append({'text': w_txt, 'left': w.get('Left', 0)})

    header_x_positions = sorted(header_x_positions, key=lambda x: x['left'])
    
    grid_left = img_w * 0.20
    grid_right = img_w * 0.98
    col_width = (grid_right - grid_left) / 7.0

    col_bounds = []
    if len(header_x_positions) >= 7:
        for i in range(7):
            c_left = header_x_positions[i]['left'] - 15
            c_right = header_x_positions[i+1]['left'] - 15 if i < 6 else img_w
            col_bounds.append((c_left, c_right))
    else:
        for i in range(7):
            col_bounds.append((grid_left + i * col_width, grid_left + (i + 1) * col_width))

    # 4. Détection des Collaborateurs (Bandes Y)
    mots_exclus = [
        "DECATHLON", "PLANNING", "TOTAL", "WELLNES", "FITNESS", "CYCLE", 
        "MONTAGNE", "WORKSHOP", "ATELIER", "CAISSE", "ACCUEIL", "RH", 
        "REPOS", "SERVICES", "GENERAL", "MANAGER", "EQUIPE", "HEURE", 
        "CIBLE", "EMPLOYES", "REC", "PÉRIODE", "FUTUR", "SEPTEMBRE", "OCTOBRE", "AOUT"
    ]

    employees = []
    for ld in lines_data:
        if ld['left'] < grid_left + 50:
            nom_match = re.search(r"([A-ZÀ-Ÿ]{2,}[\s\-]+[A-ZÀ-Ÿa-zà-ÿ]{2,}(?:[\s\-]+[A-ZÀ-Ÿa-zà-ÿ]{2,})?)", ld['text'])
            if nom_match:
                candidate = nom_match.group(1).strip()
                if not any(k in candidate.upper() for k in mots_exclus) and not re.search(r"\d", candidate):
                    if not any(e['nom'] == candidate for e in employees):
                        employees.append({'nom': candidate, 'top': ld['top']})

    employees = sorted(employees, key=lambda x: x['top'])

    emp_y_bounds = []
    for i, emp in enumerate(employees):
        y_top = emp['top'] - 12
        y_bottom = employees[i+1]['top'] - 12 if i < len(employees) - 1 else img_h
        emp_y_bounds.append((emp['nom'], y_top, y_bottom))

    # 5. Mapping Géométrique des Heures -> (Collaborateur, Jour)
    planning_realise = []
    collaborateurs = set()
    seen_entries = set()
    staff_en_rush = 0

    time_regex = r"(\d{1,2})[\.\:hH](\d{2})\s*[-|à|a]\s*(\d{1,2})[\.\:hH](\d{2})"

    for ld in lines_data:
        txt = ld['text']
        x_pos = ld['left']
        y_pos = ld['top']

        target_emp = "Inconnu"
        for nom, y_min, y_max in emp_y_bounds:
            if y_min <= y_pos < y_max:
                target_emp = nom
                break

        if target_emp == "Inconnu":
            continue

        target_day_idx = -1
        for idx, (x_min, x_max) in enumerate(col_bounds):
            if x_min <= x_pos < x_max:
                target_day_idx = idx
                break

        if target_day_idx == -1 or target_day_idx >= len(jours_detectes):
            continue

        jour_libelle = jours_detectes[target_day_idx]
        time_matches = re.findall(time_regex, txt)
        is_repos = bool(re.search(r"\b(RH|REPOS)\b", txt.upper())) and not time_matches

        if is_repos:
            unique_key = f"{target_emp}_{jour_libelle}_REPOS"
            if unique_key not in seen_entries:
                seen_entries.add(unique_key)
                planning_realise.append({
                    "nom": target_emp, "jour": jour_libelle, "creneau": "00:00 - 00:00",
                    "activite": "Repos", "rayon_cible": "Aucun", "profil": "En apprentissage ML", "status": "Repos"
                })

        elif time_matches:
            for tm in time_matches:
                h_start, m_start, h_end, m_end = tm
                creneau = f"{h_start.zfill(2)}:{m_start} - {h_end.zfill(2)}:{m_end}"
                infos_supp = txt.upper()

                rayon_detecte = "Général"
                activite = "Vente"
                if "WELLNES" in infos_supp or "FITNESS" in infos_supp: rayon_detecte = "Fitness"
                elif "CYCLE" in infos_supp or "MONT" in infos_supp: rayon_detecte = "Cycle / Montagne"
                elif "WORKSHOP" in infos_supp or "ATELIER" in infos_supp: rayon_detecte = "Workshop"
                elif "CAISSE" in infos_supp or "ACCUEIL" in infos_supp: rayon_detecte = "Ligne de Caisse"
                elif "ECOLE" in infos_supp or "FORMATION" in infos_supp: 
                    activite = "Formation"
                    rayon_detecte = "École Magasin"

                try:
                    if int(h_start) <= 15 and int(h_end) >= 17:
                        staff_en_rush += 1
                except: pass

                unique_key = f"{target_emp}_{jour_libelle}_{creneau}"
                if unique_key not in seen_entries:
                    seen_entries.add(unique_key)
                    collaborateurs.add(target_emp)
                    planning_realise.append({
                        "nom": target_emp, "jour": jour_libelle, "creneau": creneau,
                        "activite": activite, "rayon_cible": rayon_detecte, "profil": "En apprentissage ML", "status": "Planifié OCR"
                    })

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
    
    try: requests.post(f"{SUPABASE_URL}/rest/v1/historique_plannings_pdf", json=payload_db, headers=headers, timeout=5)
    except: pass

    return {
        "equipe": "Équipe Magasin",
        "semaine_iso": semaine_iso,
        "equipiersCount": len(collaborateurs),
        "couverture": couverture_calculee,
        "sousEffectifs": sous_effectif_calc,
        "planning": planning_realise
    }
