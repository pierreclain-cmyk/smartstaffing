from ml_engine import RetailMLPredictor

class MoteurPenibilite:
    def __init__(self):
        self.fatigue_db = {
            "CEAGLIO Valerie": {"fatigue": 85, "profil": "Sniper ID"},
            "DIBOINE Simon": {"fatigue": 20, "profil": "Sprinter VMA"},
            "LIOTTA Clara": {"fatigue": 45, "profil": "Expert Rush"},
            "HAMAZ Tharkoya": {"fatigue": 30, "profil": "Polyvalent"},
            "BITOUN Clara": {"fatigue": 15, "profil": "Polyvalent"}
        }

class PlanningGenerator:
    def __init__(self, budget_heures):
        self.budget = budget_heures
        self.moteur_fatigue = MoteurPenibilite()
        self.equipe = list(self.moteur_fatigue.fatigue_db.keys())
        self.ml_insights = RetailMLPredictor().learn_patterns()

    def generer_scenarios(self):
        binome = self.ml_insights["binomes_magiques"][0] if self.ml_insights["binomes_magiques"] else None
        desc_perf = f"Force le binôme magique {binome['collabs'][0].split(' ')[1]}/{binome['collabs'][1].split(' ')[1]}." if binome else "Optimisation caisse."

        return {
            "insights_ml": self.ml_insights,
            "scenarios": {
                "A": {"nom": "Option A : Budget Strict 📉", "heures_consommees": int(self.budget * 0.9), "gain_id": "+1.2 %", "score_penibilite": "⚠️ Élevé (78/100)", "description": "Respect strict de la masse salariale.", "planning": self._generer_repartition("budget")},
                "B": {"nom": "Option B : Performance Max 🚀", "heures_consommees": int(self.budget * 1.15), "gain_id": binome["impact"] if binome else "+4.0 %", "score_penibilite": "Moyen (55/100)", "description": desc_perf, "planning": self._generer_repartition("perf")},
                "C": {"nom": "Option C : Cerveau MLOps 🧠", "heures_consommees": self.budget, "gain_id": "+4.1 %", "score_penibilite": "✅ Optimal (30/100)", "description": "Respect des repos appris et lissage de la pénibilité.", "planning": self._generer_repartition("equilibre")}
            }
        }

    def _generer_repartition(self, strategie):
        planning = []
        for nom in self.equipe:
            profil = self.moteur_fatigue.fatigue_db[nom]
            activite, creneau = "Caisse", "10:00 - 17:00"
            
            if strategie == "equilibre":
                if self.ml_insights["habitudes_repos"].get(nom) == "Samedi":
                    activite, creneau = "Repos (Appris)", "00:00 - 00:00"
                elif profil["fatigue"] > 70:
                    activite, creneau = "Vente (Allégé)", "09:00 - 14:00"
            elif strategie == "perf" and profil["profil"] in ["Expert Rush", "Sniper ID", "Sprinter VMA"]:
                creneau = "13:00 - 19:30"
                
            planning.append({"nom": nom, "profil": profil["profil"], "activite": activite, "creneau": creneau, "fatigue_init": profil["fatigue"]})
        return planning
