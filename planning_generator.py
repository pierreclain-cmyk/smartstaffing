import random
from datetime import datetime

class MoteurPenibilite:
    def __init__(self):
        # Simulation d'une base de données SQL des compteurs de fatigue (0 = Reposé, 100 = Burnout)
        self.fatigue_db = {
            "CEAGLIO Valerie": {"fatigue": 85, "profil": "Sniper ID", "rayon_pref": "Caisse"}, # Très fatiguée
            "DIBOINE Simon": {"fatigue": 20, "profil": "Sprinter VMA", "rayon_pref": "Caisse"}, # En forme
            "LIOTTA Clara": {"fatigue": 45, "profil": "Expert Rush", "rayon_pref": "Caisse"},
            "Imane": {"fatigue": 30, "profil": "Polyvalent", "rayon_pref": "Nature/Glisse"},
            "Pierre": {"fatigue": 60, "profil": "Capitaine", "rayon_pref": "Rando/Cycle"}
        }

    def get_score(self, nom):
        return self.fatigue_db.get(nom, {"fatigue": 0})["fatigue"]

class PlanningGenerator:
    def __init__(self, budget_heures, contraintes):
        self.budget = budget_heures
        self.moteur_fatigue = MoteurPenibilite()
        self.equipe = list(self.moteur_fatigue.fatigue_db.keys())

    def generer_scenarios(self):
        # SCÉNARIO A : BUDGET STRICT (Minimiser les heures)
        scenario_a = {
            "nom": "Option A : Budget Strict 📉",
            "heures_consommees": int(self.budget * 0.9), # Économise 10% du budget
            "gain_id": "+1.2 %",
            "score_penibilite": "⚠️ Élevé (78/100)",
            "description": "Respect strict de la masse salariale. Forte tension prévue en caisse à 16h.",
            "planning": self._generer_repartition("budget")
        }

        # SCÉNARIO B : PERF MAX (Cibler le CA et l'ID)
        scenario_b = {
            "nom": "Option B : Performance Max 🚀",
            "heures_consommees": int(self.budget * 1.15), # Dépassement budgétaire de 15%
            "gain_id": "+6.8 %",
            "score_penibilite": "Moyen (55/100)",
            "description": "Blindage de la ligne de caisse et du rayon Nature/Glisse. ROI estimé : +12% CA.",
            "planning": self._generer_repartition("perf")
        }

        # SCÉNARIO C : CONFORT ÉQUIPE (Équilibre & Pénibilité)
        scenario_c = {
            "nom": "Option C : Confort & Équilibre ⚖️",
            "heures_consommees": self.budget,
            "gain_id": "+4.1 %",
            "score_penibilite": "✅ Optimal (30/100)",
            "description": "Valérie (fatigue 85%) est basculée en rayon calme. Simon absorbe le rush. Protection de l'équipe.",
            "planning": self._generer_repartition("equilibre")
        }

        return {"A": scenario_a, "B": scenario_b, "C": scenario_c}

    def _generer_repartition(self, strategie):
        planning = []
        for nom in self.equipe:
            profil = self.moteur_fatigue.fatigue_db[nom]
            activite = "Caisse"
            creneau = "10:00 - 17:00"
            
            # Application du Moteur de Pénibilité sur le Scénario C
            if strategie == "equilibre" and profil["fatigue"] > 70:
                activite = "Vente (Allégé)"
                creneau = "09:00 - 14:00" # Shift plus court et moins stressant pour Valérie
                
            elif strategie == "perf" and profil["profil"] in ["Expert Rush", "Sniper ID"]:
                creneau = "13:00 - 19:30" # Décalage sur le gros rush
                
            planning.append({
                "nom": nom,
                "profil": profil["profil"],
                "activite": activite,
                "creneau": creneau,
                "fatigue_init": profil["fatigue"]
            })
        return planning
