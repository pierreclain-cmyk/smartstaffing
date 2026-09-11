import io
import base64
import re
import os
import requests
import pdfplumber

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://eilyxfhxmscuwbavkpzz.supabase.co").rstrip('/')
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_eE-LmmezezF4l6L3O7hGBQ_hMOZL9i7")

JOURS_DEFAUT = ["Di 27", "Lu 28", "Ma 29", "Me 30", "Je 01", "Ve 02", "Sa 03"]

def parse_time_string(txt):
    """Extrait tous les créneaux horaires d'un texte (ex: 09.00-13.00, 14.00-19.30)."""
    clean = txt.replace(',', '.').replace('h', '.').replace('H', '.')
    clean = re.sub(r'(\d{1,2})\.\s+(\d{1,2})', r'\1.\2', clean)
    clean = re.sub(r'(\d{1,2}\.\d{1,2})\s*[-–—|àa]\s*(\d{1,2}\.\d{1,2})', r'\1-\2', clean)
    clean = re.sub(r'(\d{1,2}\.\d{1,2})\s*[-–—|àa]\s*(\d{1,2})(?!\d|\.)', r'\1-\2.00', clean)
    
    pattern = r"(\d{1,2})\.(\d{1,2})\s*[-–—|àa]\s*(\d{1,2})\.(\d{1,2})"
    matches = re.findall(pattern, clean)
    
    results = []
    for h1, m1, h2, m2 in matches:
        if len(m1) == 1: m1 += "0"
        if len(m2) == 1: m2 += "0"
        results.append(f"{h1.zfill(2)}:{m1.zfill(2)} - {h2.zfill(2)}:{m2.zfill(2)}")
    return results

def process_planning_pdf(file_b64):
    try:
        raw_b64 = file_b64.split(',')[1] if ',' in file_b64 else file_b64
        pdf_bytes = base64.b64decode(raw_b64)
        
        planning_realise = []
        collaborateurs = set()
        seen_entries = set()
        staff_en_rush = 0
        semaine_iso = "2026-S40"
        jours_detectes = JOURS_DEFAUT

        mots_exclus_noms = [
            "DECATHLON", "PLANNING", "TOTAL", "WELLNES", "FITNESS", "CYCLE", 
            "MONTAGNE", "WORKSHOP", "ATELIER", "CAISSE", "ACCUEIL", "RH", 
            "REPOS", "SERVICES", "GENERAL", "MANAGER", "EQUIPE", "HEURE", 
            "CIBLE", "EMPLOYES", "REC", "PÉRIODE", "FUTUR", "SEPTEMBRE", "OCTOBRE", "AOUT"
        ]

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text_page = page.extract_text() or ""

                # 1. Semaine ISO
                semaine_match = re.search(r"\bS(\d{2})\b", text_page, re.IGNORECASE)
                if semaine_match:
                    semaine_iso = f"2026-S{semaine_match.group(1)}"

                # 2. Reconstitution des 7 jours d'entête
                matches_jours = re.findall(r"\b(Di|Lu|Ma|Me|Je|Ve|Sa)\s*(\d{1,2})\b", text_page, re.IGNORECASE)
                if len(matches_jours) >= 7:
                    jours_detectes = [f"{j[0].capitalize()} {j[1]}" for j in matches_jours[:7]]

                # 3. Extraction par coordonnées X, Y (Word-Level Spatial Matching)
                words = page.extract_words()
                page_width = float(page.width)

                # Définition des 7 zones verticales (Colonnes de jours X)
                grid_left = page_width * 0.22
                grid_right = page_width * 0.98
                col_w = (grid_right - grid_left) / 7.0
                
                day_bounds = []
                for idx in range(7):
                    day_label = jours_detectes[idx] if idx < len(jours_detectes) else JOURS_DEFAUT[idx]
                    day_bounds.append({
                        "label": day_label,
                        "x_min": grid_left + (idx * col_w),
                        "x_max": grid_left + ((idx + 1) * col_w)
                    })

                # Regroupement des mots en lignes Y (tolérance ~4px)
                lines_by_y = []
                sorted_words = sorted(words, key=lambda w: (round(w['top'] / 4.0), w['x0']))
                
                current_line = []
                current_top = None
                for w in sorted_words:
                    if current_top is None or abs(w['top'] - current_top) < 4:
                        current_line.append(w)
                        current_top = w['top']
                    else:
                        lines_by_y.append(current_line)
                        current_line = [w]
                        current_top = w['top']
                if current_line:
                    lines_by_y.append(current_line)

                # Parcours de chaque ligne pour mapper Collaborateurs <-> Créneaux
                current_nom = "Inconnu"

                for line in lines_by_y:
                    line_text = " ".join([w['text'] for w in line])
                    
                    # Recherche d'un nom sur la partie gauche de la page (X < grid_left)
                    left_words = [w['text'] for w in line if w['x0'] < grid_left]
                    left_str = " ".join(left_words)
                    
                    nom_match = re.search(r"([A-ZÀ-Ÿa-zà-ÿ]{2,}(?:[\s\-]+[A-ZÀ-Ÿa-zà-ÿ]{2,})+)", left_str)
                    if nom_match:
                        candidate = nom_match.group(1).strip()
                        cand_upper = candidate.upper()
                        if not any(k in cand_upper for k in mots_exclus_noms) and not re.search(r"\d", candidate):
                            current_nom = candidate
                            collaborateurs.add(current_nom)

                    if current_nom == "Inconnu":
                        continue

                    # Inspection des mots situés dans la zone planning (X >= grid_left)
                    right_words = [w for w in line if w['x0'] >= grid_left - 10]
                    
                    for w in right_words:
                        w_txt = w['text'].strip()
                        x_pos = w['x0']

                        # Trouver la colonne de jour correspondante
                        matched_day = None
                        for db in day_bounds:
                            if db['x_min'] <= x_pos < db['x_max']:
                                matched_day = db['label']
                                break

                        if not matched_day:
                            continue

                        # Cas 1 : Journée de repos
                        if re.search(r"\b(RH|REPOS)\b", w_txt.upper()):
                            unique_key = f"{current_nom}_{matched_day}_REPOS"
                            if unique_key not in seen_entries:
                                seen_entries.add(unique_key)
                                planning_realise.append({
                                    "nom": current_nom,
                                    "jour": matched_day,
                                    "creneau": "00:00 - 00:00",
                                    "activite": "Repos",
                                    "rayon_cible": "Ligne de Caisse",
                                    "profil": "Hôte / Hôtesse Caisse",
                                    "status": "Repos"
                                })

                        # Cas 2 : Créneau horaire
                        creneaux_detectes = parse_time_string(w_txt)
                        for creneau in creneaux_detectes:
                            try:
                                start_h = int(creneau.split(":")[0])
                                end_h = int(creneau.split("-")[1].strip().split(":")[0])
                                if start_h <= 15 and end_h >= 17:
                                    staff_en_rush += 1
                            except: pass

                            unique_key = f"{current_nom}_{matched_day}_{creneau}"
                            if unique_key not in seen_entries:
                                seen_entries.add(unique_key)
                                planning_realise.append({
                                    "nom": current_nom,
                                    "jour": matched_day,
                                    "creneau": creneau,
                                    "activite": "Tenue de Caisse",
                                    "rayon_cible": "Ligne de Caisse",
                                    "profil": "Hôte / Hôtesse Caisse",
                                    "status": "Planifié Caisse"
                                })

        couverture_calculee = min(100, int((staff_en_rush / 4) * 100)) if staff_en_rush > 0 else 45
        sous_effectif_calc = max(0, 4 - staff_en_rush)

        payload_db = {
            "nom_fichier": "planning_horoquartz.pdf",
            "semaine_iso": semaine_iso,
            "nom_equipe": "Équipe Caisse",
            "equipiers_count": len(collaborateurs),
            "couverture_rush": couverture_calculee,
            "sous_effectifs_count": sous_effectif_calc,
            "gain_id_estime": 6.1,
            "planning_json": planning_realise,
            "status_execution": "ARCHIVE"
        }
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
        
        try:
            res_db = requests.post(f"{SUPABASE_URL}/rest/v1/historique_plannings_pdf", json=payload_db, headers=headers, timeout=5)
            if res_db.status_code not in (200, 201):
                print(f"⚠️ ERREUR SUPABASE ({res_db.status_code}): {res_db.text}")
        except Exception as e_db:
            print(f"Erreur réseau Supabase: {e_db}")

        return {
            "equipe": "Équipe Caisse",
            "semaine_iso": semaine_iso,
            "equipiersCount": len(collaborateurs),
            "couverture": couverture_calculee,
            "sousEffectifs": sous_effectif_calc,
            "planning": planning_realise
        }

    except Exception as e:
        print(f"⚠️ Erreur process_planning_pdf: {str(e)}")
        raise Exception(f"Échec de l'analyse PDF : {str(e)}")
