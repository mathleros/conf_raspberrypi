# SH-05 — blocages physiques et qualifications non exécutées

État du 2026-10-31, distinct des
[preuves logicielles sur doubles](../../specs/backlog/08_lot_a_rapport_sh09.md#18-sh-05--complément-logiciel-et-campagne-isolée-2026-10-31).
Ce document consigne des portes encore ouvertes, pas un protocole autorisant
une manipulation. Aucune campagne physique n'a été exécutée pour ce complément.

## Verdict

**No-Go mobile humain. SH-05 et SH-09 restent ouverts globalement.**
L'implémentation du contrat logiciel ne réalise ni ne qualifie les protections
indépendantes. Aucun moteur, GPIO/PWM, caméra, audio réel, Pi/SSH ou serveur
LLM n'a été activé par les validations de ce complément.

Les six sujets validés de
[SH-05](../../specs/backlog/07_suivi_humain_marqueur_backlog.md#sh-05--spécification-progressive-des-garde-fous)
et les décisions SH-02/A1–A6 sont inchangés. Aucun composant, schéma,
réglage physique ou délai indépendant n'est choisi ici.

## Blocages distincts

| Porte | Preuve physique encore nécessaire | Ce que les doubles ne démontrent pas |
|---|---|---|
| SH-02 : P2/P3/P4/P5/P6 | Réalisation et qualification de l'inhibition, surveillance indépendante, retour d'état et réarmement manuel ; défaillances couvertes et budget d'arrêt | Un port P5 injecté et une preuve de cycle ne réalisent aucun dispositif indépendant |
| Coupure/perte de contrôle | Banc protégé : programme tué/bloqué, Pi figé ou privé d'alimentation, sortie figée, coupure/rétablissement ; arrêt mesuré et absence de redépart, y compris réarmement seul/anciennes commandes | Zéro logiciel remis au double et requête d'inhibition ne prouvent ni coupure électrique ni immobilisation |
| Terrain et accès sûr en solo | Vérification opérateur du terrain et accès démontré à la coupure depuis sa position réelle ; organisation solo qualifiée | `terrain_checked`/`safe_access_demonstrated` fictifs ne vérifient ni escaliers, ni accès, ni efficacité de l'interrupteur |
| SH-03/SH-04 : perception exploitable | Montage/calibration identifiés, distance/qualité, fraîcheur et provenance qualifiées dans le domaine retenu | Images/observations synthétiques et budgets configurables ne qualifient pas l'optique ; les relevés statiques existants ne valent pas qualification mobile |
| Obstacle et volume balayé | Cibles inertes : couverture réelle de chaque mouvement, notamment rotation et volume balayé, capteur en panne et distances d'arrêt | Un booléen obstacle et une condition de couverture ne démontrent pas la couverture du seul capteur frontal |
| Vitesse et corrections | Mesures au sol : plafond validé 0,15 m/s ou moins ; vitesse angulaire, angle/durée, accélération et combinaisons qualifiés | Le réglage du driver n'est pas une conversion en m/s ; l'enveloppe fictive n'est pas un profil de production |
| Arrêt physique | Comportement électrique, maxima de délais et distances d'immobilisation mesurés selon budget SH-02 | Compteurs de stop/zéro et temps du harnais ne mesurent aucune distance d'arrêt |
| Audio et SH-10/Pi | Entrée/sortie audio opérationnelles ; charge et régularité du cycle sur Pi, délais maximaux, pertes de périphériques et supervision réelle | Un acquittement d'annonce factice ne prouve pas qu'elle a été entendue ; aucune mesure Pi/audio n'a été faite ici |
| SH-06/SH-07/SH-08/SH-11 | Comportement et intégration humaine restant à réaliser/qualifier, recette autorisée par niveau et Go explicite sur configuration documentée | Un fournisseur synthétique de mission ne livre pas un comportement humain réel ni une intégration naturelle complète |

## Restrictions maintenues

- Aucun profil `HumanMotionLimits` de production n'est renseigné. Sans profil,
  les émissions humaines non nulles sont refusées ; les valeurs des tests
  sont identifiées comme fictives, jamais recopiées en calibration.
- Aucun recul humain, rattrapage plus rapide, balayage, contournement ou
  manoeuvre exploratoire. Une rotation n'est pas autorisée par sa seule
  lenteur ou par la présence d'un capteur frontal.
- Aucun seuil supplémentaire d'accélération/combinaison n'est inventé.
  Aucune rampe de confort ou nouvelle combinaison de commandes n'est livrée.
- La cible de fraîcheur SH-04 et les budgets configurables restent provisoires
  tant qu'ils ne sont pas confrontés au budget d'arrêt ; aucun temps de
  harnais n'est une qualification.
- Retour d'énergie/programme/périphérique : jamais départ implicite.
  Réarmement physique distinct d'une nouvelle demande et de l'effacement du
  stop logiciel ; suspension ordinaire : correction des défauts puis reprise
  explicite avec nouvelle acquisition et échéance initiale conservée.
- Banc protégé puis cibles inertes avant toute proximité humaine ;
  autorisation de campagne distincte obligatoire, Go explicite ensuite.
