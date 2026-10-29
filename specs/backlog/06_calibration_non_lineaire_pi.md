# À faire — Calibration non linéaire des distances et rotations sur Pi

**Statut :** à traiter dans un second temps, après la campagne fonctionnelle.
**Origine :** observations sur le robot réel du 29 octobre 2026.

## Constat

La conversion actuelle repose sur des coefficients constants : durée = distance / vitesse linéaire, ou durée = angle / vitesse angulaire, avec une durée minimale. Les réglages sont dans [runtime_calibration.toml](../../config/runtime_calibration.toml).

Un coefficient ajusté sur une consigne ne donne pas une précision suffisante sur toute la plage :

| Consigne | Résultat observé après premiers ajustements |
|---|---|
| Rotation de 45° | Correcte selon l'observation utilisateur ; dispersion non mesurée |
| Rotation de 180° | Environ 210° réels, soit un dépassement de 30° |
| Avance de 10 cm | Environ 8 cm réels |
| Avance de 20 cm | Correcte selon l'observation utilisateur ; dispersion non mesurée |
| Avance de 50 cm | Distance réelle supérieure à 50 cm ; valeur exacte à relever |

Ces relevés ne suffisent pas à déterminer une loi de correction. Ne pas modifier à nouveau un coefficient global pour corriger une seule consigne au détriment des autres.

## Travail à prévoir

- [ ] Mesurer trois répétitions minimum par consigne sur plusieurs distances et angles, dans les deux sens : avance/recul et gauche/droite.
- [ ] Enregistrer la configuration exacte, la batterie, le sol, la vitesse moteur, les durées commandées, les distances/angles réels et leur dispersion.
- [ ] Caractériser les effets de démarrage, d'arrêt, de la durée minimale et de la charge avant de choisir un modèle.
- [ ] Déterminer une conversion adaptée à l'amplitude demandée, par exemple une loi avec compensation de démarrage ou une table avec interpolation, uniquement si les mesures le justifient.
- [ ] Préserver les calibrations distinctes avance/recul ; séparer gauche/droite seulement si nécessaire d'après les mesures.
- [ ] Appliquer la conversion de manière cohérente aux primitives, plans composés et impulsions de suivi concernés, sans changer les durées explicitement demandées.
- [ ] Conserver bornages, arrêt d'urgence, priorité obstacle et arrêt final ; vérifier l'incidence sur les budgets temporels.
- [ ] Ajouter des tests automatisés aux points mesurés et entre ces points, puis rejouer M01/M02 et les scénarios de suivi impactés sur le Pi.

## Critères de clôture

Valider la précision sur l'ensemble de la plage retenue, pas seulement sur 20 cm ou 45°. Utiliser comme référence initiale les critères M01 de la [campagne Pi](../../docs/test-campaign/plan-test-pi-post-audit-v6.md) : erreur de distance ≤ 20 % et erreur angulaire ≤ 15° pour chaque essai. Définir explicitement la plage qualifiée et conserver les résultats avant/après.

Cette optimisation ne fournit pas d'odométrie : une commande fondée sur le temps reste sensible à la batterie, au sol et au glissement.
