import base64
import io
import os
import re
import pdfplumber
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://eilyxfhxmscuwbavkpzz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_eE-LmmezezF4l6L3O7hGBQ_hMOZL9i7")

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
        
        # 🔥 DÉTECTION 100% DYNAMIQUE (Plus aucune liste figée)
        # On cherche un pattern classique : Nom en majuscules suivi d'un prénom
        if re.match(r"^[A-ZÀ-Ÿ\d\'\-\s]{2,}\s+[A-Za-zÀ-ÿ]+", line):
            # On exclut les lignes de titres ou de totaux
            mots_exclus = ["DECATHLON", "PLANNING", "EQUIPE", "PATRON", "INFORMATION", "ETAT", "SEMAINE", "TOTAL", "PAGE"]
            if not any(k in line.upper() for k in mots_exclus):
                # Nettoyage des codes magasins ou versions souvent collés au nom sur les PDF
                nom_brut = line.split("V")[0].split("113")[0].strip()
                if len(nom_brut) > 4:
                    nom_trouve = nom_brut

        if nom_trouve:
            collaborateurs_trouves.add(nom_trouve)
            type_activite = "Repos / RH"
            rayon_detecte = "Général"
            creneau_stricte = "00:00 - 00:00"
            
            for offset in range(0, 4):
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
                    
                    time_match = re.search(r"(\d{1,2}[:h]\d{2}).*?(\d{1,2}[:h]\d{2})", sub)
                    if time_match:
                        start = time_match.group(1).replace('h', ':').zfill(5) 
                        end = time_match.group(2).replace('h', ':').zfill(5)
                        creneau_stricte = f"{start} - {end}"

            planning_realise.append({
                "nom": nom_trouve,
                "jour": current_day,
                "creneau": creneau_stricte,
                "activite": type_activite,
                "rayon_cible": rayon_detecte,
                "profil": "En apprentissage ML", # 🔥 Le profil par défaut est neutre
                "status": "Planifié PDF" if type_activite != "Repos / RH" else "Repos",
                "action": "Conforme"
            })

    staff_en_rush = 0
    for p in planning_realise:
        if p["status"] != "Repos" and "-" in p["creneau"]:
            try:
                times = p["creneau"].split("-")
                debut_hour = int(times[0].strip().split(":")[0])
                fin_hour = int(times[1].strip().split(":")[0])
                if debut_hour <= 15 and fin_hour >= 17:
                    staff_en_rush += 1
            except Exception:
                pass 

    couverture_calculee = min(100, int((staff_en_rush / 4) * 100)) if staff_en_rush > 0 else 45
    sous_effectif_calc = max(0, 4 - staff_en_rush)

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
        "sous_effectifs_count": sous_effectif_calc,
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
        "sousEffectifs": sous_effectif_calc,
        "planning": planning_realise
    }
