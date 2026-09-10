import os
import requests
from collections import defaultdict

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://eilyxfhxmscuwbavkpzz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_eE-LmmezezF4l6L3O7hGBQ_hMOZL9i7")

class RetailMLPredictor:
    def __init__(self):
        self.headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        
    def _fetch_historique(self):
        try:
            res = requests.get(f"{SUPABASE_URL}/rest/v1/historique_plannings_pdf?select=planning_json,gain_id_estime", headers=self.headers, timeout=5)
            return res.json() if res.status_code == 200 else []
        except: return []

    def learn_patterns(self):
        historique = self._fetch_historique()
        if len(historique) < 5:
            return {
                "habitudes_repos": {"DIBOINE Simon": "Mardi", "CEAGLIO Valerie": "Jeudi"},
                "binomes_magiques": [{"collabs": ["LIOTTA Clara", "DIBOINE Simon"], "impact": "+2.8%"}],
                "confiance_modele": "Faible (Mode Entraînement)"
            }

        jours_repos = defaultdict(list)
        binomes_perf = defaultdict(list)

        for archive in historique:
            for shift in archive.get("planning_json", []):
                nom = shift.get("nom")
                jour = shift.get("jour", "").split(" ")[0].capitalize()
                if shift.get("activite") in ["Repos / RH", "Repos"]:
                    jours_repos[nom].append(jour)

            presents_jour = defaultdict(list)
            for shift in archive.get("planning_json", []):
                if shift.get("activite") not in ["Repos / RH", "Repos"]:
                    presents_jour[shift.get("jour", "").split(" ")[0].capitalize()].append(shift.get("nom"))

            for jour, presents in presents_jour.items():
                if len(presents) >= 2:
                    for i in range(len(presents)):
                        for j in range(i+1, len(presents)):
                            binomes_perf[tuple(sorted([presents[i], presents[j]]))].append(archive.get("gain_id_estime", 0))

        habitudes = {nom: max(set(jours), key=jours.count) for nom, jours in jours_repos.items() if jours}
        meilleur_binome = []
        if binomes_perf:
            best_pair = max(binomes_perf.items(), key=lambda x: sum(x[1])/len(x[1]))
            meilleur_binome.append({"collabs": list(best_pair[0]), "impact": f"+{round(sum(best_pair[1])/len(best_pair[1]), 1)}%"})

        return {"habitudes_repos": habitudes, "binomes_magiques": meilleur_binome, "confiance_modele": "Élevée (Data Historique)"}
