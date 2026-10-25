# Guide de Correction V4 — Priorité M3 : Formatage PEP 8 sur la Méthode `close()`

**Gravité :** Propreté & Style PEP 8 (M3)  
**Fichier cible :** `src/irobot/interfaces/voice_runtime.py`  
**Objectif :** Supprimer l'espace accidentel avant la parenthèse dans la déclaration de `def close (self)`.

---

## 1. Description du Problème

Dans `src/irobot/interfaces/voice_runtime.py` (ligne ~9442) :
```python
    def close (self) -> None:  # Espace accidentel avant la parenthèse
        """Arrête proprement les périphériques matériels et les threads d'arrière-plan"""
```
Bien que Python accepte cet espacement sans lever d'erreur de syntaxe, la norme PEP 8 recommande formellement de ne pas insérer d'espace entre le nom de la fonction et la parenthèse ouvrante.

---

## 2. Code à Modifier

Ouvrez `src/irobot/interfaces/voice_runtime.py` vers la ligne 9440.

### Repères visuels :
* `[-]` : Ligne à supprimer
* `[+]` : Ligne à ajouter
* `[u]` : Ligne modifiée

```python
    except KeyboardInterrupt:
        print("\nInterruption clavier : arrêt du runtime vocal.")

[-] def close (self) -> None:
[+] def close(self) -> None:
        """Arrête proprement les périphériques matériels et les threads d'arrière-plan."""
        if self.perception is not None and hasattr(self.perception, "close"):
```

---

### Résultat final propre :
```python
    def close(self) -> None:
        """Arrête proprement les périphériques matériels et les threads d'arrière-plan."""
        if self.perception is not None and hasattr(self.perception, "close"):
            try:
                self.perception.close()
            except Exception:
                pass
        if self.robot is not None and hasattr(self.robot, "stop"):
            try:
                self.robot.stop()
            except Exception:
                pass
```

---

## 3. Comment Tester ?

Vérifiez la conformité syntaxique et la suite de tests :
```bash
uv run pytest -q tests/unit/
```
*Résultat attendu :* 41 tests réussis sans avertissement.
