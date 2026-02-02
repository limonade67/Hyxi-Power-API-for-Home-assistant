# -*- coding: utf-8 -*-
"""
Intégration HYXi Cloud (open.hyxicloud.com) pour 2 micro-onduleurs
Requêtes GET /api/device/v1/queryDeviceData comme dans Postman
+ Gestion automatique du renouvellement du token
+ Mise à 0W à la fermeture du polling (coucher du soleil)
+ last_reset sur le compteur "aujourd'hui" pour gérer le reset minuit
"""

import appdaemon.plugins.hass.hassapi as hass
import requests
import hmac
import hashlib
import base64
from datetime import datetime
import time
import json


class HyxiCloud(hass.Hass):

    def initialize(self):
        """Initialisation au démarrage d'AppDaemon"""
        self.log("=" * 60)
        self.log("HyxiCloud - Initialisation")
        self.log("=" * 60)

        # --- Config issue de apps.yaml ---
        self.base_url = self.args.get("base_url", "https://open.hyxicloud.com")
        self.access_key = self.args["access_key"]
        self.secret_key = self.args["secret_key"]
        self.token = self.args["token"]          # ex: "Bearer xxxxx"
        self.device_sn_toit = self.args["device_sn_toit"]
        self.device_sn_jardin = self.args["device_sn_jardin"]
        self.poll_interval = int(self.args.get("poll_interval", 300))

        # Gestion du token (validité 24h)
        self.token_expires_at = 0  # timestamp d'expiration du token
        self.token_refresh_margin = 3600  # rafraîchir 1h avant expiration (sécurité)

        # État du polling : pour savoir si on était actif avant
        self.was_polling = False

        # Noms des entités HA
        self.entity_toit = {
            "power": "sensor.hyxi_toit_power",
            "today": "sensor.hyxi_toit_today_energy",
            "total": "sensor.hyxi_toit_total_energy",
            "temp": "sensor.hyxi_toit_temperature",
            "vac": "sensor.hyxi_toit_vac",
            "vpv": "sensor.hyxi_toit_vpv",
        }
        self.entity_jardin = {
            "power": "sensor.hyxi_jardin_power",
            "today": "sensor.hyxi_jardin_today_energy",
            "total": "sensor.hyxi_jardin_total_energy",
            "temp": "sensor.hyxi_jardin_temperature",
            "vac": "sensor.hyxi_jardin_vac",
            "vpv": "sensor.hyxi_jardin_vpv",
        }

        self.log(
            f"Config chargee (Toit={self.device_sn_toit}, "
            f"Jardin={self.device_sn_jardin}, interval={self.poll_interval}s)"
        )

        # Premier cycle dans 5 s, puis périodique
        self.run_in(self.poll_once, 5)

    # ------------------------------------------------------------------
    # Helpers : fermeture du polling & last_reset
    # ------------------------------------------------------------------

    def _get_today_midnight_iso(self):
        """Retourne minuit aujourd'hui au format ISO 8601 pour last_reset"""
        now = datetime.now()
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return midnight.isoformat()

    def _send_zero_and_close(self, entities, label):
        """
        Envoyé une SEULE fois quand on sort de la plage solaire.
        - Puissance → 0 W
        - Énergie aujourd'hui : on garde la dernière valeur mais on met
          last_reset à minuit aujourd'hui (HASS saura qu'il peut descendre
          à 0 demain matin sans erreur)
        - Température, tensions → 0 / inconnu
        """
        self.log(f"[{label}] Fermeture du polling — mise à 0W")

        # Puissance à 0
        self.set_state(entities["power"], state=0, attributes={
            "unit_of_measurement": "W",
            "device_class": "power",
            "state_class": "measurement",
            "friendly_name": f"HYXi {label} - Puissance",
            "icon": "mdi:solar-power"
        })

        # Température à 0
        self.set_state(entities["temp"], state=0, attributes={
            "unit_of_measurement": "°C",
            "device_class": "temperature",
            "state_class": "measurement",
            "friendly_name": f"HYXi {label} - Temperature",
            "icon": "mdi:thermometer"
        })

        # Tensions à 0
        for key, name, icon in [
            ("vac", "Tension AC", "mdi:flash"),
            ("vpv", "Tension PV", "mdi:solar-panel"),
        ]:
            self.set_state(entities[key], state=0, attributes={
                "unit_of_measurement": "V",
                "device_class": "voltage",
                "state_class": "measurement",
                "friendly_name": f"HYXi {label} - {name}",
                "icon": icon
            })

        # Énergie aujourd'hui : on ne touche pas la valeur (elle reste correcte)
        # mais on pose last_reset = minuit aujourd'hui.
        # Comme on utilise state_class: total avec last_reset, HASS sait que
        # la valeur peut redescendre à 0 après ce timestamp.
        # On récupère l'état actuel pour ne pas le changer.
        try:
            current_today = self.get_state(entities["today"])
        except Exception:
            current_today = 0

        self.set_state(entities["today"], state=current_today, attributes={
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "state_class": "total",
            "last_reset": self._get_today_midnight_iso(),
            "friendly_name": f"HYXi {label} - Energie Aujourd'hui",
            "icon": "mdi:solar-power"
        })

    # ------------------------------------------------------------------
    # Token
    # ------------------------------------------------------------------

    def _ensure_valid_token(self):
        """
        Vérifie si le token est valide, sinon le rafraîchit
        Retourne True si le token est valide, False sinon
        """
        current_time = time.time()

        # Si le token expire bientôt ou est déjà expiré
        if current_time >= (self.token_expires_at - self.token_refresh_margin):
            self.log("Token expire ou sur le point d'expirer, rafraichissement...")
            return self._refresh_token()

        return True

    def _refresh_token(self):
        """
        Rafraîchit le token en appelant POST /api/authorization/v1/token
        EXACTEMENT comme dans Postman
        Retourne True si succès, False sinon
        """
        path = "/api/authorization/v1/token"
        method = "POST"
        url = f"{self.base_url}{path}"

        # timestamp & nonce
        timestamp = str(int(time.time() * 1000))
        nonce = format(int(time.time() * 1000), "x")[-8:]

        # Body de la requête
        body = {"grantType": 1}
        body_json = json.dumps(body, separators=(',', ':'))

        # Étape 1: Construire le content à partir des Sign-headers
        sign_header_keys = "grantType"
        content = ""
        for key in sign_header_keys.split(':'):
            if key in body:
                content += f"{key}:{body[key]}"

        # Étape 2: Calculer SHA-512 du content (en hex)
        hex_content_hash = hashlib.sha512(content.encode("utf-8")).hexdigest()

        # Étape 3: Construire stringToSign
        string_to_sign = f"{path}\n{method}\n{hex_content_hash}\n"

        # Étape 4: Construire signString (sans token pour la requête d'auth)
        sign_string = f"{self.access_key}{timestamp}{nonce}{string_to_sign}"

        # Étape 5: Calculer HMAC-SHA-512 et encoder en Base64
        hmac_bytes = hmac.new(
            self.secret_key.encode("utf-8"),
            sign_string.encode("utf-8"),
            hashlib.sha512,
        ).digest()
        sign_b64 = base64.b64encode(hmac_bytes).decode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "AccessKey": self.access_key,
            "Timestamp": timestamp,
            "Nonce": nonce,
            "Sign": sign_b64,
            "Sign-headers": sign_header_keys,
        }

        self.log(f"Tentative de rafraichissement du token...")
        self.log(f"Content: {content}")
        self.log(f"HexContentHash: {hex_content_hash}")

        try:
            resp = requests.post(url, data=body_json, headers=headers, timeout=10)
            self.log(f"Response status: {resp.status_code}")
            resp.raise_for_status()
            payload = resp.json()
        except Exception as e:
            self.log(f"Erreur lors du rafraichissement du token: {e}", level="ERROR")
            self.log(f"Response text: {resp.text if 'resp' in locals() else 'N/A'}")
            return False

        if not payload.get("success") or payload.get("code") != "0":
            msg = payload.get("msg", "Unknown error")
            code = payload.get("code", "Unknown")
            self.log(f"Echec du rafraichissement du token - Code: {code}, Msg: {msg}", level="ERROR")
            return False

        # Extraction des infos du token
        data = payload.get("data", {})
        access_token = data.get("access_token")
        token_type = data.get("token_type", "bearer")
        expires_in = int(data.get("expires_in", 86400))  # FIX: L'API retourne un str → cast en int

        if not access_token:
            self.log("Token recu mais access_token manquant", level="ERROR")
            return False

        # Mise à jour du token
        self.token = f"{token_type.capitalize()} {access_token}"
        self.token_expires_at = time.time() + expires_in

        self.log(
            f"Token rafraichi avec succes. "
            f"Nouveau token: {self.token[:20]}... "
            f"Valide pendant {expires_in}s ({expires_in/3600:.1f}h)"
        )

        return True

    # ------------------------------------------------------------------
    # Polling principal
    # ------------------------------------------------------------------

    def poll_once(self, kwargs):
        """Un cycle de polling pour les 2 panneaux"""

        in_solar_window = self.now_is_between("sunrise - 00:15:00", "sunset + 00:15:00")

        if not in_solar_window:
            # On vient de sortir de la plage solaire → envoyer 0W une seule fois
            if self.was_polling:
                self.log("Sortie de la plage solaire — envoi du dernier update à 0W")
                self._send_zero_and_close(self.entity_toit, "Toit")
                self._send_zero_and_close(self.entity_jardin, "Jardin")
                self.was_polling = False

            self.log(
                "En dehors de la plage solaire (sunrise-15 / sunset+15), "
                "pas de requete HYXi"
            )
        else:
            self.was_polling = True

            # Vérifier et rafraîchir le token si nécessaire
            if not self._ensure_valid_token():
                self.log("Impossible de rafraichir le token, abandon du polling", level="ERROR")
            else:
                try:
                    self._update_panel(self.device_sn_toit, self.entity_toit, "Toit")
                    self._update_panel(self.device_sn_jardin, self.entity_jardin, "Jardin")
                except Exception as e:
                    self.log(f"Erreur dans poll_once: {e}", level="ERROR")
                    # FIX: Cast en str() avant le `in` pour éviter "is not iterable"
                    if "401" in str(e) or "Unauthorized" in str(e):
                        self.log("Erreur 401 detectee, rafraichissement force du token")
                        self.token_expires_at = 0  # Force le refresh au prochain cycle

        # replanifier le prochain cycle
        self.run_in(self.poll_once, self.poll_interval)

    # ------------------------------------------------------------------
    # Mise à jour d'un paneau
    # ------------------------------------------------------------------

    def _update_panel(self, device_sn, entities, label):
        """Appel HYXi + mise à jour des 6 entités pour un device"""
        self.log(f"Polling HYXi pour {label} ({device_sn})")

        data = self._query_device_data(device_sn)
        if data is None:
            self.log(f"Aucune data pour {label}", level="WARNING")
            return

        # data = liste de {dataKey, dataValue}
        def get_value(key):
            for item in data:
                if item.get("dataKey") == key:
                    return item.get("dataValue")
            return None

        acP = get_value("acP")
        acE = get_value("acE")
        totalE = get_value("totalE")
        temp = get_value("temp")
        vac = get_value("ph1v")
        vpv = get_value("pv1v")

        # Puissance instantanée (W)
        self.set_state(entities["power"], state=acP, attributes={
            "unit_of_measurement": "W",
            "device_class": "power",
            "state_class": "measurement",
            "friendly_name": f"HYXi {label} - Puissance",
            "icon": "mdi:solar-power"
        })

        # Énergie aujourd'hui (kWh)
        # FIX: On utilise state_class: total + last_reset (mis à minuit aujourd'hui)
        # à la place de total_increasing. Comme ça HASS accepte la descente
        # vers 0 après le reset quotidien de HYXi.
        self.set_state(entities["today"], state=round(float(acE), 1), attributes={
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "state_class": "total",
            "last_reset": self._get_today_midnight_iso(),
            "friendly_name": f"HYXi {label} - Energie Aujourd'hui",
            "icon": "mdi:solar-power"
        })

        # Énergie totale (kWh) — celle-ci ne se réinitialise jamais,
        # total_increasing reste correct ici.
        self.set_state(entities["total"], state=round(float(totalE), 1), attributes={
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "state_class": "total_increasing",
            "friendly_name": f"HYXi {label} - Energie Totale",
            "icon": "mdi:counter"
        })

        # Température (°C)
        self.set_state(entities["temp"], state=temp, attributes={
            "unit_of_measurement": "°C",
            "device_class": "temperature",
            "state_class": "measurement",
            "friendly_name": f"HYXi {label} - Temperature",
            "icon": "mdi:thermometer"
        })

        # Tension AC (V)
        self.set_state(entities["vac"], state=vac, attributes={
            "unit_of_measurement": "V",
            "device_class": "voltage",
            "state_class": "measurement",
            "friendly_name": f"HYXi {label} - Tension AC",
            "icon": "mdi:flash"
        })

        # Tension PV (V)
        self.set_state(entities["vpv"], state=vpv, attributes={
            "unit_of_measurement": "V",
            "device_class": "voltage",
            "state_class": "measurement",
            "friendly_name": f"HYXi {label} - Tension PV",
            "icon": "mdi:solar-panel"
        })

    # ------------------------------------------------------------------
    # Appel API HYXi
    # ------------------------------------------------------------------

    def _query_device_data(self, device_sn):
        """
        Copie de la logique Postman :
        GET /api/device/v1/queryDeviceData avec signature HMAC-SHA512
        """
        path = "/api/device/v1/queryDeviceData"
        method = "GET"
        query = f"deviceSn={device_sn}"
        url = f"{self.base_url}{path}?{query}"

        # timestamp & nonce
        timestamp = str(int(time.time() * 1000))
        nonce = format(int(time.time() * 1000), "x")[-8:]

        # contenu vide -> SHA512("")
        hex_content_hash = hashlib.sha512(b"").hexdigest()

        string_to_sign = f"{path}\n{method}\n{hex_content_hash}\n"
        sign_string = f"{self.access_key}{self.token}{timestamp}{nonce}{string_to_sign}"

        hmac_bytes = hmac.new(
            self.secret_key.encode("utf-8"),
            sign_string.encode("utf-8"),
            hashlib.sha512,
        ).digest()
        sign_b64 = base64.b64encode(hmac_bytes).decode("utf-8")

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "AccessKey": self.access_key,
            "Timestamp": timestamp,
            "Nonce": nonce,
            "Sign": sign_b64,
            "Authorization": self.token,
        }

        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            payload = resp.json()
        except requests.exceptions.HTTPError as e:
            # Si erreur 401, le token est invalide
            if e.response.status_code == 401:
                self.log("Erreur 401: Token invalide", level="WARNING")
                self.token_expires_at = 0  # Force le refresh
            raise
        except Exception as e:
            self.log(f"Erreur appel HYXi: {e}", level="ERROR")
            return None

        if not payload.get("success") or payload.get("code") != "0":
            self.log(f"HYXi retourne erreur: {payload}", level="WARNING")
            return None

        return payload.get("data")
