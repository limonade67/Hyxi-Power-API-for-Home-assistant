# Intégration HYXi Cloud pour Home Assistant (AppDaemon)

Intégration AppDaemon pour connecter vos micro-onduleurs HYXi (via l'API open.hyxicloud.com) à Home Assistant.

## Fonctionnalités

- ✅ Récupération automatique des données de production solaire
- ✅ Gestion automatique du token (renouvellement toutes les 24h)
- ✅ Polling intelligent (uniquement entre lever et coucher du soleil)
- ✅ Mise à 0W automatique en fin de journée
- ✅ Support de plusieurs micro-onduleurs
- ✅ 6 capteurs par micro-onduleur :
  - Puissance instantanée (W)
  - Énergie aujourd'hui (kWh)
  - Énergie totale (kWh)
  - Température (°C)
  - Tension AC (V)
  - Tension PV (V)

## Prérequis

1. **Home Assistant** avec **AppDaemon** installé
2. Compte HYXi Cloud avec accès API
3. Vos identifiants API HYXi :
   - `access_key`
   - `secret_key`
   - `token` (Bearer)
   - Numéros de série de vos micro-onduleurs (`device_sn`)

### Comment obtenir vos identifiants API ?

1. Connectez-vous sur https://open.hyxicloud.com
2. Allez dans **API Management** ou **Developer Tools**
3. Créez une application API pour obtenir :
   - Access Key
   - Secret Key
   - Token (format: `Bearer xxxxx-xxxx-xxxx...`)
4. Récupérez les numéros de série de vos appareils dans la section **Devices**

## Installation

### 1. Installer le fichier Python

Copiez le fichier `hyxi_cloud.py` dans votre répertoire AppDaemon :

```
/config/appdaemon/apps/hyxi_cloud.py
```

ou

```
/homeassistant/appdaemon/apps/hyxi_cloud.py
```

### 2. Configuration dans `apps.yaml`

Éditez `/config/appdaemon/apps/apps.yaml` et ajoutez :

```yaml
hyxi_cloud:
  module: hyxi_cloud
  class: HyxiCloud

  base_url: "https://open.hyxicloud.com"
  access_key: "VOTRE_ACCESS_KEY"           # ⚠️ À remplacer
  secret_key: "VOTRE_SECRET_KEY"           # ⚠️ À remplacer
  token: "Bearer VOTRE_TOKEN"              # ⚠️ À remplacer

  # Numéros de série de vos micro-onduleurs
  device_sn_toit: "31701244600031"         # ⚠️ À remplacer
  device_sn_jardin: "31701244600053"       # ⚠️ À remplacer

  # Intervalle de polling en secondes (300s = 5min)
  poll_interval: 300
```

**⚠️ Important** : Remplacez TOUS les champs marqués `# ⚠️ À remplacer` par vos propres valeurs.

### 3. Si vous n'avez qu'un seul micro-onduleur

Modifiez le fichier `hyxi_cloud.py` pour supprimer les références au deuxième appareil, OU laissez le code tel quel et configurez le même `device_sn` pour les deux (Toit et Jardin).

### 4. Redémarrer AppDaemon

```
Settings → Add-ons → AppDaemon → Restart
```

### 5. Vérifier les logs

Allez dans **AppDaemon → Log** et vérifiez que vous voyez :

```
HyxiCloud - Initialisation
Config chargee (Toit=..., Jardin=..., interval=300s)
Token rafraichi avec succes
Polling HYXi pour Toit (...)
Polling HYXi pour Jardin (...)
```

## Entités créées

Pour chaque micro-onduleur, 6 entités sont créées :

**Pour le micro-onduleur "Toit" :**
- `sensor.hyxi_toit_power` - Puissance instantanée (W)
- `sensor.hyxi_toit_today_energy` - Énergie aujourd'hui (kWh)
- `sensor.hyxi_toit_total_energy` - Énergie totale (kWh)
- `sensor.hyxi_toit_temperature` - Température (°C)
- `sensor.hyxi_toit_vac` - Tension AC (V)
- `sensor.hyxi_toit_vpv` - Tension PV (V)

**Pour le micro-onduleur "Jardin" :**
- `sensor.hyxi_jardin_power`
- `sensor.hyxi_jardin_today_energy`
- `sensor.hyxi_jardin_total_energy`
- `sensor.hyxi_jardin_temperature`
- `sensor.hyxi_jardin_vac`
- `sensor.hyxi_jardin_vpv`

## Dépannage

### Erreur 400 Bad Request

Si vous voyez des erreurs 400 dans les logs AppDaemon :

1. Supprimez les anciennes entités `*_today_energy` via Developer Tools → States
2. Redémarrez AppDaemon
3. Les entités seront recréées avec les bons attributs

### Le token expire

Le token se rafraîchit automatiquement toutes les ~4h. Si vous voyez des erreurs 401, vérifiez que vos `access_key` et `secret_key` sont corrects.

### Les graphes ne se mettent pas à jour

Vérifiez dans **Developer Tools → States** que les entités ont bien un `last_updated` récent (< 5 minutes).

### Modifier l'intervalle de polling

Par défaut, le polling se fait toutes les 5 minutes. Pour changer :

```yaml
poll_interval: 600  # 10 minutes
```

## Contribution

N'hésitez pas à proposer des améliorations via Issues ou Pull Requests !

## Licence

Ce projet est sous licence MIT - voir le fichier LICENSE pour plus de détails.

## Avertissement

Cette intégration n'est pas officielle et n'est pas affiliée à HYXi. Utilisez-la à vos propres risques.
