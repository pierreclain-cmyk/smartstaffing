import os
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://eilyxfhxmscuwbavkpzz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_eE-LmmezezF4l6L3O7hGBQ_hMOZL9i7")
GOOGLE_CHAT_WEBHOOK_URL = os.environ.get("GOOGLE_CHAT_WEBHOOK_URL")

def envoyer_push_google_chat(alerte_msg):
    if not GOOGLE_CHAT_WEBHOOK_URL:
        print("Webhook Google Chat non configuré.")
        return False
        
    payload = {
        "text": f"🤖 *ALERTE AGENT IDENTIFID*\n\n{alerte_msg}\n\n_Action générée automatiquement par le module MLOps._"
    }
    
    try:
        response = requests.post(GOOGLE_CHAT_WEBHOOK_URL, json=payload, timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"Erreur d'envoi Google Chat : {e}")
        return False

class StaffingAutonomousAgent:
    def __init__(self, planning_data, meteo_sky="Ensoleillé", trafic_var=0):
        self.planning = planning_data.get("planning", [])
        self.semaine = planning_data.get("semaine_iso", "S36")
        self.meteo = meteo_sky
        self.trafic_var = trafic_var
        self.headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
        
        self.perf_rayons = {
            "Nature/Glisse": {"tendance_ca": -4.2, "statut": "SOUS-PERFORMANCE"},
            "Rando/Cycle": {"tendance_ca": 8.5, "statut": "SUR-PERFORMANCE"}
        }

    def analyser_et_decider(self):
        actions_correctives = []
        
        # 1. ANALYSE LIGNE DE CAISSE (Tension VMA)
        facteur_stress = 1.0 + (0.20 if self.meteo in ["Pluvieux", "Orageux"] else 0) + (self.trafic_var / 100.0)
        caisse_count = sum(1 for p in self.planning if p.get("activite") == "Caisse")
        
        if caisse_count < 3 and facteur_stress > 1.1:
            alerte_msg = f"🚨 *Saturation VMA prévue* pour la semaine {self.semaine}.\nL'effectif caisse est sous-dimensionné (Facteur stress: {round(facteur_stress,2)}).\n👉 *Action immédiate requise :* Activer le renfort automatique sur les créneaux 14h-18h."
            
            actions_correctives.append({
                "type": "ALERTE_RUSH_CAISSE",
                "priorite": "HAUTE",
                "message": f"🚨 Saturation VMA prévue (Facteur: {round(facteur_stress,2)}).",
                "action": "Notification Push envoyée."
            })
            
            # Déclenchement autonome de la notification push
            envoyer_push_google_chat(alerte_msg)

        # 2. ANALYSE COMMERCE & RAYONS (Croisement Perf SQL)
        vendeurs = [p for p in self.planning if p.get("activite") == "Vente"]
        rayons_couverts = set(v.get("rayon_cible") for v in vendeurs)
        
        for rayon, perfs in self.perf_rayons.items():
            if perfs["statut"] == "SOUS-PERFORMANCE" and rayon not in rayons_couverts:
                alerte_commerce = f"📉 *Sous-performance {rayon}* ({perfs['tendance_ca']}% CA) mais aucun vendeur n'est planifié. Réaffecter un profil Polyvalent."
                actions_correctives.append({
                    "type": "ALERTE_COMMERCE_RAYON",
                    "priorite": "CRITIQUE",
                    "message": alerte_commerce,
                    "action": f"Réaffecter renfort commerce sur {rayon}."
                })
                envoyer_push_google_chat(alerte_commerce)

        rapport = {
            "semaine_iso": self.semaine,
            "score_coherence": max(40, int(100 - (len(actions_correctives) * 15))),
            "facteur_stress_calcule": round(facteur_stress, 2),
            "gain_id_potentiel": 4.5 if caisse_count < 3 else 0,
            "actions_suggerees": actions_correctives
        }

        self._archiver_decision_agent(rapport)
        return rapport

    def _archiver_decision_agent(self, rapport):
        endpoint = f"{SUPABASE_URL}/rest/v1/agent_decisions_log"
        try: requests.post(endpoint, json=rapport, headers=self.headers, timeout=5)
        except: pass
