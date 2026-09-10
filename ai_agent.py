import os
import requests
from datetime import datetime

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://eilyxfhxmscuwbavkpzz.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_eE-LmmezezF4l6L3O7hGBQ_hMOZL9i7")
GOOGLE_CHAT_WEBHOOK_URL = os.environ.get("GOOGLE_CHAT_WEBHOOK_URL")

class StaffingAutonomousAgent:
    def __init__(self, planning_data=None):
        if planning_data is None: planning_data = {}
        self.planning = planning_data.get("planning", [])
        self.semaine = planning_data.get("semaine_iso", "S37")
        self.trafic_var = 0
        self.headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
        self.perf_rayons = {
            "Nature/Glisse": {"tendance_ca": -4.2, "statut": "SOUS-PERFORMANCE"},
            "Rando/Cycle": {"tendance_ca": 8.5, "statut": "SUR-PERFORMANCE"}
        }

    def envoyer_push_interactif(self, titre, message, bouton_texte="Ouvrir le Cockpit"):
        if not GOOGLE_CHAT_WEBHOOK_URL: return False
        payload = {
            "cardsV2": [{
                "cardId": "alert-card",
                "card": {
                    "header": { "title": f"🤖 {titre}", "subtitle": "Workforce Agent MLOps" },
                    "sections": [{
                        "widgets": [
                            { "textParagraph": { "text": message } },
                            { "buttonList": { "buttons": [{ "text": bouton_texte, "onClick": { "openLink": { "url": "https://script.google.com/macros/s/AKfycbxNx6y8EZRE0lVinOVqQdA8BoD0PLTzxzmlnTNU_GVyybn0-68nmtDEu7Es2-kFCqT5/exec" } } }]}}
                        ]
                    }]
                }
            }]
        }
        try: requests.post(GOOGLE_CHAT_WEBHOOK_URL, json=payload, timeout=5)
        except: pass

    def analyser_et_decider(self):
        actions_correctives = []
        facteur_stress = 1.0 + (self.trafic_var / 100.0)
        caisse_count = sum(1 for p in self.planning if p.get("activite") == "Caisse")
        
        if caisse_count < 3 and facteur_stress > 1.1:
            actions_correctives.append({"type": "ALERTE_RUSH_CAISSE", "priorite": "HAUTE", "message": f"🚨 Saturation VMA prévue.", "action": "Notification Push envoyée."})
            self.envoyer_push_interactif("Alerte Saturation", f"🚨 *Saturation VMA prévue* pour la semaine {self.semaine}.")

        vendeurs = [p for p in self.planning if p.get("activite") == "Vente"]
        rayons_couverts = set(v.get("rayon_cible") for v in vendeurs)
        
        for rayon, perfs in self.perf_rayons.items():
            if perfs["statut"] == "SOUS-PERFORMANCE" and rayon not in rayons_couverts:
                actions_correctives.append({"type": "ALERTE_COMMERCE_RAYON", "priorite": "CRITIQUE", "message": f"📉 Sous-performance {rayon}.", "action": f"Réaffecter renfort sur {rayon}."})

        rapport = {
            "semaine_iso": self.semaine,
            "score_coherence": max(40, int(100 - (len(actions_correctives) * 15))),
            "facteur_stress_calcule": round(facteur_stress, 2),
            "actions_suggerees": actions_correctives
        }
        try: requests.post(f"{SUPABASE_URL}/rest/v1/agent_decisions_log", json=rapport, headers=self.headers, timeout=5)
        except: pass
        return rapport

    def generer_briefing_matin(self):
        self.envoyer_push_interactif("Briefing Nostradamus", "🌅 *Bonjour Pierre !*\n🎯 *Objectif Taux ID :* 85%\n⚠️ *Point de vigilance :* Pic attendu à 15h.")
        return {"status": "Briefing envoyé"}

    def surveiller_temps_reel(self):
        return {"status": "Surveillance active", "alertes": []}
