# ARCHITECTURE DES CAPTEURS HYXI - PANNEAUX SOLAIRES

## 📋 Vue d'ensemble

Ce document explique l'organisation complète de tous les capteurs HYXi, leur provenance, et comment ils sont utilisés.

---

## 🏗️ SCHÉMA GÉNÉRAL

```
┌─────────────────────────────────────────────────────────────────────┐
│                       API HYXI CLOUD                                │
│                  (open.hyxicloud.com)                               │
│                                                                     │
│  Données brutes pour chaque panneau:                                │
│  • acP    → Puissance instantanée (W)                               │
│  • acE    → Énergie aujourd'hui (kWh)                               │
│  • totalE → Énergie totale cumulée (kWh)                            │
│  • temp   → Température (°C)                                        │
│  • ph1v   → Tension AC (V)                                          │
│  • pv1v   → Tension PV (V)                                          │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────┐
                    │  APPDAEMON      │
                    │  hyxi_cloud.py  │
                    └─────────────────┘
                              ↓
        ┌─────────────────────┴─────────────────────┐
        ↓                                           ↓
┌───────────────────┐                    ┌───────────────────┐
│  PANNEAU TOIT     │                    │  PANNEAU JARDIN   │
│  (6 capteurs)     │                    │  (6 capteurs)     │
└───────────────────┘                    └───────────────────┘
```

---

## 📊 CAPTEURS CRÉÉS PAR APPDAEMON (pour chaque panneau)

### 🔌 1. PUISSANCE INSTANTANÉE
**Entités:**
- `sensor.hyxi_toit_power_v2`
- `sensor.hyxi_jardin_power_v2`

**Source:** API HYXi → `acP` (Puissance AC en W)

**Attributs:**
- `device_class: power`
- `state_class: measurement`
- `unit_of_measurement: W`

**Utilisé pour:**
- ✅ Monitoring temps réel
- ✅ Source pour capteur d'intégrale (Riemann)
- ✅ Graphiques de puissance dans Home Assistant

---

### ⚡ 2. ÉNERGIE AUJOURD'HUI (valeur brute API)
**Entités:**
- `sensor.hyxi_toit_today_energy_v2`
- `sensor.hyxi_jardin_today_energy_v2`

**Source:** API HYXi → `acE` (Énergie du jour en kWh)

**Attributs:**
- `unit_of_measurement: kWh`
- ⚠️ **AUCUN** `state_class` (pour éviter erreurs HTTP 400)

**Utilisé pour:**
- ✅ Affichage direct de ce que dit l'API HYXi
- ✅ Monitoring/debug
- ❌ **PAS utilisé** dans le tableau de bord Énergie

**Note:** Se réinitialise chaque jour selon l'API HYXi

---

### 🔢 3. ÉNERGIE TOTALE (compteur cumulé)
**Entités:**
- `sensor.hyxi_toit_total_energy_v2`
- `sensor.hyxi_jardin_total_energy_v2`

**Source:** API HYXi → `totalE` (Énergie totale cumulée en kWh)

**Attributs:**
- `device_class: energy`
- `state_class: total_increasing`
- `unit_of_measurement: kWh`

**Utilisé pour:**
- ✅ Monitoring production totale depuis l'installation
- ⚠️ **PROBLÈME:** Valeurs incohérentes (sauts, diminutions)
- ❌ **N'EST PLUS utilisé** pour Utility Meter (abandonné)

**Note:** Peut avoir des variations bizarres à cause de l'API HYXi

---

### 🌡️ 4. TEMPÉRATURE
**Entités:**
- `sensor.hyxi_toit_temperature_v2`
- `sensor.hyxi_jardin_temperature_v2`

**Source:** API HYXi → `temp` (Température micro-onduleur en °C)

**Attributs:**
- `device_class: temperature`
- `state_class: measurement`
- `unit_of_measurement: °C`

**Utilisé pour:**
- ✅ Monitoring santé du matériel
- ✅ Détection surchauffe

---

### 🔋 5. TENSION AC (réseau)
**Entités:**
- `sensor.hyxi_toit_vac_v2`
- `sensor.hyxi_jardin_vac_v2`

**Source:** API HYXi → `ph1v` (Tension réseau en V)

**Attributs:**
- `device_class: voltage`
- `state_class: measurement`
- `unit_of_measurement: V`

**Utilisé pour:**
- ✅ Monitoring qualité réseau électrique

---

### ☀️ 6. TENSION PV (panneau solaire)
**Entités:**
- `sensor.hyxi_toit_vpv_v2`
- `sensor.hyxi_jardin_vpv_v2`

**Source:** API HYXi → `pv1v` (Tension panneau en V)

**Attributs:**
- `device_class: voltage`
- `state_class: measurement`
- `unit_of_measurement: V`

**Utilisé pour:**
- ✅ Monitoring production panneau

---

## 🧮 CAPTEURS CRÉÉS PAR HOME ASSISTANT (Helpers)

### 📈 7. ÉNERGIE CALCULÉE (Riemann Sum - Intégrale)
**Entités:**
- `sensor.hyxi_toit_energie_riemann`
- `sensor.hyxi_jardin_energie_riemann`

**Type:** Helper "Capteur d'intégrale"

**Source:** 
- Calcule l'énergie à partir de la puissance
- Input: `sensor.hyxi_xxx_power_v2`

**Méthode:** Intégration trapézoïdale de la puissance dans le temps

**Attributs:**
- `device_class: energy`
- `state_class: total_increasing`
- `unit_of_measurement: kWh`

**Utilisé pour:**
- ✅ **TABLEAU DE BORD ÉNERGIE** (production solaire)
- ✅ Calcul précis et fiable de l'énergie produite
- ✅ Pas d'incohérences (contrairement à l'API HYXi)

**Note:** Commence à compter depuis sa création (pas d'historique antérieur)

---

### ➕ 8. PRODUCTION TOTALE (somme des deux panneaux)
**Entité:**
- `sensor.hyxi_production_totale_riemann`

**Type:** Helper "Combiner l'état de plusieurs capteurs"

**Source:** 
- Somme de: `sensor.hyxi_toit_energie_riemann` + `sensor.hyxi_jardin_energie_riemann`

**Attributs:**
- Hérités automatiquement des sources
- `device_class: energy`
- `state_class: total_increasing`
- `unit_of_measurement: kWh`

**Utilisé pour:**
- ✅ Voir la production totale des deux panneaux
- ✅ Peut être utilisé dans le tableau de bord Énergie

---

### 📅 9. ÉNERGIE QUOTIDIENNE (Utility Meter - OPTIONNEL)
**Entités (si créées):**
- `sensor.hyxi_toit_daily_riemann`
- `sensor.hyxi_jardin_daily_riemann`

**Type:** Utility Meter (dans configuration.yaml)

**Source:** 
- `sensor.hyxi_xxx_energie_riemann`

**Attributs:**
- Se réinitialise automatiquement à minuit
- Donne l'énergie produite aujourd'hui

**Utilisé pour:**
- ✅ Avoir un capteur qui affiche directement "kWh produits aujourd'hui"
- ✅ Statistiques quotidiennes

**Configuration:**
```yaml
utility_meter:
  hyxi_toit_daily_riemann:
    source: sensor.hyxi_toit_energie_riemann
    cycle: daily
```

---

## 🎯 UTILISATION DANS LE TABLEAU DE BORD ÉNERGIE

### Configuration actuelle (RECOMMANDÉE)

**Paramètres → Tableaux de bord → Énergie → Panneaux solaires:**

✅ **Production solaire - Panneau Toit:**
- Entité: `sensor.hyxi_toit_energie_riemann`

✅ **Production solaire - Panneau Jardin:**
- Entité: `sensor.hyxi_jardin_energie_riemann`

**Résultat:**
- 📊 Graphique heure par heure basé sur les statistiques
- 📈 Total quotidien calculé automatiquement
- ✅ Valeurs fiables (pas d'incohérences)

---

## 🔄 FLUX DE DONNÉES COMPLET

```
┌──────────────────────────────────────────────────────────────────┐
│                    API HYXI (toutes les 5 min)                   │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│                   APPDAEMON (hyxi_cloud.py)                      │
│                                                                  │
│  Crée 6 capteurs × 2 panneaux = 12 capteurs:                    │
│  • power_v2          (W)    → Puissance instantanée             │
│  • today_energy_v2   (kWh)  → Énergie du jour (API brute)       │
│  • total_energy_v2   (kWh)  → Énergie totale (⚠️ incohérente)   │
│  • temperature_v2    (°C)   → Température                       │
│  • vac_v2            (V)    → Tension AC                        │
│  • vpv_v2            (V)    → Tension PV                        │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│              HOME ASSISTANT - Capteur d'intégrale               │
│                                                                  │
│  Input:  power_v2 (W)                                           │
│  Calcul: Intégration trapézoïdale dans le temps                 │
│  Output: energie_riemann (kWh) ← VALEUR FIABLE                  │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│         HOME ASSISTANT - Combiner plusieurs capteurs            │
│                                                                  │
│  Toit + Jardin = Production Totale                              │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│              TABLEAU DE BORD ÉNERGIE (Affichage)                │
│                                                                  │
│  • Graphique heure par heure                                    │
│  • Total quotidien                                              │
│  • Autoconsommation                                             │
└──────────────────────────────────────────────────────────────────┘
```

---

## 📝 CAPTEURS OBSOLÈTES / NON UTILISÉS

### ❌ Utility Meter sur total_energy_v2 (ABANDONNÉ)
**Raison:** L'API HYXi renvoie des valeurs incohérentes pour `totalE`:
- Sauts brutaux
- Diminutions (alors que `total_increasing` l'interdit)
- Résultat: graphiques faux dans le tableau de bord Énergie

**Entités abandonnées:**
- `sensor.hyxi_toit_daily` (de Utility Meter)
- `sensor.hyxi_jardin_daily` (de Utility Meter)

**Solution:** Remplacé par capteurs d'intégrale (Riemann)

---

## 🎓 RÉSUMÉ POUR RETENIR

### Capteurs à UTILISER pour le tableau de bord Énergie:
✅ `sensor.hyxi_toit_energie_riemann`
✅ `sensor.hyxi_jardin_energie_riemann`
✅ `sensor.hyxi_production_totale_riemann` (si créé)

### Capteurs à UTILISER pour le monitoring:
✅ `sensor.hyxi_xxx_power_v2` (puissance temps réel)
✅ `sensor.hyxi_xxx_temperature_v2` (santé matériel)
✅ `sensor.hyxi_xxx_today_energy_v2` (comparaison avec API HYXi)

### Capteurs à IGNORER:
❌ `sensor.hyxi_xxx_total_energy_v2` (incohérent)
❌ `sensor.hyxi_xxx_daily` (Utility Meter abandonné)

---

## 🔧 FICHIERS DE CONFIGURATION

### 1. AppDaemon
**Fichier:** `/config/appdaemon/apps/hyxi_cloud.py`
- Crée les 12 capteurs de base (6 par panneau)
- Polling toutes les 5 minutes pendant la journée
- Gestion automatique du token

### 2. Home Assistant - Helpers
**Créés via UI:** Paramètres → Appareils et services → Entrées
- Capteur d'intégrale (Riemann) × 2
- Combiner capteurs × 1

### 3. Home Assistant - Utility Meter (OPTIONNEL)
**Fichier:** `/config/configuration.yaml`
```yaml
utility_meter:
  hyxi_toit_daily_riemann:
    source: sensor.hyxi_toit_energie_riemann
    cycle: daily
  hyxi_jardin_daily_riemann:
    source: sensor.hyxi_jardin_energie_riemann
    cycle: daily
```

---

## 📅 Date de création de ce document
**13 février 2026**

---

## 🔄 Historique des modifications
- **13 fév 2026:** Création initiale
- **13 fév 2026:** Ajout capteur production totale
- **13 fév 2026:** Abandon Utility Meter sur total_energy_v2, passage à Riemann
