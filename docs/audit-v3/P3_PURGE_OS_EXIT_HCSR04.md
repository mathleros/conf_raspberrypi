# Guide de Correction — Priorité P3 : Purge Résiduelle de `os._exit(0)` dans `hc_sr04.py`

**Gravité :** Propreté & Conformité Standard (P3)  
**Fichier cible :** `src/irobot/hardware/sensors/hc_sr04.py`  
**Objectif :** Supprimer le dernier appel à `os._exit(0)` qui coupe brutalement l'interpréteur Python sans exécuter les gestionnaires de fin de processus.

---

## 1. Description du Problème

Dans `src/irobot/hardware/sensors/hc_sr04.py` (lignes ~8458-8463) :
`os._exit(0)` est un appel système Unix bas niveau qui tue le processus immédiatement sans appeler les destructeurs d'objets (`__del__`), sans flusher les tampons et sans exécuter les `finally` des fonctions parentes. Bien qu'il ait déjà été supprimé de `smart_car.py`, il persiste dans ce fichier.

---

## 2. Code à Modifier

Ouvrez `src/irobot/hardware/sensors/hc_sr04.py` et localisez le bloc `finally` de `def main():`.

### Repères visuels :
* `[-]` : Ligne à supprimer
* `[+]` : Ligne à ajouter
* `[u]` : Ligne modifiée

```python
    except KeyboardInterrupt:
        print("\nInterruption clavier : arrêt du capteur.")
    finally:
        sensor.cleanup()
        if args.once:
            print("Fermeture propre du capteur...")
[-]         print("", end="", flush=True)
[-]         os._exit(0)
```

---

### Résultat final propre après modification :
```python
    except KeyboardInterrupt:
        print("\nInterruption clavier : arrêt du capteur.")
    finally:
        sensor.cleanup()
        if args.once:
            print("Fermeture propre du capteur...")
```

*(Note : la sortie normale de la fonction `main()` termine proprement le script sans forcer `os._exit`)*.

---

## 3. Comment Tester ?

### Test 1 : Lancement autonome du capteur en mode `--once` (sur Raspberry Pi)
```bash
uv run hc-sr04 --once
```
*Résultat attendu :*
Le capteur effectue une mesure, affiche la distance en cm, appelle `sensor.cleanup()` et rend la main au shell avec un code de retour `0` propre.
