import os
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://eilyxfhxmscuwbavkpzz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_eE-LmmezezF4l6L3O7hGBQ_hMOZL9i7")

class StaffingAutonomousAgent:
    def __init__(self, planning_data, meteo_sky="Ensoleillé", trafic_var=0):
        self.planning = planning_data.get("planning", [])
        self.semaine = planning_data.get("semaine_iso", "S36")
        self.meteo = meteo_sky
        self.trafic_var = trafic_var
        self.headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }

    def analyser_et_decider(self):
        """
        Analyse en autonomie la cohérence du planning et génère des actions correctives.
        """
        diagnostic = []
        actions_correctives = []
        gain_id_total = 0.0

        # 1. Analyse de la couverture des caisses
        caisse_count = sum(1 for p in self.planning if "Caisse" in p.get("activite", ""))
        
        # 2. Règle métier autonome : Ajustement Météo & Trafic
        facteur_stress = 1.0
        if self.meteo in ["Pluvieux", "Orageux", "Averses"]:
            facteur_stress += 0.20 # +20% d'affluence en caisse si mauvais temps
        facteur_stress += (self.trafic_var / 100.0)

        # 3. Détection des goulots d'étranglement
        if caisse_count < 3 and facteur_stress > 1.1:
            actions_correctives.append({
                "type": "ALERTE_RUSH",
                "priorite": "HAUTE",
                "message": f"🚨 Risque de saturation VMA détecté pour la semaine {self.semaine}. Effectif caisse sous-dimensionné face à la météo/trafic.",
                "action": "Activer le renfort automatique d'Imane et Tharkoya sur les créneaux 14h-18h."
            })
            gain_id_total += 4.5

        # 4. Détection des profils sous-exploités (Ex: Expert Rush positionné sur Repos)
        for p in self.planning:
            if p.get("profil") == "Expert Rush" and p.get("activite") == "Repos / RH":
                actions_correctives.append({
                    "type": "OPTIMISATION_PROFIL",
                    "priorite": "MOYENNE",
                    "message": f"💡 {p.get('nom')} (Expert Rush) est en repos pendant un pic VMA anticipé.",
                    "action": f"Proposer une permutation de shift avec un profil Polyvalent pour maximiser le taux d'ID."
                })
                gain_id_total += 2.3

        rapport_agent = {
            "semaine_iso": self.semaine,
            "score_coherence": max(40, int(100 - (len(actions_correctives) * 15))),
            "facteur_stress_calcule": round(facteur_stress, 2),
            "gain_id_potentiel": round(gain_id_total, 2),
            "actions_suggerees": actions_correctives
        }

        # Sauvegarde autonome dans Supabase
        self._archiver_decision_agent(rapport_agent)
        return rapport_agent

    def _archiver_decision_agent(self, rapport):
        """
        Enregistre la décision de l'agent dans la table des logs autonomes.
        """
        endpoint = f"{SUPABASE_URL}/rest/v1/agent_decisions_log"
        try:
            requests.post(endpoint, json=rapport, headers=self.headers, timeout=5)
        except Exception as e:
            print(f"Erreur d'archivage Agent : {e}")
