# SH-09 — Rapport logiciel isolé du lot A

Date : 2026-10-30. Périmètre : A1–A6 du
[backlog](07_suivi_humain_marqueur_backlog.md), pas la recette globale SH-09.

**Verdict : conforme dans le périmètre logiciel isolé décrit ici.**
Socle livré et vérifié ; aucune clôture globale SH-05/SH-09, aucune dépendance
matérielle satisfaite, aucun Go mobile humain. Sur le robot, le suivi humain
moteur reste refusé. Ce verdict ne vaut ni réalisation ni qualification
P2/P3/P4/P5/P6, audio, perception ou performance Pi.

## 1. Référence et configuration

- Référence Git : `a5c397b483fc0eda0938e5d444ecf1a3968430f9`.
  Arbre propre avant modification, aucun changement local préexistant réécrit.
  Version livrée : modifications non commitées identifiées par les empreintes
  de section 7.
- Exécution locale CPython 3.13.11 ; paquet pytest déjà installé dans
  l'environnement du projet, chargé explicitement après les gardes.
  Aucune installation, restauration de dépendance, recherche de modèle ou
  connexion réseau.
- Référence exportée en lecture seule hors arbre de travail : sources, tests,
  configuration, script documentaire de gardes LLM et manifeste du commit.
  Même sélection et mêmes attendus sur référence et version modifiée.
- Driver `SmartCar2WD`, `follow_object` et `target_tracking` non modifiés,
  vérification par diff Git. Les tests historiques n'ont pas été réécrits.
- Les six sujets documentaires SH-02, A1–A6 et le bloc détaillé SH-05 à SH-11
  ont été comparés au commit : contenu intégral préservé.

**Paramètres exclusivement fictifs :** horloge initiale 0 puis armement à 1,
fraîcheur P5 0,25 unité-seconde simulée, convention `âge <= budget` accepté,
frontières 0,249 / 0,250 / 0,251, échéance absolue de mission à 7.
Les scénarios de mouvement emploient des durées simulées de 1 à 4 secondes.
Aucune de ces valeurs ne propose un réglage réel.
Les 3 secondes d'attente avant recherche balle sont une règle préexistante,
inchangée, pas un seuil humain ni une nouvelle limite de sécurité.

Borne externe du harnais : 120 secondes murales par processus, distinctes du
temps simulé ; marge pour la sélection locale observée et arrêt explicite en
cas d'emballement. Synchronisations concurrentes bornées à 2 secondes :
dépasser cette borne échoue le test, sans résultat de remplacement.
Ces bornes ne qualifient aucun délai Pi/P3/P5/P6.

## 2. Réalisation et choix techniques

Exigences approuvées : celles du backlog, inchangées. Les choix suivants ont
été validés automatiquement comme dérivés de ces acquis :

| Sujet | Réalisation et conséquence |
|---|---|
| A1 | [Ports logiques typés](../../src/irobot/interfaces/protection.py) : P5 en lecture seule, preuve, demande d'inhibition, journal factice ; préconditions humaines inconnues par défaut invalides. Aucun port de réarmement |
| A2 | [L2](../../src/irobot/interfaces/robot_controller.py) garde directions, temporisations, vitesse et restaurations. Façade de mission sans délégation ni accès public au driver ; commandes internes sans permis refusées. Identifiants mission/contexte/armement/génération de contrôleur |
| A3 | Présence `absent`/`present`, distincte des faits de qualification synthétiques. Champ historique omis = absent, valeur invalide = erreur. Présente sans ports = erreur ; retour manquant ne rétrograde jamais vers absence. [Assemblage live](../../src/irobot/interfaces/voice_runtime.py) protégé refusé avant import matériel, faute d'adaptateur réel |
| A4 | Runtime commun propriétaire de l'admission et du cycle de vie ; coordination des permis conservée avec L2 pour sérialiser émission/invalidation. Garde d'émission courte distincte du verrou d'évaluation : stop/P1 peuvent atteindre le double même si les préconditions sont bloquées. Boucle synchrone surveillée au repos, jamais fil de preuve indépendant |
| A5 | [Matrice standard-library](../../tests/isolated/lot_a_cases.py), [contrat comparatif](../../tests/isolated/legacy_contract.py) et sélection historique explicite. Oracles fixés avant exécution, observation moteur indépendante du journal testé |
| A6 | Rapport présent, résultats effectifs et limites. Fin du seul lot isolé ; qualifications et tickets globaux restent ouverts |

P5 conserve les dates du retour et de transition fournies par sa source :
relire ne rajeunit pas. Après événement verrouillant, observation inhibée puis
transition armée strictement postérieure nécessaires ; jeton différent seul,
retour ancien, rétablissement ou effacement du drapeau logiciel insuffisants.
Réarmement observé sans nouvelle demande : aucune commande.

La façade garde également les résultats dans
[l'exécuteur](../../src/irobot/domain/orchestrator/executor.py) :
un ancien résultat n'est pas réutilisé et une étape obsolète n'est pas exécutée.
Le [contrôleur de langage](../../src/irobot/interfaces/language_controller.py)
et le runtime propagent un défaut de protection sans succès apparent, étape
suivante ou réessai.

Les demandes humaines sont refusées avant routage objet, filtrage d'étape
malformée ou expansion de plan. `follow_person` n'est pas `follow_object`.
Les missions humaines nominales utilisent uniquement un fournisseur de skill,
de conditions et une sortie moteur **explicitement factices** dans les tests.
La perception marqueur, la loi SH-06 et l'intégration naturelle complète SH-07
ne sont pas réalisées.

La réservation suspendue survit à la fin effective d'un worker. Reprise locale
sans LLM : même mission, même état utile de contexte, même échéance ; nouveau
jeton de contexte invalidant les commandes antérieures. Fin/stop nettoient cet
état. Un listener ne renouvelle pas la preuve à la place d'un worker bloqué.

## 3. Isolation avant imports et collecte

[Lanceur](../../tests/isolated/run_lot_a.py) obligatoire avec `-I -S` :

- pas de chargement automatique de `site`, `.pth`, plugins pytest ou
  `conftest` ; seuls les fichiers explicitement sélectionnés sont collectés ;
- nouveaux cas nommés `lot_a_cases.py`, chargés explicitement par le lanceur,
  pas découverts automatiquement comme tests pytest hors de leurs gardes ;
- gardes d'import pour matériel, GPIO, caméra, audio, Bluetooth, Vosk et tests
  matériels/intégration ; modules complémentaires audio/Vosk/HTTP explicitement
  factices, installés avant les imports du projet ;
- audit refusant sockets, sous-processus, accès aux dispositifs et recherche
  dans `models`/`llama.cpp`. HTTP sans double de scénario = erreur, jamais réseau ;
- trois sondes de politique appellent directement les gardes avec des données
  synthétiques (import GPIO, événement socket, ouverture GPIO) : trois refus.
  Elles n'importent, ne connectent et n'ouvrent aucune ressource réelle ;
- sorties P5, moteur, preuve, demande d'inhibition et journal observées
  séparément. Observateur indisponible : assertion inconclusive, jamais succès
  par liste vide ;
- fichiers synthétiques temporaires nettoyés ; vérification des threads
  résiduels à la fin. Pas de service, serveur ou processus externe lancé.

Toutes les campagnes finales : **0 tentative d'accès interdit observée,
0 thread résiduel, 3 sondes synthétiques refusées par processus**.
Ce constat porte sur les opérations interceptées et les chemins sélectionnés,
pas sur une qualification de l'OS ou une garantie physique.

## 4. Attendus indépendants et résultats obtenus

Les nombres de cas ci-dessous sont ceux de la matrice standard-library finale.
Ses 120 cas rattachés aux oracles, plus un cas de configuration, donnent
**121 tests réussis, aucun échec ni erreur**.

| Oracle | Cas | Attendu fixé / obtenu |
|---|---:|---|
| A-O1 | 36 | 17 conditions invalidées séparément avant admission puis avant émission : refus avec nom de condition, aucun appel moteur non nul ; nominal synthétique émet `forward`, absence de mission, échéance absente ou atteinte refusent |
| A-O2 | 11 | P5 absent/inconnu/incohérent/erreur/inhibé bloque ; 0,249 et 0,250 acceptés, 0,251 refusé ; même objet P5 relu sans date modifiée. Panne en mission : fin verrouillée |
| A-O3 | 9 | Identifiants mission/contexte/armement/génération anciens, entrée interne et changement P5 pendant les préconditions : refus avant sortie. Zéro accessible. Deadline franchie pendant calcul refuse. Résultat précédent effacé, skill obsolète non exécutée |
| A-O4 | 3 | Conditions évaluées avant émission, preuve après traitement complet ; cycles au repos changent la preuve. Cycle partiel/attente contrôlée : aucune preuve de ce cycle. Listener sans renouvellement pour worker bloqué |
| A-O5 | 5 | Demande `startup`, puis demande sur cause P6 au repos sans répétition sur la même transition. Stop, obstacle, perception, audio ordinaires : aucune nouvelle demande d'inhibition |
| A-O6 | 27 | P1/P3/P6/inhibition inconnue contre les six permutations stop/échéance/confirmation : état verrouillé et causes conservées. Succès tardif reclassé, aucune relance. P1/stop concurrents d'un calcul incomplet : zéro observé avant libération du calcul, aucun mouvement ultérieur |
| A-O7 | 2 | Séquence complète : jeton simplement différent, ancien retour et effacement logiciel refusés ; inhibition puis armement postérieur seuls ne bougent pas ; nouvelle demande admissible ensuite. Une demande déclenchant la première observation de l'armement est refusée, non conservée : autre demande nécessaire après observation. Redémarrage rapide demande inhibition et refuse l'ancien armement |
| A-O8 | 2 | Worker réellement terminé en suspension : réservation conservée, demande concurrente non mémorisée. Reprise locale même objet de contexte/compteur utile, deadline 7 inchangée, ancien jeton invalidé ; stop et échéance terminent sans reprise automatique |
| A-O9 | 11 | Sept formes humaines, entrées texte/transcription/intention, faux LLM composé/malformé/imbriqué : refus intégral, aucun moteur ni repli balle/primitive. Assemblage live présent refusé avant import matériel |
| A-O10 | 7 | Même runtime balle → humain synthétique → balle ; absent : humain refusé. Présent : avance, recul, corrections gauche/droite et balayage balle permis, sans conditions humaines. Attente balle 3 s sans balayage puis scénario 4 s avec balayage. P5 perdu : une tentative, une étape, pas de restauration de vitesse non nulle |
| A-O11 | 4 | Pannes preuve/inhibition/journal et zéro moteur : erreurs visibles, pas de succès de remplacement. Journal en panne : suspension, zéro observé indépendamment, pas d'inhibition P1 artificielle. Zéro échoué : aucune preuve d'application ni de cycle fabriquée |
| A-O12 | 3 | Deux replays recalculés pour chaque scénario, mêmes attendus fixes ; changement d'ordre change effectivement la décision. Replay runtime : `accepted,suspended,rejected,success,accepted`, sorties `forward,forward,forward,backward`, réservation finale vide. Observateur absent traité comme inconclusif |

Le cas supplémentaire vérifie les erreurs de présence/ports et l'impossibilité
de rétrograder la présence en réaffectant la propriété publique.
Les tests comparent des listes de commandes effectivement reçues par le
double, pas le journal du logiciel pour se donner raison.

### Non-régression

Sélection historique : neuf fichiers unitaires déclarés dans le lanceur :
suivi objet, câblage, scénario balle jaune, arrêt de primitive, urgence,
primitives, contrôleur de langage, gardes de plan et runtime vocal.

| Campagne | Résultat effectif |
|---|---|
| Commit de référence, sélection historique | **214 réussis, 7 désélectionnés** |
| Version livrée, même sélection historique | **214 réussis, 7 désélectionnés** |
| Contrat standard-library sur référence | **4 réussis** |
| Même contrat sur version livrée | **4 réussis** |

Contrat complémentaire : sorties exactes avance/recul/rotation/vitesse restaurée/
stop ; suivi balle approche/maintien/recul dans la même instance ; stop pendant
primitive sans étape suivante ni réessai ; plan invalide refusé intégralement.
Avec protection présente, les compléments A-O10 vérifient le raccordement L2 :
les tests historiques passant directement un `World` ne sont pas rebaptisés
preuves du garde.

## 5. Écarts et historique conservés

1. Première tentative : `ModuleNotFoundError: pytest`, avant collecte.
   Diagnostic initial de dépendance inaccessible, pas résultat de tests.
   Inspection ultérieure : paquet déjà installé ; chemin ajouté explicitement
   **après** les gardes, sans exécuter `.pth` ni installer quoi que ce soit.
2. Première matrice : 81 cas, 79 réussis, deux échecs. Stop protégé incorrectement
   reclassé en urgence ; corrigé. Retour inhibé du scénario placé au même instant
   que la transition armée : injection incohérente, corrigée à une transition
   ultérieure sans changer l'attendu P6.
3. Extensions : 82, puis 104, puis 106 cas réussis ; ajout des changements
   intercalés, réservation, données utiles, concurrence et listener bloqué.
4. Première matrice élargie de 118 cas : un échec et une erreur.
   Observation inhibée perdue lors du classement P1 : corrigée en conservant
   l'observation courante si elle satisfait la barrière temporelle.
   Cas de balayage à exactement 3 s : il ne dépassait pas l'attente historique.
   Scénario complété par **absence de balayage à 3 s** puis **balayage à 4 s**,
   sans modifier seuil ni comportement balle.
5. Dernière matrice : **121/121**, avec échéance humaine obligatoire et ordre
   strict observation d'armement puis demande explicitement vérifiés. Dernière sélection historique :
   **214/214** sur référence et version livrée.
   Le filtre initial `not main` écartait involontairement `stop maintenant` ;
   retiré, ce cas a été exécuté sur les deux versions.

Aucun attendu historique adapté pour faire passer une régression. Aucun écart
final observé dans cette sélection, aucune anomalie préexistante détectée par
ces campagnes. Cela ne constitue pas un audit de toute la suite ou du projet.

## 6. Non exécuté, limites et portes suivantes

- Sept cas de préchauffage/assemblage vocal et configuration associée
  désélectionnés, hors preuve du socle ; aucune promesse sur le préchauffage.
- Suite globale, intégration LLM avec modèles/serveur, tests matériels,
  adaptateur réel P5, GPIO, caméra, capteurs, Bluetooth/audio réels :
  **non exécutés**. Pas de découverte globale.
- Perception marqueur, loi SH-06, intégration humaine SH-07 complète et chaîne
  d'annonces/journal réel SH-08 : **non réalisées/non qualifiées par ce lot**.
- Inhibition observée = état du **double P5 scripté**. Une demande d'inhibition
  ne modifie pas automatiquement ce double. Arrêt demandé, tentative de zéro
  et zéro effectivement reçu par le double sont des faits distincts.
  **Aucune immobilisation physique mesurée**, protection réelle attestée,
  annonce réelle, audition ou persistance après coupure affirmée.
- Aucune charge/mesure Pi SH-10, moyenne/p95 ou durée simulée ne qualifie un
  délai obligatoire. Aucun délai ni composant matériel nouveau retenu.
- P2/P3/P4/P5/P6 restent à réaliser et qualifier. Famille P6 non choisie,
  accès sûr solo non démontré ; proximité et audio ne le démontrent pas.
  Budget d'arrêt, fraîcheur réelle P5, freinage, couverture obstacle,
  perception et recette physique restent ouverts.
- Collecte minimale locale : code, cas synthétiques et présent rapport.
  Pas d'image, audio, identité personnelle, export ou donnée réelle ajoutée.
  Journal humain double en mémoire sans garantie de persistance ; fichiers
  temporaires de tests nettoyés, pas de purge de données historiques.
  Les comptes rendus locaux de campagne ne valent pas clôture utilisateur.
  Politique SH-08 inchangée, aucune nouvelle durée de conservation.

### Critères A6

1. Socle et raccordements réalisés : sections 2/4, sorties moteur observées.
2. Douze oracles exécutés aux niveaux pertinents : unités, intégration et
   replays ; aucune obligation du lot laissée bloquée dans la matrice finale.
3. Non-régression ciblée de référence et compléments présents/absents exécutés.
4. Refus humain réel testé ; nominaux humains exclusivement à moteur factice,
   aucun commutateur live ou adaptateur réel livré.
5. Rapport relié aux versions/cas/attendus/obtenus et vérifié par comparaison
   des résultats, empreintes et préservation documentaire.

**Étape suivante proposée, non commencée :** revue et validation explicite du
dossier du lot A, puis choix du prochain lot isolé ou de l'étude documentaire
des protections. Aucune campagne matérielle, Pi/audio ou activation humaine
n'est engagée par ce rapport.

## 7. Reproduction et empreintes

Depuis `conf_raspberrypi`, sans installation :

```bash
.venv/bin/python -I -S tests/isolated/run_lot_a.py --stdlib
.venv/bin/python -I -S tests/isolated/run_lot_a.py
.venv/bin/python -I -S tests/isolated/run_lot_a.py --legacy-stdlib
```

Le dernier argument facultatif est le chemin d'une référence exportée du
commit, contenant `src`, `tests`, `config`, le script de gardes et le manifeste.
Les deux commandes de non-régression acceptent ce chemin. Ne pas utiliser le
mode `--stdlib` du nouveau socle sur l'ancien commit dépourvu de ce socle.

Empreintes SHA-256 du code exécuté (documents exclus pour éviter auto-référence) :

| Fichier | SHA-256 |
|---|---|
| `src/irobot/interfaces/protection.py` | `b1d5a3bee308c722f58fcb515499702d408844f8a3e307a84c252be0c73a8de5` |
| `src/irobot/interfaces/robot_controller.py` | `1b585603fe5d6851e401a973224942bbf9cabdd91463b8b74c14ba592feccd9e` |
| `src/irobot/interfaces/voice_runtime.py` | `a3a666ebf3fa49e0982a90898222e4b30e03e7381ca9781daa3fb3581b3a64d2` |
| `src/irobot/interfaces/language_controller.py` | `8006329fd0f352ac44a94fb95bb82a9c615a45910aa22600726b0c83c6edda35` |
| `src/irobot/interfaces/intent_parser.py` | `93d8ee7a1eed07e36f6e9d6922cf253a68ddc7c971fa78446cf469358c6a4d2d` |
| `src/irobot/interfaces/plan_guards.py` | `8d9fd2b5cb2aff206cf143b44a82cda22921fd8cbb15a8b754cf1b63be175a18` |
| `src/irobot/interfaces/__init__.py` | `7b6da8aea7403808710e80aeed445084c3512a9074a144d755743d93c688a0af` |
| `src/irobot/domain/orchestrator/executor.py` | `c248dbf857e601ed5e352e8e20b6d11e952a48fcb47e6309d3c1392baa071254` |
| `src/irobot/config/settings.py` | `1403cd5dd55b7c6acffacdbd006ce18a129786534c252d465f469923106a9dc8` |
| `tests/isolated/run_lot_a.py` | `7d64c5279d3c9d46f3e914f9ed49bdfed5a1f57f7dfd2480beed39006334d3de` |
| `tests/isolated/lot_a_cases.py` | `d86567f98a2b1cd3662aae2ae08c56142c1143fb4543c0bde878fbe810e2d7ea` |
| `tests/isolated/legacy_contract.py` | `20ec49c3495a72f04f296b1f76904d6c8a64e1b6c04f2023291876ec649860a8` |
