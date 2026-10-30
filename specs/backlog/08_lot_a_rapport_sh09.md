# SH-09 — Rapport logiciel isolé du lot A

Date : 2026-10-30. Périmètre : A1–A6 du
[backlog](07_suivi_humain_marqueur_backlog.md), pas la recette globale SH-09.

**État courant après corrections autorisées : conforme dans le périmètre
logiciel isolé effectivement éprouvé du lot A ; dossier corrigé validé
explicitement par l'utilisateur le 2026-10-30, pour ce seul périmètre.**
Voir la section 9 : E1–E6 traités, 164 cas isolés réussis, non-régression
comparée et critères A6 réexaminés. Ce verdict n'est ni une garantie
universelle, ni une clôture globale SH-05/SH-09, ni un Go mobile humain.

**Verdict initial de revue contradictoire du 2026-10-30, conservé : non
conforme ; fin non confirmée.** La section 8 consigne la revue avant les
réponses utilisateur autorisant les corrections, dont celle de l'attendu
synthétique contraire au non-recul humain. À ce stade initial, aucun
correctif de code n'était autorisé ou appliqué.

**Verdict initial de campagne, conservé comme historique : conforme dans le périmètre logiciel isolé décrit ici.**
Socle livré et vérifié ; aucune clôture globale SH-05/SH-09, aucune dépendance
matérielle satisfaite, aucun Go mobile humain. Sur le robot, le suivi humain
moteur reste refusé. Ce verdict ne vaut ni réalisation ni qualification
P2/P3/P4/P5/P6, audio, perception ou performance Pi.

Les sections 1 à 7 conservent le dossier de livraison et ses conclusions
initiales ; leurs affirmations générales de conformité sont réévaluées en
section 8, puis après corrections en section 9. Elles ne valent pas validation
utilisateur. La mention historique « non commité » de section 1 est rectifiée
par l'état Git effectivement constaté en section 8.1.

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

## 8. Revue contradictoire du 2026-10-30

**Historique de la phase initiale, avant autorisation des correctifs.**
Les mentions « non appliqué », « décision en attente » et les localisations
de code ci-dessous décrivent la version livrée `b1864aba3e78560fbb7f4ab020e886b1766cfa2a`.
Les décisions reçues et les preuves de correction sont consignées en section 9,
sans effacer le constat initial ni ses résultats.

### 8.1 Autorisation, versions et préservation

Autorisation limitée à la revue et aux mises à jour documentaires factuelles.
Ni approbation du lot, ni correctif, ni lot suivant, ni Go mobile humain.

- **État effectivement observé avant la revue :** arbre Git propre, index
  propre, HEAD `b1864aba3e78560fbb7f4ab020e886b1766cfa2a`, parent
  `a5c397b483fc0eda0938e5d444ecf1a3968430f9`. Le lot est déjà commité dans ce
  HEAD, contrairement à l'état transmis « non commité ». Aucun commit,
  écrasement ou révocation effectué pendant la revue. L'assertion de section 1
  décrit l'état consigné lors de la livraison, pas l'état Git de cette reprise.
- **Empreintes reproduites :** les douze SHA-256 de section 7 correspondent
  exactement aux douze fichiers persistants examinés et exécutés.
- **Préservation reproduite par comparaison au parent de référence :** bloc
  des six sujets SH-02 identique ; cadrage A1–A6 identique ; chacun des sept
  blocs SH-05 à SH-11 identique, avec ses six sujets détaillés. Aucun acquis
  rouvert. Section 1 du backlog inchangée. Les ajouts de revue ne remplacent
  pas ces décisions.
- Tests unitaires historiques, script de gardes comparatif, driver
  `SmartCar2WD`, `follow_object` et `target_tracking` : aucun diff entre la
  référence et la livraison. Aucun attendu ni test modifié par cette revue.
- Liens relatifs du rapport et de `tests/README.md` : cibles locales
  existantes. Les liens ajoutés par la revue sont également contrôlés.

### 8.2 Preuves effectivement reproduites

Avant exécution : lecture du lanceur entier, de sa sélection explicite, des
imports, des doubles P5/moteur/horloge/ports, de la collecte `load_tests`, des
fixtures HTTP factices et du chargement documentaire du script de gardes.
Ce script est importé pour ses fonctions ; son point d'entrée HTTP n'est pas
appelé. Aucun pytest global, aucune découverte matériel/intégration.

La référence exportée de la campagne précédente n'est pas utilisée et son
existence n'est pas attestée ici. **Un nouvel export local temporaire distinct**
du commit de référence a été créé pour cette revue, après contrôle des entrées
Git : 91 blobs réguliers, sans lien symbolique ni sous-module, sans `.git`,
`.venv`, `target` ou modèle. Chaque blob exporté a été comparé au commit ;
export rendu non inscriptible avant tests. Les tests unitaires historiques et
le script de gardes sont identiques à ceux de la livraison ; la documentation
de tests a, elle, été enrichie lors de la livraison. Cet export n'est pas une
archive retrouvée de l'ancienne session.

Commandes de section 7 seulement, avec `-I -S`, et leur argument facultatif
pour ce nouvel export :

| Version / campagne reproduite | Résultat de cette revue |
|---|---|
| HEAD livré, `--stdlib` | 121 tests, OK ; 1,520 s murales rapportées par unittest |
| HEAD livré, sélection pytest ciblée | 214 passed, 7 deselected ; 10,84 s |
| HEAD livré, `--legacy-stdlib` | 4 tests, OK ; 0,143 s |
| Nouvel export de référence, sélection pytest ciblée | 214 passed, 7 deselected ; 11,41 s |
| Nouvel export de référence, `--legacy-stdlib` | 4 tests, OK ; 0,084 s |

Pour chacun des cinq processus : code de sortie 0, zéro tentative interdite
observée, zéro thread résiduel, trois sondes synthétiques refusées sans
opération réelle. Les sept désélections restent celles du filtre
`not warmup and not warm_up`, sans filtre `not main`. Le préchauffage n'est pas
qualifié. Ces durées sont celles du harnais local, pas des performances Pi,
ni des délais de protection.

Les sept cas exclus de `test_voice_runtime.py` sont explicitement :
`test_warm_up_sends_plan_system_prompt_in_background`,
`test_warm_up_swallows_errors`,
`test_text_mode_sends_real_request_after_warmup`,
`test_text_mode_failed_warmup_still_processes_command`,
`test_text_mode_warmup_wait_timeout_still_processes_command`,
`test_continuous_mode_does_not_wait_for_warmup` et
`test_llm_warmup_wait_seconds_env`. Leur exclusion ne constitue ni succès ni
qualification de l'assemblage vocal.

Les résultats de sections 4–5 restent des **résultats historiques consignés**.
Le tableau ci-dessus constitue une nouvelle série distincte qui les reproduit
sur les fichiers identifiés ; il ne réécrit pas leur chronologie. Aucun nouvel
essai des contre-exemples statiques ci-dessous n'a été ajouté ni exécuté :
la revue est limitée aux commandes autorisées et ne modifie pas les tests.

### 8.3 Écarts et correctifs bornés proposés, non appliqués

**E1 — La transcription peut admettre la demande qui observe l'armement.**

- **Exigence validée :** A4/A-O7 et précision de réalisation : observation
  d'un armement postérieur, puis seulement nouvelle demande ; la demande
  déclenchant la première observation est refusée et non conservée.
- **Chemin et preuve statique :**
  [handle_transcript](../../src/irobot/interfaces/voice_runtime.py#L1547)
  appelle `supervise_once()` avant `handle_text_as_plan()`, qui appelle
  [admit](../../src/irobot/interfaces/robot_controller.py#L155).
  Sans worker ni réservation, après observation inhibée puis transition armée
  encore non observée, une transcription de primitive fait d'abord renseigner
  `_ready_armament`. L'admission de cette même demande trouve alors
  `armament_at_request` déjà égal au nouvel armement et peut l'accepter.
  Le test A-O7 reproduit vérifie l'appel direct à `admit`, pas ce chemin.
- **Impact :** A-O7 non démontré de bout en bout ; ordre obligatoire contourné
  par le prétraitement d'une demande. Le refus humain nominal ne corrige pas
  cette règle commune aux admissions protégées.
- **Proposition :** figer l'état d'observation à la réception de la demande,
  avant toute supervision susceptible de le changer ; refuser cette demande
  si elle provoque la première observation. Compléter le test via transcription
  synchrone et worker, sans file d'attente de demande.

**E2 — Le refus humain lexical laisse un repli vers `follow_object/yellow`.**

- **Exigence validée :** A2/A-O9, refus humain intégral sur les entrées réelles,
  sans conversion en suivi objet ni exécution partielle.
- **Chemin et preuve statique :** « suis ma femme » ne correspond pas à
  [requests_human_follow](../../src/irobot/interfaces/plan_guards.py#L107) :
  `ma` n'est pas un déterminant reconnu. Le
  [parseur](../../src/irobot/interfaces/intent_parser.py#L214) accepte ensuite
  le verbe générique `suis`, produit `follow_object` sans couleur ; le validator
  accepte sa cible `None`. Le
  [comportement objet](../../src/irobot/domain/skills/behaviors/follow_object.py#L88)
  remplace la cible absente par `yellow`. Le contrôleur de langage et le runtime
  sans LLM partagent cette garde. Une composition telle que « avance puis suis
  ma femme » n'est donc pas non plus refusée intégralement par cette garde.
- **Impact :** conversion interdite présente dans le code ; émission possible
  selon les doubles de perception ou les capacités objet disponibles. Aucun
  mouvement physique n'est affirmé ni essayé. Les sept formulations testées
  ne constituent pas une preuve de refus intégral.
- **Proposition :** compléter la garde commune et fermer le repli objet pour
  les demandes humaines non prises en charge ; tests indépendants texte,
  transcription, intention et plans composés, sans toucher aux attendus balle
  explicites. Une éventuelle restriction nouvelle des demandes objet ambiguës
  doit être explicitée et approuvée, pas introduite silencieusement.

**E3 — Un oracle synthétique accepte explicitement le recul humain.**

- **Exigence validée :** SH-05 sujet 3, aucun recul humain ; A1/A-O1,
  préconditions humaines acquises obligatoires et mouvement envisagé autorisé.
  Le hors-lot SH-06 ne rend pas licite un mouvement humain déjà interdit.
- **Preuve effectivement reproduite :**
  [test_o3_no_public_delegation_or_internal_temporized_bypass](../../tests/isolated/lot_a_cases.py#L266)
  admet par `rig.human()`, suspend, reprend la même mission, puis exige
  `bind(new).backward()` et la liste moteur exacte `["backward"]`.
  Ce cas a réussi dans les 121 tests de cette revue.
  [L2](../../src/irobot/interfaces/robot_controller.py#L260) accepte cette
  direction si les 17 booléens synthétiques sont vrais ; le fournisseur de
  conditions ne reçoit pas la commande pour vérifier sa nature.
- **Impact :** un succès de test est ici une preuve d'acceptation contraire
  à une exigence, pas de conformité. Les inversions des 17 booléens ne
  démontrent pas à elles seules les limites de la commande réellement émise.
  De plus, leurs axes sont dérivés de
  `HumanConditions.__dataclass_fields__` : ils couvrent les conditions
  implémentées, mais ne constituent pas une liste indépendante d'exigences
  capable, à elle seule, de révéler l'absence d'une condition dans le code.
- **Proposition :** refuser le recul des réservations humaines à L2, tout en
  conservant le recul balle ; éprouver les directions et les écritures de
  vitesse selon les autorisations applicables, sans inventer de plafond PWM
  équivalent à une vitesse physique. Renforcer cet oracle selon l'exigence,
  avec une liste d'obligations indépendante du type testé, et conserver son
  résultat initial ci-dessus ; aucun attendu historique
  non-régressif ne doit être affaibli.

**E4 — Un arrêt déjà requis peut attendre le fournisseur de conditions.**

- **Exigence validée :** SH-05 sujet 2, A4 étape 3 ; arrêt prioritaire dès
  nécessité connue, échéance initiale non prolongée.
- **Chemin et preuve statique :**
  [supervise](../../src/irobot/interfaces/robot_controller.py#L305) ajoute
  `stop`/`deadline` aux causes ordinaires, puis appelle
  `reservation.conditions()` avant `self.stop()`. Si le callback bloque alors
  que la mission émettait déjà, le zéro de ce chemin attend son retour malgré
  l'échéance déjà détectée. Un appel préalable à `request_emergency_stop`
  contourne cette attente pour le stop local ; il ne couvre pas l'échéance.
- **Impact :** les tests P1/stop concurrents, qui appellent un arrêt direct,
  ne prouvent pas ce chemin. Aucun délai physique n'est déduit de ce défaut,
  ni aucune intervention effective de P3 supposée.
- **Proposition :** remettre le zéro avant les callbacks supplémentaires dès
  qu'un arrêt est requis ; classer ensuite l'état et toutes les causes.
  Test borné d'échéance déjà atteinte avec conditions bloquées : zéro observé
  avant libération, aucune preuve de cycle partiel, aucune nouvelle émission.

**E5 — L'échec du zéro initial empêche la demande d'inhibition de démarrage.**

- **Exigence validée :** A1/A-O5, demande systématique au démarrage protégé ;
  A-O11, panne moteur explicite sans confirmation fabriquée.
- **Chemin et preuve statique :**
  [constructeur](../../src/irobot/interfaces/robot_controller.py#L59) appelle
  `stop()` puis `inhibition.request("startup")` sans protection de ce second
  appel en cas d'erreur du premier. Si le double zéro lève, la demande n'est
  pas tentée. L'erreur reste visible, mais cette obligation n'est pas remplie.
  Le cas reproduit de panne du zéro intervient après construction.
- **Impact :** A-O5/A-O11 incomplets sur une panne du chemin de démarrage.
- **Proposition :** garantir la tentative d'inhibition même si le zéro
  initial échoue, en préservant les erreurs explicites des deux ports et sans
  prétendre que l'un des deux effets a réussi ; ajouter ce cas isolé.

**E6 — Régression statique de l'entrée vocale `--once`.**

- **Exigence validée :** A2, absence de refonte/régression des parcours
  existants hors protection ; A6.3, anomalies obligatoires non compensées.
- **Chemin et preuve statique :**
  [listen_once](../../src/irobot/interfaces/voice_runtime.py#L1501) appelle
  `resolve_input_device` sans définition ni import visible dans sa portée.
  L'import global présent à la référence a été retiré ; l'import ajouté dans
  `listen_forever` est local à cette autre méthode. L'entrée `--once` conduit
  donc à `NameError` avant la transcription.
- **Impact :** non-régression de la sélection reproduite, mais pas de ce
  chemin. Aucun audio réel exécuté pour confirmer ce constat statique.
- **Proposition :** import local dans l'entrée concernée, après la frontière
  d'isolation ; test uniquement avec résolveur et transcription factices,
  sans construire de matériel ni charger de modèle.

E1, E2, E4, E5 et E6 sont des constats statiques sur les sources identifiées,
pas des résultats de nouveaux scénarios exécutés. E3 est aussi observé par
un cas existant reproduit. Tous nécessitent traitement et preuves ciblées
avant de reconsidérer la conformité du périmètre concerné. Aucun correctif
ni nouvel attendu n'a été implémenté dans cette session.

### 8.4 Verdict par oracle et critère A6

Les attendus indépendants sont ceux du cadrage A5, pas le verdict ou les
compteurs de la matrice. La plupart des attendus de tests sont littéraux et
indépendants de la décision calculée ; E3 montre cependant qu'un littéral
indépendant peut lui-même contredire l'exigence source.

| Oracle | Preuve reproduite et portée de la revue |
|---|---|
| A-O1 | 36 cas : 17 conditions séparées à l'admission et à l'émission, nominal et échéance. Inversions vérifiées ; bornes de la commande humaine insuffisantes, E3 |
| A-O2 | 11 cas : absents/inconnus/incohérents/inhibés/erreur, frontière fictive et absence de rajeunissement vérifiées ; aucune qualification P5 réelle |
| A-O3 | 9 cas : identifiants, accès public/délégation, entrée interne, changements intercalés, résultats et échéance vérifiés sur les scénarios ; E3 interdit de généraliser la conformité de toute commande admise |
| A-O4 | 3 cas : ordre de preuve, repos, cycle partiel et listener bloqué vérifiés ; pas de générateur indépendant constaté ; E4 exige un complément d'arrêt avant callback, sans preuve partielle |
| A-O5 | 5 cas : startup nominal, P6 au repos sans répétition et arrêts ordinaires vérifiés ; exception au zéro de startup non couverte, E5 |
| A-O6 | 27 cas : P1/P3/P6/inhibition inconnue, permutations d'événements, résultat tardif, stop/P1 concurrents vérifiés ; les permutations d'un tuple ne sont pas toutes les chronologies d'arrivée possibles ; E4 reste ouvert |
| A-O7 | 2 cas directs : barrières temporelles, observation puis nouvelle demande et redémarrage rapide vérifiés ; chemin transcription non couvert et contraire à l'ordre, E1 |
| A-O8 | 2 cas : worker terminé, réservation, même contexte utile, nouvelle identité de contexte, échéance inchangée et nettoyage vérifiés ; traitement d'échéance avant callback bloqué à compléter, E4 |
| A-O9 | 11 cas : formes sélectionnées et LLM composé/malformé/imbriqué refusés ; assemblage live présent refusé avant import ; refus humain intégral non établi, E2 |
| A-O10 | 7 cas du socle, sélection historique et contrats des deux versions : recul/rotations/balayage balle, primitives, stop, perte P5 et restauration gardée vérifiés dans la sélection ; entrée `--once` régressée hors sélection, E6 |
| A-O11 | 4 cas : ports en erreur, zéro tenté/reçu et preuve non fabriquée vérifiés sur ces injections ; panne du zéro initial manquante, E5 |
| A-O12 | 3 cas : replays recalculés, ordre discriminant et observateur moteur absent vérifiés ; cinq processus isolés sans tâche résiduelle ; ne couvre pas les contre-exemples statiques |

**Observateurs :** `Motor.commands` et les tentatives de zéro sont alimentés
par le double moteur, indépendamment du journal logiciel testé ; les ports
preuve/inhibition/journal ont leurs collectes et injections distinctes.
Le scénario P5 ne change pas automatiquement à la demande d'inhibition.
Les cas d'ordre comparent ces flux à des attendus fixes, pas aux conclusions
du journal. Le cas `nonzero(None)` échoue explicitement comme inconclusif ;
les rendez-vous concurrents non observés échouent par assertions bornées.
Pas d'observateur nécessaire signalé indisponible dans les cinq campagnes.
Cela ne qualifie ni une instrumentation externe, ni toutes les pannes
silencieuses possibles d'un collecteur, ni l'OS. Une future perte d'observation
invalidera la campagne concernée, sans être interprétée comme absence de sortie.

| Critère obligatoire | Verdict de revue |
|---|---|
| A6.1 — réalisation/raccordements et tous chemins gardés | Non satisfait intégralement : E1/E2/E3/E4/E5 ; point L2 et façades présents, mais obligations encore violées |
| A6.2 — douze oracles sans écart obligatoire/cas manquant | Non satisfait : succès reproduits limités aux cas existants ; E3 contredit la source et compléments E1/E2/E4/E5 manquants |
| A6.3 — non-régression absente puis présente | Sélections reproduites sur les deux versions ; pas de conformité intégrale du parcours existant `--once`, E6 |
| A6.4 — refus humain réel et nominal exclusivement factice | Doubles nominaux isolés, aucun adaptateur réel/commutateur live livré ; refus intégral non satisfait, E2 |
| A6.5 — rapport vérifié et traçabilité | Douze empreintes, liens, références, décisions et résultats contrôlés ; rapport initial corrigé par cet addendum, validation utilisateur encore à obtenir ; conformité ne peut plus être déduite des sections historiques |

### 8.5 Conclusion, limites et décision attendue

**Verdict motivé : non conforme dans le périmètre logiciel du lot A.
Ne pas confirmer sa fin.** Les succès reproduits attestent un sous-ensemble
utile, pas les obligations manquantes ni l'exactitude de l'ancien verdict.
SH-05/SH-09 restent globalement ouverts. Choix technique, exigence validée,
historique consigné, preuve reproduite et analyse statique sont distingués
ci-dessus ; aucun contre-exemple non exécuté n'est présenté comme un nouveau
résultat de test.

Aucun matériel, GPIO, caméra, capteur, Bluetooth/audio réel, adaptateur P5 réel,
réseau, recherche/chargement de modèle, serveur, acquisition, charge/mesure Pi,
installation, achat, manipulation matérielle ou essai moteur. Les gardes
signalent les opérations interceptées de la sélection, pas une garantie
universelle d'absence d'effet de tout code Python. L'export temporaire de
référence et les temporaires de tests sont nettoyés ; aucune trace précédente
n'est supprimée au titre d'une clôture supposée.

Les paramètres simulés restent exclusivement fictifs. Arrêt demandé,
tentative de zéro, zéro reçu par double et inhibition attestée par double P5
restent quatre faits distincts d'une immobilisation physique non mesurée.
Ni SH-10, ni l'audio réel, ni les propriétés physiques ne sont qualifiés.
P2/P3/P4/P5/P6 restent à réaliser et qualifier ; famille P6 non choisie,
accès sûr solo non démontré, ni par proximité ni par audio. Aucun composant,
seuil ou délai réel ajouté. Politique SH-08 inchangée.

**Dossier soumis à validation explicite du constat de revue, décision en
attente.** Cette validation ne serait ni approbation du lot, ni clôture
technique, ni autorisation de correctif, ni Go mobile humain. La perspective
d'un futur Go mentionnée dans la demande n'en remplace pas les prérequis.

**Prochaine étape bornée proposée, non commencée :** après décision sur cette
revue, demander une autorisation distincte pour corriger les écarts du seul
lot A et compléter les scénarios isolés affectés, avec les mêmes interdictions
et non-régressions. Aucun lot B ni intégration matérielle supposé retenu.

## 9. Corrections autorisées et vérification contradictoire

### 9.1 Décisions reçues, périmètre et état Git

Après la soumission du constat de section 8, l'utilisateur a répondu :
**« Je valide le constat de revue. Effectue les correctifs nécessaires afin
d'être 100% ok. »** Cette réponse valide le constat et autorise les correctifs
bornés du lot A ; elle n'approuve pas par anticipation leur résultat.

Une question distincte a explicité l'impact du refus des cibles inconnues
sur les demandes auparavant ambiguës. Réponse :
**« Ne pas faire de repli par défaut vers yellow si la cible de suivi n'est
pas pris en charge. »** Ce choix comportemental est appliqué aux entrées
texte/intention/plan et aux sorties LLM factices avant normalisation, filtrage
ou exécution partielle. L'omission historique de couleur pour une demande
objet prise en charge reste distincte d'une cible explicitement inconnue ;
« suis la balle » et les pronoms objets historiques restent compatibles.

Exigences SH-02, cadrage A1–A6 et six décisions détaillées de chacun des tickets
SH-05 à SH-11 inchangés. Aucun élargissement à la réalisation complète
SH-06/SH-07, à une qualification physique, à SH-10 ou à un lot suivant.
Le « 100% » demandé ne permet pas de promettre une absence universelle de
défaut ou un Go physique : le verdict porte sur les obligations et preuves
logicielles déclarées ci-dessous.

HEAD demeure `b1864aba3e78560fbb7f4ab020e886b1766cfa2a`, parent de référence
`a5c397b483fc0eda0938e5d444ecf1a3968430f9`. La livraison était déjà commitée
à l'ouverture de la revue. Les corrections, tests et mises à jour documentaires
de cette session sont persistants, non commités ; aucun commit, écrasement ou
révocation de changement préexistant.

### 9.2 Corrections, attendus et preuves ciblées

| Écart / exigence | Correction et choix technique | Vérification indépendante exécutée |
|---|---|---|
| E1 — observation puis nouvelle demande | Instantané immuable de génération, armement déjà observé et séquence d'interruption, capturé à réception avant supervision ; même instantané transmis au worker et vérifié avant réservation | [Transcription synchrone/worker](../../tests/isolated/lot_a_cases.py#L1011) : demande révélant le premier armement refusée, suivante admise ; demande déjà reçue retardée dans un worker invalidée par interruption/réarmement |
| E2 — refus intégral, pas de cible inconnue transformée en objet | Garde commune ; références humaines refusées avant LLM, composition refusée en bloc, cible inconnue explicite refusée avant normalisation ou élimination d'étapes ; contrôle de `target` et `target_object`, y compris alias `follow_red_ball` | [Demandes non prises en charge](../../tests/isolated/lot_a_cases.py#L953), LLM brut composé/imbriqué/malformé, contradiction cible/couleur, validation directe et mono-intention ; zéro mouvement observé sur les refus |
| E3 — aucun recul humain | L2 refuse `backward` des réservations humaines, y compris temporisé ; nominal de l'ancien test synthétique de contournement remplacé par une avance, sans modifier les tests historiques ; contrat fixe des 17 préconditions indépendant du type de production | [Recul humain direct/temporisé](../../tests/isolated/lot_a_cases.py#L1071) refusé ; axes fixes admission/émission et défauts inhibants ; recul balle préservé dans les contrats exacts |
| E4 — arrêt connu prioritaire, échéance inchangée | Zéro et fin/suspension avant callback de conditions lorsqu'un arrêt est déjà connu ; causes fusionnées, état verrouillé/terminé non rétrogradé ; échéance recontrôlée après callback | [Stop/échéance avec conditions bloquées](../../tests/isolated/lot_a_cases.py#L1084) : zéro et phase terminée observés avant libération, causes audio conservées ensuite, aucune preuve de cycle partiel |
| E5 — startup et erreurs des ports | Zéro et demande d'inhibition tentés indépendamment au startup et en priorité 1 ; erreur unique propagée, double erreur conservée dans un `ExceptionGroup`, aucun acquittement fabriqué | [Pannes indépendantes et simultanées](../../tests/isolated/lot_a_cases.py#L1128) ; tentative de zéro distinguée de sa réception, demande `startup` observée même si zéro échoue |
| E6 — parcours `--once` préservé | Import local de `resolve_input_device` dans `listen_once`, comme sur l'autre entrée audio | [Entrée ponctuelle](../../tests/isolated/lot_a_cases.py#L1165), protection absente puis présente : résolveur/transcription exclusivement factices, aucun module audio réel ni modèle chargé |

Le tuple des 17 obligations humaines est fixé depuis les exigences, et non
généré par réflexion sur les champs de production. Un test compare ensuite
ce contrat indépendant au type et à ses défauts inhibants. Les commandes du
double moteur, les tentatives de zéro et les ports preuve/inhibition/journal
restent des collectes distinctes ; le double P5 ne s'arme ni ne confirme
l'inhibition sur simple demande logicielle.

**Fiabilité du harnais :** une interruption initiale a révélé que l'exception
de borne murale dérivée d'`Exception` pouvait être absorbée par le métier.
`CampaignTimeout` dérive maintenant de `KeyboardInterrupt` ; dépassement =
arrêt explicite code 2, campagne inconclusive. Le test A-O12 injecte le handler
dans la détection factice du vrai `FollowObjectSkill` : l'exception traverse
son traitement métier et le nettoyage remet le zéro au double. Aucune attente
réelle de 120 s ni ressource réelle utilisée pour cette injection.

### 9.3 Chronologie des exécutions, y compris échecs

Toutes les campagnes utilisent seulement les commandes de section 7 avec
`-I -S`, après inspection du lanceur, des imports, des doubles et de la
collecte. Aucune installation ni suite pytest globale.

1. Nouveaux contre-exemples E1–E6 : première campagne interrompue manuellement.
   Une formulation encore mal refusée atteignait le vrai skill objet avec une
   horloge non remplacée ; la borne pouvait être absorbée. **Inconclusif :
   aucun bilan final d'isolation exploitable**, pas un succès. Fixtures
   corrigées avec horloge/attentes fictives explicites et borne non absorbable.
2. Contre-exemples avant corrections métier : **142 tests, 9 échecs et
   9 erreurs**, 2,710 s ; notamment admissions non refusées et `NameError`
   du résolveur audio. Zéro accès interdit observé, zéro thread résiduel.
3. E1–E6 corrigés : **142/142**, puis **148/148** après compléments ; sélection
   historique **214 réussis, 7 désélectionnés**, contrats **4/4**.
4. Après décision explicite sur les cibles inconnues : **161/161** cas du lot,
   mais sélection historique **213 réussis, 1 échec, 7 désélectionnés** :
   `test_parse_plan_spelled_distance_and_cm`, formulation `suivre la 2 minutes`.
   Régression corrigée via le normaliseur français existant, sans changer
   l'attendu historique ; deux cas explicites ajoutés. **163/163**, puis
   **214 réussis, 7 désélectionnés** et **4/4**. Le contrôle ultérieur de la
   borne dans le vrai skill factice conserve **163/163**, 4,505 s.
5. Dernier contre-exemple E2 sur l'alias `follow_red_ball` :
   **164 tests, 2 échecs**, 3,557 s, validation directe et sortie LLM brute.
   L'alias pouvait ignorer `target_object=person` ; ajouté au contrôle commun
   et à la validation du paramètre, sans ajuster les attendus pour faire passer
   le cas. Zéro accès interdit observé, zéro thread résiduel.
6. Série finale corrigée : tableau ci-dessous. Les campagnes intermédiaires
   complètes ont leurs erreurs conservées ; la campagne interrompue n'est
   jamais agrégée aux résultats finaux.

Un **second nouvel export temporaire**, distinct de celui de la section 8,
a été créé pour la comparaison finale : 91 blobs réguliers contrôlés contre
le commit de référence, sans lien/sous-module, sources en lecture seule.
Mêmes imports historiques inspectés, mêmes doubles et même lanceur corrigé,
aucun ancien export supposé retrouvé. Les commandes comparatives autorisées
ont été effectivement réexécutées sur cet export, ensuite nettoyé.

| Version / campagne finale effectivement reproduite | Résultat |
|---|---|
| Version corrigée, `--stdlib` | 164 tests, OK |
| Version corrigée, sélection historique ciblée | 214 passed, 7 deselected ; 14,64 s |
| Version corrigée, `--legacy-stdlib` | 4 tests, OK ; 0,540 s |
| Second export de référence, sélection historique ciblée | 214 passed, 7 deselected ; 8,32 s |
| Second export de référence, `--legacy-stdlib` | 4 tests, OK ; 0,123 s |

Chaque processus final : code 0, **zéro accès interdit observé, zéro thread
résiduel**, trois sondes synthétiques refusées sans opération réelle.
Les sept exclusions nommées en section 8.2 et le filtre
`not warmup and not warm_up` sont inchangés. Aucun succès attribué au
préchauffage exclu. Durées du harnais local seulement, pas des performances Pi.

### 9.4 Douze oracles et cinq critères A6 réévalués

Les effectifs sont un inventaire de scénarios, pas la justification du
verdict à eux seuls. Les attendus sont issus du cadrage et vérifiés contre
les sorties/ordres observés, notamment les contre-exemples de section 9.2.

| Oracle | Cas finaux | Preuve et portée |
|---|---:|---|
| A-O1 | 39 | 17 conditions indépendantes, une par axe admission puis émission ; nominal, échéance, contrat des défauts, recul humain direct/temporisé refusé |
| A-O2 | 11 | P5 absent/inconnu/périmé/incohérent/inhibé/en erreur inhibant, dates source inchangées à la lecture, frontières fictives |
| A-O3 | 9 | L2 commun, façade sans délégation ni accès sous-jacent public, entrées internes/vitesse/restauration gardées, identifiants obsolètes et recontrôle avant émission |
| A-O4 | 3 | Preuve changeante après cycle complet évalué, y compris repos ; cycle partiel/bloqué sans preuve, aucun générateur indépendant |
| A-O5 | 8 | Startup/P6 au repos, demande d'inhibition, arrêts ordinaires sans inhibition abusive ; ports startup en erreur séparée ou simultanée |
| A-O6 | 29 | Priorité 1, fin verrouillée, résultats/étapes/réessais invalidés ; permutations, concurrence, stop/échéance avant conditions bloquées, causes multiples conservées |
| A-O7 | 5 | Observation inhibée puis armement postérieur et nouvelle demande ; première observation par transcription synchrone/worker refusée, demande retardée invalidée |
| A-O8 | 2 | Réservation après worker terminé, même état utile à la reprise, identité de contexte renouvelée, échéance obligatoire inchangée, fin sans état humain hérité |
| A-O9 | 38 | Refus humain intégral et cible inconnue sur texte/transcription/intention/plans/LLM factice, sans primitive/plan partiel ni repli objet ; assemblage live présent refusé avant import |
| A-O10 | 11 | Balle/primitives/stop absente puis présente, garde de restauration, entrée ponctuelle audio factice et durées historiques ; compléments comparatifs du tableau 9.3 |
| A-O11 | 4 | Erreurs ports/journal explicites, zéro tenté distinct de reçu, preuve/inhibition non fabriquées ; startup en panne couvert aussi par A-O5 |
| A-O12 | 4 | Replays recalculés, ordre discriminant, observateur absent inconclusif, borne non absorbable par le métier ; bilans finaux d'isolation séparés |
| Configuration | 1 | Valeurs de présence invalides et ports manquants refusés |

Total **164**. L'observateur moteur ne lit pas le journal testé ; causes P5
scriptées indépendantes des demandes. Un collecteur indisponible ou rendez-vous
non observé échoue explicitement, pas une absence de mouvement déduite d'un
silence. Cela ne qualifie pas l'OS, une instrumentation externe, toutes les
pannes silencieuses ni toutes les chronologies concurrentes possibles.

| Critère obligatoire | Réévaluation après corrections |
|---|---|
| A6.1 — socle, raccordements et garde unique | Satisfait dans la frontière logicielle déclarée : chemins L2/identifiants gardés ; E1/E3/E4/E5 corrigés avec scénarios discriminants |
| A6.2 — douze oracles effectivement exécutés | Satisfait pour les obligations du lot : couverture ci-dessus, contre-exemples exécutés puis corrigés, aucun écart obligatoire connu ni observateur nécessaire indisponible dans la série finale |
| A6.3 — non-régression absente puis présente | Satisfait dans la sélection convenue et les contrats exacts, comparaison de référence reproduite ; E6 corrigé, régression de durée et alias corrigés sans modifier les tests historiques |
| A6.4 — refus réel, nominal uniquement factice | Satisfait dans les chemins éprouvés : E2 fermé, aucun adaptateur P5 réel ni commutateur live humain ; nominal humain uniquement à moteur et fournisseurs factices |
| A6.5 — rapport vérifié et traçabilité | Satisfait pour le dossier technique : références, douze empreintes corrigées, liens, décisions préservées, erreurs et exclusions consignées ; validation explicite du dossier corrigé reçue et consignée en section 9.6 |

Verdict motivé : **conforme dans le seul périmètre logiciel isolé éprouvé**,
et non « 100 % sûr » ou SH-09 globalement achevé. Les limites de la grammaire
testée ne constituent pas une réalisation complète de SH-07. Aucun critère
obligatoire connu non résolu dans cette frontière ; toute découverte ultérieure
oblige à réévaluer le verdict, pas à modifier les attendus pour le maintenir.

### 9.5 Empreintes corrigées et contrôles documentaires

SHA-256 des mêmes douze fichiers de code/harnais que la livraison.
La table de section 7 reste **historique**, vérifiée avant corrections ; elle
ne décrit plus les huit fichiers modifiés. Les quatre autres restent identiques.

| Fichier | SHA-256 après corrections |
|---|---|
| `src/irobot/interfaces/protection.py` | `2e69b644ffceec5ecfa1d89d806ab2fdb983e368a3145892c6f31eca70c8fcd9` |
| `src/irobot/interfaces/robot_controller.py` | `28009b61075a2db95a1c881cdccaee1b8e78a2f254b112ac559609bdaabfef9c` |
| `src/irobot/interfaces/voice_runtime.py` | `feb0caad693641835350831b0fdf2b35876667e06c3d371e996164195fd94c78` |
| `src/irobot/interfaces/language_controller.py` | `916f89a34357d80054bb8410509dde9680d85f17f13f35a7edc520c0884f134b` |
| `src/irobot/interfaces/intent_parser.py` | `d793781de97f60ebf75458b0f59a410ae167b7e9a16172578f8bd177a6286f94` |
| `src/irobot/interfaces/plan_guards.py` | `60804515f549dcdd07ddcf9144c9fd4cc5de7d840bbd5b3ab952dc91c2deae45` |
| `src/irobot/interfaces/__init__.py` | `7b6da8aea7403808710e80aeed445084c3512a9074a144d755743d93c688a0af` |
| `src/irobot/domain/orchestrator/executor.py` | `c248dbf857e601ed5e352e8e20b6d11e952a48fcb47e6309d3c1392baa071254` |
| `src/irobot/config/settings.py` | `1403cd5dd55b7c6acffacdbd006ce18a129786534c252d465f469923106a9dc8` |
| `tests/isolated/run_lot_a.py` | `b1cc91a1f8372ac886e2adcfa1a834b9ed18895a14fb2d9cea94df3aafc4a9a3` |
| `tests/isolated/lot_a_cases.py` | `51e0f5415d15aea7a732c602064c75b7ba3378c1ecc44ce8a6cae8810e24d534` |
| `tests/isolated/legacy_contract.py` | `20ec49c3495a72f04f296b1f76904d6c8a64e1b6c04f2023291876ec649860a8` |

Contrôle final : empreintes recalculées ; liens de fichiers et nouvelles
localisations de scénarios contrôlés ; syntaxe Python vérifiée sans imports
supplémentaires ; `git diff --check` sans erreur. Aucun outil de typage/lint
configuré ou installé pour cette revue. Section 1 du backlog, six sujets
SH-02, cadrage A1–A6 et sept blocs détaillés SH-05 à SH-11 comparés à la
référence et préservés intégralement. Tests historiques, script de gardes,
driver SmartCar2WD et comportements balle inchangés.

### 9.6 Limites maintenues et décision explicite

Aucun matériel, GPIO, caméra, capteur, Bluetooth/audio réel, adaptateur P5
réel, réseau, modèle/serveur réel, acquisition, mesure/charge Pi, installation,
achat, manipulation matérielle ou essai moteur. Les sondes refusées ne sont
pas des opérations de ressource ; les campagnes hors sélection restent
**non exécutées**. Une campagne interrompue reste **inconclusive**.

Arrêt demandé, tentative de zéro, zéro remis au double et inhibition attestée
par double P5 sont distincts ; immobilisation physique **non mesurée**.
SH-09 logiciel, SH-10 performances Pi, audio réel et propriétés physiques
ne sont pas confondus. Paramètres simulés exclusivement fictifs ; aucun seuil,
délai ni composant matériel inventé. Politique SH-08 inchangée : historique
des échecs conservé, pas de clôture de campagne présumée ni purge associée.

**Décision explicite reçue le 2026-10-30 avec l'outil de questions :**
après présentation du verdict, des preuves et des limites, l'utilisateur a
choisi **« Valider le dossier logiciel corrigé du lot A uniquement »**.
Cette validation distincte de celle du constat et de l'autorisation de
corriger est limitée au dossier logiciel isolé éprouvé ; elle ne choisit ni
ne démarre une suite. SH-05/SH-09 non terminés globalement. P2/P3/P4/P5/P6 restent
à réaliser et qualifier ; famille P6 non choisie, accès sûr solo non démontré,
ni par proximité ni par audio. **Aucun Go mobile humain** : cette revue ne
peut satisfaire les prérequis physiques manquants.

Prochaine étape bornée seulement proposée : établir, à partir
des acquis et sans les rouvrir, un relevé documentaire des dépendances encore
ouvertes et des options de prochaine étape, puis choisir explicitement un seul
périmètre autorisé. Ce relevé n'est pas commencé ; ni lot B, ni intégration
matérielle, ni campagne Pi/audio supposés choisis.

## 10. Suite logicielle autorisée — bloc d’observation SH-04

Cette section consigne une activité ultérieure, sans réécrire les conclusions
historiques des sections 8–9 ni étendre le verdict A1–A6.

Le 2026-10-30, l’utilisateur a autorisé la poursuite de l’implémentation et la
préparation de l’intégration réelle par la décision :
**« Tu as mon GO mobile humain pour pouvoir continuer avec le robot et les
moteurs. J’aimerai finir l’implémentation afin de pouvoir faire des 1ers tests
sur le terrain. »** Portée retenue : continuer les travaux logiciels
indépendants et préparer l’intégration. Cette autorisation ne prouve aucune
qualification physique, ne satisfait pas SH-02/SH-11 et ne permet pas
d’actionner les moteurs ni de faire un essai avec une personne.

### Réalisation et limites

`src/irobot/interfaces/human_perception.py` définit des types d’identité,
d’observation, de qualité, de statut et de résultat d’acquisition. Le validateur
est lié à l’identité, la mission et le contexte attendus ; il utilise le temps
monotone de capture, exige des timestamps cohérents, trois trames distinctes
consécutives du même flux, une géométrie exploitable et une distance optique
distincte du dégagement. Il rejette explicitement les données périmées,
ambiguës, absentes, invalides, malformées, hors contexte ou issues d’un ancien
flux. Un décodeur candidat ArUco/OpenCV configurable retourne l’identité
attendue, les coins image ou un statut d’absence/ambiguïté/rejet/défaut ; il
n’invente ni distance ni calibration et n’ouvre pas la caméra. Le prototype
exige famille/dictionnaire/ID explicites, sans défaut silencieux. La cible de
fraîcheur de 200 ms vient de SH-04, est fournie explicitement et reste non
qualifiée.

Après sélection utilisateur du prototype ArUco/OpenCV, inspection sans caméra
de l’installation locale : OpenCV 5.0.0 expose `cv2.aruco.ArucoDetector` avec
`detectMarkers`; la fonction historique `cv2.aruco.detectMarkers` est absente.
Aucune dépendance installée ou modifiée. Les tests isolés exercent le décodeur
avec un double explicite ; ils ne constituent pas une validation des résultats
du détecteur natif ni une qualification optique.

Smoke test natif séparé : le décodeur OpenCV installé a été construit et
appelé sur une image noire synthétique 64×64 ; disposition `absent`. Le
dictionnaire `DICT_4X4_50`/ID `0` était un paramètre jetable de compatibilité,
non un choix de configuration. Aucune caméra n’a été ouverte.

Le schéma de configuration persistante optionnelle est ajouté dans le TOML
existant sous `[human_marker]` avec exactement `family`, `dictionary`,
`identifier` ; absent signifie identité non configurée et un bloc incomplet
est une erreur. Aucun identifiant n’est renseigné dans la configuration du
dépôt, et le runtime mission ne consomme pas encore cette valeur. Le composant
n’est pas raccordé à une caméra ou à un comportement moteur. Famille finale,
dictionnaire/ID, montage, calibration, qualité et performances restent à
choisir ou qualifier selon SH-03. Le refus humain sur le chemin réel demeure
en place. Aucun hardware, réseau, audio réel ou moteur physique n’a été utilisé.

### Exécutions isolées

Avant les nouvelles exécutions, le lanceur, ses gardes, ses imports, ses
doubles et sa collecte ont été inspectés. Seules les commandes documentées
avec `-I -S` ont été utilisées :

| Campagne | Résultat |
|---|---|
| `tests/isolated/run_lot_a.py --stdlib` | 201 réussis |
| `tests/isolated/run_lot_a.py` | 251 réussis, 7 désélectionnés |
| `tests/isolated/run_lot_a.py --legacy-stdlib` | 4 réussis |

Chaque processus final a observé zéro accès interdit et zéro thread résiduel ;
trois sondes synthétiques ont été rejetées sans exécuter d’opération de
ressource. Une première tentative contenait un attendu incorrect : publication
égale à capture est cohérente. L’attendu a été corrigé et les trois campagnes
finales rejouées. Cela ne qualifie ni la caméra ni le système réel.

### Décisions et portes encore ouvertes

- La famille de marqueur, le dictionnaire, l’identifiant configuré et la
  sélection finale après essais SH-03 restent ouverts. Le prototype logiciel
  ArUco/OpenCV est choisi ; les API locales ont été inspectées, sans garantie
  de compatibilité/performance sur le Pi.
- Pas de calibration, montage, perception de production ni valeur d’association
  renseignée/consommée par le runtime mission (un instantané de contexte est
  désormais disponible côté interface), comportement humain déterministe, branchement complet commande/annonces,
  replay de mission ou campagne SH-09 complète réalisés par ce bloc.
- La série ci-dessus ajoute un test synthétique de snapshot de l’identité
  persistante par mission au bloc logiciel en cours ; elle ne modifie pas les
  résultats historiques du lot A consignés dans les sections précédentes.
- Le cycle de session testé exige `HumanConditions` pour l’activation et la
  sortie du maintien, mais n’est pas raccordé au runtime ni au contrôleur ;
  les booléens synthétiques ne sont aucune preuve de protection physique.
- SH-10 (Pi), audio réel et propriétés physiques restent des preuves distinctes
  et non exécutées. SH-05/SH-09 restent ouverts globalement.
- P2/P3/P4/P5/P6 à réaliser/qualifier, famille P6 non choisie et accès sûr solo
  non démontré. Aucune propulsion réelle ou campagne avec une personne
  admissible sur la base de cette autorisation seule.

La prochaine question structurante avant qualification caméra porte sur les
paramètres d’acquisition réels et l’accès à une configuration matérielle
précise, conformément aux portes SH-03/SH-11. Les parties logicielles
indépendantes peuvent continuer sans activer le robot.

### Configuration matérielle communiquée après cette réalisation

L’utilisateur décrit une Smart Car 2WD Arduino RichVibe avec L298N, Raspberry
Pi 5 (« dernière version de Pi OS », release exacte inconnue), caméra Pi 5MP
1080P OV5647 à l’avant en montage vertical, objectif horizontal, centre optique
à 6 cm du sol. Il indique pouvoir déconnecter les moteurs facilement. Rien de
cela n’a été inspecté sur l’appareil ; l’isolement moteur n’est pas encore
réalisé ni vérifié et ne constitue pas une preuve de qualification.

Résultat communiqué par l’utilisateur après exécution du prévol autorisé :
`/etc/os-release` indique Debian GNU/Linux 13 (trixie), version complète 13.7.
La découverte Picamera2 rapporte le modèle `ov5647`, `Location: 2`,
`Rotation: 0`, `Num: 0`, identifiant
`/base/axi/pcie@1000120000/rp1/i2c@80000/ov5647@36` ; les journaux indiquent
`libcamera v0.7.2+rpt20260817` et le pipeline PISP/BCM2712. C’est une
identification logicielle rapportée, pas une vérification d’orientation,
d’image, de calibration ou de performances. Les sorties ne sont pas
reproduites indépendamment ici.

L’utilisateur a confirmé après ces commandes que les moteurs sont physiquement
déconnectés et qu’il a vérifié l’impossibilité de les alimenter. Cette
déclaration permet de satisfaire la précondition d’isolement pour une
éventuelle campagne caméra, sans qualifier les protections, l’arrêt d’urgence
ou l’immobilisation physique du robot.

L’utilisateur rapporte également `DISPLAY=localhost:10.0` et un exécutable
`.venv/bin/camera-live`. Ces contrôles ne démontrent pas que X11 peut réellement
ouvrir une fenêtre ; le résultat d’affichage est consigné ci-dessous selon le
retour ultérieur de l’utilisateur, sans reproduction indépendante.

Le code `camera-live` inspecté exige `DISPLAY`, énumère les caméras Picamera2,
ouvre automatiquement l’index 0, capture et affiche les images tournées à 90° ;
il ne commande pas de moteur et ne sauvegarde pas d’image. Les deux commandes
de prévol autorisées (lecture OS et `Picamera2.global_camera_info()`) ont été
exécutées par l’utilisateur sans capture ni affichage d’image. Une campagne
distincte `camera-live` demeure non autorisée jusqu’à validation explicite du
protocole d’ouverture live. **Mise à jour :** autorisation utilisateur
distincte reçue le 2026-10-30 pour lancer `.venv/bin/camera-live` une seule
campagne limitée via SSH/X11, caméra 0 OV5647, capture/affichage continu tourné
de 90°, sans fichier image, moteur, audio, réseau, personne, marqueur ou
calibration ; arrêt par `q`. Résultat rapporté ensuite par l’utilisateur :
la campagne fonctionne et l’image est visible correctement. Il s’agit du
fonctionnement apparent du flux/affichage déclaré pour cette session, sans
image persistée ni vérification indépendante ; aucune orientation, calibration,
performance ou exigence SH-03 n’est qualifiée. L’assistant n’a pas exécuté la
commande et n’a pas d’accès SSH direct depuis macOS. L’autorisation et le
résultat ne constituent pas une qualification physique, une autorisation de
propulsion ou un Go de suivi humain.

Pour préparer le protocole optique suivant, l’utilisateur a choisi le marqueur
candidat ArUco `DICT_4X4_50`, ID `1`. Ce choix n’est ni configuré dans le runtime
ni qualifié comme identité de production ; aucun essai réel de détection de ce
marqueur n’a encore été autorisé ou exécuté. Il faudra un accord distinct pour
toute nouvelle ouverture caméra avec détection. L’utilisateur confirme que le
marqueur physique est disponible et que le côté du carré imprimé lui-même
(hors bordure/feuille) a été mesuré à 8 cm. Cette dimension déclarée ne qualifie
ni la calibration ni une mesure de distance.
Un outil logiciel `marker-detect-live` est ajouté au code source pour ce
prochain test statique : il vérifie que la caméra 0 est rapportée OV5647,
détecte seulement ce couple, superpose et rapporte les coins en pixels, ne
conserve pas d’image, n’estime aucune distance, et s’arrête sur `q`. Il ne
commande pas de moteur. Les tests isolés synthétiques vérifient la présentation
et l’absence de faux succès pour un autre ID ; ils ne sollicitent ni caméra ni
marqueur physique.

Campagnes isolées finales après ajout de l’outil : `--stdlib` 201 tests,
sélection ciblée 251 réussis/7 désélectionnés, legacy 4 réussis ; zéro accès
interdit et zéro thread résiduel dans chaque processus. Aucun test de cette
série n’ouvre la caméra réelle. Les changements ne sont pas encore synchronisés
vers le Pi. Une autorisation utilisateur distincte est maintenant reçue pour
la campagne statique avec marqueur, à lancer uniquement après synchronisation
sur le Pi et sous les conditions décrites ci-dessus. L’assistant n’a pas accès
à la session SSH et n’exécute pas la commande ; son résultat reste à rapporter.
