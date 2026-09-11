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
    """Extrait tous les créneaux horaires d'un texte (ex: 09.00-13.00)."""
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

        mots_exclus_noms = [
            "DECATHLON", "PLANNING", "TOTAL", "WELLNES", "FITNESS", "CYCLE", 
            "MONTAGNE", "WORKSHOP", "ATELIER", "CAISSE", "ACCUEIL", "RH", 
            "REPOS", "SERVICES", "GENERAL", "MANAGER", "EQUIPE", "HEURE", 
            "CIBLE", "EMPLOYES", "REC", "PÉRIODE", "FUTUR", "SEPTEMBRE", "OCTOBRE", "AOUT"
        ]

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text_page = page.extract_text() or ""
                words = page.extract_words()

                # 1. Semaine ISO
                semaine_match = re.search(r"\bS(\d{2})\b", text_page, re.IGNORECASE)
                if semaine_match:
                    semaine_iso = f"2026-S{semaine_match.group(1)}"

                # 2. Construction de la grille dynamique (Ancrage sur les vrais jours du PDF)
                header_words = []
                for w in words:
                    if re.match(r"^(Di|Lu|Ma|Me|Je|Ve|Sa)$", w['text'], re.IGNORECASE):
                        header_words.append(w)
                
                header_words = sorted(header_words, key=lambda x: x['x0'])
                
                day_bounds = []
                if len(header_words) >= 7:
                    # Le PDF contient bien l'entête des jours
                    for i in range(7):
                        x_min = header_words[i]['x0'] - 20  # Marge gauche
                        x_max = header_words[i+1]['x0'] - 20 if i < 6 else float(page.width)
                        # Retrouver le numéro du jour (ex: Di 27)
                        nom_jour = header_words[i]['text'].capitalize()
                        numero_jour = ""
                        # Cherche le mot qui suit immédiatement à droite pour trouver le numéro
                        for w2 in words:
                            if w2['top'] == header_words[i]['top'] and w2['x0'] > header_words[i]['x1'] and w2['x0'] < x_max:
                                if w2['text'].isdigit():
                                    numero_jour = w2['text']
                                    break
                        label = f"{nom_jour} {numero_jour}".strip()
                        day_bounds.append({"label": label, "x_min": x_min, "x_max": x_max})
                else:
                    # Sécurité si les jours ne sont pas détectés : découpe mathématique
                    grid_left = float(page.width) * 0.22
                    col_w = (float(page.width) - grid_left) / 7.0
                    for i in range(7):
                        day_bounds.append({
                            "label": JOURS_DEFAUT[i],
                            "x_min": grid_left + (i * col_w),
                            "x_max": grid_left + ((i + 1) * col_w)
                        })

                # 3. Regroupement par Ligne Y (Tolérance de 5px)
                lines_by_y = []
                sorted_words = sorted(words, key=lambda w: (round(w['top'] / 5.0), w['x0']))
                
                current_line = []
                current_top = None
                for w in sorted_words:
                    if current_top is None or abs(w['top'] - current_top) < 5:
                        current_line.append(w)
                        current_top = w['top']
                    else:
                        lines_by_y.append(current_line)
                        current_line = [w]
                        current_top = w['top']
                if current_line:
                    lines_by_y.append(current_line)

                # 4. Lecture Nominative et Horaires
                grid_left_start = day_bounds[0]['x_min']
                current_nom = "Inconnu"

                for line in lines_by_y:
                    left_str = " ".join([w['text'] for w in line if w['x0'] < grid_left_start])
                    
                    nom_match = re.search(r"([A-ZÀ-Ÿa-zà-ÿ]{2,}(?:[\s\-]+[A-ZÀ-Ÿa-zà-ÿ]{2,})+)", left_str)
                    if nom_match:
                        candidate = nom_match.group(1).strip()
                        if not any(k in candidate.upper() for k in mots_exclus_noms) and not re.search(r"\d", candidate):
                            current_nom = candidate
                            collaborateurs.add(current_nom)

                    if current_nom == "Inconnu":
                        continue

                    # Mapping des mots dans les bonnes colonnes
                    for w in line:
                        if w['x0'] < grid_left_start:
                            continue
                            
                        w_txt = w['text'].strip()
                        x_pos = w['x0']

                        matched_day = None
                        for db in day_bounds:
                            if db['x_min'] <= x_pos < db['x_max']:
                                matched_day = db['label']
                                break

                        if not matched_day:
                            continue

                        # Repos
                        if re.search(r"\b(RH|REPOS)\b", w_txt.upper()):
                            unique_key = f"{current_nom}_{matched_day}_REPOS"
                            if unique_key not in seen_entries:
                                seen_entries.add(unique_key)
                                planning_realise.append({
                                    "nom": current_nom, "jour": matched_day, "creneau": "00:00 - 00:00",
                                    "activite": "Repos", "rayon_cible": "Ligne de Caisse",
                                    "profil": "Hôte / Hôtesse Caisse", "status": "Repos"
                                })

                        # Travail
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
                                    "nom": current_nom, "jour": matched_day, "creneau": creneau,
                                    "activite": "Tenue de Caisse", "rayon_cible": "Ligne de Caisse",
                                    "profil": "Hôte / Hôtesse Caisse", "status": "Planifié Caisse"
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
        
        try:
            headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
            requests.post(f"{SUPABASE_URL}/rest/v1/historique_plannings_pdf", json=payload_db, headers=headers, timeout=5)
        except: pass

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
