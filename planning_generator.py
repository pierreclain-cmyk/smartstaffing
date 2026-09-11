from ml_engine import RetailMLPredictor

class MoteurPenibilite:
    def __init__(self):
        self.fatigue_db = {
            "CEAGLIO Valerie": {"fatigue": 85, "profil": "Sniper ID"},
            "DIBOINE Simon": {"fatigue": 20, "profil": "Sprinter VMA"},
            "LIOTTA Clara": {"fatigue": 45, "profil": "Expert Rush"}
        }

class PlanningGenerator:
    def __init__(self, budget_heures, jour_cible="Samedi", semaine_cible="S+3"):
        self.budget = budget_heures
        self.jour_cible = jour_cible
        self.semaine_cible = semaine_cible
        self.moteur_fatigue = MoteurPenibilite()
        self.equipe = list(self.moteur_fatigue.fatigue_db.keys())
        self.ml_insights = RetailMLPredictor().learn_patterns()

    def generer_scenarios(self):
        binome = self.ml_insights["binomes_magiques"][0] if self.ml_insights["binomes_magiques"] else None
        return {
            "insights_ml": self.ml_insights,
            "scenarios": {
                "A": {"nom": f"Option A", "heures_consommees": int(self.budget * 0.9), "gain_id": "+1.2 %", "score_penibilite": "⚠️ Élevé", "description": "Budget strict", "planning": self._generer_repartition("budget")},
                "C": {"nom": f"Option MLOps", "heures_consommees": self.budget, "gain_id": "+4.1 %", "score_penibilite": "✅ Optimal", "description": "Respect des rayons", "planning": self._generer_repartition("equilibre")}
            }
        }

    def _generer_repartition(self, strategie):
        planning = []
        for nom in self.equipe:
            profil = self.moteur_fatigue.fatigue_db.get(nom, {"fatigue": 30, "profil": "Polyvalent"})
            activite, creneau = "Affecté", "10:00 - 17:00"
            rayon_predit = self.ml_insights.get("rayons_habituels", {}).get(nom, "Ligne de Caisse")

            if strategie == "equilibre":
                if self.ml_insights.get("habitudes_repos", {}).get(nom) == self.jour_cible:
                    activite, creneau = "Repos", "00:00 - 00:00"
                elif profil["fatigue"] > 70:
                    activite, creneau = "Tâche Allégée", "09:00 - 14:00"
                    
            planning.append({
                "nom": nom, "jour": self.jour_cible, "profil": profil["profil"], 
                "activite": activite, "creneau": creneau, "fatigue_init": profil["fatigue"], "rayon": rayon_predit
            })
        return planning
