import os
import requests
import pandas as pd
from collections import defaultdict

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://eilyxfhxmscuwbavkpzz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_eE-LmmezezF4l6L3O7hGBQ_hMOZL9i7")

class RetailMLPredictor:
    def __init__(self):
        self.headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        
    def _fetch_historique(self):
        endpoint = f"{SUPABASE_URL}/rest/v1/historique_plannings_pdf?select=planning_json,gain_id_estime"
        try:
            res = requests.get(endpoint, headers=self.headers, timeout=5)
            if res.status_code == 200:
                return res.json()
            return []
        except:
            return []

    def learn_patterns(self):
        historique = self._fetch_historique()
        
        # Fallback de simulation si la base est encore trop vide pour le Machine Learning
        if len(historique) < 5:
            return {
                "habitudes_repos": {"DIBOINE Simon": "Mardi", "CEAGLIO Valerie": "Jeudi"},
                "binomes_magiques": [{"collabs": ["LIOTTA Clara", "DIBOINE Simon"], "impact": "+2.8%"}],
                "confiance_modele": "Faible (Mode Entraînement)"
            }

        jours_repos = defaultdict(list)
        binomes_perf = defaultdict(list)

        for archive in historique:
            planning = archive.get("planning_json", [])
            gain = archive.get("gain_id_estime", 0)
            presents_jour = defaultdict(list)

            for shift in planning:
                nom = shift.get("nom")
                jour = shift.get("jour", "").split(" ")[0].capitalize()
                activite = shift.get("activite")

                if activite in ["Repos / RH", "Repos"]:
                    jours_repos[nom].append(jour)
                else:
                    presents_jour[jour].append(nom)

            # Algorithme d'association : Calcul de l'impact des paires (Binômes)
            for jour, presents in presents_jour.items():
                if len(presents) >= 2:
                    for i in range(len(presents)):
                        for j in range(i+1, len(presents)):
                            paire = tuple(sorted([presents[i], presents[j]]))
                            binomes_perf[paire].append(gain)

        # 1. Extraction des habitudes de repos (Le jour le plus fréquent)
        habitudes = {}
        for nom, jours in jours_repos.items():
            if jours:
                jour_prefere = max(set(jours), key=jours.count)
                habitudes[nom] = jour_prefere

        # 2. Extraction du meilleur binôme (Moyenne de gain ID la plus haute)
        meilleur_binome = []
        if binomes_perf:
            best_pair = max(binomes_perf.items(), key=lambda x: sum(x[1])/len(x[1]))
            avg_gain = sum(best_pair[1]) / len(best_pair[1])
            meilleur_binome.append({
                "collabs": list(best_pair[0]),
                "impact": f"+{round(avg_gain, 1)}%"
            })

        return {
            "habitudes_repos": habitudes,
            "binomes_magiques": meilleur_binome,
            "confiance_modele": "Élevée (Basé sur Data Historique)"
        }
