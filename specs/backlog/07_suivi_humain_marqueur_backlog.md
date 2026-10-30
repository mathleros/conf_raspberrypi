# Étude et backlog — Suivre un humain comme un chien

Date de création : 2026-10-29. Mise à jour : 2026-10-30. Statut : SH-01 validé ; cadres SH-02 à SH-11 et leurs décisions détaillées préservés. Conception fonctionnelle documentaire SH-02 en six sujets, sans réalisation ni qualification physique. **Lot A logiciel isolé réalisé et vérifié**, après autorisation explicite : L2/P5, admission/verrous, refus humain réel et preuves limitées au lot. Rapport [SH-09 du lot A](08_lot_a_rapport_sh09.md) : 121 cas du socle réussis, non-régression ciblée de 214 tests réussis sur référence et version livrée. SH-05/SH-09 non terminés globalement ; choix, réalisations et qualifications hors lot restent ouverts. Aucun Go mobile humain.

## 1. Besoin et décision de cadrage

**Besoin utilisateur :** pouvoir dire « suis-moi » et marcher pendant que le robot suit, conserve une distance confortable, s'arrête lorsque la personne s'arrête et reste sous contrôle.

**Choix confirmé par l'utilisateur :** accepter un marqueur visuel porté pour la première version.

**Précision validée le 2026-10-30 :** le suivi humain est une capacité du même assistant et du même runtime que la recherche de balle, pas un mode supplémentaire à sélectionner. L'utilisateur dit directement « suis-moi », comme « cherche la balle jaune ». Aucun lancement séparé, bascule manuelle ou redémarrage ne doit être nécessaire pour choisir entre ces capacités lorsque le robot est disponible.

Cela signifie que le robot suit **un marqueur associé à la personne**, et non une identité humaine reconnue. Il ne sait pas vérifier qui porte ce marqueur. Si celui-ci est transféré à quelqu'un d'autre, le robot ne peut pas le distinguer. Deux copies du même identifiant constituent également une ambiguïté.

### Périmètre MVP validé, à qualifier avant roulage

- Une personne coopérante porte un marqueur visible depuis l'arrière, sur un support stable.
- Intérieur privé, sol plat et sec, espace contrôlé, sans escalier accessible, enfant ni animal dans la zone d'essai.
- Marche lente adaptée au robot ; ne pas promettre le suivi à vitesse de marche habituelle avant mesures.
- Trajet simple, ligne droite et virages doux avec visibilité maintenue.
- Arrêt sur obstacle, perte de cible, mesure périmée, défaut matériel ou demande utilisateur.
- Pas de recul automatique ; si la personne revient vers le robot, celui-ci reste arrêté.
- Pas de contournement autonome, de recherche en déplacement ou de reprise après défaut sans confirmation.
- Session bornée : 60 secondes par défaut, demande explicite de 10 à 300 secondes après qualification terrain ; paramètres cibles validés en SH-01, étape 4.

Le « chien » est une métaphore d'interaction, pas une promesse de navigation générale. Suivre quelqu'un derrière une porte, dans une foule ou autour d'un angle masquant la cible est hors MVP.

### Hors périmètre initial

Reconnaissance faciale ou vocale du propriétaire, suivi sans accessoire, réidentification après longue occultation, cartographie/SLAM, navigation autonome dans le logement, extérieur, escaliers, retour à la base, poursuite d'une personne hors champ.

### Validation progressive de SH-01

Les cinq étapes de SH-01 sont validées. Le contrat d'usage est approuvé ; les capacités matérielles, seuils techniques et performances restent à qualifier.

| Étape | Sujet | Statut | Décision |
|---|---|---|---|
| 1 | Lieu et conditions d'usage | Validé par l'utilisateur le 2026-10-29 | Intérieur privé, sol plat et sec, espace dégagé et contrôlé, aucun escalier ou rebord accessible, sans enfant ni animal dans la zone d'essai ; marqueur porté visible depuis l'arrière, marche lente, trajet simple et virages doux. Extérieur, foule et suivi derrière un angle masquant le marqueur exclus du MVP. |
| 2 | Association du marqueur à « moi » | Validé par l'utilisateur le 2026-10-29 | Association fixe : identifiant choisi explicitement lors de la configuration et conservé entre les sessions ; acquisition vérifiée à chaque démarrage, jamais de substitution automatique ; changement explicite robot arrêté. Le marqueur identifie la cible, pas la personne ni la voix. |
| 3 | Arrêts et reprises | Validé par l'utilisateur le 2026-10-30 | Arrêt normal : session active, redépart automatique sous conditions. Perte, ambiguïté, donnée périmée, obstacle ou défaut : suspension et reprise explicite après vérifications. Stop/annulation/échéance : session terminée. Urgence physique : réarmement manuel. L'échéance continue pendant la suspension. |
| 4 | Distance, vitesse et durée | Validé par l'utilisateur le 2026-10-30 | Distance par défaut 1,5 m, demandable de 1,2 à 2 m dans la plage qualifiée ; objectif stabilisé ±30 cm. Plafond physique initial 0,15 m/s, non relevable par la voix. Durée par défaut 60 s, demandable de 10 à 300 s après qualification ; chronomètre à l'activation après acquisition, sans remise à zéro ni prolongation automatique. |
| 5 | Retour utilisateur | Validé par l'utilisateur le 2026-10-30 | Messages vocaux courts et déterministes, limités aux transitions, et traces horodatées obligatoires. Sortie audio opérationnelle requise au démarrage ; panne détectée en cours : suspension. L'arrêt moteur reste prioritaire sur toute annonce. |

La précision d'intégration au même assistant complète SH-01 sans remettre en cause ses cinq décisions. Une « session de suivi » désigne l'exécution bornée d'une mission, pas un mode utilisateur ou un runtime distinct. La configuration initiale du marqueur reste nécessaire ; elle n'est pas une bascule de mode.

### Association fixe du marqueur — décision validée

- « Moi » désigne l'identifiant de marqueur enregistré dans la configuration, conservé entre les sessions ; aucune association manuelle n'est requise à chaque session.
- À chaque « suis-moi », le robot reste immobile jusqu'à obtenir plusieurs images récentes et cohérentes du marqueur attendu, sans ambiguïté et avec les autres préconditions de démarrage satisfaites.
- Un identifiant absent de la configuration, un marqueur attendu non visible ou plusieurs exemplaires visibles de cet identifiant interdisent le démarrage, avec un motif explicite. Un autre identifiant n'est jamais adopté comme remplacement.
- Changer de cible exige une modification explicite de la configuration, robot arrêté, puis une nouvelle acquisition ; le LLM ne choisit pas un nouvel identifiant.
- Cette association ne reconnaît ni le propriétaire ni la voix qui commande. Une autre personne portant le marqueur configuré sera suivie ; un exemplaire unique visible ne permet pas de prouver l'absence de copies ailleurs.
- Le dictionnaire, la valeur de l'identifiant, la taille et la fixation du marqueur seront définis lors de l'étude de perception SH-03 ; aucun numéro n'est choisi à ce stade.

### Arrêts et reprises — décision validée

| Événement | Action et état de session | Conditions de redémarrage |
|---|---|---|
| Porteur arrêté ou trop proche, sans anomalie de perception ni obstacle | Immobilisation sans recul ; session active en maintien | Redépart automatique lorsque le porteur s'éloigne, uniquement avec le même marqueur visible, des observations fraîches, une distance valide et une zone protégée libre |
| Marqueur perdu ou ambigu, image périmée | Arrêt et suspension ; aucun balayage ni contournement | « Reprends le suivi », puis nouvelle acquisition du même identifiant et vérification de toutes les préconditions |
| Obstacle ou défaut | Arrêt et suspension avec motif explicite | Obstacle dégagé ou défaut corrigé, puis commande explicite de reprise et nouvelle acquisition ; la seule disparition du problème ne provoque aucun mouvement |
| « Stop », annulation ou fin de durée | Arrêt et session terminée | Nouvelle commande « suis-moi » et vérification des préconditions ; « reprends le suivi » ne réactive pas une session terminée |
| Arrêt d'urgence physique | Arrêt et session terminée ; redémarrage vocal seul interdit | Remise en état et réarmement manuel, puis nouvelle commande « suis-moi » et vérification des préconditions |

- Les interruptions de sécurité sont prioritaires sur le maintien normal : si un obstacle ou une anomalie est aussi détecté à proximité du porteur, la reprise automatique est interdite.
- Une suspension ne remet pas la durée à zéro et ne décale pas l'échéance initiale. À l'échéance, même suspendue, la session se termine ; une reprise tardive exige une nouvelle session.
- La distinction entre maintien normal, suspension et fin de session doit être explicite dans les états, retours utilisateur et traces.
- Les délais d'arrêt, seuils et limites physiques restent à définir/qualifier aux étapes suivantes ; cette validation ne vaut pas validation matérielle.

### Distance, vitesse et durée — paramètres cibles validés

| Paramètre | Décision d'usage |
|---|---|
| Distance par défaut | 1,5 m de dégagement entre l'avant du robot et le porteur, et non entre la caméra et le marqueur |
| Distance demandable | De 1,2 à 2 m, uniquement dans la plage finalement qualifiée ; demande hors plage refusée avec explication, jamais corrigée silencieusement |
| Maintien de distance | Objectif de ±30 cm en suivi stabilisé ; précision à démontrer, non garantie à ce stade |
| Vitesse | Plafond physique initial de 0,15 m/s (0,54 km/h), mesuré au sol ; environ 67 s pour 10 m. Le porteur adapte son allure ; aucun rattrapage au-delà du plafond et aucune commande vocale ne le relève |
| Durée par défaut | 60 s |
| Durée demandable | De 10 à 300 s après qualification terrain ; demande hors plage refusée explicitement, ni suivi illimité ni prolongation automatique |
| Début du chronomètre | À l'activation du suivi, après acquisition initiale et annonce ; préconditions recontrôlées avant mouvement. Acquisition initiale bornée à 10 s selon SH-04 |
| Maintien et suspension | Comptés dans la durée ; une reprise ne remet pas le chronomètre à zéro et ne décale pas l'échéance |

La distance minimale de sécurité est distincte de la distance demandée et sera arrêtée en SH-02. Le seuil de 0,8 m mentionné en recette reste provisoire : ce n'est pas une consigne autorisée à demander.

Ces valeurs définissent le besoin cible et ne constituent aucune autorisation de roulage. SH-02 et la qualification terrain doivent confirmer leur faisabilité et leur sécurité ; sinon, le contrat devra être révisé avant les essais près d'une personne. Les objectifs de maintien ne définissent pas à eux seuls les seuils de commande, l'hystérésis ou le freinage.

### Retour utilisateur — décision validée

Le MVP utilise des messages vocaux courts et déterministes, non générés librement par le LLM, pour être perceptible lorsque le porteur est dos au robot. Le choix technique (messages préenregistrés ou synthèse vocale), la sortie audio et son contrôle de disponibilité restent à qualifier en SH-02 puis à réaliser en SH-08.

| Événement | Retour attendu |
|---|---|
| Acquisition initiale, robot immobile | « Je cherche votre marqueur. » |
| Avant activation du suivi | Annonce de l'état et des paramètres réellement retenus, par exemple « Suivi actif, à un mètre cinquante, pendant une minute. » |
| Reprise après suspension | Annonce de la reprise, de la distance et du temps réellement restant ; aucune annonce ne doit laisser croire à une remise à zéro de la durée |
| Maintien normal dans la zone de confort | Pas de message répété |
| Porteur trop proche | « Trop près, je reste arrêté », une fois à l'entrée dans cet état ; pas de compte à rebours avant le redépart automatique autorisé |
| Suspension | Motif et action attendue, par exemple « Marqueur perdu, suivi suspendu. Dites : reprends le suivi » ou « Obstacle détecté, suivi suspendu » ; la reprise reste conditionnée à la correction du problème |
| Reprise refusée, demande invalide ou démarrage impossible | Refus avec raison explicite |
| Fin de durée | « Durée écoulée, suivi terminé. » |
| Stop ou annulation | « Suivi arrêté. » |

- Traces horodatées obligatoires des changements d'état, paramètres et motifs ; annonces limitées aux transitions pour éviter les répétitions.
- Aucun arrêt moteur n'attend la fin d'un message. La lecture audio ne doit ni bloquer la surveillance ni empêcher la prise en compte du stop.
- Sans sortie audio opérationnelle, démarrage du suivi humain interdit et défaut explicite dans les logs/terminal ; panne audio détectée en cours : suspension et arrêt, reprise explicite après correction.
- L'audio ne constitue pas un dispositif de sécurité et ne remplace jamais le coupe-circuit. Une coupure d'alimentation peut empêcher toute annonce.
- L'intelligibilité dos au robot, la disponibilité audio et la reconnaissance de « stop » pendant les annonces doivent être éprouvées ; le retour vocal ne doit pas déclencher lui-même de commandes.

## 2. Parcours utilisateur attendu

1. L'opérateur vérifie le terrain, le coupe-circuit accessible, les capteurs et la caméra ; il place le marqueur dans le champ.
2. Lors de la configuration, il associe explicitement un identifiant de marqueur à la cible « moi ». Cette association est conservée entre les sessions ; elle n'est modifiable explicitement que robot arrêté. Le robot n'adopte pas automatiquement le premier marqueur aperçu.
3. « Suis-moi à un mètre cinquante pendant une minute » produit une intention validée. Sans distance/durée explicite, le système utilise des valeurs documentées et annonce les paramètres retenus.
4. Robot immobile : acquisition de plusieurs observations cohérentes du bon identifiant, distance exploitable et préconditions de sécurité valides.
5. Le robot signale « prêt / suivi actif », puis ajuste son orientation et son avance ; dans la zone de confort, il s'arrête.
6. La personne s'arrête : le robot ralentit et s'immobilise sans la toucher. Si elle s'approche trop, il reste arrêté et signale la proximité. Sans interruption de sécurité, la session reste active et le robot peut repartir automatiquement lorsqu'elle s'éloigne, sous les conditions validées ci-dessus.
7. Marqueur perdu ou ambigu, image périmée, obstacle ou défaut : arrêt et suspension avec motif explicite, aucune substitution par une balle ou une autre cible.
8. « Reprends le suivi » exige une session suspendue non expirée, la correction du problème, une nouvelle acquisition du même identifiant et toutes les préconditions valides. La suspension ne décale pas l'échéance.
9. « Stop » reste prioritaire et local ; stop, annulation ou fin de durée terminent la session avec arrêt et bilan. Un nouveau départ exige « suis-moi ». Une urgence physique exige aussi un réarmement manuel ; elle ne devient jamais une fin normale silencieuse.

Le retour utilisateur retenu est vocal et déterministe, accompagné de traces horodatées, selon la décision de la section 1. La sortie audio et la production des messages ne sont pas considérées comme déjà livrées.

## 3. État réel du projet et écarts

Constats fondés sur le code inspecté, et non uniquement sur le backlog historique. Aucun essai physique n'a été exécuté pour cette étude.

| Domaine | Existant vérifié | Écart pour le suivi humain |
|---|---|---|
| Compréhension | LLM local, parser déterministe, validation et garde lexicale | Pas d'intention dédiée au suivi humain ; « suis-moi » peut être interprété comme `follow_object` sans cible |
| Planification | Mapping déterministe intention → skills, registre, orchestration | Ajouter le nouveau comportement et ses préconditions sans détourner le suivi de balle |
| Perception live | Picamera2, OpenCV, sélection d'un objet rouge/jaune | Aucun détecteur de marqueur identifié, aucune association à une personne |
| Observation | `ObjectDetection` : label, position discrète, distance, confiance, diamètre | Pas d'horodatage de capture, d'identifiant de trame, d'identité verrouillée ou de qualité géométrique dans le contrat |
| Distance | Diamètre apparent d'une balle de taille connue, lissage ; fusion ultrason optionnelle | Modèle balle non applicable au porteur ; calibration caméra et géométrie d'un marqueur nécessaires |
| Contrôle | `FollowObjectSkill`, impulsions avant/arrière, alignement, maintien de distance | Recul à interdire pour ce mode ; vitesse physique, accélération, fraîcheur et identité à contrôler |
| Perte de cible | Arrêt puis balayage tournant et réacquisition du suivi objet | Politique plus conservatrice : arrêt, pas de balayage automatique dans le MVP humain |
| Obstacles | HC-SR04 frontal, arrêt sur proximité ou erreur de lecture si capteur présent | Un capteur frontal ne couvre ni tout le gabarit, ni côtés/arrière, ni vides ; couverture à qualifier |
| Préconditions matérielles | Le constructeur live utilise `require_obstacle_sensor=False` | Le mode humain doit refuser le démarrage sans protection qualifiée, même si d'autres modes restent permissifs |
| Arrêt | Événement d'urgence, mouvements temporisés surveillés, arrêt en sortie | Ne démontre pas un arrêt sur processus gelé/tué ; coupe-circuit et watchdog indépendants à étudier puis éprouver |
| Performances | Boucle nominale de suivi à 20 ms, caméra avec attente nominale de 50 ms | Ce ne sont pas des latences garanties ; concurrence vision/audio/LLM à mesurer sur Pi |
| Tests et exploitation | Mocks, horloge injectable, tests de suivi objet, traces JSONL, protocoles Mac/Pi | Scénarios marqueur, données périmées, mauvais identifiant, défauts et recette physique à ajouter |

### Sources principales

- [Contrat livré du suivi de balle](../01_skills_inventory.md#contrat-runtime-livré-2026-10-29).
- [Contrat de perception](../../src/irobot/interfaces/perception_pipeline.py) et [pipeline caméra](../../src/irobot/hardware/camera/camera_live_pipeline.py).
- [Suivi objet](../../src/irobot/domain/skills/behaviors/follow_object.py) et [briques de tracking](../../src/irobot/domain/skills/behaviors/target_tracking.py).
- [Parser et validation](../../src/irobot/interfaces/intent_parser.py), [gardes du plan LLM](../../src/irobot/interfaces/plan_guards.py), [runtime et assemblage matériel](../../src/irobot/interfaces/voice_runtime.py).
- [Planner](../../src/irobot/domain/orchestrator/planner.py), [contrôleur](../../src/irobot/interfaces/robot_controller.py), [driver moteur et capteur](../../src/irobot/hardware/smart_car/smart_car.py).
- [Calibration actuelle](../../config/runtime_calibration.toml), [dépendances](../../pyproject.toml), [campagne Pi existante](../../docs/test-campaign/plan-test-pi-post-audit-v6.md).

**Attention :** la documentation conserve des sections historiques et le backlog M1–M7 n'est pas une preuve de reste à faire. Réutiliser ce qui est livré ; vérifier séparément sa validation sur le robot.

## 4. Architecture recommandée, non encore implémentée

### Un assistant, plusieurs capacités

- Conserver l'entrée voix/texte, le runtime, le planner, le registre de skills, le contrôleur moteur et la supervision communs.
- La commande sélectionne l'intention et la cible ; elle n'impose pas à l'utilisateur de sélectionner un mode « balle », « humain » ou, à terme, « robots ».
- `follow_person` peut rester une intention interne dédiée avec ses propres préconditions et règles de suivi. Une intention ou une skill spécialisée n'est pas un mode d'utilisation séparé.
- Le runtime sélectionne automatiquement la perception appropriée : couleur pour une balle, marqueur associé pour « moi ». Partager l'acquisition caméra et les ressources matérielles ; ne pas créer deux pilotes concurrents de la caméra ou des moteurs.
- Les restrictions du suivi humain s'appliquent à cette capacité ; elles ne rendent pas implicitement l'audio ou le marqueur obligatoires pour les missions balle existantes.
- Cette intégration ne signifie pas exécution simultanée : une seule mission pilote les moteurs. Les règles existantes pendant une mission restent inchangées ; aucune interruption ou substitution implicite par une nouvelle demande. Stop reste prioritaire.

### Extension future exprimée : « rapproche-toi des autres robots »

Ce besoin est enregistré comme future capacité du même assistant, hors livraison du MVP de suivi humain. Il s'agit d'une approche avec condition d'arrivée, pas nécessairement d'un suivi continu.

Son étude devra préciser comment reconnaître les autres robots, résoudre une cible plurielle (robot particulier, plus proche ou groupe), définir la distance d'arrêt et gérer les robots mobiles et obstacles. Aucun marqueur sur les robots, protocole de communication, mouvement coordonné ou mécanisme de découverte n'est supposé acquis.

Les notions de type de cible, identité, position, distance, fraîcheur et qualité doivent rester distinguables dans les contrats de perception. Réutiliser les briques communes utiles sans généraliser prématurément les comportements ni confondre une balle, un porteur de marqueur et un robot. Aucun nouvel intent ou mécanisme multi-robots n'est à implémenter dans ce backlog MVP.

### Rôle du LLM

Le LLM comprend « suis-moi », extrait distance/durée et demande une action de haut niveau. Il ne traite pas chaque image et ne décide ni de la vitesse moteur ni des conditions d'arrêt.

Chaîne proposée :

**Voix/texte → intention `follow_person` → validation et association de cible → planner → comportement déterministe → `RobotController` → moteurs.**

En parallèle : **caméra → observations horodatées du marqueur → estimation distance/orientation**, et **supervision locale → arrêt prioritaire**.

Le nom `follow_person` décrit le besoin ; sa méthode de perception MVP est explicitement `marker`, sélectionnée automatiquement par le runtime. L'identifiant associé vient de la configuration persistante validée, jamais d'un identifiant inventé par le LLM.

### Perception et distance

- Étudier un marqueur fiduciel à identifiant, par exemple ArUco, plutôt qu'une simple pastille colorée. Ce choix technique reste à confirmer par un prototype hors mouvement.
- Vérifier l'API réellement disponible dans l'installation OpenCV du Pi, le coût CPU et les conditions de distribution avant de décider d'une nouvelle dépendance.
- Déterminer taille physique, dictionnaire, identifiant, impression mate, rigidité, hauteur et fixation selon le champ réel de la caméra montée.
- Calibrer intrinsics et distorsion à la résolution/orientation effectivement utilisées ; ne pas réutiliser seulement la focale calibrée pour une balle.
- Estimer distance et angle avec les coins du marqueur et sa taille connue ; rejeter une pose ambiguë, trop oblique, trop petite ou de mauvaise qualité.
- Distinguer distance caméra–marqueur, distance horizontale de déplacement et dégagement pare-chocs–personne. Tenir compte de l'inclinaison, de la hauteur caméra et des déports du porteur/robot.
- L'ultrason détecte le premier écho dans son cône : il sert de garde obstacle, pas d'identification du porteur ni de distance cible fiable par défaut.
- Chaque observation doit porter capture monotone, numéro de trame, identifiant, position/angle, distance et qualité ; relire une même trame ne vaut pas plusieurs confirmations.
- Autre identifiant : ignorer. Identifiant attendu présent en plusieurs exemplaires ou observation incohérente : arrêter pour ambiguïté.

### Comportement et sécurité

États proposés : `idle → acquiring → following ↔ holding`, puis suspension `lost`, `blocked` ou `fault`, ou fin `completed`, `cancelled` ou `emergency_stopped`. Toute annulation mène à un état arrêté explicite.

- `acquiring` : robot arrêté ; confirmations sur des trames distinctes avant toute avance.
- `following` : avance uniquement avec cible fraîche, distance valide, orientation acceptable et zone protégée ; correction d'orientation bornée.
- `holding` : pas de mouvement dans la zone de confort ni si la personne est trop proche ; aucun recul. Retour automatique vers `following` permis uniquement avec toutes les conditions de suivi valides et sans interruption de sécurité.
- `lost` : arrêt sur absence ou péremption, sans recherche tournante ni translation.
- `blocked/fault` : arrêt, raison et verrouillage ; réarmement explicite et nouvelle acquisition.
- `completed` : durée normale atteinte ; pas de mission enchaînée après défaut.
- `cancelled` : stop ou annulation ; nouvelle session nécessaire.
- `emergency_stopped` : urgence physique ; réarmement manuel puis nouvelle session nécessaires.

La réapparition du marqueur ne suffit pas à redémarrer après perte. La reprise d'une session suspendue est explicite et passe par `acquiring`, uniquement avant l'échéance initiale et après correction du problème. Cette échéance continue de courir pendant la suspension et termine aussi une session suspendue. La reprise automatique après interruption de sécurité reste hors MVP ; elle ne doit pas être confondue avec le redépart normal depuis `holding`.

Réutiliser les contrats, traces et helpers éprouvés, mais **ne pas activer les politiques de recul et de balayage du suivi de balle**. La mutualisation devra préserver les comportements objet existants.

### Matériel : réutilisation et points à lever

| Élément | Proposition |
|---|---|
| Pi 5, caméra, châssis 2WD/L298N | Réutilisation sous réserve du benchmark et des mesures mécaniques ; RAM, refroidissement, autonomie et montage à relever |
| Marqueur porté | Nouveau consommable/support ; vérifier visibilité arrière, oscillations et angles en marchant |
| Protection obstacle | Qualifier le HC-SR04 sur tout le volume balayé, y compris les rotations ; ajouter protection/capteurs si couverture insuffisante |
| Arrêt physique | Dispositif accessible coupant l'énergie motrice ; ne pas confondre avec une commande vocale |
| Watchdog indépendant | Étudier mise hors mouvement sur perte de battement/processus/commande ; le Python seul ne suffit pas à démontrer ce cas |
| Capteurs arrière | Non requis pour un MVP strictement sans recul ; nécessaires à réévaluer avant tout recul autonome |
| Encodeurs/IMU | Candidats si le contrôle temporel ne tient pas les critères ; pas déclarés disponibles ni imposés sans mesure |
| Détection de vide | Absente des capacités constatées ; exclusion physique des escaliers et rebords, sinon matériel et périmètre à revoir |

### SH-02 — Inventaire réel déclaré le 2026-10-30

L'utilisateur confirme que le matériel décrit dans le dépôt a été installé et testé. Cet inventaire reprend sa déclaration ; aucun nouveau test physique ni accès au Pi n'a été effectué pendant cette étude. Les essais antérieurs ne démontrent pas à eux seuls les propriétés requises pour le suivi humain.

| Élément | Installation déclarée | Reste à qualifier pour le suivi humain |
|---|---|---|
| Calculateur et base | Raspberry Pi 5, Smart Car 2WD avec L298N, installés et testés | RAM, refroidissement, charge simultanée vision/audio/LLM, masse/gabarit et vitesse physique à relever ou mesurer |
| Caméra | Caméra CSI à l'avant de la Smart Car, installée et testée ; centre de l'objectif à 6 cm du sol ; carte verticale, objectif regardant droit devant, axe approximativement horizontal, confirmé par l'utilisateur | Référence précise, champ vertical/horizontal après rotation de l'image, fixation et réglage éventuel, champ utile sur le marqueur porté, calibration à la résolution/orientation réelles |
| Obstacles | HC-SR04 à l'avant, installé et testé | Position et couverture effective, obstacles bas/latéraux et volume balayé en rotation ; aucun capteur supplémentaire n'est confirmé par cet inventaire |
| Arrêts logiciels existants | L'utilisateur confirme que les moteurs s'arrêtent déjà sur détection d'obstacle et sur commande vocale d'arrêt ; ces capacités sont présentes dans le code inspecté | Réutiliser ces mécanismes, sans les recréer ; mesurer leurs délais et distances d'arrêt dans les conditions du suivi humain et vérifier le stop pendant les annonces audio |
| Coupure physique actuelle et cible | Précision utilisateur : déconnexion d'un fil entre la batterie et le L298N ; Pi alimenté séparément ; un interrupteur physique est prévu en cible, pas déclaré installé | Qualifier l'étendue effective de la coupure et l'interrupteur prévu : adéquation électrique, accessibilité sans approcher les roues, immobilisation et absence de redémarrage au rétablissement. Ne pas assimiler cette coupure à un arrêt d'urgence qualifié |
| Audio | Casque Jabra Bluetooth ; micro/commandes vocales et lecture audio depuis le Pi dans le casque vérifiés séparément par l'utilisateur, pas simultanément | Qualifier le fonctionnement simultané micro/sortie, le stop pendant une annonce, la portée et la détection de perte de chaque sens audio ; la vérification séparée ne démontre pas le fonctionnement simultané |
| Alimentation | Batterie reliée au L298N ; Pi 5 alimenté par une source distincte embarquée sur le robot, sans câble secteur, confirmé par l'utilisateur | Caractéristiques des deux alimentations à relever ; fixation et cheminement des câbles, coupure effective, comportement sur perte/rétablissement et variations de batterie à documenter |
| Watchdog indépendant | Non confirmé | Identifier un dispositif existant ou prévoir une solution ; ne pas déduire sa présence du stop logiciel |

Les arrêts sur obstacle et commande vocale sont des acquis fonctionnels, pas des fonctionnalités manquantes. La qualification complémentaire porte sur leurs limites physiques et sur les cas distincts où le logiciel, le capteur ou la liaison audio ne peut plus transmettre l'arrêt ; elle ne remet pas en cause leur existence.

**Précision sur la coupure physique :** l'emplacement de la déconnexion actuelle (batterie → L298N) et l'intention d'y substituer un interrupteur sont confirmés par l'utilisateur. L'exigence d'inhibition au rétablissement est validée ci-dessous ; sa réalisation, le montage électrique définitif et l'accès à la coupure pendant le suivi restent à concevoir et qualifier. Couper la puissance n'implique pas une immobilisation instantanée ; la distance d'arrêt doit être mesurée. Un interrupteur manuel ne remplace pas un arrêt automatique sur blocage du logiciel.

**Alimentations séparées confirmées :** la coupure batterie → L298N ne coupe pas, par principe, l'alimentation distincte du Pi. Le maintien effectif du calculateur et de l'audio reste à vérifier sur le montage. Cette séparation ne prouve pas que le logiciel détecte la coupure motrice : la détection et le verrouillage empêchant la réapplication d'une commande au rétablissement restent à définir. Aucun redémarrage spontané ne doit être permis.

Le casque porté peut être le canal des annonces : le contrat SH-01 n'impose pas de haut-parleur sur le robot. Sa qualification doit néanmoins démontrer que l'utilisateur entend les messages tout en donnant ses commandes et que les pertes audio détectées provoquent le comportement validé.

### SH-02 — Exigences cibles et preuves à fournir

La validation d'une exigence ne prouve ni sa réalisation ni son fonctionnement. Les décisions suivantes complètent l'inventaire ; la qualification physique reste ouverte.

| Sujet | Statut de spécification | Exigence cible | Preuve de qualification attendue |
|---|---|---|---|
| Rétablissement de la puissance motrice | Validé par l'utilisateur le 2026-10-30 | Toute coupure motrice termine la mission ; le rétablissement laisse les moteurs inhibés. Réarmement manuel distinct, puis nouvelle commande nécessaires pour repartir. Détection de coupure et mécanisme d'inhibition restent à concevoir ; un simple interrupteur coupure/marche ne démontre pas cette garantie | Sur banc protégé, coupure pendant une commande active puis rétablissement : aucun mouvement, aucune reprise de mission ; réarmement seul sans nouvelle commande : aucun mouvement |
| Perte du contrôle logiciel | Validé par l'utilisateur le 2026-10-30 | Surveillance indépendante du programme de pilotage imposant l'inhibition motrice si le programme ne répond plus, si le Pi se bloque ou perd son alimentation. Mission terminée ; retour du programme sans reprise automatique, réarmement manuel puis nouvelle commande. Dispositif et délai maximal à déterminer avec le budget d'arrêt ; matériel non confirmé installé | Injection de perte du programme et de son signal de supervision sur banc protégé, vérification du cas Pi indisponible/perte d'alimentation selon protocole adapté ; délai et distance d'arrêt mesurés ; retour à la normale sans mouvement spontané |
| Organisation et accès à la coupure | Contrainte utilisateur recueillie ; emplacement confirmé, accessibilité non qualifiée | Essais souhaités seul, à proximité du robot, avec casque Bluetooth ; interrupteur prévu sur le robot, nécessitant de s'en approcher. Aucun second opérateur confirmé. La proximité déclarée et le casque ne démontrent pas un accès sûr et suffisamment rapide à la coupure physique depuis la position de suivi ; cette limite du montage doit être résolue avant les essais mobiles avec porteur | Vérification de l'accès depuis la position réelle, sans se pencher vers les roues ni entrer dans la trajectoire, d'abord moteurs déconnectés ; essais mobiles avec porteur non autorisés tant que cet accès et les autres protections ne sont pas qualifiés |
| Géométrie caméra et visibilité du porteur | Montage déclaré ; visibilité non qualifiée | Objectif frontal à 6 cm du sol, regard horizontal. Ne pas présumer qu'un marqueur au dos ou à la ceinture entre dans le champ ; hauteur du marqueur, inclinaison/réhausse éventuelle et fixation à déterminer avec les essais optiques SH-03 | Moteurs déconnectés : relever le champ effectif après orientation de l'image, vérifier les coins du marqueur aux distances demandables et lors de virages doux ; montage final documenté avant calibration |
| Protection obstacle et mouvements autorisés | Validé par l'utilisateur le 2026-10-30 | Conserver le HC-SR04 frontal ; autoriser uniquement les mouvements dont tout le volume balayé est protégé dans le domaine d'essai, rotations comprises. Angle mort incompatible : restriction du trajet/mouvement ou protection complémentaire avant roulage près du porteur. La caméra de suivi n'est pas un détecteur général d'obstacles. Lecture absente, périmée ou en erreur : refus de départ ou arrêt/suspension, reprise explicite après correction. Seuil et âge maximal à déduire du budget d'arrêt, sans reprise aveugle du seuil actuel ; aucun achat imposé à ce stade | Essais avec obstacles inertes de hauteurs/positions représentatives ; couverture et angles morts cartographiés, défauts de lecture injectés, latences et freinage mesurés ; domaine et mouvements permis explicités |
| Disponibilité audio et Jabra | Validé par l'utilisateur le 2026-10-30 | Entrée vocale et sortie audio opérationnelles avant départ ; statut Bluetooth connecté insuffisant comme preuve. Stop pris en compte pendant les annonces, sans auto-commande vocale. Perte détectée d'un sens audio : arrêt/suspension ; reconnexion puis reprise explicite avec vérifications. Si le profil/casque ne tient pas ces exigences, solution audio à revoir avant essais humains. Moyens de détection et délais à documenter, sans garantie de détection de toute panne acoustique silencieuse | Essais des deux sens simultanés, stop pendant lecture, absence d'auto-commande, perte de chaque sens et reconnexion sans mouvement spontané ; portée, intelligibilité et délais mesurés |
| Protocole et décision Go/No-Go | Validé par l'utilisateur le 2026-10-30 | Relevés matériels, essais sans propulsion, banc protégé, cible inerte puis porteur après qualification des protections. Mesurer les maxima de réaction et distances d'arrêt sur sols, charges et états de batterie retenus, rotations comprises ; en déduire seuils obstacle, délais de surveillance et distance minimale avant essais humains. Aucun dépassement du plafond cible de 0,15 m/s ; si la base n'est pas contrôlable à cette vitesse, revoir matériel ou contrat. Aucun Go mobile humain avec l'accès actuel à la coupure non résolu | Fiche de configuration, protocole, résultats et échecs, budget d'arrêt et décision motivée ; le seuil provisoire de 0,8 m n'est pas une validation. Conception et essais requis même après validation documentaire |

### SH-02 — Livrables de qualification et points restant ouverts

Les exigences et l'ordre des essais sont validés. Les inconnues suivantes sont des travaux de relevé, de conception ou de qualification, pas des capacités présumées acquises.

| Action restante | Livrable attendu | Critère de clôture |
|---|---|---|
| Relever la configuration matérielle | Référence caméra, champ/fixation, RAM/refroidissement, gabarit/masse, caractéristiques des deux alimentations embarquées, câbles et fixation | Montage identifié et reproductible ; valeurs inconnues relevées, pas inventées |
| Concevoir la coupure, le réarmement et la surveillance indépendante | Choix des composants/dispositifs, schéma, états d'inhibition, détection de coupure, défaillances couvertes et délais | Mécanismes répondant aux exigences validées puis éprouvés sur banc ; aucun redémarrage au rétablissement ou au réarmement seul. Avancement 2026-10-30 : architecture, états d'inhibition, séquences et contrat logiciel validés (sujets 1, 2, 3 et 5 ci-dessous) ; composants, schéma et délais ouverts |
| Résoudre l'accès physique en essai solo | Solution et protocole compatibles avec le porteur devant le robot | Accès sûr démontré sans rejoindre la trajectoire ou les roues ; l'interrupteur embarqué actuel n'est pas considéré suffisant sur la seule proximité déclarée. Avancement 2026-10-30 : principe d'arrêt opérateur porté P6 validé (sujet 4 ci-dessous), famille non choisie, accès non démontré |
| Vérifier le domaine visuel sans propulsion | Champ réel et géométrie du montage ; données d'entrée pour le choix du marqueur SH-03 | Visibilité non supposée à partir de la seule présence de caméra ; choix final et calibration détaillée en SH-03 |
| Qualifier les obstacles | Mesures de couverture/angles morts et domaine des mouvements permis | Volume balayé protégé ou restrictions/protections complémentaires définies et vérifiées |
| Qualifier le Jabra | Résultats simultanéité, stop pendant annonce, perte/reconnexion, moyens et limites de détection | Exigences audio démontrées dans le domaine retenu, pas seulement micro et sortie testés séparément |
| Mesurer la dynamique et fixer les seuils | Vitesses, maxima de latence, distances de freinage et budget conservateur, sur conditions retenues | Seuils et délais numériques justifiés ; plafond respecté ; toute insuffisance entraîne restriction ou révision explicite avant essai humain |
| Statuer sur le passage aux essais | Rapport avec configuration/version, moyens de mesure, résultats bruts, maxima, échecs, restrictions et verdict | Aucun Go mobile humain tant qu'une protection obligatoire ou l'accès à la coupure reste non qualifié |

Ordre validé : moteurs déconnectés pour caméra/audio ; banc protégé pour coupure, réarmement et perte de contrôle ; cible inerte pour couverture obstacle et dynamique ; porteur humain uniquement après qualification des protections. Les essais sous puissance exigent leur propre protocole protégé ; ce document n'autorise pas de manipulations improvisées.

**Statut de sortie documentaire :** le cadre d'exigences et le protocole de SH-02 sont spécifiés et validés, mais la conception détaillée des protections, les relevés et les mesures ne sont pas terminés. SH-02 reste donc ouvert pour sa qualification. Les données visuelles peuvent préparer SH-03 sans propulsion ; cela ne supprime pas sa dépendance à SH-02 pour la qualification complète ni n'autorise un suivi mobile.

### SH-02 — Conception détaillée documentaire des protections et de l'organisation solo

Engagée le 2026-10-30, en lien avec SH-05, sans code, test, mesure, achat, installation, manipulation matérielle ni essai moteur. Elle réutilise les exigences SH-02/SH-05 validées sans les rouvrir. Aucun composant ni montage électrique n'est choisi ; aucune protection n'est déclarée conçue, installée ou qualifiée ; aucune dépendance technique n'est satisfaite par cette conception documentaire. Aucun Go mobile humain.

Constat du code, lecture seule : `RobotController` porte un verrou d'urgence purement logiciel, effaçable par `clear_emergency_stop()` ; `SmartCar2WD` réalise les rotations sur place en inversant un moteur ; aucun retour d'état d'inhibition ni signe de vie externe n'existe.

#### Sujet 1 — Architecture fonctionnelle des protections

**Décision validée par l'utilisateur le 2026-10-30.** Fonctions et responsabilités, indépendamment de leur réalisation :

| Fonction | Responsabilité | Limites explicites |
|---|---|---|
| P1 — Coupure manuelle de l'énergie motrice | Retirer l'énergie batterie → L298N à l'initiative de l'opérateur | N'empêche pas à elle seule un redémarrage au rétablissement ; pas d'immobilisation instantanée garantie ; accès en solo non résolu |
| P2 — Inhibition motrice indépendante verrouillée | Inhibée par défaut (démarrage, rétablissement, état inconnu) ; verrouillage sur P1, P3 ou perte du Pi, sans dépendre du programme de pilotage | Ne détecte ni obstacle ni erreur logicielle générale ; ne mesure pas l'arrêt |
| P3 — Surveillance indépendante du pilotage et du Pi | Déclenche P2 si le pilotage cesse de prouver son fonctionnement réel : programme arrêté/bloqué, Pi bloqué ou sans alimentation ; extérieure au Pi pour couvrir ces derniers cas ; un signe de vie sans rapport avec le pilotage ne suffit pas | Ne couvre pas un pilotage « vivant mais faux » : relève de L1 |
| P4 — Réarmement manuel | Acte physique distinct après remise en état ; résultat « autorisé, à l'arrêt » | Ne commande jamais de mouvement ; aucun réarmement vocal, textuel ou logiciel |
| P5 — Retour d'état vers le logiciel, lecture seule | Expose inhibé/autorisé, cause si connue et changement d'armement | Le logiciel ne peut jamais lever P2 ; état absent, périmé ou inconnu = inhibé |
| L1 — Supervision logicielle du runtime commun | Préconditions SH-05 avant et pendant chaque mouvement, arbitrage, demande d'arrêt ; réutilise les arrêts existants sur obstacle et commande vocale/texte | Inopérante si le logiciel est indisponible : P2/P3 prennent le relais |
| L2 — Point unique d'émission moteur | N'émet une commande que si P5 indique « autorisé », pour la mission courante, l'armement inchangé et les préconditions valides ; rejette toute commande d'un armement ou contexte antérieur | N'est pas une protection indépendante |
| O — Observabilité SH-08 | Distingue **arrêt demandé**, **commande nulle émise**, **inhibition confirmée** par P5 et **immobilisation physique mesurée** par référence externe | Aucune annonce, trace, persistance ou protection affirmée sans preuve ; politique de données SH-08 inchangée |
| H — Procédure opérateur | Terrain, accès sûr à la coupure depuis la position de suivi, remise en état et réarmement | Le robot ne vérifie pas ces points ; ni la proximité ni l'audio ne démontrent l'accès |

**Remarque utilisateur intégrée :** les arrêts et démarrages courants se font à la voix ou en ligne de commande (L1, stop vocal/texte existants) ; les arrêts physiques sont exceptionnels. Leur caractère exceptionnel ne réduit aucune exigence : P1–P4 restent obligatoires, qualifiés et accessibles avant tout Go mobile humain. Conséquence des exigences SH-05 déjà validées : P2 étant inhibée au démarrage, un réarmement manuel P4 est requis après mise sous tension ou rétablissement ; c'est un acte de préparation, pas un départ de mission, qui exige ensuite une commande vocale/textuelle et toutes les préconditions.

**Conséquences :** le verrou d'urgence logiciel actuel n'est pas une protection indépendante et son effacement logiciel ne suffit jamais après un événement de priorité 1 SH-05. Les règles balle et du runtime commun restent inchangées ; l'exigence P5/L2 vise le suivi humain sans imposer de nouveau mouvement interdit aux missions balle.

**Choix techniques ouverts :** réalisation de P1–P5, forme de la preuve de fonctionnement du pilotage, représentation de l'armement, délais issus du budget d'arrêt.

**Preuves attendues :** conception documentée puis épreuves sur banc protégé selon SH-02/SH-05 ; tests logiciels SH-09 de L1/L2 avec doubles explicites, sans valeur de qualification physique.

#### Sujet 2 — Inhibition et surveillance indépendante

**Décision validée par l'utilisateur le 2026-10-30.**

| État P2 vu via P5 | Signification | Sortie |
|---|---|---|
| `inhibé-verrouillé`, avec cause : mise sous tension, coupure P1, défaut de surveillance P3, perte du Pi, demande logicielle, inconnue | Aucune énergie ou commande motrice ne peut agir | Uniquement par réarmement P4, sans cause encore active |
| `armé-à-l'arrêt` | Le matériel n'interdit plus ; aucun mouvement produit | Tout déclencheur ramène à `inhibé-verrouillé` |

P2 armée ne vaut jamais autorisation de départ : tout mouvement reste soumis à L1/L2 et aux préconditions SH-05.

- **Preuve de fonctionnement du pilotage :** émise par L2 à la fin de chaque cycle de supervision ayant réellement évalué l'état courant (mission, préconditions, âge des observations), y compris à l'arrêt sans mission ; jamais par un minuteur ou un fil d'exécution indépendant du pilotage. Elle change à chaque cycle ; un signal figé, constant ou rejoué vaut absence de preuve.
- **Déclenchement P3 :** absence ou gel de la preuve au-delà d'un délai maximal déduit du budget d'arrêt SH-02 ; aucune valeur fixée. Cas couverts : processus tué, arrêté proprement ou bloqué, boucle de pilotage bloquée, Pi figé ou privé d'alimentation. Non couverts : pilotage vivant mais erroné (L1, SH-09), obstacles, vérification du terrain.
- **Demande d'inhibition logicielle à sens unique :** le logiciel peut demander le verrouillage de P2, jamais le lever ; réservée aux événements de priorité 1 SH-05 qu'il détecte (coupure ou perte de contrôle détectée, exception inattendue dans la boucle motrice).
- **Arrêts courants sans verrouillage matériel :** stop vocal ou texte, obstacle, perception et audio produisent une commande nulle puis la suspension ou la fin prévues par SH-01/SH-05, sans réarmement matériel supplémentaire.
- **Contrainte de réalisation :** P2 ne doit pas pouvoir être contournée par l'état des sorties GPIO du Pi, y compris figées dans un état « marche ». Point d'action exact non choisi.

**Choix techniques ouverts :** support physique de la preuve et de P5, point d'action de P2, délai P3, moyen d'injection des pannes.

**Preuves attendues, séparées :** SH-09 — preuve émise seulement après un cycle complet, absente si boucle bloquée, demande d'inhibition à sens unique, P5 inconnu/périmé traité comme inhibé ; banc protégé SH-02/SH-05 — processus tué/bloqué, Pi figé ou sans alimentation, sortie figée, délai réel et arrêt physique mesurés ; SH-10 — régularité réelle du cycle sous charge sur Pi. Aucune simulation ne qualifie le délai P3 ni un réglage.

#### Sujet 3 — Coupure, rétablissement et réarmement sans départ spontané

**Décision validée le 2026-10-30, par délégation de l'utilisateur, car dérivée des exigences SH-02/SH-05 et des sujets 1–2.**

| Séquence | Déroulement exigé | Garantie contre le départ spontané |
|---|---|---|
| Mise sous tension | P2 `inhibé-verrouillé` (mise sous tension) ; mission humaine motrice refusée avec motif « réarmement requis » ; après P4, `armé-à-l'arrêt` et nouvel armement observé sans commande ; départ seulement sur « suis-moi » vocal ou textuel et préconditions complètes | P4 ne produit aucun mouvement |
| Démarrage ou redémarrage du programme | Le pilotage demande systématiquement l'inhibition à son démarrage, ce qui couvre un redémarrage plus rapide que le délai P3 et impose P4 ; aucune mission ou commande antérieure restaurée | Retour du programme sans reprise |
| Coupure P1 en mission | P2 verrouillé ; dès observation via P5 : priorité 1, mission terminée et verrouillée, commande nulle, commandes en vol invalidées, trace ; annonce tentée seulement si l'audio est disponible, jamais affirmée sans preuve | — |
| Rétablissement de l'énergie | P2 reste verrouillé, mission toujours terminée ; P4 possible seulement énergie rétablie et sans cause active ; ensuite « reprends le suivi » refusé, nouvelle commande « suis-moi » requise | L'énergie seule ne lève pas P2 |
| Perte du pilotage ou du Pi (P3) | P2 verrouillé par la surveillance indépendante ; aucun compte rendu logiciel présumé, trace éventuellement incomplète non reconstituée par invention ; puis séquence de redémarrage | — |
| Inhibition inattendue observée en mission | Toute transition vers inhibé pendant une mission humaine vaut priorité 1, même de cause inconnue | — |
| Suspension ordinaire (marqueur, obstacle, audio) | P2 reste armée, aucun réarmement ; reprise explicite SH-01, échéance inchangée | Inchangé |
| Changement d'armement | Toute transition d'armement invalide dans L2 tout contexte et toute commande antérieurs | Aucune ancienne commande réappliquée |

**Choix techniques ouverts :** représentation de l'armement, moyen d'observer la cause, réalisation de P4 et condition « sans cause active ».

**Preuves attendues, séparées :** SH-09 — séquences sur doubles explicites de P5 avec horloge simulée et ordres d'arrivée concurrents ; banc protégé — coupure pendant commande active puis rétablissement, réarmement seul, redémarrage rapide du programme ; propriétés physiques — arrêt mesuré par référence externe.

#### Sujet 4 — Accès sûr à la coupure depuis la position de suivi, en solo

**Décision validée par l'utilisateur le 2026-10-30.** Constat inchangé : en suivi, l'opérateur seul est devant le robot, dos à lui ; l'interrupteur embarqué P1 impose de revenir vers la trajectoire et les roues. Ni la proximité, ni le casque, ni le stop vocal ou en ligne de commande, qui passent tous par le logiciel du Pi (L1), ne démontrent cet accès.

Ajout de la fonction **P6 — arrêt opérateur porté** :

- Porté ou tenu par l'opérateur, actionnable depuis la position réelle de suivi sans se retourner, sans regarder le robot ni s'en approcher.
- Agit directement sur P2, jamais via le Pi, l'audio Bluetooth, le LLM ou la ligne de commande.
- Sécurité positive : perte de liaison, alimentation du dispositif épuisée ou état inconnu verrouillent aussi P2. En mission, c'est un événement de priorité 1 : fin, verrouillage, réarmement P4 puis nouvelle commande. La fréquence réelle de ces pertes reste à mesurer.
- P6 ne réarme jamais. P1 est conservé pour la préparation et la remise en état, pas comme arrêt depuis la position de suivi. P6 s'ajoute aux déclencheurs de P2 des sujets 1–2 et sa cause est exposée par P5 lorsqu'elle est connue.
- Usage exceptionnel : les arrêts courants restent vocaux ou textuels ; P6 est le recours lorsque logiciel, audio ou voix font défaut, sans réduction d'exigence.

**Choix techniques ouverts :** famille (sans fil supervisé, filaire avec risque d'accrochage, commande à maintien), portée, délai action opérateur → inhibition confirmée déduit du budget d'arrêt, ergonomie. Aucune famille ni composant choisi.

**Preuves attendues, séparées :** moteurs déconnectés — action réalisable depuis la position réelle, dos au robot, sans approcher les roues ; banc protégé — délai jusqu'à inhibition confirmée, arrêt physique mesuré, perte de liaison, alimentation faible et perturbation provoquant le verrouillage ; SH-09 — traitement logiciel de la cause P6 sur doubles. **Aucun essai mobile avec porteur tant que P6 n'est pas réalisé et qualifié.**

#### Sujet 5 — Informations, autorisations et verrouillages imposés au logiciel

**Décision validée par l'utilisateur le 2026-10-30.** Ports logiques destinés à des doubles explicites ; noms de classes non imposés.

| Port | Sens | Contenu minimal | Règle |
|---|---|---|---|
| État de protection P5 | Entrée | `inhibé` / `armé` / `inconnu` ; cause si connue (mise sous tension, P1, P3, P6, demande logicielle, inconnue) ; identifiant d'armement changeant à chaque transition ; instant de lecture monotone | Absent, périmé ou incohérent = inhibé ; seuil de péremption issu du budget d'arrêt, non fixé |
| Preuve de fonctionnement | Sortie | Identifiant de cycle changeant à chaque cycle | Émise par L2 seulement après un cycle complet évalué (sujet 2) |
| Demande d'inhibition | Sortie | Cause | À sens unique ; aucun port de levée |
| Commande moteur L2 | Interne | Type (avance, correction d'orientation, nulle), bornes, identifiants de mission, contexte et armement | Point d'émission unique ; rejet si un identifiant ne correspond pas ; commande nulle toujours permise |

- **Autorisation de mouvement recalculée à chaque cycle :** P5 `armé` et frais, armement identique à celui de l'admission, mission courante active non suspendue non expirée, préconditions SH-05 sujet 1 valides, mouvement dans les limites qualifiées, configuration déclarée qualifiée. Tout élément inconnu interdit le mouvement.
- **Verrous :** après un événement de priorité 1, mission terminée ; nouvelle admission seulement avec un armement postérieur à l'événement, donc un P4 réellement observé. Aucun réarmement vocal, textuel ou logiciel ; le verrou d'urgence logiciel existant ne lève pas ces verrous. Le logiciel n'affirme jamais une vérification opérateur (terrain, accès à P6).
- **Premier lot sans matériel :** aucun adaptateur P5 réel ; sur le robot, P5 inconnu = inhibé, donc mission humaine motrice refusée. Paramètres de test marqués fictifs et non qualifiés selon SH-09.
- **Traces SH-08 :** état/cause P5, armement, identifiants de cycle de preuve, demande d'inhibition, commande nulle émise ; « inhibition confirmée » seulement si P5 l'atteste ; immobilisation physique jamais inscrite par le logiciel. Politique de données SH-08 inchangée.
- **Missions balle :** protection déclarée absente (situation actuelle) : balle strictement inchangée, suivi humain moteur refusé. Protection déclarée présente : toute mission motrice, balle comprise, consulte P5 ; P5 inhibé → refus ou fin sur défaut explicite, sans réessai automatique ni commandes sans effet masquant le défaut. Aucune autre règle balle modifiée : ni marqueur, ni audio, ni P6 imposés, aucun mouvement balle nouvellement interdit ; un réarmement P4 après mise sous tension devient aussi nécessaire avant une mission balle.

**Choix techniques ouverts :** représentation concrète des ports, moyen de déclaration de la présence de la protection et de la configuration qualifiée, adaptateur matériel P5, seuil de péremption.

**Preuves attendues, séparées :** SH-09 — chaque condition d'autorisation invalidée séparément, commandes à identifiants obsolètes rejetées, admission refusée sans armement postérieur, P5 inconnu/périmé, non-régression balle avec protection déclarée absente puis présente ; banc protégé — cohérence entre P5 et l'état réel de P2 ; SH-10 — fraîcheur réelle de P5 sous charge.

#### Sujet 6 — Organisation solo et bilan de l'étape

**Décision validée le 2026-10-30, par délégation de l'utilisateur, car dérivée des sujets 1–5.**

Organisation solo cible, à transformer en procédure puis à qualifier ; non exécutable aujourd'hui :

1. Au robot, avant tout mouvement : terrain vérifié, P1 fermée, P6 porté et opérationnel, P4 réarmé ; le robot reste `armé-à-l'arrêt`.
2. L'opérateur rejoint sa position de suivi sans que le robot puisse partir : aucun départ sans commande vocale ou textuelle et préconditions complètes.
3. Départs et arrêts courants à la voix ou en ligne de commande (L1) ; P6 en recours exceptionnel ; P1 seulement pour la remise en état, robot inhibé.
4. Après tout verrouillage : remise en état au robot, P4, nouvelle commande. Aucune intervention improvisée près des roues ; organisation conforme au sujet 3 de SH-11.

**Bilan des interfaces :** les informations, autorisations, verrous et ports logiques sont suffisamment clarifiés pour proposer un premier lot logiciel isolé avec doubles explicites, sans accès matériel : autorisation motrice et verrous côté logiciel (L1 pour P5, L2), doubles de P5, de la preuve de fonctionnement et de la demande d'inhibition, propagation de priorité 1, déclaration de présence de la protection et non-régression balle. Ce lot ne qualifie aucune protection ni aucun délai ; sur le robot il laisse le suivi humain moteur refusé.

**Blocages restants, non clôturés :** réalisation et qualification de P2, P3, P4, P5 et P6 ; famille et ergonomie de P6 ; point d'action de P2 ; budget d'arrêt et délais P3/P5/P6 ; mesures de freinage et de couverture obstacle ; performances Pi SH-10 ; audio réel Jabra ; perception SH-03/SH-04. Aucune dépendance SH-02/SH-04/SH-05 n'est satisfaite par cette conception. Aucun Go mobile humain.

**Statut :** conception détaillée documentaire ciblée SH-02 des protections et de l'organisation solo réalisée en six sujets ; SH-02 et SH-05 restent ouverts pour conception électrique, réalisation et qualification.

### Lot A — Cadrage documentaire du premier lot logiciel isolé

Cadrage du 2026-10-30, rattaché à SH-02/SH-05 et à un sous-ensemble de SH-09 ; pas un nouveau ticket remplaçant leurs dépendances. Les six sujets SH-02 ci-dessus et les six décisions détaillées de chacun des tickets SH-05 à SH-11 restent intégralement applicables. Aucun code ni test créé ou exécuté pendant cette étape.

#### Sujet A1 — Périmètre et limites

**Décision validée automatiquement le 2026-10-30 par délégation de l'utilisateur, car dérivée du contrat SH-02, sujets 1–3 et 5–6, et de SH-05.**

Le lot prépare uniquement le socle logiciel d'autorisation et de verrouillage :

- Lecture seule de P5 ; état absent, inconnu, périmé ou incohérent traité comme inhibé, sans confirmation matérielle inventée.
- L2 : autorisation recalculée par cycle, liée à la mission, au contexte et à l'armement courants ; refus explicite des commandes obsolètes et commande nulle toujours permise. Les préconditions humaines acquises restent obligatoires ; aucune condition inconnue n'est rendue vraie par défaut.
- Preuve de fonctionnement changeante, émise après chaque cycle réellement et complètement évalué, y compris à l'arrêt sans mission ; aucun générateur indépendant de la boucle surveillée.
- Demande d'inhibition à sens unique, au démarrage du programme dans le chemin protégé et pour les événements de priorité 1 détectés ; aucune opération logicielle de réarmement.
- Propagation de priorité 1 : arrêt demandé sans attendre annonces/arbitrage, fin verrouillée, invalidation des commandes/résultats antérieurs, aucune étape suivante ni relance automatique.
- Nouvelle admission après priorité 1 uniquement sur observation d'un armement postérieur à l'événement, puis nouvelle demande valide ; ni retour de P5, ni effacement du verrou d'urgence logiciel, ni réarmement seul ne valent départ.
- Déclaration explicite de présence de la protection, distincte de son état et de sa qualification : absente, balle/primitives/stop inchangés et humain moteur refusé ; présente, toute mission motrice consulte P5, sans autre restriction balle ajoutée.

**Hors lot :** réalisation de P2/P3/P4/P5/P6 et adaptateur matériel P5 ; perception marqueur et calibration ; loi de suivi SH-06 ; intégration naturelle complète SH-07 ; audio réel, mesures Pi et recette physique. Les raccordements logiciels strictement nécessaires et les doubles de mission ne constituent pas ces réalisations.

**Choix techniques ouverts :** implantation du point L2, représentation concrète des ports/identifiants/résultats, coordination des cycles et de l'admission, support déclaratif de présence. Aucun composant, réglage ou délai réel choisi.

**Preuves attendues :** vérifications unitaires, intégration simulée des composants réellement concernés et replay recalculant les décisions selon SH-09 ; aucune preuve acquise dans cette session. Une réussite future ne clôturera ni SH-05 ni SH-09 globalement et ne satisfera aucune dépendance matérielle. Sur le robot, le suivi humain moteur restera refusé.

#### Sujet A2 — Frontière d'intégration et surfaces existantes

**Décision structurante validée explicitement par l'utilisateur le 2026-10-30 :** ancrer L2 dans `RobotController` et l'admission/propagation des verrous dans le runtime commun. Conserver `SmartCar2WD` et le comportement balle ; éprouver le raccordement humain par missions synthétiques, sans livrer SH-06 ni l'intégration naturelle complète SH-07. Sur le chemin réel, refus humain explicite, sans repli vers une balle par défaut.

Inspection en lecture seule du 2026-10-30, pas constat d'exécution :

| Surface existante | Constat et responsabilité du futur lot | À préserver / limite |
|---|---|---|
| [RobotController](../../src/irobot/interfaces/robot_controller.py) | Commandes directes et temporisées, horloge/attentes injectables, événement d'arrêt logiciel, délégation `__getattr__`. Ancrage L2 : contrôler les émissions effectives, associer contexte/armement, recontrôler pendant les mouvements temporisés et propager un refus/défaut explicite | `stop` toujours accessible ; effacer l'événement logiciel ne réarme pas. Les méthodes déléguées ou l'accès au robot sous-jacent ne doivent pas fournir un contournement dans le chemin protégé. Aucun changement de contrat hors protection déclarée présente |
| [SmartCar2WD](../../src/irobot/hardware/smart_car/smart_car.py) | Driver directions/PWM/stop et lecture obstacle ; aucune P2–P5 identifiée dans cette surface. `set_speed` écrit déjà les PWM : l'inventaire des émissions ne se limite pas à `forward` | Aucun GPIO, câblage, PWM, cache capteur, seuil obstacle ou CLI matériel modifié par ce lot. Les écritures préparatoires de vitesse du chemin protégé doivent être ordonnées/gardées en amont ; le driver seul n'est pas L2 et ne sera pas présenté comme protégé |
| [VoiceRuntime](../../src/irobot/interfaces/voice_runtime.py) | Assemblage live, validation de plan, exécution/réessais, listener stop, worker et nettoyage. `mission_running` repose actuellement sur la vie du worker ; les budgets génériques utilisent aussi l'heure civile | Ajouter seulement les raccordements du socle : présence, admission, réservation humaine même worker terminé, priorité 1, résultat explicite sans étape suivante ni réessai humain. Échéance humaine monotone inchangée ; budgets/réessais balle conservés hors défaut de protection |
| [LanguageController](../../src/irobot/interfaces/language_controller.py) | Entrées texte et intention créent chacune un contexte puis exécutent des skills. Ces deux parcours doivent transmettre admission/identifiants et interruptions, sans succès apparent après refus L2 | Pas de contournement par appel interne ; pas de refonte des parcours balle |
| [Planner](../../src/irobot/domain/orchestrator/planner.py), [registre](../../src/irobot/domain/orchestrator/registry.py), [exécuteur](../../src/irobot/domain/orchestrator/executor.py) | Mapping/registre existants à conserver ; chaîne réelle à traverser pour les scénarios du socle. Aucun comportement humain de production à inventer pour compléter un plan absent | `follow_person` distinct ; capacité/skill absente = refus motivé, jamais fallback sur plan partiel, balle ou primitive. Un fournisseur synthétique explicite est réservé aux tests isolés |
| [follow_object](../../src/irobot/domain/skills/behaviors/follow_object.py), [tracking](../../src/irobot/domain/skills/behaviors/target_tracking.py), [primitives](../../src/irobot/domain/skills/primitives/base_motion_primitive.py) | Appels directs/temporisés et sorties à inventorier pour traverser L2 lorsque la protection est présente ; certains résultats d'arrêt objet sont historiquement `success` et sont reclassés par le runtime | Aucun changement de recul, balayage, alignement, cible `yellow`, distance ou résultat objet hors adaptation de propagation d'un défaut de protection ; ne pas recopier ces règles dans l'humain |
| [Parser/validator](../../src/irobot/interfaces/intent_parser.py), [gardes](../../src/irobot/interfaces/plan_guards.py) et entrées LLM/locales | Garde de refus humain nécessaire dans les entrées concernées, demande complète comprise ; l'actuel routage objet ne doit pas convertir une demande humaine en `follow_object` | Pas de compréhension humaine partielle activée. Stop local préservé ; reprise locale sans LLM, recevable seulement dans une session synthétique admissible, refusée sinon. Validation intégrale, aucune suppression de morceau interdit pour exécuter le reste |
| [Settings](../../src/irobot/config/settings.py) et assemblage du runtime | Déclaration de présence explicitement transmise, distincte de l'état P5 et de la qualification ; aucun adaptateur P5 réel | Aucune découverte matérielle, aucun simulateur de secours, aucun réglage réel déclaré qualifié ; calibration d'exploitation inchangée |

**Conséquence de frontière :** absence d'algorithme de suivi, de détecteur marqueur, de prompt humain complet ou d'annonce audio réelle n'empêche pas de vérifier le socle avec des producteurs de faits/commandes synthétiques. Ces absences restent des travaux SH-03/SH-04/SH-06/SH-07/SH-08, jamais des fonctions déclarées livrées. Les gardes de refus et les composants d'admission/L2 réellement raccordés ne peuvent pas être remplacés par des doubles qui feraient la décision à leur place.

**Choix techniques ouverts dans cette frontière :** noms/types concrets, organisation interne des cycles, mécanisme de synchronisation et support de configuration. L'implantation ne doit pas introduire de second runtime, de mode utilisateur, de propriétaire caméra concurrent ou d'accès moteur parallèle.

**Preuves attendues :** traçabilité de tous les chemins d'émission du périmètre, refus explicites traversant les contrôleurs/exécuteur/runtime, tests de contournement et non-régression. Ni lecture du code ni approbation de cette frontière ne démontrent ces propriétés.

#### Sujet A3 — Doubles explicites, temps et présence de protection

**Décision validée automatiquement le 2026-10-30 par délégation, car dérivée de SH-02 sujet 5 et SH-09 sujets 1–3.** Les ports restent logiques ; aucun nom de classe, support électrique ou protocole matériel imposé.

| Double obligatoire | Faits fournis / sorties observées | Cas et limites |
|---|---|---|
| P5 en lecture seule | État, cause disponible, identifiant d'armement, instant monotone du retour ; séquence scriptée par le scénario, indépendante de la décision L2 | Armé/inhibé/inconnu, absent, périmé, incohérent, erreur de lecture, rétablissement, anciens retours/rejeu et changement d'armement. Relire le même retour ne le rajeunit pas ; ne pas fabriquer de cause ou de confirmation |
| Sortie de preuve de cycle | Collecte ordonnée des identifiants changeants et du point d'émission observé | Aucun acquittement de P3 simulé comme réel ; vérifie absence avant fin de cycle, absence si cycle interrompu/bloqué, identifiants non constants/non rejoués, erreur du port explicite |
| Sortie de demande d'inhibition | Collecte ordonnée de la cause et de la demande | Aucune méthode de levée/réarmement ; appel enregistré distinct de P2 effectivement verrouillée. Panne du port injectable ; P5 ne change pas automatiquement pour donner raison au logiciel |
| Horloge monotone et attentes contrôlées | Avancement explicite, instants/frontières et points de synchronisation ; heure civile séparée si nécessaire | Aucun sommeil réel pour valider une durée simulée, aucune qualification de délai Pi ; blocage d'un cycle simulé distinct d'un gel réel du Pi |

Compléments nécessaires à l'intégration : sortie moteur factice enregistrant aussi vitesse et commande nulle, fournisseur synthétique de mission/contexte/préconditions humaines, perception/LLM/audio/journal factices selon les chemins traversés. Les contrôleurs, admission, arbitrage et L2 restent les composants réels du lot. Une précondition « qualifiée » synthétique est un fait de scénario explicitement fictif, jamais une qualification ni un moyen d'autoriser le robot.

**Déclaration de présence :** deux situations explicites, absente (référence actuelle) et présente. La compatibilité avec une configuration historique sans ce nouveau champ doit être documentée comme situation actuelle absente, pas comme une détection matérielle. Une valeur fournie mais invalide est une erreur explicite, jamais convertie en absence. Une présence déclarée sans port P5 exploitable reste présente avec état inconnu/inhibé ; aucune rétrogradation automatique vers le fonctionnement non protégé. Présence, état d'armement, qualification et environnement synthétique sont des informations distinctes. Ni une variable ni un double ne qualifie P2–P6.

**Isolation attendue :** raccordement explicite avant imports/initialisation à effet matériel ; aucune construction live, GPIO, caméra, capteur, audio/Bluetooth, recherche de modèle, serveur ou réseau, découverte des tests comprise. Dépendance factice manquante ou accès interdit = échec explicite, jamais recours au réel. Fichiers/configurations synthétiques isolés, tâches de test bornées puis terminées ; borne externe justifiée lors de la réalisation, distincte du temps simulé.

**Choix techniques ouverts :** types/noms des doubles et déclarations, injection et garde d'accès, synchronisation, borne externe. Péremption P5 et délai P3 réels restent issus du futur budget SH-02 ; uniquement paramètres fictifs identifiés pour les cas logiques, sans valeur proposée ici.

**Preuves attendues :** appels et erreurs observables indépendamment du journal testé, rejeu déterministe, accès interdits détectés et absence de ressources/tâches résiduelles. Aucun double créé ni essayé dans cette session.

#### Sujet A4 — Cycles L2, verrous et propagation

**Décision validée automatiquement le 2026-10-30 par délégation, car dérivée de SH-02 sujets 2–3/5, SH-05 et SH-07 sujets 4–5.** Ce séquencement précise le socle, sans redéfinir les états et priorités approuvés.

1. Dans le chemin protégé, démarrage du programme : demande d'inhibition, aucune restauration de mission/commande ni admission sur un ancien état armé ; un redémarrage rapide ne dispense pas de P4.
2. Chaque cycle prend en compte l'état courant de P5, la mission/réservation, le contexte et l'armement, les préconditions applicables et leur fraîcheur, les interruptions et l'échéance. À l'arrêt sans mission, l'absence de mission est évaluée explicitement ; elle n'autorise aucun mouvement.
3. Si arrêt requis, le demander sans attendre classement, annonce ou écriture de trace. Déterminer ensuite état/causes selon les priorités SH-05, sans masquer les événements simultanés.
4. Toute émission non nulle du périmètre, y compris les écritures de vitesse pouvant agir sur les sorties, passe par L2. Vérification coordonnée avec l'émission et l'invalidation du contexte ; une autorisation calculée avant suspension/fin/changement d'armement ne reste pas utilisable après. Recontrôles pendant commandes temporisées, pas seulement au début ou au retour de l'appel.
5. Après évaluation complète et traitement des décisions du cycle, émettre une preuve changeante. Le cycle peut conclure à l'inhibition ou à l'arrêt : preuve de fonctionnement ne signifie ni autorisation ni succès de mission. Avant complétude, blocage ou exception inattendue : aucune preuve de ce cycle ; arrêt/défaut explicite et demande d'inhibition de priorité 1 lorsque détectables. Aucune confirmation d'arrêt ou d'inhibition si l'appel ou le retour nécessaire manque.

Le fonctionnement au repos exige une évaluation réelle même sans worker de mission ; un minuteur d'émission autonome est exclu. L'organisation de l'exécution reste à choisir, mais elle doit permettre qu'une boucle surveillée bloquée cesse de produire sa preuve. Ni le listener vocal ni un autre fil ne peut renouveler celle-ci en se bornant à constater que le programme existe. Aucune période ou garantie de temps réel déduite des constantes nominales existantes.

**Verrous et admission :** fin verrouillée après priorité 1, commandes/résultats antérieurs invalidés et motifs propagés à l'exécuteur, au contrôleur de langage puis au runtime. Aucun `accepted`/`success` apparent ne doit cacher le défaut de protection, aucun réessai générique ni étape suivante ne doit l'effacer. Toutes les causes conservées ; P6 n'est qu'une cause P5 scriptée dans ce lot, pas une liaison réelle. État de protection inexploitable interdit l'émission ; en mission humaine, perte de l'autorisation de protection vaut fin verrouillée selon SH-02. Protection présente : une mission balle rencontre aussi un refus/une fin explicite sur défaut P5, sans réessai automatique.

**Postériorité de l'armement :** l'ordre d'observation doit établir une transition d'armement postérieure à l'événement verrouillant ; une simple inégalité de jetons, un retour ancien retardé ou un état armé déjà présent au redémarrage ne la démontre pas. Pas d'ordre numérique arbitraire imposé aux identifiants. Sans preuve de postériorité, admission refusée. Armement postérieur observé sans nouvelle demande : toujours aucune mission ni commande. Nouvelle demande validée et préconditions complètes restent nécessaires ; aucune commande reçue avant disponibilité n'est conservée pour plus tard.

**Suspension ordinaire :** maintien de la réservation même après fin du worker, stop/reprise locaux sans LLM, reprise de la même session synthétique seulement après correction et contrôles requis. Même échéance, aucun réessai humain automatique ; disparition d'un défaut sans mouvement. Ces raccordements sont vérifiés sans implémenter la réacquisition optique ou la loi de suivi. Sur le chemin réel, la reprise humaine reste refusée sans session admissible et capacité réalisée/qualifiée.

**Choix techniques ouverts :** représentation et coordination atomique des identifiants/verrous/émissions, propriétaire du cycle, résultat d'interruption partagé et mécanique de réservation. Les choix devront satisfaire ces invariants, sans effacer le stop logiciel existant ni prétendre rendre atomiques les phénomènes physiques.

**Preuves attendues :** coupure/rétablissement/réarmement et redémarrage scriptés ; invalidation entre contrôle et émission ; priorité 1 contre stop/échéance/confirmation/reprise ; erreur de chaque port ; arrêt sans journal disponible ; réservation et échéance conservées. Pas d'épreuve de panne matérielle dans ce lot.

#### Sujet A5 — Oracles SH-09 et non-régression ciblée

**Décision validée automatiquement le 2026-10-30 par délégation, car dérivée des six sujets SH-09 et de SH-02 sujet 5.** Sous-matrice documentaire du lot, pas création de tests ni remplacement des matrices complètes SH-04 à SH-11.

Chaque cas futur identifie sa décision source, configuration/doubles, faits et ordre injectés, attendus et interdits établis avant exécution, observations obtenues et limites. Oracles indépendants des décisions calculées : ne pas appeler la fonction d'autorisation testée pour fabriquer son attendu. Observer séparément admission/résultats, commandes réellement remises au moteur factice, preuve, demande d'inhibition et traces ; panne du journal sans perte de l'observation des sorties. Observateur indisponible = résultat inconclusif, jamais réussite par absence d'événement.

| Référence du lot / source | Oracle indépendant attendu |
|---|---|
| A-O1 — SH-02 sujet 5, SH-05 sujet 1 | Invalider séparément chaque condition applicable de l'autorisation humaine : aucun appel moteur non nul ; motif exact et arrêt permis. État de mission actif seul insuffisant. Cas nominal exclusivement synthétique démontrant aussi que le garde ne refuse pas indistinctement toute entrée valide |
| A-O2 — SH-02 sujets 2/5 | P5 absent/inconnu/inhibé/périmé/incohérent ou lecture en erreur : aucun mouvement, état/motif explicites ; retour répété sans rajeunissement. Frontières temporelles avant/à/après la convention déclarée du paramètre fictif, sans trancher le futur seuil réel |
| A-O3 — SH-02 sujets 3/5 | Mission, contexte ou armement obsolète, changement entre contrôle et émission, résultats tardifs : aucune commande antérieure émise. Commande nulle accessible quel que soit le verrou |
| A-O4 — SH-02 sujet 2 | Pour chaque cycle complètement évalué : une preuve changeante après complétude, y compris au repos et si décision d'arrêt. Cycle non évalué, partiel ou bloqué : aucune preuve de ce cycle ; pas de renouvellement par listener/minuteur indépendant ni rejeu constant |
| A-O5 — SH-02 sujets 2–3 | Demande d'inhibition au démarrage protégé et sur priorité 1 détectée ; aucune demande sur simple stop/obstacle/perception/audio ordinaires. Aucun port de levée ; demande observée sans « inhibition confirmée » tant que P5 ne l'atteste pas |
| A-O6 — SH-02 sujet 3, SH-05 sujets 2/5 | P1/P3/P6 et inhibition inattendue scriptés ; priorité 1 contre stop/échéance/reprise/confirmation, ordres concurrents identifiés : arrêt prioritaire, toutes causes conservées, fin verrouillée, aucune étape suivante ni réessai, aucun résultat de substitution favorable |
| A-O7 — SH-02 sujets 3/5 | Rétablissement, effacement logiciel, ancien jeton ou retour retardé ne permettent pas l'admission. Armement postérieur observé seul : aucun départ. Nouvelle demande complète après cet armement : admissibilité réévaluée, sans ressusciter une ancienne demande. Redémarrage rapide également couvert |
| A-O8 — SH-05 sujet 5, SH-07 sujets 4–5 | Session synthétique suspendue avec worker terminé : réservation conservée ; autres demandes non exécutées/non mémorisées. Stop/reprise locaux avec LLM indisponible ; même mission/contexte utile/échéance et nouvelles validations, aucune réinitialisation ni relance automatique |
| A-O9 — SH-07 sujets 1/3–4 | Voix transcrite synthétique, texte, intention et sortie LLM factice : demande humaine réelle refusée, jamais convertie en `follow_object`/`yellow`. Demande composée/invalide refusée intégralement, sans exécution partielle. Skill/dépendance/plan humain absent = motif explicite, pas de succès vide |
| A-O10 — SH-02 sujet 5, SH-09 sujet 4 | Protection absente : référence balle/primitives/stop inchangée. Présente et P5 armé frais après préparation requise : mêmes commandes/comportements balle autorisés ; P5 inexploitable avant/pendant : refus/fin explicite sans réessai. Aucun marqueur/audio/P6 propre à l'humain exigé de la balle ; la cause P6 d'inhibition reste applicable via P5 |
| A-O11 — SH-08 sujets 4–6, SH-09 sujet 5 | Arrêt demandé, commande nulle remise au double, état d'inhibition attesté par double P5 et immobilisation physique distingués dans les sorties. Aucun énoncé physique, d'audition ou de persistance inventé ; panne d'un port/journal visible, arrêt non tributaire du journal, aucune donnée supplémentaire |
| A-O12 — SH-09 sujets 1/3/6 | Chaîne réelle du socle traversée en intégration et replay recalculant les décisions ; violation d'isolation détectée, absence de tâches résiduelles et résultats reproductibles. Tests des doubles seuls ou relecture d'un journal de succès insuffisants |

**Référence existante inspectée, à identifier par version lors de la future réalisation :**

- [test_follow_object](../../tests/unit/test_follow_object.py) : robot/perception et temps simulés, maintien, approche, recul, alignement, perte/balayage/réacquisition, obstacle et arrêt. Les cas qui passent directement un `World` à la skill ne prouvent pas le passage par L2 : conserver leur contrat et compléter le raccordement, pas les rebaptiser tests du garde.
- [test_follow_object_wiring](../../tests/unit/test_follow_object_wiring.py) et [test_scenario_yellow_ball](../../tests/unit/test_scenario_yellow_ball.py) : parser/validator/planner et chaîne balle, cible, budgets et traces ; cinq minutes simulées ne sont pas cinq minutes qualifiées sur Pi.
- [test_primitive_safety_stop](../../tests/unit/test_primitive_safety_stop.py), [test_emergency_stop](../../tests/unit/test_emergency_stop.py), [test_skills_primitives](../../tests/unit/test_skills_primitives.py) : arrêt pendant primitive, exception, pas d'étape suivante/réessai, stop local et commandes existantes. Effacement du drapeau logiciel attendu historiquement conservé, mais sans effet de réarmement du nouveau verrou.
- [test_voice_runtime](../../tests/unit/test_voice_runtime.py) : validation intégrale du plan, stop sans LLM, interruptions, budgets/réessais et traces ; sélectionner les cas et contrôler leurs dépendances avant toute future exécution.
- [test_smart_car_sensor](../../tests/unit/test_smart_car_sensor.py) : pins/capteur remplacés après import, cache et verrou capteur. Ni l'import du driver ni ce remplacement ne démontrent l'isolation préalable aux imports exigée pour le lot.
- [Intégration LLM existante](../../tests/integration/test_voice_runtime_llm_integration.py) : recherche de modèles, réseau local et démarrage possible d'un serveur ; exclue de la campagne isolée en l'état. Aucun lancement global ou collecte automatique de toute la suite ne doit l'activer.

Non-régression en deux configurations déclaratives distinctes, sans altérer les attendus historiques pour faire passer un écart. Dans une même instance de runtime : balle → mission humaine synthétique → balle ; humain suspendu puis demande balle non exécutée, reprise ou fin explicite, et nouvelle demande balle après nettoyage. Répéter les parcours pertinents avec P5 présent/armé puis ses pertes ; observer aussi les appels directs, temporisés, vitesse/restauration de vitesse et stop. La garde des sorties ne doit pas introduire une nouvelle interdiction balle de recul, rotation ou balayage.

**Choix techniques ouverts :** format concret des cas/rapports, sélection exacte et injection des suites, synchronisations et références de version. **Preuves attendues :** couverture par obligation des niveaux unitaire/intégration/replay pertinents, attendus/obtenus, écarts préexistants distincts des régressions, cas bloqués et historique conservés. Moyennes/p95 ou taux global de réussite ne compensent aucun écart obligatoire ; aucun réglage/délai réel qualifié par une durée fictive.

#### Sujet A6 — Critères de fin, bilan et blocages

**Décision validée automatiquement le 2026-10-30 par délégation, car dérivée de SH-09 sujets 5–6, SH-10/SH-11 et des sujets A1–A5.**

La future réalisation du lot ne sera terminée que si :

1. Le socle et ses raccordements sont effectivement réalisés dans la frontière A2 ; tous les chemins d'émission concernés traversent L2, avec refus/fins explicites et sans contournement par entrée interne, délégation ou écriture de vitesse.
2. Les obligations A-O1 à A-O12 ont leurs vérifications pertinentes effectivement exécutées, aux niveaux unitaire/intégration/replay convenus, sans écart obligatoire, cas manquant, violation d'isolation ou observateur nécessaire indisponible. Frontières sous paramètres fictifs explicitement séparées de la validation des futurs réglages réels, hors lot.
3. La non-régression balle/primitives/stop est démontrée protection absente puis présente selon A5, sans modification opportuniste des attendus ni restriction humaine ajoutée à la balle. Une anomalie obligatoire non résolue, même préexistante, interdit le verdict conforme du périmètre concerné.
4. Les cas du chemin réel démontrent le refus humain moteur sans protection/qualification/capacité requise ; aucun adaptateur P5 réel ni commutateur de simulation ne permet d'autoriser le robot. Les cas nominaux humains ne commandent que le moteur factice explicitement isolé.
5. Un rapport vérifié relie exigences, références de version/configuration, doubles, scénarios, attendus/obtenus et commandes observées ; limites, paramètres fictifs, erreurs, cas non exécutés et historique conservés selon SH-08. Aucune nouvelle collecte, durée de conservation ou export implicite.

Verdicts limités au lot : conforme dans le périmètre logiciel déclaré / non conforme / incomplet-bloqué selon SH-09. Écrire des tests sans les exécuter ne démontre rien ; un sous-ensemble réussi ne clôture ni SH-09 ni SH-05. Les fonctions humaines complètes hors frontière restent non réalisées, pas réputées testées par leurs fournisseurs synthétiques.

**Ce que le lot ne prouvera pas :** aucune protection indépendante réalisée/qualifiée ; aucun délai P3/P5/P6 ni réglage réel, aucune régularité garantie du cycle sur Pi ; aucune précision optique, couverture de volume balayé, vitesse au sol ou distance d'arrêt ; aucun accès sûr à la coupure en solo ; aucune disponibilité/intelligibilité audio réelle, audition ou persistance garantie. Une commande nulle remise au double n'est ni une inhibition physique confirmée ni une immobilisation mesurée. Précision visée, zone de commande et distance minimale de sécurité restent trois notions distinctes, sans nouveau seuil ni algorithme dans ce lot.

**Bilan documentaire : le lot A est suffisamment cadré pour une implémentation dans une session ultérieure, sous autorisation explicite.** Aucun blocage matériel n'oblige à rendre le matériel disponible pour réaliser ce socle isolé ; cela ne satisfait pas ses dépendances techniques. Types/noms, coordination concrète des cycles/admission et format des scénarios/rapports restent des choix de réalisation à expliquer dans la frontière approuvée ; tout changement structurant de cette frontière exige une nouvelle validation. Une isolation non démontrable ou une obligation logicielle non vérifiable bloque le verdict du lot, sans être masquée par les doubles.

**Blocages réels conservés :** P2/P3/P4/P5/P6 à réaliser et qualifier ; famille de P6 et ergonomie non choisies, accès sûr depuis la position de suivi non démontré ; point d'action P2 et conception électrique ouverts ; budget d'arrêt, délais et fraîcheur P5 à établir/qualifier ; freinage/couverture obstacle, perception SH-03/SH-04, réalisations SH-05 à SH-08, performances Pi SH-10, audio réel et recette progressive SH-11 encore requis selon leur domaine. Aucune dépendance technique satisfaite par sa seule spécification/conception. Ni proximité du robot ni audio ne démontrent l'accès. **Suivi humain moteur toujours refusé sur le robot ; aucun Go mobile humain.**

**État de cette session :** cadrage et inspection en lecture seule uniquement ; backlog seul modifié, aucun code ni test créé, aucun test, mesure, acquisition matérielle, charge, achat, installation, manipulation matérielle ou essai moteur. Critères ci-dessus = preuves futures, pas résultats actuels.

**Prochaine étape proposée puis validée explicitement par l'utilisateur le 2026-10-30, non commencée :** réalisation du seul lot A dans une session ultérieure, avec ses vérifications logicielles isolées et rapport SH-09 limité au lot. Ni intégration matérielle, campagne Pi/audio, recette physique, suivi humain réel ni passage à SH-12. La décision est consignée en section 9 ; aucune réalisation engagée dans la présente session.

### SH-03 — Spécification progressive sans propulsion

Cadre d'exigences et protocole validés avec l'utilisateur le 2026-10-30 ; aucun code, acquisition caméra ou essai physique réalisé. SH-02 reste ouvert. Cette préparation documentaire et optique ne clôture pas la dépendance de qualification.

| Sujet | Décision / statut | Suite requise |
|---|---|---|
| Géométrie caméra–marqueur | L'utilisateur souhaite décider après observation du champ réel, moteurs déconnectés ; ni rehausse/inclinaison caméra ni emplacement porté plus bas ne sont choisis | Relever référence caméra et champ après orientation de l'image ; observer les emplacements candidats aux distances d'usage, puis choisir et documenter le montage avant calibration |
| Technologie du marqueur | Principe validé : marqueur fiduciel noir et blanc à identifiant ; ArUco candidat initial, pas choix définitif de bibliothèque/dictionnaire | Vérifier les API disponibles dans OpenCV sur Pi et les performances avant de choisir famille, dictionnaire et identifiant ; aucune nouvelle dépendance décidée. Ne constitue pas une authentification du porteur |
| Support porté | Validé : un seul marqueur cible sur support léger, plan et suffisamment rigide, mat et contrasté, avec marge claire conforme à la famille choisie ; fixation stable sur le porteur, non tenu à la main, sans cordon pendant ni élément traînant. Pas d'impression directement sur vêtement souple ni de copies du même identifiant | Hauteur de port et dimensions finales après observation/essais ; mesurer et configurer la taille physique imprimée avec une convention explicite, distincte de la taille totale du support |
| Acceptation des observations | Validé : identifiant attendu unique dans l'image, quatre coins visibles, géométrie exploitable et distance fraîche. Rejet des observations tronquées, trop petites/obliques, floues, ambiguës ou sans distance fiable ; motif explicite, pas de mouvement sur observation invalide et application de la suspension validée | Établir et consigner les seuils de qualité par essais sur Pi. Aucun repli sur couleur/autre ID/taille humaine supposée/dernière distance ; lissage éventuel sans masquer une perte ni rajeunir une observation |
| Calibration et référence de distance | Validé : calibration du montage final avec résolution, orientation, focale et distorsion documentées ; taille du marqueur mesurée selon la convention du détecteur, distincte de la marge/plaque. Ne pas assimiler distance caméra–marqueur et dégagement avant du robot–porteur | Tenir compte des hauteurs, inclinaisons et déports avec une référence reproductible de la partie du porteur la plus proche dans les postures testées. Si précision insuffisante : réduire le domaine ou revoir le montage avant pilotage. Toute modification du montage, taille ou paramètres optiques exige revalidation et recalibration si nécessaire |
| Recette optique et objectifs | Validé : robot immobile, moteurs déconnectés ; points d'usage 1,2/1,5/2 m de dégagement, limites caractérisées à 1/2,5 m sans élargir les consignes ; face et ±15°/±30°, décalages dans le champ utile, porteur immobile puis marche lente dans le champ du robot fixe ; éclairage consigné, faible lumière/contre-jour pour éprouver les rejets | Par condition nominale supportée, au moins 100 images nouvelles, observations acceptées ≥95 %, erreur absolue de dégagement ≤20 cm pour ≥95 % des observations acceptées. Rapporter maxima, biais et séries de rejets. Débit cible ≥10 observations nouvelles/s et latence capture→observation p95 ≤150 ms sur Pi, à confirmer sous charge en SH-10. Échec : domaine explicitement réduit ou montage revu et retesté |
| Cas négatifs et fraîcheur | Validé dans le protocole de recette : autre ID jamais adopté ; doublon visible de l'ID attendu traité comme ambiguïté ; occultation, pli, troncature et flux figé éprouvés | Rejet/perte ou péremption explicites selon le cas, jamais maintien artificiel d'une observation exploitable ; ces essais sans propulsion ne démontrent pas le freinage |
| Livrables, références et données | Validé : fiche reproductible caméra/OpenCV, montage, famille/dictionnaire/ID, taille mesurée et impression, calibration, critères de rejet, domaine retenu, résultats bruts et verdict. Références de mesure indépendantes de l'estimation caméra, méthode et incertitude consignées. Pas de vidéo par défaut ; images de diagnostic uniquement avec accord explicite et règles de conservation/suppression définies | Traces et métriques sans images par défaut. Choix final après observation du champ, comparaison de candidats puis calibration. Le cadrage ne déclenche ni développement ni achat ; clôture du ticket après choix justifiés et preuves, pas sur validation documentaire seule |

#### SH-03 — Ordre des travaux et décisions encore ouvertes

1. **Relever caméra et champ réel**, après orientation effective de l'image, sans propulsion ; comparer les emplacements portés et réglages possibles. Le montage caméra/marqueur reste à choisir, conformément au choix utilisateur de différer la décision.
2. **Comparer des candidats de marqueur/support** : famille disponible sur Pi, tailles imprimées mesurées, visibilité et qualité ; choisir dictionnaire et identifiant cohérents avec la configuration persistante de « moi ». ArUco n'est encore qu'un candidat ; aucun numéro ni dimension finale n'est fixé.
3. **Arrêter le montage et calibrer** ; documenter les transformations et références nécessaires au dégagement, sans modèle de balle ni taille humaine supposée.
4. **Établir les seuils de qualité et le domaine retenu** par les essais positifs/négatifs ; couvrir les distances d'usage et caractériser les limites. Ces seuils ne sont pas encore des valeurs mesurées.
5. **Rapporter les résultats**, y compris acceptations/rejets, erreurs maximales et distributions, séries de pertes, débit et latences ; justifier les éventuelles restrictions et le verdict.

Les objectifs d'acceptation et le protocole sont spécifiés. La référence caméra, la géométrie finale, les dimensions, le dictionnaire/ID, les seuils de qualité et la précision atteinte sont des relevés, décisions techniques ou résultats de qualification restant à obtenir. Ils ne sont ni implicitement validés ni remplacés par des valeurs par défaut.

**Statut SH-03 : spécification du besoin et de la recette validée ; réalisation et qualification à faire.** Aucun Go mobile humain ; préparation optique sans propulsion uniquement tant que SH-02 n'est pas qualifié. Une réussite optique ne qualifie ni la couverture obstacle, ni la dynamique, ni la sécurité du porteur.

### SH-04 — Contrat de perception et cycle de mission

Cadre d'exigences et recette validés avec l'utilisateur le 2026-10-30, sans code. Les résultats techniques de SH-03 restent requis pour la réalisation et la qualification.

| Sujet | Décision validée | Réalisation / preuve attendue |
|---|---|---|
| Identité de mission | À « suis-moi », lire l'association persistante et verrouiller famille/dictionnaire + identifiant pour toute la mission, suspension comprise. Aucun changement de cible ; reconfiguration uniquement après fin/annulation, robot arrêté, puis nouvelle mission. Reprise : réacquisition de la même cible, sans anciennes observations | Tester changement de configuration en mission, suspension/reprise et nouvelle mission ; aucun basculement de cible. Verrouillage interne au runtime commun, sans mode utilisateur |
| Données d'observation | Contrat typé : source/caméra et génération du flux, numéro de trame, capture monotone et publication, identité famille/dictionnaire + ID, position image et dimensions, angle horizontal relatif à l'avant du robot, distance optique distincte du dégagement robot–porteur, référence/version de calibration, métriques de qualité et résultat de validation. Distances en cm, angles en degrés avec signe documenté, âge calculé en temps monotone ; mesure absente jamais remplacée par zéro | Raccorder métriques et repères aux résultats SH-03 ; contrôler types, unités, références et données manquantes. Un score global de confiance ne remplace ni la géométrie ni les contrôles de validité |
| Fraîcheur et acquisition | Âge depuis capture, jamais lecture/publication ; trame identifiée par génération du flux + numéro. Publication atomique d'un résultat cohérent, sans accumulation d'images anciennes. Relecture sans rajeunissement ni confirmation supplémentaire ; un résultat récent absent/invalide prime sur un ancien résultat valide en cache. Acquisition : au moins 3 trames distinctes, valides et consécutives du même flux/cible, chacune âgée de 200 ms maximum lors de la décision. Plus de 200 ms, temps futur/incohérent ou trame hors ordre : inexploitable, sans mouvement | Seuil de 200 ms à qualifier avec SH-02/SH-03. Tester horloge, cache, retards et ordre des trames. Perte/reprise : remise à zéro confirmations/filtres ; redémarrage du flux en mission : suspension et réacquisition explicite, anciennes trames invalidées |
| Résultats et erreurs | Distinguer valide, cible absente, ambiguë, rejetée pour qualité/géométrie, périmée et perception en défaut (caméra indisponible, calibration incompatible, données malformées…). Motif et références disponibles explicites, sans mesures inventées ni confusion absence/panne par un None isolé ou une exception silencieuse. Avant activation : départ interdit ; pendant suivi : résultat inexploitable impose arrêt/suspension et reprise explicite après correction | Tester chaque catégorie et propagation vers état/trace/feedback ; la perception ne commande pas les moteurs, elle fournit les faits au comportement et à la supervision |
| Cycle et contexte de mission | Identifiant unique de mission et version du contexte (cible, montage/calibration, taille). Résultat d'un ancien contexte ignoré avec motif. Calibration devenue incompatible : suspension, puis fin/reconfiguration avant nouvelle mission. Acquisition initiale au plus 10 s à l'arrêt ; échec : tentative terminée, nouvelle commande nécessaire. Reprise : réacquisition au plus 10 s sans dépasser l'échéance initiale ; échec : reste suspendu si non expiré, sans tentative automatique. Stop/urgence préemptent toute attente | Tester expiration initiale, reprise échouée et échéance pendant acquisition, anciens résultats et changement de calibration. Durée de suivi à partir de l'acquisition initiale et de l'annonce d'activation, préconditions recontrôlées avant mouvement ; aucune remise à zéro à la reprise |
| Fin et ressources communes | Fin/annulation/urgence : vider l'état de suivi, invalider résultats en vol, conserver l'association persistante de « moi ». Ne pas fermer la caméra partagée si le runtime en a encore besoin | Tester nettoyage et mission suivante, sans état/filtres réutilisés ni arrêt indu du runtime commun |
| Compatibilité et extension | Contrat intégré au runtime existant, interfaces adaptées si nécessaire, sans imposer aux missions balle les exigences/champs propres au marqueur humain. Type de cible distinct de son identité ; aucun protocole ou skill multi-robots anticipé. Acquisition caméra partagée, une seule mission motrice | Scénarios balle et stop inchangés ; aucune bascule de mode ni ressources matérielles concurrentes |
| Recette et traces | Tests déterministes par horloge/perception simulées ; traces corrélées par mission, contexte, capture/trame, résultat et motif, sans images par défaut | Chaque statut ; nombres invalides/mesures absentes ; trames répétées/périmées/hors ordre, temps futur, génération changée, ancien contexte, mauvaise cible/doublon ; trois confirmations ; limites exactes 200 ms/10 s ; stop pendant acquisition ; suspension/reprise/échéance ; nettoyage puis mission balle ; régressions existantes |

#### SH-04 — Règles de frontière et travaux restant ouverts

- Acquisition réussie uniquement sur des résultats exploitables appartenant au contexte courant. Chaque trame de confirmation doit encore respecter l'âge maximal lors de la décision ; trois lectures du même résultat ne sont jamais trois confirmations.
- Âge de 200 ms inclus dans la cible de fraîcheur, âge supérieur rejeté ; durée d'acquisition écoulée de 10 s sans acquisition finalisée : échec. La fin de session et les arrêts restent prioritaires sur une confirmation simultanée.
- La version de contexte représente la demande et les paramètres de validation, pas nécessairement un champ que le pilote caméra connaît. Le raccordement au flux partagé doit empêcher l'emploi de résultats d'une ancienne cible/validation sans obliger à redémarrer la caméra à chaque mission.
- Les noms de champs, types concrets, conventions d'angle, repères géométriques, métriques/seuils de qualité et mécanismes de synchronisation restent à détailler lors de la conception, avec les mesures SH-03 ; ils ne sont pas déclarés implémentés.
- Les 200 ms sont une cible à qualifier avec le budget d'arrêt SH-02 ; les 10 s bornent une attente immobile et ne permettent jamais de prolonger une mission expirée ni de retarder un stop.

**Statut SH-04 : cadre du contrat, cycle et recette spécifiés et validés ; conception détaillée, implémentation et vérification à faire.** Aucun résultat de test ou Go matériel n'est déduit de cette validation documentaire.

### SH-05 — Spécification progressive des garde-fous

Les six sujets d'exigences et de recette sont validés avec l'utilisateur le 2026-10-30, sans code, installation ni essai moteur. La validation documentaire ne clôture ni SH-05 ni ses dépendances techniques SH-02/SH-04 et n'autorise aucun suivi mobile humain.

#### Sujet 1 — Préconditions de départ et de chaque mouvement

**Exigence validée par l'utilisateur le 2026-10-30 :** deux niveaux de vérification, dans le runtime commun, sans mode utilisateur supplémentaire.

Avant activation, robot immobile :

- Configuration identifiée et qualifiée pour le domaine retenu : montage/calibration, paramètres, mouvements permis et protections.
- Terrain vérifié par l'opérateur selon SH-01 ; accès sûr à la coupure depuis sa position réelle démontré, y compris en essai solo. La proximité du robot et le casque ne prouvent pas cet accès.
- Inhibition motrice et surveillance indépendante qualifiées, disponibles, sans verrouillage actif ; réarmement manuel effectué lorsqu'il est requis. Le réarmement seul ne commande aucun mouvement.
- Runtime disponible, aucune autre mission motrice et demande valide.
- Caméra et contexte valides ; acquisition du marqueur configuré selon SH-04 : même identité, au moins trois trames distinctes cohérentes et fraîches, dégagement exploitable.
- Protection obstacle et entrée/sortie audio opérationnelles. Réutiliser les arrêts logiciels sur obstacle et commande vocale déjà disponibles et déclarés testés.

L'acquisition initiale reste immobile et bornée à 10 s selon SH-04. L'annonce d'activation ne dispense pas de recontrôler les préconditions avant le premier mouvement ; le début du chronomètre reste celui validé en SH-01/SH-04.

Avant et pendant chaque mouvement, rotation comprise :

- L'autorisation n'est jamais acquise pour toute la session : elle dépend de l'état courant de la mission, de son échéance, des observations, de l'audio, des protections et de l'inhibition.
- Le mouvement envisagé reste dans les limites qualifiées ; tout son volume balayé doit être protégé.
- Une condition obligatoire absente, invalide ou inconnue n'autorise aucun mouvement. Sa perte en session impose l'arrêt et la suspension ou la fin déjà prévues selon l'événement ; les priorités sont détaillées au sujet 2.
- Une personne simplement trop proche relève du maintien immobile, sans recul ; cela ne masque jamais un défaut simultané. Les règles acquises de redépart normal et de reprise explicite restent inchangées.

**Conséquences :** aucun départ « au mieux » sur une ancienne mesure valide, une simple connexion Bluetooth ou la seule présence du capteur. Les contrôles automatiques et la vérification humaine du terrain restent distincts : le robot ne prétend pas vérifier l'absence d'escaliers ou l'accès physique à l'interrupteur.

**Choix techniques restant ouverts :** mécanismes de contrôle, seuils et délais à concevoir ou qualifier ; la fraîcheur de 200 ms reste une cible à confronter au budget d'arrêt SH-02. Les dispositifs d'inhibition et de surveillance indépendante ne sont pas déclarés conçus ou installés.

**Preuves de qualification attendues :** invalider chaque précondition séparément, vérifier l'absence de commande motrice, puis éprouver les pertes en cours et l'arrêt physique selon les protocoles protégés. Documenter séparément les vérifications opérateur et les contrôles automatiques, leurs moyens et leurs limites.

**État actuel : aucun Go mobile humain.** L'accès à la coupure depuis la position de suivi, l'inhibition et la surveillance indépendante restent notamment non résolus.

#### Sujet 2 — Priorité et arbitrage des événements simultanés

**Exigence validée par l'utilisateur le 2026-10-30 :** l'arrêt moteur est immédiatement prioritaire et n'attend ni le classement des événements, ni une annonce, ni le LLM. L'arbitrage détermine ensuite l'état et les possibilités de reprise, selon l'ordre suivant :

| Priorité | Événements présents | Décision |
|---|---|---|
| 1 | Urgence physique, coupure motrice ou perte du contrôle logiciel | Mission terminée et verrouillage ; réarmement manuel puis nouvelle commande nécessaires. Un stop ou une échéance simultanés ne suppriment jamais cette obligation |
| 2 | Sinon, stop ou annulation | Mission terminée, reprise impossible ; défauts simultanés consignés et à corriger avant une nouvelle mission |
| 3 | Sinon, échéance atteinte | Mission terminée, même pendant suspension/réacquisition ; défaut simultané toujours signalé, jamais transformé en réussite par la fin de durée |
| 4 | Sinon, obstacle ou perception/audio invalides | Arrêt et suspension ; tous les problèmes bloquants corrigés avant reprise explicite et nouvelle acquisition |
| 5 | Aucune interruption ; porteur arrêté ou trop proche | Maintien immobile normal ; redépart automatique uniquement sous les conditions déjà validées |

- Une confirmation d'acquisition, une disparition d'obstacle ou une réapparition du marqueur ne gagne jamais contre un arrêt simultané.
- Toutes les causes sont conservées dans les traces ; l'annonce courte indique en priorité celle qui impose la conduite la plus contraignante.
- Un défaut détecté pendant une suspension reste pris en compte ; une coupure ou une perte de contrôle impose la fin verrouillée.
- Aucun acquittement ne peut effacer un autre problème encore actif.

**Choix techniques restant ouverts :** mécanisme d'arbitrage, mémorisation des causes et remontée au runtime.

**Preuves de qualification attendues :** tests déterministes des événements simultanés et de leur ordre d'arrivée ; preuves sur banc protégé pour les coupures et pertes de contrôle. Aucun essai lancé lors de cette validation.

#### Sujet 3 — Actions autorisées et limites de mouvement

**Exigences validées par l'utilisateur le 2026-10-30 :**

- Avance seulement, plafonnée à 0,15 m/s mesuré au sol, ou moins si la qualification l'exige. Ni la voix ni le LLM ne peuvent relever ce plafond ; aucun rattrapage plus rapide.
- Aucun recul commandé, y compris pour augmenter la distance avec le porteur.
- Corrections d'orientation uniquement pour suivre le marqueur actuellement exploitable, jamais pour rechercher une cible perdue. Pas de balayage, de contournement ou de manoeuvre exploratoire.
- Une rotation sur place n'est pas automatiquement autorisée : qualification propre, cible valide avec dégagement exploitable et protection de tout le volume balayé obligatoires. À défaut, le robot reste arrêté et explique la limite.
- Vitesse angulaire, angle/durée d'une correction, accélération et combinaisons avance-rotation bornés par les mesures ; aucun chiffre supplémentaire fixé aujourd'hui.
- Orientation nécessaire hors domaine qualifié : arrêt/suspension, sans tenter un autre mouvement. Reprise explicite après retour dans les conditions autorisées.
- Une rampe de confort ne retarde jamais une demande d'arrêt de sécurité. Le comportement électrique d'arrêt et la distance physique d'immobilisation restent à qualifier.

**Conséquence :** avec le seul capteur frontal, certains virages peuvent être interdits tant que leur couverture n'est pas démontrée. Restreindre les mouvements ou revoir la protection ; tourner lentement ne suffit pas à démontrer leur sûreté.

**Choix techniques restant ouverts :** technique de correction, autorisation effective des rotations sur place et valeurs numériques hors plafond déjà validé.

**Preuves de qualification attendues :** tests des commandes interdites et des frontières, puis mesures sur cible inerte des vitesses, volumes balayés et arrêts dans les conditions retenues.

#### Sujet 4 — Supervision logicielle et inhibition indépendante

**Exigences validées par l'utilisateur le 2026-10-30 :**

- Supervision logicielle : réutiliser les arrêts existants sur obstacle et commande vocale ; ajouter les contrôles du suivi humain (perception, fraîcheur, contexte, audio, limites de mouvement et échéance). Demander l'arrêt dès que requis, puis propager état et motif. Cette supervision ne constitue pas sa propre protection contre un blocage du Pi.
- Protection indépendante : inhiber la motorisation sans dépendre de l'exécution du programme de pilotage ; couvrir programme arrêté/bloqué et Pi bloqué/privé d'alimentation selon SH-02. La surveillance ne doit pas être entretenue par un simple signe de vie sans rapport avec le fonctionnement du pilotage surveillé ; moyen de démonstration à concevoir.
- Documenter le périmètre et les limites de cette protection ; ne pas lui attribuer implicitement la détection des obstacles ou de toutes les erreurs logicielles.
- Au démarrage, après coupure motrice ou déclenchement de cette protection : moteurs inhibés, aucune ancienne commande réappliquée.
- Retour de l'énergie ou du programme : aucune reprise. Après remise en état, réarmement manuel distinct, puis nouvelle commande et toutes les préconditions.
- Retour d'un périphérique après suspension ordinaire : aucune reprise automatique ; pas de réarmement matériel supplémentaire imposé sans événement qui l'exige, mais reprise explicite selon SH-01.
- Le logiciel ne contourne pas un verrouillage physique. Si l'état nécessaire à l'autorisation n'est pas établi, aucun mouvement n'est autorisé.

**Conséquence :** l'interrupteur embarqué prévu ne démontre à lui seul ni surveillance indépendante ni inhibition au rétablissement. Son accès en solo reste un point bloquant distinct.

**Choix techniques restant ouverts :** composants, schéma, détection de coupure, mécanisme de surveillance, retour d'état, réarmement et délais issus du budget d'arrêt. Aucun composant ni montage électrique choisi ici.

**Preuves de qualification attendues :** sur banc protégé, pertes du pilotage et du Pi, coupure/rétablissement, retour du programme, réarmement seul et commandes anciennes ; mesurer l'arrêt physique et démontrer l'absence de redémarrage spontané.

#### Sujet 5 — Propagation des interruptions au runtime

**Exigences validées par l'utilisateur le 2026-10-30 :**

- Une interruption remonte avec identité de mission, état suspendu ou terminé, causes, échéance initiale et action nécessaire pour repartir.
- Une suspension n'est ni un succès ni une fin normale. Le runtime conserve la mission suspendue, sans relancer automatiquement la skill et sans passer à une étape suivante.
- Une fin sur défaut ou urgence interrompt le plan : aucune autre mission, cible de remplacement ou action motrice de secours enchaînée automatiquement.
- « Reprends le suivi » ne vaut que pour la session suspendue non expirée : correction de toutes les causes bloquantes, réacquisition de la même cible et vérification des préconditions obligatoires.
- Suspension, réacquisition et reprise ne remettent jamais le temps à zéro ; l'échéance initiale termine la session, y compris au milieu d'une attente.
- Stop/annulation terminent la session ; après coupure ou perte de contrôle, le verrouillage manuel s'ajoute selon le sujet 4.
- Résultats et commandes en vol de l'ancien contexte invalidés : aucun mouvement issu de ceux-ci après suspension, fin ou changement de mission.
- Exception inattendue : arrêt demandé, défaut explicite et aucune relance automatique ; jamais de résultat vide ou de succès de substitution. Logiciel indisponible : inhibition assurée par la protection indépendante, sans supposer qu'un compte rendu logiciel a pu être produit.

**Conséquence :** le même assistant reste utilisable, mais le LLM/planner ne peut pas « réparer » un arrêt par une autre action inventée. Préserver la politique existante des nouvelles demandes pendant une mission et les comportements balle.

**Choix techniques restant ouverts :** représentation des résultats, propagation des annulations et invalidation des commandes en vol ; noms de classes/statuts non imposés ici.

**Preuves de qualification attendues :** tests d'intégration de bout en bout (défaut, arrêt, état du runtime, absence de relance ou d'étape suivante), échéance pendant reprise, résultats tardifs et régression balle/stop.

#### Sujet 6 — Observabilité, recette et preuves nécessaires avant Go

**Exigences validées par l'utilisateur le 2026-10-30 :**

- Traces horodatées et corrélées : mission/contexte, état, causes présentes, préconditions bloquantes, références et âge des observations, distance/qualité, commande motrice demandée, demande d'arrêt et autorisation/inhibition connue.
- Distinguer arrêt demandé, commande moteur nulle et immobilisation physique mesurée ; une trace logicielle ne prouve pas cette dernière.
- Annonces déterministes, courtes et non bloquantes selon SH-01, arrêt toujours prioritaire. Audio ou Pi indisponible : ne pas prétendre avoir annoncé l'événement.
- Aucune image ni vidéo par défaut. Format et conservation des traces à préciser avec SH-08 ; pas de nouvelle collecte implicite.

Ordre de recette approuvé :

1. Tests déterministes sans moteurs : chaque précondition invalidée séparément, limites temporelles et numériques, événements simultanés, commandes obsolètes, transitions, reprises et échéances.
2. Intégration dans le runtime commun : aucun défaut transformé en succès, aucune relance automatique, stop et missions balle préservés.
3. Banc protégé : coupures, arrêt/blocage du pilotage, perte de supervision et indisponibilité du Pi selon protocole adapté ; rétablissement et réarmement sans départ spontané.
4. Cibles inertes : couverture obstacle, volume balayé, vitesses et distances d'arrêt. Porteur humain uniquement après qualification des protections et décision Go explicite.

Conditions du verdict :

- Rapporter version/configuration, protocole, référence de mesure, résultats bruts, maxima, échecs et restrictions. Moyennes/p95 n'excusent aucun dépassement d'une limite obligatoire.
- Fixer seuils et délais à partir du budget d'arrêt SH-02 avant les essais humains ; aucun objectif provisoire transformé en garantie.
- Aucun Go si une protection obligatoire ou l'accès sûr à la coupure reste non qualifié.
- Protocole compatible avec l'opérateur seul, sans présumer un second opérateur. La mention historique « porteur accompagné » de SH-11 est remplacée par une organisation qualifiée compatible avec cette contrainte, sans assouplissement des protections ni présomption que l'interrupteur embarqué suffit.
- Un futur Go ne vaut que pour la configuration et le domaine documentés ; modification pertinente : revalidation des propriétés affectées.

**Choix techniques restant ouverts :** moyens de mesure et d'injection, nombre d'essais des cas non encore chiffrés, seuils issus des mesures et livrables techniques.

**Preuves de qualification attendues :** résultats des étapes ci-dessus, moyens de mesure indépendants pour les propriétés physiques et chronologies de panne selon la section 7, budget d'arrêt justifié, limites et décision Go/No-Go explicites. Aucun essai lancé ni Go donné par cette approbation.

#### SH-05 — Statut et travaux techniques restants

**Cadre d'exigences et de recette spécifié et validé ; conception détaillée, implémentation et qualification à faire.** Les six validations ne constituent ni une réalisation ni une clôture technique du ticket.

| Travail restant | Livrable / preuve attendu |
|---|---|
| Qualifier les prérequis SH-02/SH-03/SH-04 | Configuration reproductible, perception exploitable, protections et accès à la coupure en solo démontrés ; aucun prérequis déduit de sa seule spécification |
| Concevoir les contrôles et l'arbitrage | Vérifications de départ/mouvement, états, causes multiples, bornes, annulation et propagation au runtime ; seuils fondés sur les qualifications |
| Concevoir l'inhibition et la surveillance indépendante avec SH-02 | Dispositifs, schéma, détection, réarmement, défaillances couvertes, délais et limites documentés puis éprouvés. Avancement 2026-10-30 : conception fonctionnelle et contrat logiciel validés en section 4 (« SH-02 — Conception détaillée documentaire des protections et de l'organisation solo ») ; dispositifs, schéma, délais et épreuves restent à faire |
| Réaliser et vérifier l'intégration | Réutilisation des arrêts existants, commandes obsolètes neutralisées, annonces/traces et non-régression balle/stop dans le même runtime |
| Fournir les preuves de qualification | Tests déterministes, intégration, banc protégé puis cibles inertes ; maxima et distances physiques mesurés, échecs/restrictions consignés ; aucune proximité humaine avant Go explicite |

### SH-06 — Spécification progressive du comportement déterministe

Les six sujets d'exigences et de recette sont validés avec l'utilisateur le 2026-10-30, sans code, installation ni essai moteur. Les exigences SH-01 et les cadres SH-04/SH-05 sont repris sans réouverture ; leurs dépendances techniques et qualifications restent ouvertes. Aucun Go mobile humain.

#### Sujet 1 — États et transitions

**Exigence validée par l'utilisateur le 2026-10-30 :** séparer l'état du comportement, les causes et l'action nécessaire pour repartir. Les noms ci-dessous sont descriptifs ; ils n'imposent ni classes ni représentation technique.

| État | Règle et transitions validées |
|---|---|
| Disponible, sans mission de suivi | Une demande « suis-moi » recevable ouvre l'acquisition initiale, sans mode utilisateur supplémentaire. Les préconditions SH-05 restent obligatoires |
| Acquisition immobile | Distinguer acquisition initiale et réacquisition après reprise. Même identité verrouillée et confirmations SH-04. Acquisition initiale : au plus 10 s ; échec : tentative terminée, nouvelle commande nécessaire. Réacquisition : au plus 10 s, sans dépasser l'échéance initiale ; échec : retour en suspension si non expirée, sans nouvel essai automatique |
| Suivi actif | Après acquisition initiale et annonce, activation et début du chronomètre selon SH-01/SH-04 ; recontrôle avant mouvement. Après réacquisition, annonce du temps restant, sans remise à zéro. L'état actif ne suffit jamais à autoriser les moteurs : chaque mouvement dépend des contrôles SH-05 |
| Maintien normal | Session active, commande motrice nulle, aucun recul ni correction d'orientation en maintien. Redépart automatique vers le suivi seulement lorsque la situation le justifie et que toutes les conditions sont valides, sans interruption de sécurité. Frontières de distance à préciser au sujet 2, sans assimiler l'objectif de ±30 cm à une zone de commande |
| Suspension | Arrêt demandé, aucun mouvement ; identité, échéance initiale et toutes les causes conservées. La disparition des causes ne suffit pas. « Reprends le suivi » recevable, causes corrigées et session non expirée : réacquisition immobile de la même cible |
| Fin | Arrêt demandé, ancien contexte et commandes invalidés ; aucune reprise de cette session, nouvelle mission nécessaire. Urgence physique, coupure ou perte de contrôle : verrouillage et réarmement manuel distinct obligatoires avant une nouvelle commande |

- Perte, ambiguïté, péremption, obstacle, défaut audio, orientation hors domaine, etc. sont des causes distinctes de l'état. « Perdu » et « bloqué » peuvent coexister comme causes de suspension ; aucun défaut n'est effacé par le choix d'un état unique.
- Une fin conserve sa nature : échéance, stop/annulation, échec de démarrage, défaut imposant une nouvelle configuration ou événement exigeant un réarmement. Un défaut simultané reste visible ; « fin » ne signifie pas automatiquement « succès ».
- L'arrêt moteur est demandé immédiatement, sans attendre l'arbitrage. Priorités SH-05 inchangées : urgence/coupure/perte de contrôle, puis stop/annulation, puis échéance, puis suspension pour condition invalide, puis maintien normal.
- Une acquisition réussie ou une cause disparue ne l'emporte jamais sur un arrêt simultané. L'échéance termine aussi une suspension ou une réacquisition. Une calibration incompatible impose suspension puis fin/reconfiguration selon SH-04.
- Maintien, suspension et réacquisition ne remettent jamais l'échéance à zéro. Le maintien permet un redépart conditionnel ; la suspension exige une reprise explicite ; une fin exige une nouvelle mission.
- Distinguer arrêt demandé, commande nulle et immobilisation physique mesurée. Si le logiciel est indisponible, la protection indépendante doit arrêter sans supposer que le runtime a pu enregistrer la fin.

**Choix techniques restant ouverts :** représentation des états/causes, synchronisation et mécanismes de transition. Aucun seuil nouveau ni autorisation implicite de rotation.

**Preuves de qualification attendues :** tests par horloge et observations simulées couvrant transitions, causes multiples, acquisition initiale et reprise, limites des 10 s, échéance et événements simultanés ; qualification physique séparée. Aucun test exécuté par cette validation.

#### Sujet 2 — Approche et maintien de la distance

**Exigences validées par l'utilisateur le 2026-10-30 :** approche bornée puis maintien avec hystérésis, sans fixation de nouveaux seuils numériques.

| Notion | Règle de distinction |
|---|---|
| Consigne et précision visée | Dégagement avant du robot–porteur demandé ; objectif stabilisé de ±30 cm à démontrer. Ni bande de commande imposée ni garantie de sécurité |
| Zone de commande | Frontières de ralentissement, demande d'arrêt et autorisation de redépart, justifiées par précision réelle, retards, freinage et limites mécaniques |
| Distance minimale de sécurité | Issue du budget d'arrêt SH-02, avec incertitude et marge. Ni consigne ni valeur fixée par le seuil provisoire de recette de 0,8 m |

- Avance uniquement avec dégagement exploitable, cible et orientation valides et toutes les préconditions SH-05. Mesure absente ou incohérente : suspension, jamais d'avance par défaut.
- Réduire la vitesse à l'approche du maintien, puis demander l'arrêt assez tôt pour intégrer délais, freinage et incertitude ; ne pas attendre le franchissement d'une limite physique. Loi de vitesse et seuils à concevoir ; plafond SH-01 inchangé.
- En maintien, toutes les commandes motrices sont nulles. Si le porteur revient vers le robot, rester arrêté sans recul. Aucune garantie de distance minimale face à une personne continuant volontairement à s'approcher.
- Hystérésis : seuil de redépart plus éloigné que le seuil d'entrée en maintien pour éviter les alternances arrêt/départ dues au bruit. Largeur et symétrie autour de la consigne non fixées. Une observation invalide n'est jamais absorbée par l'hystérésis : arrêt/suspension prioritaires.
- Porteur s'éloignant trop vite : aucun rattrapage au-delà du plafond. Suivi dans les limites tant que les observations et le domaine de mouvement restent valides ; sortie du domaine exploitable : suspension explicite, sans poursuite aveugle.
- Consigne incompatible avec commande, freinage et sécurité dans la configuration qualifiée : refus de départ motivé. Conditions devenant invalides en mission : suspension. Aucune modification silencieuse de la consigne ou de la distance minimale pour poursuivre.

**Conséquences :** la bande réelle de commande peut différer de ±30 cm ; elle doit permettre de viser la précision demandée en respectant le budget d'arrêt. Si cette compatibilité n'est pas démontrable, restreindre le domaine ou revoir explicitement le contrat, sans masquer l'échec. Aucune rampe de confort ne retarde un arrêt prioritaire.

**Choix techniques restant ouverts :** loi de vitesse, ralentissement, seuils/hystérésis, traitement des mesures selon SH-04 et compatibilité des consignes avec la dynamique réelle. Aucun nouveau chiffre fixé.

**Preuves de qualification attendues :** tests simulés aux frontières et avec bruit de mesure, rapprochement/éloignement du porteur, dégagement invalide, absence de recul et respect des priorités ; mesures indépendantes sur cibles inertes du freinage, des distances et vitesses. La simulation seule ne qualifie pas la sécurité physique.

#### Sujet 3 — Orientation et coordination avec l'avance

**Exigences validées par l'utilisateur le 2026-10-30 :** corriger seulement pour suivre une cible actuellement exploitable, dans un domaine de mouvement explicitement qualifié.

- La direction repose sur l'angle horizontal de la cible par rapport à l'avant du robot, distinct de l'inclinaison ou du lacet du marqueur servant notamment au contrôle de qualité géométrique.
- Cible suffisamment alignée : avance possible selon les règles de distance. Décalage compatible avec une correction qualifiée : correction bornée, avec avance seulement si la combinaison est elle-même qualifiée et son volume balayé protégé. Ne pas avancer pour aider à tourner si les conditions d'avance ne sont pas remplies.
- L'importance de la correction limite l'avance selon une règle déterministe à concevoir. Aucune combinaison avance–rotation improvisée ; bornes de vitesse, accélération, angle et durée issues des mesures SH-02.
- Aucune rotation sur place autorisée par défaut. Son inclusion dans la configuration utilisable exige qualification propre, cible fraîche, dégagement exploitable et protection de tout le volume balayé. Correction nécessaire non réalisable avec les mouvements autorisés : arrêt/suspension et motif explicite, sans mouvement de remplacement.
- En maintien normal, aucune rotation, même pour recentrer le marqueur. Si le porteur s'éloigne, un redépart ne peut inclure qu'une correction autorisée avec toutes les conditions de distance et de protection ; orientation nécessaire hors domaine : suspension.
- Perte, ambiguïté ou péremption de cible, dégagement invalide ou autre interruption : arrêt prioritaire, aucune fin de rotation sur une ancienne commande, aucune correction d'après le dernier angle mémorisé. L'arrêt demandé ne signifie pas immobilisation physique instantanée.
- Aucun recul, balayage, contournement ou recherche par rotation. La seule réapparition de la cible après suspension n'autorise pas la reprise.

**Conséquence :** certains virages seront refusés si la protection est insuffisante, même lents et marqueur visible. L'opérateur doit rétablir les conditions autorisées puis demander la reprise ; aucune manoeuvre de réalignement inventée par le robot.

**Choix techniques restant ouverts :** domaine d'alignement, hystérésis angulaire contre les oscillations, coordination avec l'avance et bornes de correction ; qualification éventuelle des rotations sur place. Aucun seuil angulaire ni mouvement ajouté par cette validation.

**Preuves de qualification attendues :** tests simulés du sens des corrections, des frontières, des oscillations et combinaisons interdites, du maintien sans rotation et des interruptions pendant une correction ; puis vérification sur cibles inertes des vitesses, volumes balayés et arrêts. Le domaine de visibilité du marqueur SH-03 ne vaut pas autorisation de tourner du même angle.

#### Sujet 4 — Redépart normal et reprise explicite

**Exigences validées par l'utilisateur le 2026-10-30 :** deux chemins distincts, sans autorisation de reprise laissée en attente.

Depuis le maintien normal :

- Redépart automatique possible quand le porteur s'éloigne au-delà de la frontière qualifiée, avec même cible exploitable, données fraîches, dégagement/orientation autorisés, protections et audio valides, aucune cause de suspension et échéance non atteinte.
- Pas de commande de reprise ni de nouvelle acquisition initiale imposée tant que la continuité des observations reste valide. Perte de validité : suspension, jamais maintien normal.
- Aucun compte à rebours ni message répété de maintien ; contrôle de chaque mouvement obligatoire.

Depuis une suspension :

- « Reprends le suivi » recevable uniquement pour cette session suspendue non expirée. Cause bloquante connue encore active : refus motivé, sans mémoriser une permission de repartir plus tard.
- Après perte de cible, le même marqueur doit redevenir exploitable ; les confirmations fraîches de réacquisition servent à le vérifier. Ni retour du flux ni détection isolée ne provoquent seuls une reprise.
- Demande recevable : une tentative immobile de réacquisition, confirmations et filtres remis à zéro ; aucune confirmation antérieure réutilisée. Même identité et contexte compatibles, jamais de cible de remplacement.
- Tentative bornée à 10 s selon SH-04 et à l'échéance initiale. Échec : reste suspendu si non expiré ; nouvelle commande nécessaire pour réessayer. Répéter « reprends » pendant la tentative ne la duplique pas et ne repousse aucune limite temporelle.
- Réacquisition réussie : annonce de reprise, distance et temps réellement restant ; recontrôle de toutes les préconditions avant mouvement. Retour au suivi ou au maintien selon la distance ; aucun départ forcé par la demande de reprise.

Depuis une fin :

- Reprise refusée avec raison ; nouvelle commande « suis-moi » nécessaire, avec réarmement manuel préalable lorsque requis.
- Une reprise ne modifie ni distance, ni cible, ni durée. Changer ces paramètres exige la fin de la mission puis une nouvelle demande selon la politique du runtime.

**Conséquences :** une commande prématurée n'arme aucun départ différé. Anomalie, stop ou échéance pendant réacquisition/annonce conservent la priorité SH-05. Maintien, suspension, annonces et tentative de reprise consomment tous le temps de session déjà commencé.

**Choix techniques restant ouverts :** réception/déduplication des commandes, vérification des causes et raccordement des annonces ; aucune temporisation ni seuil supplémentaire fixé.

**Preuves de qualification attendues :** tests simulés du redépart normal, des reprises refusées et réussies, confirmations anciennes, demandes répétées, défauts simultanés et échéance pendant acquisition/annonce ; aucun mouvement dû à la seule disparition d'un défaut.

#### Sujet 5 — Commandes, interruptions et sortie du comportement

**Exigences validées par l'utilisateur le 2026-10-30 :** comportement déterministe subordonné aux garde-fous, sortie explicite et aucune commande survivante.

- Arrêt prioritaire dans toutes les phases : acquisition initiale, suivi, maintien, suspension, réacquisition et annonces. Réutiliser les arrêts obstacle/voix existants ; ne jamais attendre LLM ou annonce. Perte du programme/Pi : inhibition indépendante SH-05, sans supposer un traitement par le programme indisponible.
- Autorisation réévaluée avant chaque commande et surveillée pendant son exécution. Commande valable uniquement pour mission/contexte courants, observation et limites valides. Une interruption demande l'arrêt sans attendre la fin prévue d'une avance/correction engagée ; exécution interruptible à concevoir.
- Suspension ou fin : invalider commandes et résultats en vol du contexte de commande interrompu. Reprise : autorisation renouvelée après vérifications, jamais réapplication d'une ancienne consigne. Acquisition, calculs ou annonces tardifs ne peuvent réactiver les moteurs ni afficher un état devenu faux.
- Retour au runtime avec identité de mission, état, ensemble des causes, échéance initiale, action requise et état connu d'autorisation/inhibition. Suspension : mission conservée, aucune relance automatique de la skill ni étape suivante du plan. Fin : reprise de cette mission interdite ; défaut/urgence interrompent le plan, sans mission de secours, balle ou cible de remplacement.
- Exception inattendue : arrêt demandé, défaut explicite, aucune relance automatique ni faux succès. État suspendu ou terminé selon la nature de l'événement et SH-04/SH-05 ; aucune reprise inventée par une gestion générique d'exception. Défaut simultané à l'échéance toujours signalé.
- Nettoyage en suspension : conserver identité et échéance, invalider données de commande et confirmations requises pour la reprise. En fin : vider l'état transitoire et invalider le contexte. Préserver association persistante et ressources partagées encore utilisées par le runtime.
- Même assistant, une seule mission motrice ; aucune substitution par une nouvelle demande pendant suivi/suspension. Préserver la politique existante du runtime, les missions balle et le stop ; aucune bascule de mode ni exigence humaine imposée globalement aux autres capacités.

**Conséquences :** calcul engagé ou commande déjà en file ne justifient aucun mouvement après suspension/fin. Traces distinguant arrêt demandé, commande nulle et immobilisation mesurée ; sans retour matériel, aucune confirmation inventée d'arrêt physique ou d'inhibition.

**Choix techniques restant ouverts :** forme des retours, annulation/invalidation des commandes et résultats, coordination avec contrôleur et ressources communes ; réalisation matérielle de l'inhibition toujours ouverte.

**Preuves de qualification attendues :** tests d'intégration avec stop dans chaque phase, interruptions pendant commande/annonce, commandes/résultats tardifs, exception, échéance avec défaut, nettoyage et mission suivante ; non-régression balle/stop. Protection indépendante et arrêt physique : preuves distinctes.

#### Sujet 6 — Recette déterministe sans moteurs

**Exigences et protocole validés par l'utilisateur le 2026-10-30 :** recette reproductible par horloge, observations, commandes utilisateur et états de protection simulés. Approbation du protocole uniquement ; aucun test créé ni exécuté pendant cette étude.

| Famille | Couverture attendue |
|---|---|
| États et transitions | Tous les chemins autorisés et refusés des sujets 1 à 5 : départ, suivi, maintien, suspension, reprise, fins et verrouillage ; distinguer état, causes et action requise |
| Perception et identité | Confirmations sur trames distinctes ; absence, ambiguïté, qualité insuffisante, dégagement invalide, cache, répétitions, retard, trames hors ordre, temps incohérent, changement de flux et ancien contexte ; aucune adoption d'une autre cible |
| Frontières temporelles | Juste avant, à et après les limites SH-04 de fraîcheur et d'acquisition ; âge de 200 ms inclus dans la cible actuelle, au-delà rejeté ; 10 s écoulées sans acquisition finalisée : échec. Échéance de session prioritaire même pendant maintien, suspension, réacquisition ou annonce. Aucun redémarrage du chronomètre |
| Distance et orientation | De part et d'autre et exactement aux futures frontières qualifiées : ralentissement, arrêt, hystérésis, redépart, alignement, correction et domaine interdit. Bruit autour des frontières, porteur qui revient ou s'éloigne trop vite ; aucune confusion entre ±30 cm, zone de commande et minimum de sécurité |
| Mouvements interdits | Aucun recul, balayage, contournement, rattrapage au-delà du plafond ou rotation sur place non autorisée ; aucune commande motrice en acquisition, maintien ou suspension ; pas d'avance sans dégagement valide, ni combinaison avance–rotation non qualifiée |
| Événements concurrents | Combinaisons et ordres d'arrivée pertinents : confirmation contre stop, défaut contre échéance, obstacle et proximité, coupure pendant suspension, reprise avec une autre cause active ; ordre SH-05 et conservation de toutes les causes |
| Reprises et commandes tardives | Aucun redépart sur seule disparition d'un défaut ; reprise prématurée non mémorisée, confirmations anciennes effacées, demandes répétées sans tentative parallèle ni report des limites ; aucun effet moteur de commandes/résultats/annonces obsolètes |
| Runtime et ressources | Suspension ni succès ni étape suivante ; fin sur défaut sans relance ; exception visible ; nettoyage puis nouvelle mission sans état hérité ; caméra partagée, une seule mission motrice, non-régression balle/stop et absence de mode supplémentaire |

Méthode et verdict validés :

- Chaque scénario fixe entrées, chronologie, configuration et résultat attendu : états, toutes les causes, échéance, commandes autorisées/interdites, demande d'arrêt, annonces attendues ou invalidées, retour au runtime et nettoyage.
- Rejouer les mêmes entrées avec la même configuration produit les mêmes décisions et commandes. Faire varier l'ordre d'arrivée pour vérifier l'arbitrage, sans imposer un résultat identique à des situations réellement différentes.
- Éprouver les futurs seuils de commande avec leurs valeurs justifiées et leurs conventions de frontière documentées. Des paramètres de simulation peuvent préparer les tests, sans devenir réglages terrain ni preuves de qualification.
- Aucun scénario obligatoire en échec ne permet une recette conforme ; moyenne ou taux de réussite ne masquent aucune violation. Rapporter configuration/version, cas exécutés, résultats attendus/obtenus, chronologies et échecs, sans images par défaut.

**Limite de preuve :** ces tests démontrent des décisions et commandes logicielles, pas vitesse au sol, freinage, couverture obstacle, audio réel, inhibition indépendante ou accès sûr à la coupure. Qualifications protégées SH-02/SH-05 puis SH-10/SH-11 toujours nécessaires ; aucun Go humain n'en découle.

**Choix techniques restant ouverts :** organisation des scénarios, simulateurs/doubles de test, moyens de rapport et valeurs issues des qualifications ; réutiliser l'horloge injectable et les outils du dépôt, sans nouvelle dépendance décidée.

**Preuves de qualification attendues :** résultats reproductibles de la matrice ci-dessus et de l'intégration, puis preuves physiques distinctes suivant les protocoles protégés déjà validés. Aucun résultat de test déduit de l'approbation documentaire.

#### SH-06 — Statut et travaux techniques restants

**Cadre d'exigences et de recette spécifié et validé ; conception détaillée, implémentation et qualification à faire.** Les six validations ne clôturent ni le ticket technique ni ses dépendances SH-04/SH-05.

| Travail restant | Livrable / preuve attendu |
|---|---|
| Qualifier les données et protections requises | Résultats SH-02/SH-03/SH-04/SH-05 : contexte et perception exploitables, domaine de mouvement, budget d'arrêt, inhibition et surveillance indépendante, accès sûr à la coupure en solo ; aucune capacité présumée à partir de sa spécification |
| Concevoir la commande déterministe | États/causes et transitions, approche/maintien, hystérésis de distance et d'angle, coordination avance–orientation et limites ; valeurs numériques justifiées, consigne/précision/minimum de sécurité distincts |
| Réaliser les reprises et l'intégration | Même identité et échéance, tentatives bornées, aucune commande ancienne, arrêt prioritaire, propagation explicite au runtime, annonces et ressources communes cohérentes ; balle/stop préservés |
| Exécuter la recette logicielle | Matrice du sujet 6 avec horloge/observations simulées, frontières, défauts simultanés, résultats tardifs, absence de mouvements interdits et régression ; résultats attendus/obtenus et échecs consignés |
| Fournir les preuves physiques et le verdict | Selon SH-02/SH-05 puis SH-10/SH-11 : banc protégé, cibles inertes, vitesses/arrêts/volumes balayés, audio et protections mesurés ; porteur uniquement après qualification et Go explicite |

Aucun code, essai ou achat autorisé par cette clôture documentaire. Les protections indépendantes restent à concevoir et qualifier ; l'accès sûr à l'interrupteur embarqué depuis la position de suivi reste non résolu. Aucun Go mobile humain.

### SH-07 — Spécification progressive de la commande naturelle

Étude documentaire avec l'utilisateur le 2026-10-30 ; inspection du code en lecture seule, sans création de code, test, installation ni essai moteur. Les décisions SH-01 à SH-06 sont préservées. La spécification ne clôture pas la dépendance technique à SH-06 et ne donne aucun Go mobile humain.

#### Sujet 1 — Contrat des commandes et distinction des capacités

**Exigences validées par l'utilisateur le 2026-10-30 :**

| Demande | Contrat validé |
|---|---|
| « Suis-moi » | Nouvelle mission de suivi du marqueur configuré, uniquement avec runtime disponible et préconditions satisfaites. Jamais une reprise ni une mission balle |
| « Reprends le suivi » | Commande de contrôle locale, sans dépendance au LLM, concernant uniquement la session humaine suspendue non expirée. Réacquisition et contrôles SH-06 obligatoires ; aucun changement de paramètres |
| Stop, arrêt ou annulation reconnus | Terminent la session, jamais une simple suspension. Traitement prioritaire réutilisant les mécanismes existants sans attendre le LLM. Les formulations d'arrêt déjà reconnues, dont « pause », ne deviennent pas implicitement une suspension reprenable |
| « Suis la balle jaune/rouge » | Mission objet existante, sans application implicite des règles propres au suivi humain |
| Formulations ambiguës : « suis », « suis-le », « reprends » sans précision | Ne pas déduire une cible ou une reprise humaine du seul contexte. Pour le suivi humain, refuser avec indication d'une formulation explicite ; aucune permission de départ différée. Préserver les formulations objet déjà prises en charge |

- Pendant une mission humaine, maintien compris, une nouvelle demande « suis-moi » ne redémarre ni ne prolonge la session. En suspension, seul « reprends le suivi » engage la reprise ; « suis-moi » n'en est pas un alias.
- Les autres nouvelles missions restent non exécutées selon la politique existante, sans mise en attente pour un départ ultérieur.
- MVP : départ et reprise humains sont des demandes autonomes. Phrase combinant suivi humain et autre action motrice, par exemple « suis-moi puis cherche la balle » : refus sans exécution partielle.
- Un ordre d'arrêt explicite effectivement reconnu reste prioritaire ; sa reconnaissance ne se réduit pas à rechercher un mot dans une phrase négative ou citée.
- Aucune résolution de pronoms ajoutée pour le suivi humain, substitution par une balle ou séquence automatique inventée. Reprise hors suspension : refus motivé, aucune nouvelle mission. Aucune reconnaissance de personne ou de voix promise.

**Choix techniques restant ouverts :** routage, grammaire des formulations, alias et contrôle des phrases composées ; noms d'intentions internes non imposés.

**Preuves de qualification attendues :** tests des commandes dans chaque état, distinction humain/balle, ambiguïtés et négations, demandes répétées, phrases composées, stop prioritaire et non-régression objet ; aucun test exécuté ici.

**Constats de lecture, pas réalisations SH-07 :** le parser local classe actuellement les verbes de suivi dans `follow_object` ; le runtime traite l'arrêt localement et ignore les autres phrases pendant une mission. Les surfaces à adapter comprennent notamment [le parser](../../src/irobot/interfaces/intent_parser.py), [les gardes](../../src/irobot/interfaces/plan_guards.py) et [le runtime](../../src/irobot/interfaces/voice_runtime.py). Les mécanismes existants d'arrêt sont à réutiliser ; le routage humain et la reprise restent à réaliser.

#### Sujet 2 — Paramètres, valeurs par défaut et normalisation

**Exigences validées par l'utilisateur le 2026-10-30 :** seuls le dégagement demandé et la durée sont paramétrables dans une nouvelle demande de suivi humain.

- Distance omise : 1,5 m ; durée omise : 60 s, exclusivement dans une configuration qualifiée pour ces valeurs. Sinon refus motivé, jamais de remplacement silencieux.
- Distance demandable : 1,2 à 2 m dans la plage effectivement qualifiée. Durée : 10 à 300 s après qualification. Bornes incluses ; valeur hors plage refusée, jamais écrêtée ou arrondie pour la rendre acceptable.
- Unités explicites équivalentes acceptées : mètres/centimètres, secondes/minutes ; chiffres ou nombres français non ambigus. « À un mètre cinquante pendant une minute » équivaut à « à 150 cm pendant 60 s ». Normalisation conservant exactement le sens demandé.
- Valeur explicitement donnée sans unité, nombres contradictoires ou rôle ambigu : refus avec indication de la formulation attendue. Une valeur illisible n'est pas une omission autorisant un défaut. Valeurs machine non finies, booléens et structures inattendues invalides.
- « Suis-moi à 150 pendant 60 » : aucune unité devinée. « De plus près » : aucune distance arbitraire.
- Aucun réglage vocal de vitesse, seuil de sécurité, tolérance, rotation, marqueur ou protection dans cette commande MVP. Demande contenant un tel réglage refusée en entier, sans suppression discrète pour exécuter le reste. Plafond physique SH-01 inchangé ; vitesse autorisée choisie par le contrôleur, pas le LLM.
- Reprise avec les paramètres de la session ; nouvelle distance/durée dans une reprise : refus, même si acceptable pour une nouvelle mission. Aucun défaut de paramètre réinjecté dans une reprise.
- Normalisation de casse, espaces, accents et traits d'union équivalents sans changement de sens. Départ : « suis-moi », « suis moi », « suivez-moi ». Reprise : « reprends le suivi », « reprenez le suivi ».
- « Reprends » seul, pronoms de cible, variantes anglaises et formules de pause reprenable ne deviennent pas des alias humains par déduction ; commandes existantes hors suivi humain préservées.

**Conséquences :** conversion d'unités permise, correction du besoin interdite ; paramètres annoncés conformes à ceux validés réellement retenus. Ni ±30 cm ni distance minimale de sécurité paramétrables par la voix.

**Choix techniques restant ouverts :** représentation interne, analyse des nombres/unités, précision numérique et mécanisme de normalisation ; aucune dépendance nouvelle décidée.

**Preuves de qualification attendues :** équivalence formulations/unités, omission distincte d'invalidité, limites incluses et hors plage, qualification plus restrictive, contradictions, paramètres interdits et reprises paramétrées. Aucun test exécuté ici.

#### Sujet 3 — Contrat d'intention et chaîne de validation

**Exigences validées par l'utilisateur le 2026-10-30 :** intention humaine dédiée, validation sans réparation silencieuse.

Contrat de départ :

- Nom interne `follow_person`, distinct de `follow_object`, sans mode utilisateur supplémentaire.
- Format de plan existant : une seule étape humaine ; `intent: follow_person`, `target` absent ou nul ; `parameters` contient uniquement les valeurs explicitement demandées, `stand_off_cm` et/ou `duration_s`. Objet de paramètres vide permis en cas d'omission.
- Aucun identifiant de marqueur dans la sortie LLM. Cible réelle issue exclusivement de la configuration persistante, verrouillée à l'admission de mission.
- Défauts SH-01 appliqués par validation déterministe seulement aux paramètres réellement omis dans la phrase, puis vérifiés contre le domaine qualifié. Une valeur explicitement demandée mais oubliée par le LLM n'autorise pas un défaut.

Prompt, schéma et gardes :

- Enseigner distinction humain/balle, formulations approuvées et interdiction des enchaînements humains MVP ; ajouter l'intention au schéma et aux listes autorisées pertinentes, pas seulement au prompt.
- Valider structure, types et champs autorisés, puis correspondance avec la demande complète : cible humaine explicite, rôle des nombres/unités, absence d'action ou paramètre interdit. Verbe « suis » isolé et score de confiance insuffisants.
- Conversion d'unités justifiée permise ; valeurs inventées/oubliées/modifiées, champs inattendus, cible objet/ID fourni, étape supplémentaire ou structure invalide : refus de la demande humaine entière. Aucun champ ni étape supprimé pour rendre le reste exécutable. Métadonnées de diagnostic séparées du contrat exécutable.

Parser local et replis :

- Reconnaître les formulations humaines approuvées avant la branche générique de suivi d'objet ; mêmes règles que le chemin LLM.
- Erreur technique du chemin LLM : repli local permis uniquement si le parser reconnaît et valide indépendamment la demande humaine complète et non ambiguë. Erreur et recours local explicites dans les traces ; aucun repli vers une balle ou une primitive.
- Réponse LLM exploitable mais contradictoire, hors contrat ou non justifiée : refus, aucun second essai réparant le besoin par l'exécution d'un sous-ensemble. Un refus ne se transforme pas en départ silencieux par un autre chemin.
- Stop/annulation et reprise reconnus routés localement avant l'attente du LLM. Reprise : contrôle de session, pas nouvelle étape de plan soumise au choix du LLM.

**Conséquences :** tous les chemins convergent vers les mêmes validations sémantiques et préconditions ; parser et LLM sans accès direct aux moteurs. Politique stricte humaine sans modification implicite des nettoyages ou plans objet existants.

**Choix techniques restant ouverts :** types concrets, emplacement des contrôles, coordination schémas/prompts et représentation du contrôle de reprise ; réutiliser les normaliseurs utiles, sans reprendre leurs éventuels écrêtages pour le suivi humain.

**Preuves de qualification attendues :** tests LLM/local/repli : schéma, champs inconnus, nombres inventés/oubliés, conversions, demande interdite nettoyée à tort, mauvaise cible, plan partiel, panne LLM et refus sans mouvement ; non-régression objet. Aucun test exécuté.

#### Sujet 4 — Raccordement au runtime commun

**Exigences validées par l'utilisateur le 2026-10-30 :** intégrer `follow_person` dans la chaîne existante avec admission explicite et ressources partagées.

- Planner/registre : sélection explicite du comportement SH-06. Skill manquante, dépendance indisponible ou plan incomplet : refus motivé ; jamais plan vide traité comme succès, exécution des seules skills présentes ou remplacement par `follow_object`/primitives.
- Toutes les entrées concernées, voix, texte, chemin LLM, parser local et appels internes d'intention, passent par les validations et l'admission nécessaires. Appel direct au contrôleur sans contournement de configuration qualifiée, contexte ou supervision SH-05. Scénarios simulés explicitement séparés du matériel réel.
- Perception automatique par capacité : couleur pour balle, marqueur pour humain. Une acquisition caméra partagée, aucun pilote concurrent ; aucune ancienne détection balle injectée comme observation humaine, aucun modèle de distance balle utilisé. Identité, calibration et génération de flux selon SH-04.
- Une seule mission motrice, admission coordonnée face aux demandes simultanées. Acquisition, suivi, maintien, suspension et réacquisition conservent la réservation de mission ; fin d'un worker ne signifie pas disponibilité du robot.
- Suspension : runtime réceptif au stop et à la reprise locale de cette même session ; autres demandes sans remplacement ni mise en attente. Reprise sans démarrage générique réinitialisant mission, paramètres ou échéance.
- Fin : invalider résultats/commandes de l'ancien contexte et nettoyer les données transitoires avant libération de l'admission ; préserver les ressources partagées utiles. Demande reçue trop tôt non mémorisée pour partir plus tard.
- Assemblage matériel : capacité humaine indisponible/non qualifiée refusée avec motif, sans imposer ses préconditions aux missions balle. Aucun matériel manquant remplacé silencieusement par un simulateur ; présence d'un objet logiciel insuffisante pour autoriser le mouvement.
- Nouvelle commande ou effacement d'indicateur logiciel ne valent jamais réarmement manuel ; raccordement des mécanismes existants sans levée implicite d'un verrouillage SH-05.

**Conséquences :** même assistant pour balle et humain ; seule la capacité requise et son contexte changent. La suspension conserve une mission sans imposer qu'un thread particulier reste vivant. Aucune architecture de threads ni nouvelle interface utilisateur imposée.

**Choix techniques restant ouverts :** représentation de mission suspendue, coordination admission/annulations, sélection des fournisseurs de perception et raccordement registre/contrôleur ; protections indépendantes toujours à concevoir et qualifier.

**Preuves de qualification attendues :** tests d'intégration simulés des entrées concernées, skill/dépendance absente, demandes simultanées, suspension avec worker terminé, reprise sans reset, résultats tardifs et absence de concurrence matérielle ; balle → humain → balle sans redémarrage, stop et réarmement non contournés. Aucun test exécuté.

#### Sujet 5 — Budgets et cycle de mission

**Exigences validées par l'utilisateur le 2026-10-30 :** une échéance de suivi unique, distincte des budgets techniques de préparation et de supervision.

| Phase | Contrat temporel |
|---|---|
| Compréhension et validation | Aucun mouvement dû à la demande ; durée de suivi non commencée. Attentes techniques bornées, stop prioritaire. Échec : refus explicite sans mission motrice de substitution |
| Acquisition initiale | Après admission de la demande validée ; attente immobile au plus 10 s selon SH-04. Échec : tentative terminée, nouvelle commande nécessaire. Aucun budget de recherche objet ajouté |
| Annonce initiale | Aucun départ prématuré ; attente bornée et supervisée, budget à définir avec l'audio SH-08 sans chiffre inventé. Panne ou dépassement avant activation : départ refusé et tentative terminée avec motif, aucun suivi actif fictif |
| Activation | Après acquisition initiale et annonce selon SH-01/SH-04 : échéance fixée une fois en temps monotone à partir de la durée validée. Préconditions recontrôlées avant mouvement |
| Suivi, maintien, suspension et reprise | Même échéance sans remise à zéro. Réacquisition au plus 10 s et jamais au-delà du temps restant. Annonces de reprise comptées. Échéance : arrêt et fin même au milieu d'une attente ; aucune annonce tardive de reprise active |

- Raccorder les budgets mission/étape au cycle humain réel, attentes immobiles comprises. Configuration incapable d'honorer la durée demandée dans ce cycle : refus avant départ, jamais réduction silencieuse.
- Marges techniques éventuelles de préparation/nettoyage sans ajout de temps de mouvement à l'échéance ; nettoyage sans retard de demande d'arrêt.
- Délai technique anormalement dépassé : défaut explicite, ni durée normale écoulée ni succès. Suspension ou fin selon nature du défaut et SH-04/SH-05/SH-06 ; perte de contrôle : fin verrouillée et protection indépendante.
- Aucun réessai automatique d'exécution humaine par les mécanismes génériques après échec initial, suspension, reprise échouée ou défaut. Le repli de compréhension strictement validé au sujet 3 n'autorise aucun réessai moteur.
- Contrôles temporels actifs pendant exécution et attentes ; vérification seulement au retour d'un appel bloquant insuffisante. Supervision logicielle distincte de la surveillance indépendante du Pi.
- Heure civile sans effet sur la durée ; stop, coupure, défauts simultanés et échéance arbitrés selon SH-05, sans masquer les autres causes.

**Conséquences :** durée demandée hors préparation initiale, mais consommée par toutes les attentes après activation ; aucune garantie de mouvement continu. Aucun budget générique ne prolonge ni ne redémarre le suivi.

**Choix techniques restant ouverts :** intégration de l'horloge, attentes interruptibles, budgets préactivation/annonce/nettoyage et propagation des expirations ; aucun nouveau seuil fixé.

**Preuves de qualification attendues :** tests par horloge simulée : acquisition initiale, activation après annonce, limites exactes, échéance pendant maintien/suspension/reprise/annonce, délais techniques, saut d'heure civile et absence de réessai automatique ; qualification physique séparée. Aucun test exécuté.

#### Sujet 6 — Recette d'intégration sans moteurs

**Exigences et protocole validés par l'utilisateur le 2026-10-30 :** matrice de recette de bout en bout avec LLM simulé, horloge injectable et périphériques factices explicitement identifiés. Aucun appel moteur réel, acquisition caméra ou test lancé pendant cette étude.

| Famille | Vérifications attendues |
|---|---|
| Langage et capacités | Départs/reprises approuvés, variations de casse/accents/espaces/traits d'union ; humain distinct de balle ; ambiguïtés, pronoms, négations/citations et phrases composées ; stop prioritaire sans faux déclenchement sur simple mot cité |
| Paramètres | Défauts seulement sur omission réelle ; mètres/cm, minutes/secondes et nombres français ; bornes incluses et hors plage, qualification plus restrictive, unités manquantes, contradictions, valeurs machine invalides et réglages interdits |
| Contrat LLM/local | Forme exacte de l'étape `follow_person`, champs autorisés, cible absente/nulle, aucun ID inventé ; nombre oublié/modifié/ajouté, étape invalide ou supplémentaire : refus intégral, aucun plan partiel. Erreur technique avec repli local complet validé distincte d'un refus sémantique sans réparation |
| Chaque état de session | Départ, acquisition, suivi, maintien, suspension, réacquisition, fin et verrouillage ; reprise recevable/refusée, paramètres inchangés, aucune permission différée ; autres demandes non exécutées pendant réservation |
| Admission et ressources | Entrées voix/texte/intention concernées, demande simultanée, worker terminé avec mission suspendue, skill/dépendance absente, indisponibilité humaine sans régression balle ; bonne perception, une acquisition caméra et une mission motrice, aucun simulateur implicite en réel |
| Temps et interruptions | Échéance et frontières SH-04, activation après annonce, temps restant, attente/annonce interrompue, défaut avec échéance, heure civile modifiée ; aucun reset ni réessai générique ; commandes/résultats tardifs inopérants |
| Runtime et non-régression | Refus sans commande de mouvement, suspension jamais transformée en succès, aucune étape suivante ni substitution, exceptions visibles ; nettoyage, balle → humain → balle dans le même runtime sans bascule/redémarrage ; stop existant et verrouillage manuel préservés |

- Chaque scénario documente texte d'entrée, sortie LLM simulée ou chemin local, contexte/qualification, chronologie et résultat attendu : intention et paramètres exacts, provenance des défauts de paramètres/conversions, admission, état, causes, échéance, retour au runtime, annonces et commandes de mouvement interdites/autorisées. Une demande d'arrêt peut être émise même lorsqu'aucun mouvement n'est permis.
- Mêmes entrées et configuration : mêmes décisions. Tous les cas obligatoires conformes ; aucun taux moyen masquant une violation. Rapporter version/configuration, attendus/obtenus, échecs et limites ; outils du dépôt réutilisés, aucune dépendance nouvelle décidée.
- La transcription simulée ne qualifie pas la reconnaissance vocale réelle.

**Limite de preuve :** recette démontrant routage, validation et logique d'intégration, pas vitesses, distances d'arrêt, couverture obstacle, audio réel, surveillance indépendante ou accessibilité de la coupure. Qualifications SH-02/SH-05/SH-10/SH-11 ouvertes ; aucun Go humain déduit d'une réussite logicielle.

**Choix techniques restant ouverts :** organisation des tests/doubles/rapports, raccordement aux suites existantes et valeurs techniques à justifier.

**Preuves de qualification attendues :** résultats de cette matrice et non-régression, puis preuves physiques distinctes suivant les protocoles protégés ; implémentation et exécution des tests à faire. Aucun résultat déduit de l'approbation documentaire.

#### SH-07 — Statut et travaux techniques restants

**Cadre d'exigences et de recette spécifié et validé ; conception détaillée, implémentation et qualification à faire.** Les six validations ne clôturent ni le ticket technique ni sa dépendance à SH-06.

| Travail restant | Livrable / preuve attendu |
|---|---|
| Concevoir le contrat exécutable et ses validations | Types/schémas/prompts/lexique cohérents, paramètres et omissions distingués, conversions sans écrêtage, refus intégraux et repli technique strictement validé |
| Raccorder tous les chemins concernés | Parser local, gardes, validator, runtime et contrôleur : départ `follow_person`, reprise/stop locaux, aucun détournement vers balle/primitives ; appels internes sans contournement |
| Réaliser l'intégration commune | Planner/registre, assemblage et perception partagée, admission unique, mission suspendue conservée, nettoyage et invalidation des résultats tardifs ; aucune dépendance humaine imposée globalement aux missions balle |
| Raccorder budgets et interruptions | Échéance monotone unique, attentes bornées, aucune remise à zéro/prolongation ou relance automatique ; annonces et délais techniques cohérents avec SH-08, verrouillage manuel non contourné |
| Exécuter la recette et qualifier l'ensemble | Résultats simulés du sujet 6 et régression balle/stop ; prérequis techniques SH-02 à SH-06 et qualifications physiques toujours requis avant Go selon les protocoles validés |

Aucun code créé, test exécuté, dépendance installée ou essai moteur réalisé pendant cette spécification. Aucun Go mobile humain ; dispositifs indépendants et accès sûr à la coupure en solo toujours à concevoir/résoudre et qualifier.

### SH-08 — Spécification progressive de l'observabilité

Étude documentaire avec l'utilisateur le 2026-10-30, sans code, essai ni installation. Les décisions SH-01 à SH-07 sont préservées intégralement. La validation documentaire ne clôture aucune dépendance technique ; conception, réalisation et qualification restent ouvertes. Aucun Go mobile humain.

#### Sujet 1 — Catalogue des annonces

**Exigences et catalogue validés par l'utilisateur le 2026-10-30 :** catalogue fermé de phrases et de gabarits déterministes, associés aux transitions ou aux commandes refusées. Les champs entre accolades proviennent des données validées du runtime, jamais d'une génération libre par le LLM. Maintien normal, suspension et fin restent distincts selon SH-06 ; priorités SH-05 et contrat de commandes SH-07 inchangés.

| Transition ou événement | Annonce validée | Sens / action attendue |
|---|---|---|
| Entrée en acquisition initiale | « Je cherche votre marqueur. » | Attendre ; aucune activation à ce stade |
| Acquisition réussie, avant activation | « Je vais suivre votre marqueur, à {distance}, pendant {durée}. » | Paramètres réellement retenus ; activation après annonce et recontrôle. La formulation prospective précise l'exemple « Suivi actif » de SH-01 sans changer le cycle SH-07 |
| Entrée en maintien normal, hors proximité | Silence | Session active ; redépart automatique conditionnel possible |
| Entrée en proximité, sans interruption de sécurité | « Trop près, je reste arrêté. » | Aucun recul ; une seule annonce à l'entrée, aucun compte à rebours |
| Redépart normal depuis le maintien | Silence | Ni nouvelle mission ni reprise après suspension |
| Entrée en suspension | « {Motif}, suivi suspendu. {Correction attendue}. Dites : reprends le suivi. » | Correction puis reprise explicite ; disparition du problème insuffisante |
| Reprise recevable : entrée en réacquisition | « Je recherche votre marqueur pour reprendre. » | Tentative immobile de la même session, pas reprise déjà réussie |
| Réacquisition réussie, avant retour au suivi ou maintien | « Je reprends le suivi à {distance}. Il reste {temps restant}. » | Même cible, paramètres et échéance ; aucun mouvement forcé si maintien requis. Temps réellement restant, jamais nouvelle durée complète |
| Reprise refusée ou réacquisition échouée | « Reprise impossible : {raison}. {Action attendue}. » | Aucune permission mémorisée ni nouvel essai automatique ; reste suspendu si non terminé |
| Demande invalide ou départ impossible | « Suivi non démarré : {raison}. {Action attendue}. » | Refus intégral, aucun départ différé |
| Nouvelle demande pendant la réservation humaine | « Une mission de suivi est déjà en cours. Nouvelle demande non exécutée. » | Aucun remplacement, prolongement ou stockage pour plus tard ; réservation conservée en suspension |
| Échéance atteinte | « Durée écoulée, suivi terminé. » | Nouvelle commande nécessaire ; défaut simultané toujours à signaler |
| Stop ou annulation | « Suivi arrêté. » | Session terminée, non reprenable ; verrouillage simultané toujours à signaler |
| Fin exigeant reconfiguration | « Suivi terminé : {raison}. {Reconfiguration attendue} avant une nouvelle mission. » | Une reprise ne résout pas une incompatibilité de configuration |
| Urgence, coupure ou perte de contrôle connue | « {Événement détecté}, suivi terminé. Réarmement manuel puis nouvelle commande nécessaires. » | Seulement si logiciel et audio disponibles ; aucune confirmation inventée d'inhibition ou d'immobilisation |

Motifs et corrections de suspension validés :

| Motif constaté | Correction attendue annoncée |
|---|---|
| Marqueur perdu | « Rendez votre marqueur visible. » |
| Identifiant attendu en plusieurs exemplaires | « Ne laissez visible qu'un exemplaire du marqueur configuré. » |
| Observation rejetée pour qualité ou géométrie | « Présentez votre marqueur dans les conditions prévues. » |
| Image périmée ou flux indisponible | « Rétablissez la caméra. » |
| Dégagement inexploitable | « Rétablissez les conditions de mesure. » |
| Obstacle détecté | « Dégagez l'obstacle. » |
| Correction d'orientation hors domaine autorisé | « Replacez votre marqueur dans le domaine autorisé. » |
| Entrée ou sortie audio défaillante | « Rétablissez l'audio. » ; seulement sur une sortie encore utilisable |
| Autre défaut identifié | Correction propre au défaut ; diagnostic insuffisant : « Vérifiez le défaut signalé. » |

- Refus couvrant paramètres invalides, commandes ambiguës ou composées, capacité indisponible, absence de configuration du marqueur, reprise hors suspension et réarmement requis. Raison spécifique ; aucun refus générique masquant une cause connue ni diagnostic inventé.
- L'annonce indique d'abord la conduite la plus contraignante selon SH-05. Stop ou échéance ne masquent jamais réarmement requis ou défaut simultané ; toutes les causes sont conservées dans les traces. Arbitrage et invalidation détaillés au sujet 3.
- La correction annoncée n'invite jamais à s'approcher des roues ou à entrer dans la trajectoire ; elle ne démontre pas l'accès sûr à la coupure en solo.
- Les formulations SH-01 « Suivi arrêté » et « je reste arrêté » expriment le comportement commandé, pas une preuve d'immobilisation physique mesurée.
- L'arrêt moteur est demandé sans attendre une annonce. Aucune annonce impossible n'est déclarée effectuée ; logiciel ou audio indisponible : aucune confirmation inventée.

**Choix techniques restant ouverts :** production et canal audio, contrôle de disponibilité, interruption et péremption des messages, budgets et représentation des gabarits ; sujets suivants à valider.

**Preuves de qualification attendues :** correspondance exacte événements/messages en simulation, puis qualification réelle séparée de l'intelligibilité, de la simultanéité micro/sortie et du stop pendant les annonces. Aucun résultat de test déduit de cette validation.

#### Sujet 2 — Production des messages et disponibilité audio

**Orientation et exigences validées par l'utilisateur le 2026-10-30 :**

- Synthèse vocale locale alimentée exclusivement par le catalogue validé. Le runtime construit les textes depuis les gabarits et les données effectives : distance retenue, durée initiale ou temps restant ; la synthèse les prononce sans reformulation. Aucun appel au LLM ni à un service distant pour produire l'annonce.
- Jabra retenu comme canal candidat à qualifier, pas comme solution déjà qualifiée. La synthèse permet les valeurs variables sans préenregistrer toutes les distances/durées ; moteur, voix française, prononciation des nombres, charge et délais restent à choisir et qualifier. Aucune installation autorisée par cette orientation.

| Niveau de disponibilité | Contrat validé et limites |
|---|---|
| Configuration et qualification | Entrée/sortie identifiées, profil compatible avec leur usage simultané, voix et catalogue disponibles. Jabra candidat tant que la simultanéité n'est pas démontrée |
| Contrôle avant chaque départ et reprise | Vérifier les chemins d'entrée/sortie, l'ouverture des flux et les défauts détectables de capture, synthèse et lecture. Connexion Bluetooth ou objet logiciel insuffisants. Aucun nouveau test sonore parlé systématique retenu |
| Surveillance en session | Surveiller déconnexions, erreurs, fins inattendues de flux et blocages détectables. Panne détectée : arrêt/suspension ; retour du périphérique sans reprise automatique |

- Flux ouvert ou lecture achevée ne prouvent pas que l'utilisateur a entendu ; silence du micro ne prouve pas une panne. Documenter les défauts détectables et les limites des contrôles, sans promettre la détection de toute panne acoustique silencieuse.
- Avant activation : entrée/sortie non opérationnelle, synthèse ou lecture initiale en échec imposent refus du départ et fin de tentative avec motif explicite.
- Après activation : panne audio détectée impose arrêt demandé immédiatement et suspension, sauf événement imposant une fin selon SH-05.
- Sortie indisponible : aucune annonce vocale garantie ; diagnostic terminal/traces seulement si ces moyens fonctionnent. Aucun repli silencieux vers un autre périphérique, du texte seul pour autoriser le départ ou une annonce libre du LLM.
- Écoute du stop maintenue pendant les annonces, sans auto-commande vocale ; mécanisme, interruptions et preuve à détailler au sujet 3. L'audio ne remplace ni coupure physique ni surveillance indépendante.

**Constats de lecture, pas qualification :** [entrée audio](../../src/irobot/hardware/audio/voice_assistant.py), [runtime vocal](../../src/irobot/interfaces/voice_runtime.py) et [script Jabra](../../scripts/install/connect_jabra_bt.sh) fournissent des points de raccordement existants ; les extraits inspectés ne prouvent pas la chaîne simultanée requise.

**Choix techniques restant ouverts :** moteur/voix, routage, contrôles et surveillance des flux, charge et délais ; aucun dispositif déclaré réalisé.

**Preuves de qualification attendues :** audio réel simultané, intelligibilité, pertes de chaque sens, erreurs de synthèse/lecture et reconnexion sans mouvement spontané. Aucun essai effectué.

#### Sujet 3 — Priorité, interruption et validité des annonces

**Règles validées par l'utilisateur le 2026-10-30 :** l'annonce suit l'état, elle ne le commande jamais.

- Demande d'arrêt moteur immédiate et indépendante de la préparation, lecture ou interruption audio. Aucune opération audio ne bloque supervision, stop local ou échéance.
- Acquisition et annonce initiales sans mouvement. Après activation, toutes les annonces consomment le temps restant sans prolongation.
- Priorités SH-05 inchangées : urgence/coupure/perte de contrôle, stop/annulation, échéance, suspension, maintien normal. Un événement plus contraignant interrompt une annonce devenue incompatible.
- À priorité égale, une nouvelle situation invalide ou remplace un message devenu inexact ; causes compatibles regroupables dans une annonce courte. Causes secondaires tracées et annoncées lorsqu'elles changent l'action nécessaire, notamment défaut simultané à la fin de durée.
- Aucune répétition automatique ni rattrapage vocal de tout l'historique : annoncer la situation actuelle et la conduite nécessaire, pas une file de messages anciens.
- Chaque annonce liée à mission, contexte et transition ou commande concernée. Validité vérifiée avant lecture et surveillée pendant lecture. Résultat de synthèse tardif ou d'ancien contexte inutilisable ; aucune annonce obsolète ne peut activer ou reprendre la mission.
- Stop pendant annonce initiale : interruption, aucune activation. Échéance pendant annonce de reprise : fin, jamais reprise tardive. Réapparition du marqueur après suspension : aucune annonce de reprise spontanée.
- Temps restant calculé sur l'échéance monotone initiale, actualisé au plus près de sa prononciation et recontrôlé selon la précision de diction retenue. Valeur devenue périmée non prononcée ; référence temporelle tracée, jamais nouvelle durée complète.

| Budget à définir et qualifier | Exigence validée |
|---|---|
| Annonce initiale | Budget total incluant préparation/synthèse et lecture ; attente bornée et supervisée avant activation |
| Autres annonces | Limites de préparation et de lecture explicites |
| Interruption et péremption | Délai d'interruption audio et règles de péremption, dont temps restant, explicités |

- Aucun chiffre fixé ici. Budgets justifiés sur la chaîne retenue et éprouvés à leurs frontières ; configuration sans budgets obligatoires renseignés et qualifiés non prête à l'usage réel.
- Dépassement avant activation : départ refusé et tentative terminée. En session, panne ou blocage audio détecté : arrêt/suspension selon les acquis ; échéance et événements plus prioritaires gardent leur effet. Invalidation normale d'un message périmé distincte d'une panne audio.
- Ne jamais couper le micro ni ignorer globalement les transcriptions pendant une annonce : le stop utilisateur reste pris en compte localement.
- Séparation parole du robot/commandes utilisateur à concevoir et qualifier ; ni simple comparaison de textes ni présence du casque ne prouvent l'absence d'auto-commande. Chaîne non qualifiée si stop et absence d'auto-commande ne sont pas préservés simultanément.

**Choix techniques restant ouverts :** lecteur interruptible, invalidation des résultats, buffers, séparation audio, précision de diction et valeurs des budgets ; aucune valeur ni solution déclarée réalisée.

**Preuves de qualification attendues :** scénarios simulés d'interruption, priorités et messages tardifs ; mesures audio réelles, stop pendant lecture et absence d'auto-commande. Aucun arrêt physique ni Go humain déduit de ces preuves logicielles ou audio.

#### Sujet 4 — Traces corrélées et niveaux de preuve

**Contrat validé par l'utilisateur le 2026-10-30 :** réutiliser JSONL avec schéma versionné et événements corrélés permettant de reconstruire les décisions. L'écriture JSONL et l'heure UTC existantes dans [le runtime](../../src/irobot/interfaces/voice_runtime.py) ne démontrent pas à elles seules ce contrat humain.

| Groupe | Informations à relier |
|---|---|
| Références communes | Version du schéma, exécution du runtime, configuration/version logicielle, séquence, heure UTC et temps monotone |
| Demande et mission | Identifiant de demande même avant admission/refus ; mission après admission, contexte et tentative de reprise |
| Commande comprise | Intention, paramètres demandés/retenus, unités et provenance : explicite, défaut sur omission ou conversion ; chemin local/LLM/repli et motifs de refus. Phrase brute non nécessaire au contrat |
| Perception utilisée | Source/génération, capture/trame, identité du marqueur, calibration, âge, qualité, dégagement et résultat de validation. Observations effectivement utilisées, acceptées ou rejetées, sans journalisation implicite de toutes les images |
| Décision | État précédent/nouveau, toutes les causes, préconditions bloquantes, action nécessaire, échéance initiale et temps restant à son instant de référence |
| Commande motrice | Décision associée, commande demandée et limites, demande d'arrêt, commande nulle, autorisation/inhibition telles que connues avec leur source |
| Audio | Identifiant du gabarit et valeurs, événement associé ; préparation, lecture commencée/achevée selon le lecteur, interruption, invalidation ou échec ; références temporelles et motif |
| Résultat et nettoyage | Suspension ou fin et sa nature, absence de relance, invalidation de contexte et libération de réservation lorsqu'elle a effectivement lieu |

- Événements de demande, transition, interruption, refus, commande et cycle audio conservés sans échantillonnage faisant disparaître une décision. Cadence des mesures répétitives de charge/diagnostic à définir sans perdre les références nécessaires à l'explication d'une décision.
- Mesure absente explicitement indisponible avec raison, jamais zéro de remplacement. Latence seulement entre événements compatibles dans un référentiel temporel maîtrisé.
- Pour une panne injectée, son instant de référence ne peut être uniquement celui de sa détection logicielle si l'on prétend mesurer tout le délai de réaction.

| Fait / niveau de preuve | Affirmation autorisée |
|---|---|
| Demande d'arrêt émise | Le logiciel a demandé l'arrêt |
| Commande nulle transmise ou appliquée | Seulement ce que l'interface ou le retour disponible établit ; distinguer ces étapes |
| Inhibition confirmée | Retour adapté, identifié et suffisamment récent obligatoire ; sinon état inconnu |
| Immobilisation physique mesurée | Mesure indépendante identifiée, méthode, horodatage et incertitude ; jamais déduite d'une commande nulle |
| Lecture achevée selon le lecteur | Fin rapportée par le lecteur, pas preuve d'audition par l'utilisateur |
| Événement écrit | Seulement le niveau de confirmation disponible ; aucune garantie inventée de persistance après coupure |

Disponibilité du journal obligatoire :

- Indisponibilité avant activation : départ refusé.
- Perte détectée d'écriture ou impossibilité de conserver les événements obligatoires en session : arrêt/suspension, sans attendre une écriture bloquée.
- Rétablissement sans reprise automatique. Diagnostic par un autre canal seulement s'il fonctionne, aucune trace manquante déclarée produite.
- Stockage plein, journal bloqué ou trous détectés empêchent de déclarer la session conforme. Programme entier indisponible : protection indépendante toujours requise, aucune trace supposée.

**Choix techniques restant ouverts :** schéma exact, synchronisation, écriture non bloquante, garanties de persistance, détection des pertes et moyens de mesure. Politique de collecte, accès et conservation à valider au sujet 5.

**Preuves de qualification attendues :** reconstruction des chronologies, absence de faux acquittements, détection de données manquantes et injections de panne du journal ; preuves physiques séparées. Aucun test exécuté.

#### Sujet 5 — Données, accès, conservation et suppression

**Politique validée par l'utilisateur le 2026-10-30 :** collecte minimale et locale, conservation liée à la campagne, sans durée maximale calendaire fixée.

Collecte :

- Données structurées du sujet 4 uniquement, nécessaires à l'explication et à la qualification : décisions, paramètres, observations utilisées, commandes, annonces et chronologies.
- Aucune image, vidéo, capture audio du micro, phrase brute, transcription complète, prompt ou réponse brute du LLM conservés par défaut. Signal audio synthétisé non conservé au-delà du traitement nécessaire à sa lecture.
- Capture micro et images nécessaires au fonctionnement traitées en mémoire, sans enregistrement implicite. Temporaires de synthèse nettoyés, interruption comprise ; restes après incident détectables et supprimables.
- L'écriture actuelle du texte d'entrée et des sorties LLM dans [le runtime](../../src/irobot/interfaces/voice_runtime.py) n'est pas reprise telle quelle pour le suivi humain. Couvrir logs annexes, messages d'erreur et diagnostics ; pas de modification implicite du contrat des missions balle.
- Toute collecte exceptionnelle d'image, audio ou texte brut exige accord distinct sur contenu, finalité, accès, conservation et suppression ; non autorisée par cette validation.

Emplacement et accès :

- Stockage local identifié et configurable sur Pi ; données humaines isolables pour consultation/suppression.
- Accès réservé au compte d'exécution et à l'utilisateur administrateur autorisé, selon les permissions effectivement mises en place.
- Aucun envoi distant, partage réseau, synchronisation ou export automatique. Export manuel sur décision explicite avec inventaire des données et destination.
- Identifiant du marqueur : référence technique, jamais identité personnelle reconnue. Aucun nom de porteur ni adresse Bluetooth ajoutés sans nécessité.

| Données | Règle de conservation validée |
|---|---|
| Traces détaillées | Pendant une campagne identifiée, jusqu'à clôture explicite par l'utilisateur ; produire et vérifier le rapport minimal, puis supprimer les traces détaillées |
| Rapport de qualification | Localement jusqu'à suppression explicite : configuration, protocole, résultats, maxima, échecs, restrictions et références de preuve utiles |
| Campagne interrompue ou oubliée | Signalée non clôturée ; fin de mission ou redémarrage ne valent pas clôture. Aucune durée maximale calendaire approuvée |

- Rapport suffisamment probant pour justifier le verdict après suppression des traces : aucune simple affirmation de réussite invérifiable. Rapport non correctement produit/vérifié : clôture incomplète, aucune suppression déclarée effectuée.
- Suppression sur demande avec périmètre affiché : campagne, traces, rapports, temporaires et exports connus. Journal obligatoire non supprimé pendant une mission réservée ; terminer la mission avant l'opération.
- Suppression des traces distincte de l'association persistante du marqueur et de la calibration, qui ne sont pas effacées par cette commande.
- Échec ou suppression partielle explicitement signalés. Suppression logique des fichiers, sans promesse d'effacement physique irréversible sur carte SD ni disparition de copies externes inconnues.
- Données historiques existantes ni purgées ni migrées dans cette étude ; aucun fichier de données supprimé maintenant.

**Choix techniques restant ouverts :** chemins, permissions, gestion des campagnes, rapport minimal, nettoyage et commande de suppression.

**Preuves de qualification attendues :** absence des contenus exclus dans toutes les sorties concernées, contrôle d'accès, cycle clôture/suppression et erreurs de nettoyage. Aucun essai ni effacement exécuté.

#### Sujet 6 — Recette d'observabilité

**Protocole validé par l'utilisateur le 2026-10-30 :** deux niveaux de recette avec preuves explicitement différentes. Approbation documentaire uniquement, aucun test créé ou exécuté.

**A. Recette déterministe sans moteurs**

Réutiliser les outils du dépôt, l'horloge injectable et des doubles explicites pour perception, synthèse, lecteur, entrée vocale, protections et journal. Aucun périphérique réel activé implicitement.

| Famille | Vérifications attendues |
|---|---|
| Catalogue et états | Chaque annonce, silences en maintien/redépart normal, proximité une fois par entrée, suspension distincte de fin, motifs/actions corrects |
| Paramètres et reprise | Valeurs réellement retenues, aucune correction silencieuse ; temps restant référencé à l'échéance initiale, jamais nouvelle durée complète ni valeur périmée |
| Priorités et interruptions | Stop dans chaque phase ; événements simultanés selon SH-05 ; défaut avec échéance ; aucun arrêt retardé par audio/journal |
| Messages tardifs | Synthèse ancienne, annonce devenue fausse en attente, interruption et buffers résiduels ; aucun message obsolète ni effet moteur tardif |
| Budgets | Juste avant, à et après chaque future limite documentée ; attente initiale supervisée, échéance pendant reprise/annonce, absence de prolongation ou réessai humain |
| Audio simulé | Absence au départ, panne de chaque sens, synthèse/lecteur en échec ou bloqué, reconnexion ; refus/suspension corrects sans reprise spontanée |
| Traces et preuves | Corrélations complètes, refus avant admission, causes multiples, séquences manquantes, données indisponibles, temps incohérents ; aucun faux acquittement d'inhibition, immobilisation, audition ou persistance |
| Journal défaillant | Stockage plein, permission refusée, erreur/blocage d'écriture, perte d'événements détectée ; arrêt indépendant de l'écriture et session non déclarée conforme |
| Données et suppression | Aucun média/texte brut dans les sorties concernées ; temporaires, permissions, clôture, rapport vérifié, suppression partielle/erreurs ; calibration/association préservées |
| Runtime commun | Balle puis humain puis balle sans mode ni redémarrage ; stop local, réservation conservée en suspension, aucune demande différée ni relance ; aucune collecte humaine imposée implicitement à la balle |

Valeurs ouvertes non remplacées par des seuils arbitraires. Paramètres de simulation explicitement fictifs permis pour préparer les scénarios, sans qualifier les budgets réels.

**B. Qualification réelle de la chaîne audio et de journalisation**

D'abord sans propulsion, avec la configuration Pi/audio réellement retenue :

- Micro/sortie simultanés, stop utilisateur pendant chaque type d'annonce pertinent ; aucune auto-commande, notamment lorsque le robot prononce « reprends le suivi ».
- Intelligibilité avec casque porté, positions, bruit et portée documentés ; compréhension de l'état, motif, action et paramètres vérifiée, sans reconnaissance d'identité ou de voix.
- Pertes séparées des deux sens, déconnexion/reconnexion et limites de détection.
- Temps de préparation, lecture, interruption et détection mesurés sous charge représentative vision/audio/LLM/journal.
- Événements réellement écrits et limites de persistance après incident vérifiés.
- Aucun enregistrement audio/vidéo autorisé par défaut. Références de mesure indépendantes choisies sans collecte implicite ; média exceptionnel soumis à l'accord distinct du sujet 5.

Conditions avec motorisation ou bruit moteur réel : protocoles protégés SH-02/SH-05 puis SH-10/SH-11 ; non remplacées par un bruit simulé et non lancées par cette validation.

Méthode et verdict :

- Chaque cas indique niveau simulé/réel, version/configuration, préconditions, chronologie, attendu/obtenu, moyens/incertitudes de mesure, maxima, échecs et limites.
- Aucun cas obligatoire en échec ne permet une conformité ; moyenne ne masquant aucune violation.
- Budget obligatoire non fixé/qualifié ou preuve indisponible : non qualifié ou bloqué, jamais réussite par défaut.
- Rapport vérifiable selon la politique de conservation ; absence de trace jamais transformée en preuve d'absence d'événement.
- Réussite logicielle distincte d'audio réel qualifié, d'arrêt physique qualifié et de Go mobile humain.

**Choix techniques restant ouverts :** organisation des scénarios, instrumentation, nombres de répétitions non déjà définis, budgets mesurés et moyens de rapport.

**Preuves de qualification attendues :** résultats effectifs des deux niveaux et non-régression ; rien réputé exécuté par l'approbation du protocole.

#### SH-08 — Statut et travaux techniques restants

**Six sujets de spécification et de recette validés avec l'utilisateur le 2026-10-30 ; orientations synthèse locale et JSONL acquises. Conception détaillée, réalisation et qualification à faire.** Aucune clôture technique du ticket ni de ses dépendances SH-01/SH-06.

| Travail restant | Livrable / preuve attendu |
|---|---|
| Qualifier les prérequis techniques | Résultats SH-02 à SH-07 nécessaires : protections, accès sûr à la coupure en solo, perception, comportement, commandes et cycle de mission ; aucune dépendance satisfaite par sa seule spécification |
| Réaliser le catalogue et la synthèse locale | Gabarits déterministes, prononciation exacte des paramètres et temps restant, moteur/voix choisis et justifiés ; aucun LLM ni service distant pour les annonces |
| Concevoir et qualifier la chaîne audio | Jabra candidat, routage et contrôles des deux sens, surveillance et limites de détection, simultanéité, intelligibilité et stop pendant parole sans auto-commande |
| Réaliser priorité et validité des annonces | Lecture interruptible, invalidation des messages/résultats/buffers obsolètes, précision de diction ; budgets renseignés, justifiés et qualifiés, aucun délai inventé |
| Réaliser les traces et leur surveillance | Schéma JSONL versionné, corrélations, horloges, événements obligatoires et références de preuve ; journal sans blocage de l'arrêt, pertes détectées et aucun acquittement fictif |
| Appliquer la politique de données | Stockage/permissions, absence de médias et textes bruts par défaut dans toutes les sorties concernées, campagnes, rapport probant, temporaires et suppression vérifiable sans effacer calibration/association |
| Fournir les résultats et le verdict | Recette simulée, audio réel sans propulsion, qualifications protégées et non-régression ; maxima, échecs, restrictions et niveaux de preuve explicites. Aucun Go humain implicite |

Aucun code créé, test exécuté, dépendance installée ou essai moteur réalisé pendant cette spécification ; aucune donnée historique purgée. Inhibition et surveillance indépendante restent à concevoir et qualifier ; accès sûr à l'interrupteur embarqué depuis la position de suivi non résolu. Aucun Go mobile humain.

### SH-09 — Spécification progressive de la validation hors roulage

Étude documentaire avec l'utilisateur le 2026-10-30, sans code, création/exécution de tests, acquisition matérielle, installation ni essai moteur. Décisions SH-01 à SH-08 préservées intégralement ; dépendances techniques SH-05/SH-06/SH-07/SH-08 inchangées. Aucun Go mobile humain.

#### Sujet 1 — Périmètre et niveaux de preuve

**Périmètre validé par l'utilisateur le 2026-10-30 :** recette logicielle hors matériel organisant et vérifiant les exigences SH-04 à SH-08 sans redéfinir comportement, commandes ou protections.

| Niveau | Périmètre | Preuve après exécution conforme |
|---|---|---|
| Tests unitaires déterministes | Validation des demandes/observations, états, priorités, échéances, autorisations, annonces et traces, avec dépendances contrôlées | Règles des composants respectées pour les entrées/frontières couvertes |
| Intégration simulée | Chaîne logicielle réelle concernée : entrée texte/intention, validation, admission, comportement, contrôleur à sortie factice, annonces/traces ; LLM et périphériques explicitement simulés | Propagation correcte des décisions, interruptions et résultats ; aucune mission concurrente, substitution ou relance interdite |
| Replay sans moteurs | Réinjection d'événements structurés dans les composants testés, chronologie maîtrisée, comparaison aux attendus | Décisions attendues reproduites pour la séquence/configuration ; aucune preuve sur le matériel d'origine |

- Replay recalculant les décisions, pas simple relecture d'un journal de succès. Scénarios synthétiques suffisants, aucun enregistrement réel exigé. Données réelles éventuellement réutilisées soumises à SH-08 ; aucun média/texte brut supplémentaire autorisé.
- Dans SH-09 : matrices acquises SH-04 à SH-08, refus, défauts simultanés, résultats tardifs et indisponibilités ; non-régression balle/stop dans le même runtime ; commandes/demandes d'arrêt sur interfaces factices ; traces et opérations sur fichiers de test isolés sans toucher aux données d'exploitation.
- Hors preuve SH-09 : précision optique réelle, vitesse au sol, freinage, couverture obstacle ; audio simultané réel, reconnaissance vocale, intelligibilité et absence d'auto-commande acoustique ; charge/délais réels sur Pi ; inhibition indépendante, réarmement matériel et accès sûr à la coupure.
- « Hors roulage » n'inclut pas implicitement tout essai sans déplacement : essais réels audio/matériels distincts, qualifications dans leurs tickets/protocoles respectifs.
- Logique préparée et vérifiable avec protections simulées sans prétendre les rendre réellement disponibles. Contexte de simulation explicite, ne pouvant autoriser le matériel réel ; aucune précondition contournée.
- Fonction non réalisée : non exécuté ou bloqué, jamais réussite. Seuil ouvert : paramètre fictif possible pour étudier la logique, aucune qualification du réglage réel.
- Réussite d'un sous-ensemble limitée à celui-ci, sans clôture globale du ticket/dépendances. Demande d'arrêt observée distincte de commande nulle appliquée au matériel et d'immobilisation physique mesurée.

**Choix techniques restant ouverts :** outils, doubles, formats de scénarios et organisation des suites ; aucune solution choisie par ce périmètre.

**Preuves attendues :** résultats effectivement exécutés, corrélés aux exigences et limités au périmètre testé. Aucun test lancé pendant cette validation.

#### Sujet 2 — Jeux de scénarios et résultats attendus

**Organisation validée par l'utilisateur le 2026-10-30 :** matrice unique reliant exigences, scénarios et vérifications ; chaque obligation SH-04 à SH-08 référencée de façon stable vers sa décision source. Réutiliser les matrices acquises sans ajouter de comportement.

- Chaque scénario décrit exigences couvertes, niveau unitaire/intégration/replay, conditions initiales, configuration/provenance des paramètres, entrées/chronologie/ordres concurrents, attendus établis avant exécution d'après les exigences, résultats interdits et limites de preuve.
- Attendus indépendants de la sortie du programme testé, jamais copiés depuis celle-ci pour confirmer sa propre erreur.

| Famille | Couverture issue des décisions acquises |
|---|---|
| Perception/contexte | Identité, confirmations distinctes, fraîcheur depuis capture, cache, ambiguïté, qualité, génération de flux, calibration et résultats anciens |
| Commandes/paramètres | Humain/balle, chemins local/LLM/repli, omission distincte d'invalidité, unités/bornes, refus intégraux, reprise sans paramètres modifiés |
| Mission/mouvements | Acquisition, suivi, maintien, suspension, reprise et fin ; mouvements interdits, domaine autorisé, réservation/nettoyage |
| Temps/concurrence | Échéance unique, attentes bornées, stop dans chaque phase, défauts simultanés, ordres d'arrivée et résultats tardifs |
| Observabilité/données | Catalogue, temps restant, invalidation des annonces, pannes audio/journal simulées, corrélations, niveaux de preuve, collecte/suppression |
| Non-régression | Balle, primitives et stop existants ; balle puis humain puis balle dans le même runtime, sans concurrence ni état humain hérité |

- Vérifier ensemble selon pertinence : état, toutes les causes, paramètres, cible et échéance ; commandes permises et absence de commandes interdites ; demande d'arrêt et ordre des opérations observables ; annonces, silences et invalidations ; retour runtime, réservation et traces.
- Refus compatible avec demande d'arrêt : aucun mouvement autorisé ne signifie pas aucun appel d'arrêt.
- Frontières juste avant, à et après les limites documentées, conventions acquises préservées. Seuil ouvert : cas logique avec paramètre fictif identifié distinct du cas de validation du réglage réel, bloqué tant que valeur/justification manquent.
- Concurrence : ordres d'arrivée ou points de synchronisation étudiés définis, sans prétendre couvrir tous les entrelacements possibles. Confirmation contre stop et défaut contre échéance notamment obligatoires selon acquis.
- Couverture jugée sur les obligations effectivement vérifiées, pas nombre de tests ou pourcentage global. Séquence pouvant couvrir plusieurs exigences, chaque attendu identifiable ; obligations non couvertes/bloquées visibles.

**Choix techniques restant ouverts :** format concret de matrice, nommage, granularité et mécanisme des assertions ; aucun outil ni nombre supplémentaire de tests imposé.

**Preuves attendues :** correspondance exigence, cas, attendus/obtenus. Aucune matrice exécutable ni test créé pendant cette validation.

#### Sujet 3 — Isolation et reproductibilité

**Contrat validé par l'utilisateur le 2026-10-30 :** environnement explicite sans découverte automatique des ressources réelles ; le nom d'un dossier de tests ne garantit pas l'isolation.

| Surface | Règle d'isolation |
|---|---|
| Moteurs, GPIO, caméra, capteurs, Bluetooth et audio | Doubles explicitement raccordés ; aucun accès réel, imports, initialisation et découverte des tests compris |
| LLM | Réponses/erreurs scriptées, aucun réseau, serveur lancé ou modèle recherché automatiquement |
| Temps | Horloge monotone et attentes contrôlées ; heure civile simulable séparément |
| Fichiers | Répertoire propre à l'exécution, configurations/données synthétiques dédiées ; aucun journal, calibration ou association d'exploitation |
| Tâches concurrentes | Déclenchements/synchronisations contrôlés ; tâches terminées ou annulées en fin de cas, aucun travail survivant |

- Dépendance factice absente ou appel à une ressource interdite : échec explicite, aucun recours au matériel réel. Aucun constructeur matériel utilisé pour sonder sa disponibilité.
- Aucune simulation injectée silencieusement pour faire passer un chemin représentant le réel ; chemins distingués et raccordement matériel non qualifié par cette recette.
- Références de version, configuration, scénario, données synthétiques, doubles et séquence d'événements conservées. Aléa éventuel : graine et réalisation permettant le rejeu, sans outil aléatoire imposé.
- Mêmes entrées/configuration/ordre : décisions et commandes pertinentes identiques. Identifiants générés et dates de rapport peuvent varier, mais relations de corrélation vérifiées ; aucun contrôle effacé sous prétexte de normalisation.
- Borne technique externe d'exécution pour éviter qu'un cas bloque la campagne, distincte du temps simulé ; expiration = erreur de test explicite, jamais fin normale de mission. Valeur à justifier.
- Suite utilisable sans matériel robot ni modèle LLM installé ; aucune recherche dans les modèles, périphériques ou données personnelles du poste.
- Nettoyage limité aux ressources de test explicitement créées, échecs signalés, aucune donnée extérieure supprimée. Isolation sans preuve sur pilotes réels ou performances Pi.

**Constats de lecture, pas qualification :** [tests de suivi objet](../../tests/unit/test_follow_object.py) avec robot/horloge simulés ; [intégration LLM](../../tests/integration/test_voice_runtime_llm_integration.py) pouvant rechercher un modèle et démarrer un serveur local. Aucun test modifié/exécuté ; sélectionner et adapter les surfaces réutilisables lors de la réalisation, sans supposer toute la suite déjà isolée.

**Choix techniques restant ouverts :** injection, garde d'accès, contrôle du temps/tâches, borne externe et raccordement aux outils existants.

**Preuves attendues :** reproductibilité sans ressources réelles, appels interdits détectés, absence de tâches/ressources de test résiduelles. Aucun mécanisme créé ou essayé.

#### Sujet 4 — Intégration et non-régression

**Contrat validé par l'utilisateur le 2026-10-30 :** traverser les composants logiciels réels concernés avec périphériques explicitement remplacés, pas une seconde implémentation simplifiée du comportement attendu.

| Axe | Contrat à vérifier |
|---|---|
| Entrées | Texte, transcription simulée, intention interne, LLM simulé, parser local et repli technique : validations/admission non contournées |
| Commandes locales | Stop/reprise avec LLM simulé indisponible ou en attente ; aucun traitement attendant le LLM |
| Chaîne humaine | `follow_person`, comportement et observations marqueur explicitement sélectionnés ; aucune balle, primitive ou cible par défaut en remplacement |
| Ressources | Une mission motrice, une acquisition caméra logique partagée ; aucun second propriétaire concurrent |
| Suspension | Réservation même si worker terminé ; disparition des défauts sans départ, autres demandes non exécutées/non mémorisées |
| Reprise | Même mission, cible, distance, échéance ; nouvelles confirmations, contrôles et annonce ; aucun démarrage générique réinitialisant le contexte |
| Fin/nettoyage | Anciennes commandes, observations, réponses LLM et annonces inopérantes ; nettoyage avant libération, ressources partagées préservées |
| Erreurs | Skill/dépendance absente, exception, plan incomplet : refus/interruption explicite selon contrat ; aucun succès vide, exécution partielle, secours ou réessai humain |

- Restrictions humaines non globalisées au suivi objet. Exemple : recul balle prévu dans [les tests existants](../../tests/unit/test_follow_object.py), non supprimé pour satisfaire l'interdiction humaine.
- Référence de non-régression : contrats livrés et tests pertinents inspectés avant adaptation, version de référence identifiée ; échecs préexistants distingués des régressions. Aucun attendu existant modifié pour faire passer une régression.
- Incohérence contrat/test signalée et arbitrée, jamais corrigée silencieusement.

Séquences obligatoires dans la même instance de runtime :

1. Mission balle terminée, mission humaine, puis nouvelle mission balle après fin/nettoyage.
2. Mission humaine suspendue, demande balle refusée/non exécutée, reprise humaine ou fin explicite.
3. Après fin humaine, nouvelle demande balle nécessaire ; demande reçue pendant réservation jamais exécutée plus tard.
4. Capacité humaine indisponible : refus humain motivé sans indisponibilité implicite des capacités balle.

Inclure stop et primitives existantes pertinentes ; aucune exigence humaine de marqueur, audio, configuration ou collecte imposée globalement. Coordination logicielle démontrable, pas partage effectif des pilotes ou performances matérielles réelles.

**Choix techniques restant ouverts :** injection/observation, sélection des tests existants, gestion des workers et version de référence.

**Preuves attendues :** résultats de bout en bout et comparaisons de non-régression, échecs préexistants et chemins non testés visibles. Aucun test exécuté.

#### Sujet 5 — Rapports et couverture

**Contrat validé par l'utilisateur le 2026-10-30 :** distinguer couverture, exécution et preuve ; rapport permettant de retrouver les scénarios/résultats de chaque obligation, pas simple total de tests réussis.

| Partie | Informations nécessaires |
|---|---|
| Références | Version logicielle et référence de non-régression, configuration, scénario, doubles, données synthétiques ; paramètres fictifs ou issus d'une qualification identifiée |
| Exécution | Niveau unitaire/intégration/replay ; cas sélectionnés, exécutés, interrompus ou non exécutés ; environnement/chronologie |
| Résultats | Attendus/obtenus, première divergence/contexte utile, états, toutes les causes, paramètres, échéance, commandes, annonces et traces pertinentes |
| Couverture | Chaque obligation liée aux vérifications effectuées ; manques, limites, variantes et ordres concurrents non couverts visibles |
| Preuve | Nature simulée ou observation du logiciel réel, origine/limites ; aucune extrapolation à l'audio ou au mouvement physiques |
| Synthèse | Conformités observées, échecs, blocages, erreurs d'exécution, régressions et anomalies préexistantes, sans compensation entre catégories |

- Temps/durées simulés étiquetés et séparés du temps réel d'exécution de la suite, jamais mesures de latence Pi.
- Résultat du système distinct du résultat du test : panne injectée du journal conforme seulement si défaut, arrêt/suspension et autres attendus observés. Échec attendu d'une opération pas automatiquement échec du test ; exception/absence de résultat non prévue jamais réussite sous prétexte d'injection de défaut.
- Dispositif de test observant appels d'arrêt et chronologie indépendamment du journal mis en panne, via sorties de test contrôlées. Aucun faux événement reconstitué comme écrit par le runtime ; provenance d'observation par le test explicite.
- Observateur de test en échec : résultats concernés indisponibles/inconclusifs, jamais conformes par défaut. Processus simulé indisponible non réputé avoir journalisé sa propre fin.
- Politique SH-08 appliquée au rapport/traces sans collecte supplémentaire. Formulations entièrement synthétiques nécessaires aux cas de langage : entrées de test identifiées, aucune autorisation de capture de vraies commandes.
- Rapport vérifié gardant les éléments probants nécessaires au verdict après suppression des traces détaillées ; aucun export automatique ni durée supplémentaire.
- Couverture de code éventuellement utile au diagnostic, sans remplacement de la couverture des exigences ni seuil de conformité inventé.

**Choix techniques restant ouverts :** format du rapport, outil de couverture, observateur, stockage isolé et vérification du rapport ; aucun pourcentage imposé.

**Preuves attendues :** rapport exploitable pour campagne partielle/en échec, provenance contrôlée et obligations non démontrées visibles. Aucun rapport d'essai produit ni test exécuté par cette spécification.

#### Sujet 6 — Verdict et passage aux qualifications suivantes

**Règles validées par l'utilisateur le 2026-10-30 :** verdict limité au périmètre démontré, blocages conservés.

| Verdict de recette | Condition |
|---|---|
| Conforme dans le périmètre logiciel déclaré | Toutes les obligations obligatoires du périmètre vérifiées, sans échec, cas manquant, violation d'isolation ni preuve nécessaire indisponible |
| Non conforme | Au moins un écart observé à une exigence obligatoire ; blocages et cas non exécutés également mentionnés |
| Incomplète / bloquée | Conclusion globale impossible : réalisation absente, scénario obligatoire non exécuté, attendu dépendant d'un choix ouvert, observateur défaillant ou résultat inexploitable |

- Conformité partielle rapportable, jamais conformité globale SH-09. Propriétés physiques hors périmètre : non qualifiées par SH-09, ni réussies ni en échec sans mesure.
- Trois niveaux réalisés selon la matrice, sans imposer artificiellement chaque exigence à chacun des niveaux. Composants concernés réellement raccordés ; tests des seuls doubles insuffisants à valider l'intégration.
- Refus, arrêts, fins, suspensions, annonces, traces et absence d'actions interdites conformes aux attendus.
- Non-régression balle/primitives/stop démontrée dans le périmètre sélectionné ; anomalie obligatoire non résolue empêchant conformité globale, même préexistante.
- Rapport vérifié et éléments probants conservés selon SH-08 ; trace manquante jamais preuve d'absence d'événement.
- Réglages réels encore ouverts : cas bloqués, paramètres fictifs ne les rendant pas conformes.
- Après échec : correction ultérieure de la cause, référence de l'échec conservée, rejeu des cas affectés et régressions pertinentes. Test devenu conforme sans effacement de l'historique.
- Relance d'un test de campagne distincte d'un réessai de mission : aucun premier échec masqué par répétitions jusqu'au succès, aucun réessai automatique d'exécution humaine introduit.
- Dossier de sortie précisant réalisé/démontré hors matériel, blocages/restrictions/paramètres fictifs, preuves Pi restantes et prérequis réels de chaque futur essai.
- SH-10 non déclenché automatiquement ; sa spécification n'autorise pas ses mesures. Toute mesure réelle exige protocole/préconditions adaptés ; essais moteurs selon protections/protocoles acquis.
- Clôture technique SH-09 non déduite de l'approbation documentaire ni d'un sous-ensemble conforme : réalisation, résultats complets, rapport vérifié et traitement explicite des dépendances requis. Aucune dépendance clôturée par substitution d'une simulation.
- Hors conclusion SH-09 : inhibition indépendante qualifiée, accès sûr à la coupure en solo, immobilisation physique et Go mobile humain.

**Choix techniques restant ouverts :** agrégation des résultats, gestion des anomalies et livrables concrets.

**Preuves attendues :** verdict justifié par les résultats effectifs et dossier de passage sans qualification inventée. Aucun test exécuté.

#### SH-09 — Statut et travaux techniques restants

**Six sujets de spécification et de recette validés avec l'utilisateur le 2026-10-30. Conception détaillée, réalisation et exécution de la recette à faire.** Ticket technique et dépendances SH-05/SH-06/SH-07/SH-08 non clôturés.

| Travail restant | Livrable / preuve attendu |
|---|---|
| Établir la matrice et les prérequis | Références stables vers SH-04 à SH-08, scénarios/attendus indépendants, frontières et ordres concurrents ; fonctions absentes et réglages ouverts signalés, aucun prérequis satisfait par la seule documentation |
| Concevoir les suites isolées | Tests unitaires, intégration simulée et replay recalculant les décisions ; temps/doubles explicites, garde des ressources, tâches et fichiers isolés, borne externe justifiée |
| Raccorder les composants et la non-régression | Chaîne réelle à périphériques simulés, version de référence et tests existants pertinents, même instance de runtime, séquences balle/humain/balle ; commandes locales, réservation et nettoyage vérifiés |
| Réaliser les observations et rapports | Observation indépendante du journal testé, attendus/obtenus et provenance, couverture par obligation, données minimales et conservation SH-08 |
| Exécuter et fournir le verdict | Résultats reproductibles des trois niveaux, écarts/blocages explicites, absence de faux succès et d'effacement des échecs par répétition ; rapport vérifié et dossier des preuves restantes |

Aucun code ni test créé, aucun test exécuté, acquisition matérielle, installation ou essai moteur pendant cette spécification ; inspections en lecture seule et mise à jour documentaire uniquement. Les six décisions de chacun des tickets SH-05 à SH-08 sont préservées. Aucune qualification physique ni clôture de dépendance, aucun Go mobile humain. Inhibition/surveillance indépendante et accès sûr à l'interrupteur embarqué en solo restent à concevoir/résoudre et qualifier.

### SH-10 — Spécification progressive des mesures du système intégré sur Pi

Étude documentaire avec l'utilisateur le 2026-10-30. Six sujets validés ; conception détaillée, réalisation et mesures à faire, sans qualification ni clôture technique implicite. Aucun code ni test créé, aucun test, mesure, acquisition matérielle, charge, installation ou essai moteur lancé. Les six décisions détaillées de chacun des tickets SH-05 à SH-09 sont préservées intégralement. Dépendances SH-03/SH-07/SH-08 inchangées, aucune réalisation ni qualification déduite de leur spécification. Aucun Go mobile humain.

#### Sujet 1 — Périmètre et prérequis des mesures

**Périmètre et prérequis validés par l'utilisateur le 2026-10-30 :** mesurer les performances du système effectivement intégré sur Pi ; limiter chaque conclusion aux composants réellement présents et aux conditions éprouvées.

| Niveau | Périmètre validé | Prérequis et limites |
|---|---|---|
| Première étape sans propulsion | Vision réelle, audio bidirectionnel, LLM local et journalisation sur Pi, séparément puis ensemble selon leur disponibilité ; observation des décisions et demandes de commande sans actionnement réel | Moteurs déconnectés, configuration identifiée, composants mesurés réalisés, protocole et instrumentation préparés. Toute sortie motrice observée explicitement non actionnante ; aucun contournement des préconditions du suivi réel pour obtenir artificiellement une activation |
| Éventuels essais protégés ultérieurs | Compléments nécessitant une motorisation réelle, notamment son bruit et ses effets sur le système intégré | Protocole distinct compatible avec l'opérateur seul, risques maîtrisés et protections requises pour l'essai effectivement disponibles et vérifiées. Ordre SH-02/SH-05 : banc protégé puis cibles inertes. Aucun essai sous puissance autorisé par la spécification SH-10 |
| Propriétés exclues des conclusions de performance | Sécurité physique globale, vitesse au sol, freinage, couverture obstacle, efficacité de l'inhibition indépendante, accès sûr à la coupure et aptitude au suivi mobile humain | Preuves propres aux qualifications concernées. Ni mesure de latence ni succès audio ne démontre ces propriétés ; aucun Go humain implicite |

- Les protections encore ouvertes ne bloquent pas par principe toute caractérisation sans propulsion correctement isolée. Celle-ci ne les qualifie pas et ne lève aucun verrou du fonctionnement réel.
- Avant chaque mesure, identifier les réalisations nécessaires, les vérifications disponibles et les limites encore ouvertes. Aucune dépendance technique satisfaite par sa seule spécification.
- Fonction absente : mesure correspondante bloquée. Une caractérisation partielle reste possible, mais ne constitue pas une qualification du système intégré complet.
- Distinguer composants réellement exécutés, simulés, absents et non qualifiés ; aucune durée simulée présentée comme mesure Pi.
- Exigences SH-01 à SH-09 inchangées : runtime commun, arrêts prioritaires, contrats de perception/mission/observabilité, collecte minimale et niveaux de preuve distincts. Inhibition et surveillance indépendante restent à concevoir et qualifier ; accès sûr à l'interrupteur embarqué depuis la position de suivi en solo non résolu.

**Conséquences :** la première étape caractérise uniquement le périmètre sans propulsion réellement disponible. Elle ne démontre ni les effets des moteurs réels ni les propriétés physiques ; toute extension sous puissance reste conditionnée à ses preuves et à son protocole propres.

**Choix techniques restant ouverts :** raccordement non actionnant, moyens de vérification de la déconnexion, instrumentation et protocoles protégés. Aucun instrument ni seuil numérique choisi par cette validation.

**Preuves attendues :** dossier par mesure identifiant configuration, périmètre réellement exécuté ou simulé, réalisations nécessaires, prérequis effectivement vérifiés et limites de conclusion. Aucune preuve d'exécution produite pendant cette étude documentaire.

#### Sujet 2 — Charges et scénarios représentatifs

**Organisation validée par l'utilisateur le 2026-10-30 :** comparer des références par composant à leur fonctionnement conjoint réel, sans nouveau comportement ni charge artificiellement illimitée.

| Famille | Scénarios sans propulsion |
|---|---|
| Références séparées | Chaque chaîne disponible : vision, audio bidirectionnel, compréhension locale/LLM, journal ; dépendances nécessaires documentées. Points de comparaison, pas preuve d'intégration |
| Charge intégrée nominale | Acquisition caméra et traitement marqueur, écoute active, synthèse/lecture du catalogue, LLM et journal réellement raccordés ; distinguer ressources chargées en mémoire et traitements effectivement actifs |
| Transitions | Préparation initiale, acquisition, annonce, suivi logique, maintien, suspension, reprise et fin ; première utilisation distincte du fonctionnement déjà initialisé. Dépendances simulées explicitement étiquetées, aucune qualification du suivi réel déduite |
| Concurrence autorisée | Stop local pendant annonce et attente LLM ; reprise locale recevable ; nouvelles demandes selon l'admission existante. Aucune seconde mission ni inférence concurrente artificiellement engagée si le runtime ne doit pas l'engager |
| Enchaînements et répétitions | Balle puis humain puis balle dans le même runtime sans redémarrage ni actionnement, selon les réalisations disponibles ; répétitions pour observer dérives de ressources et échauffement, durées et nombres à justifier ultérieurement |

- Référence reproductible : Pi, alimentations, refroidissement, versions, modèle LLM/réglages, caméra/montage/calibration, chaîne audio et journal identifiés. Conditions optiques/acoustiques et autres activités du Pi consignées ; chaque variation étudiée constitue un cas identifié.
- Références séparées insuffisantes pour conclure sur la concurrence. LLM en mémoire distinct d'une inférence active ; concurrence revendiquée seulement si effectivement observée.
- Séquence partiellement simulée : portée limitée aux chemins réels traversés. Aucun contournement des préconditions acquises.
- Pannes et surcharges provoquées à cadrer au sujet 4 ; aucun stress arbitraire décidé.
- Aucun média ni texte brut réel conservé par défaut selon SH-08 ; formulations synthétiques identifiées utilisables pour les cas de langage.

**Choix techniques restant ouverts :** jeux d'entrées précis, organisation des séquences, durées et répétitions ; aucun nouveau seuil fixé.

**Preuves attendues :** configuration, composants réels/simulés, chronologie et activité effective des chaînes par scénario, pour rattacher les futures mesures à une charge identifiable. Aucun scénario exécuté par cette validation.

#### Sujet 3 — Mesures et références temporelles

**Cadre validé par l'utilisateur le 2026-10-30 :** mesurer des intervalles précisément définis, pas une latence globale sans étapes explicables.

| Chaîne | Mesures attendues |
|---|---|
| Vision | Débit de trames et observations nouvelles, acceptations/rejets et séries de pertes ; capture vers publication ; âge depuis capture à la décision. Retard de traitement, répétition et ancien cache distingués |
| Compréhension et mission | Entrée structurée disponible vers validation/admission ou refus ; temps local et LLM séparés ; acquisition et préparation initiale distinctes du temps de mission ; échéance monotone unique et temps réellement restant |
| Audio | Préparation/synthèse, attente avant lecture, lecture, interruption et détection des défauts. Stop vocal : émission acoustique de référence, disponibilité de transcription, reconnaissance locale et demande d'arrêt distinguées selon les moyens disponibles |
| Arrêt | Événement déclencheur, détection, demande d'arrêt, commande nulle transmise ou appliquée : intervalles seulement entre étapes observables. Inhibition confirmée et immobilisation physique distinctes, jamais déduites de ces temps |
| Pi et journal | CPU, mémoire, température, fréquence et éventuelle limitation thermique ; évolution temporelle, ressources du processus et du système distinguées. Retard d'écriture, pertes et erreurs selon les confirmations disponibles |

- Temps monotone pour les durées, UTC pour situer la campagne. Autre horloge : rapprochement et incertitude documentés.
- Bornes de début/fin définies avant mesure ; événement indisponible : intervalle non mesurable, jamais zéro.
- Panne injectée : référence d'injection indépendante de la détection logicielle. Référence manquante : seul le segment effectivement mesuré peut être revendiqué.
- Effectifs, distributions, p95 pertinent, maxima, chaque dépassement obligatoire et données manquantes rapportés. Aucune moyenne ne compense une violation.
- Coût de l'instrumentation évalué ; comparaison avec journalisation allégée ne remplaçant pas la mesure dans la configuration à journal obligatoire.
- Objectifs/frontières acquis conservés avec leur statut exact ; cibles à qualifier et objectifs provisoires ne deviennent pas garanties. Aucun nouveau seuil numérique.
- Aucun média implicitement autorisé pour établir une référence ; politique SH-08 inchangée. Durées simulées distinctes des mesures Pi.

**Choix techniques restant ouverts :** instruments, points d'observation, fréquence d'échantillonnage, synchronisation et incertitudes.

**Preuves attendues :** définition, source, horloge, méthode, incertitude, scénario et limites de chaque métrique. Résultats caractérisant les essais effectués, pas un pire cas garanti dans toutes les situations. Aucune mesure effectuée pendant cette validation.

#### Sujet 4 — Dégradations et limites

**Matrice et limites validées par l'utilisateur le 2026-10-30 :** dégradations contrôlées d'abord sans propulsion, pour vérifier les délais observables et les réactions déjà exigées.

| Famille | Cas à préparer | Attendus acquis |
|---|---|---|
| Vision | Ralentissement, flux figé, répétitions/retards, perte/rejet/ambiguïté de cible, indisponibilité caméra | Aucun rajeunissement ni ancienne observation autorisant le mouvement ; refus ou arrêt/suspension selon la phase |
| LLM et contention | Réponse lente, erreur/indisponibilité ; concurrence représentative CPU/mémoire | Stop/reprise locaux indépendants du LLM ; aucun départ partiel, secours moteur ou réessai humain ; repli de compréhension uniquement selon SH-07 |
| Audio | Perte de chaque sens, synthèse/lecture lente ou bloquée, déconnexion/reconnexion | Refus avant activation ou arrêt/suspension après ; aucune reprise spontanée ni audition prétendument confirmée |
| Journal | Erreur, permission refusée, écriture bloquée, capacité indisponible, perte d'événements détectée | Arrêt indépendant de l'écriture ; événements obligatoires manquants empêchant conformité de session |
| Temps et concurrence | Budget dépassé, stop pendant attente/annonce, échéance pendant reprise, défaut simultané | Priorités SH-05, échéance inchangée, causes conservées, résultats tardifs inopérants |

- Panne simulée à une interface distincte d'une défaillance réelle du périphérique/processus : preuves différentes.
- Avant chaque injection : périmètre, référence temporelle, risques, borne d'exécution, conditions d'interruption et remise en état définis.
- Moyens isolés et bornés ; aucune saturation du stockage global ni perturbation d'autres usages, périmètre dédié. Charge supplémentaire éventuelle justifiée ; aucun stress illimité ni franchissement improvisé des limites matérielles.
- Blocage/arrêt du pilotage, indisponibilité du Pi, coupure/rétablissement sous puissance : protocoles protégés SH-02/SH-05 distincts. Processus indisponible jamais supposé avoir journalisé sa propre fin.
- Injection ou observateur défaillant : résultat inconclusif et interruption de la campagne concernée, jamais réussite par absence de trace.
- Budgets approuvés conservant leur statut ; autres budgets à justifier et qualifier. Caractérisation exploratoire utile pour les établir, mais ne validant pas un seuil encore ouvert. Aucune valeur fictive ne devient réglage Pi.

**Choix techniques restant ouverts :** moyens d'injection/observation, bornes justifiées, limites matérielles applicables, budgets non encore établis et procédures de remise en état.

**Preuves attendues :** panne effectivement produite, chronologie, attendus/obtenus, dépassements, état final et remise en état. Bonne détection distincte d'inhibition indépendante et d'arrêt physique. Aucune injection ni charge lancée pendant cette validation.

#### Sujet 5 — Rapports et gestion des réglages

**Cadre validé par l'utilisateur le 2026-10-30 :** dossier de campagne permettant de comprendre et vérifier le verdict, y compris après suppression des traces détaillées selon SH-08.

| Partie | Contenu attendu |
|---|---|
| Références | Version logicielle, configuration effective, matériel/montage, calibration, modèle LLM, audio, journal, instrumentation et conditions de charge |
| Traçabilité | Exigence source et statut : exigence validée, objectif à qualifier ou choix ouvert ; liens vers scénarios, métriques et critères établis avant exécution |
| Résultats | Cas prévus/exécutés/non exécutés, réel/simulé, attendus/obtenus, effectifs, distributions, maxima, dépassements, données manquantes, incertitudes et limites |
| Écarts | Échecs, blocages, erreurs d'instrumentation et anomalies préexistantes, sans compensation par les réussites d'autres cas |
| Synthèse probante | Verdict par propriété/configuration ; éléments structurés nécessaires pour vérifier sa justification sans conservation implicite de toutes les traces ni de médias |

- Chaque configuration mesurée figée et identifiée ; modification, raison et propriétés potentiellement affectées consignées.
- Après correction/réglage : référence de l'échec initial conservée, nouvelle série distincte ; aucune répétition jusqu'au succès effaçant les échecs.
- Revalidation des propriétés affectées et régressions pertinentes. Résolution, modèle, audio, refroidissement ou journalisation peuvent affecter plusieurs budgets.
- Aucun seuil déplacé ni périmètre réduit silencieusement pour déclarer conformité. Restriction explicite ne validant pas le périmètre initial.
- Révision d'une exigence acquise : décision distincte obligatoire ; aucun réglage contournant une protection ou relevant le plafond de vitesse.
- Politique SH-08 inchangée : collecte locale minimale sans médias/textes bruts réels par défaut, aucun export automatique ; traces jusqu'à clôture explicite puis suppression après rapport produit et vérifié ; rapport jusqu'à suppression explicite. Aucun délai calendaire ajouté.

**Choix techniques restant ouverts :** format concret du dossier, références de configuration et méthode de vérification du rapport ; aucun outil imposé.

**Preuves attendues :** dossier vérifié reliant chaque conclusion aux résultats utiles, historique des réglages et limites conservé. Rapport incomplet ou données manquantes jamais transformés en réussite. Aucun rapport d'essai produit pendant cette validation.

#### Sujet 6 — Verdict et articulation avec SH-11

**Règles validées par l'utilisateur le 2026-10-30 :** séparer validation documentaire, résultats de mesure et autorisation d'essai.

| Verdict futur | Conditions |
|---|---|
| Conforme dans le périmètre mesuré déclaré | Toutes les obligations de ce périmètre vérifiées, critères applicables justifiés, résultats exploitables et rapport vérifié ; aucun dépassement obligatoire ni cas obligatoire manquant |
| Non conforme | Au moins un écart observé à une exigence obligatoire ; autres blocages et cas non exécutés également visibles |
| Incomplet / bloqué | Réalisation absente, prérequis non satisfait, critère nécessaire encore ouvert, scénario obligatoire non exécuté ou preuve indisponible/inexploitable empêchant la conclusion |

- Caractérisation exploratoire rapportable avec résultats et limites, sans qualification si critères non établis. Objectif provisoire conservant son statut ; atteinte ne démontrant pas à elle seule une propriété de sécurité.
- Sous-ensemble conforme distinct de conformité globale SH-10 et de clôture d'une dépendance.
- Maxima, dépassements et cas manquants décisifs ; aucune moyenne, p95 ou répétition favorable ne les efface.
- Conformité informatique sans propulsion ne qualifiant ni audio avec moteurs réels, ni dynamique, inhibition indépendante ou accès sûr à la coupure.
- Clôture technique SH-10 seulement après réalisations, mesures requises, traitement explicite des dépendances et rapport vérifié ; jamais sur approbation documentaire.
- Prochaine session : spécifier SH-11, sans commencer les essais. Premier sujet : portes d'entrée et preuves nécessaires à chaque étape, sans propulsion, banc protégé, cibles inertes, puis éventuel porteur humain uniquement après qualifications et Go explicite.
- Dossier de passage maintenant visibles les résultats SH-09/SH-10 à produire, protections SH-02/SH-05 à concevoir et qualifier, accès sûr à la coupure en solo non résolu, autres réalisations/réglages/preuves manquants.
- Aucun passage automatique à une campagne, aucun Go mobile humain ; SH-11 non commencé par cette validation.

**Choix techniques restant ouverts :** critères encore à justifier/qualifier, agrégation des résultats, gestion des blocages et dossier de passage concret. Aucun nouveau seuil ni dispositif choisi.

**Preuves attendues :** verdict motivé par propriété/configuration, rapport vérifié et dossier des preuves manquantes avant chaque étape ultérieure. Aucun résultat de mesure produit.

#### SH-10 — Statut et travaux techniques restants

**Six sujets de spécification validés avec l'utilisateur le 2026-10-30. Conception détaillée, réalisation et mesures à faire.** Ticket technique et dépendances SH-03/SH-07/SH-08 non clôturés.

| Travail restant | Livrable / preuve attendu |
|---|---|
| Établir les prérequis réels | Configuration Pi et réalisations disponibles identifiées ; périmètre sans propulsion isolé, limites et fonctions absentes explicites ; aucun prérequis satisfait par documentation seule |
| Préparer les scénarios représentatifs | Références séparées, charge intégrée et activité réelle, transitions, concurrence autorisée et séquences runtime commun ; conditions, durées et répétitions justifiées |
| Concevoir l'instrumentation | Intervalles/horloges, références indépendantes nécessaires, incertitudes et coût ; vision/audio/arrêt/Pi/journal distincts, sans faux acquittement ni preuve physique déduite |
| Préparer les dégradations contrôlées | Moyens bornés/isolés, risques, références d'injection et remise en état ; simulation distincte du réel, essais sous puissance selon protocoles protégés séparés |
| Réaliser les mesures et gérer les réglages | Résultats réels, maxima/dépassements et données manquantes, configurations identifiées, historique des échecs et revalidation ; politique SH-08 appliquée |
| Vérifier le rapport et fournir le verdict | Conclusions limitées au périmètre démontré, obligations et dépendances traitées explicitement, blocages et dossier de passage SH-11 ; aucun Go humain implicite |

Aucun code ni test créé ; aucun test, mesure, acquisition matérielle, charge, installation ou essai moteur lancé pendant cette spécification. Six décisions détaillées de chacun des tickets SH-05 à SH-09 préservées intégralement. Inhibition et surveillance indépendante restent à concevoir et qualifier ; accès sûr à l'interrupteur embarqué depuis la position de suivi en solo non résolu. Aucun Go mobile humain.

### SH-11 — Spécification progressive de la recette et de la décision Go/No-Go

Étude strictement documentaire avec l'utilisateur le 2026-10-30. Les sujets validés sont détaillés ci-dessous ; statut de progression en fin de cette sous-section. Les six décisions détaillées de chacun des tickets SH-05 à SH-10 sont préservées intégralement. Aucune dépendance technique satisfaite par sa seule spécification ; aucune réalisation, recette, mesure ou qualification déduite de cette validation. Aucun code ni test créé ; aucun test, mesure, acquisition matérielle, charge, essai moteur ou installation de dépendance exécuté. Aucun Go mobile humain.

#### Sujet 1 — Portes d'entrée et preuves requises par niveau d'essai

**Exigences validées par l'utilisateur le 2026-10-30 :** chaque niveau possède une porte d'entrée propre et produit un dossier de preuves limité à ce qui a réellement été éprouvé. Une réussite ne déclenche jamais automatiquement le niveau suivant. La validation de ces portes n'autorise aucune exécution.

| Niveau | Porte d'entrée validée | Preuves à obtenir à ce niveau |
|---|---|---|
| Sans propulsion | Pour SH-09 : isolation logicielle prévue par son cadre. Pour les observations réelles : moteurs déconnectés, déconnexion vérifiée, sorties explicitement non actionnantes ; configuration, composants disponibles, protocole et instrumentation identifiés. Une fonction absente bloque son cas, sans interdire une caractérisation partielle clairement délimitée | Séparément : résultats logiciels SH-09 ; mesures réelles Pi SH-10 ; qualification optique SH-03 ; audio/journal réels SH-08. Aucune conclusion sur la dynamique ou la protection physique |
| Banc protégé | Protocole sous puissance distinct, adapté à l'opérateur seul ; dispositif de banc et protection de l'opérateur effectivement vérifiés pour les défaillances injectées, moyens d'interruption et de mesure disponibles. Le banc ne peut pas compter uniquement sur la protection qu'il cherche à qualifier. Réalisations et résultats logiciels nécessaires aux cas prévus disponibles | Coupure/rétablissement, perte ou blocage du pilotage, indisponibilité du Pi, surveillance indépendante, inhibition et réarmement ; absence de réapplication d'anciennes commandes et de départ spontané. Mesures physiques adaptées au banc, sans les extrapoler au freinage au sol |
| Cibles inertes | Résultats pertinents du banc conformes ; protections requises pour ces essais qualifiées ; terrain, organisation solo et accès sûr à la coupure vérifiés pour la position réelle d'essai. Résultats logiciels, perception, performances Pi et audio nécessaires disponibles. Protocole de caractérisation physique défini, sans supposer déjà connus les réglages qu'il doit établir | Couverture obstacle et volume balayé, vitesse au sol, réactions et immobilisation physique dans les conditions retenues ; budget d'arrêt et réglages justifiés, puis vérifiés. Audio avec motorisation réelle évalué séparément lorsque nécessaire. Aucune personne utilisée comme obstacle ou cible exposée |
| Éventuel porteur humain | Dossiers requis SH-09/SH-10 et qualifications physiques/audio applicables complets et conformes pour la configuration retenue ; protections indépendantes qualifiées, budget d'arrêt et réglages établis, accès sûr à la coupure depuis la position de suivi démontré en solo. Go humain explicite préalable, limité à ce domaine et à ce protocole | Seulement ensuite, résultats de suivi avec porteur dans le domaine autorisé. Ils ne peuvent pas servir à découvrir ou qualifier les protections qui conditionnaient l'entrée. Cette porte reste fermée aujourd'hui |

Règles transversales validées :

- Exigences déjà acquises inchangées : ordre progressif, arrêt prioritaire, aucune qualification déduite d'une spécification, aucun mouvement interdit ajouté. Runtime commun humain/balle, `follow_person` distinct sans cible `yellow` par défaut, stop/reprise locaux, validation intégrale des demandes, réservation en suspension, échéance inchangée et absence de demande différée ou réessai humain automatique préservés.
- Chaque dossier indique configuration/version, prérequis effectivement vérifiés, attendus/obtenus, références et incertitudes, maxima, dépassements, échecs et manques. Une preuve obligatoire absente ou inexploitable bloque le passage concerné ; moyennes et p95 ne compensent aucun dépassement obligatoire.
- Preuves logicielles SH-09, performances Pi SH-10, audio réel et propriétés physiques distincts. Simulation et durée simulée ne qualifient aucun réglage ou délai Pi.
- Précision visée, zone de commande et distance minimale de sécurité distinctes ; aucun seuil nouveau ni objectif provisoire transformé en garantie.
- Arrêt demandé, commande nulle, inhibition confirmée et immobilisation physique mesurée restent quatre faits distincts. Aucune confirmation d'annonce, d'audition, de persistance ou de protection inventée.
- Politique de données SH-08 inchangée ; l'audio ne remplace aucune protection.

**Conséquence :** les préparations et caractérisations partielles sans propulsion restent distinguées de la qualification complète. Le banc sert notamment à qualifier les protections, mais sa propre protection pour les défaillances prévues doit être établie avant l'essai. Aucun succès de banc ne qualifie à lui seul la dynamique au sol. Le porteur humain n'est jamais un moyen de qualification initiale des protections.

**Choix techniques restant ouverts :** conception du banc, inhibition et surveillance indépendante, solution d'accès sûr à la coupure en solo, instrumentation, réglages et budgets non établis. Aucun dispositif ni valeur choisi par cette décision ; accès sûr à l'interrupteur embarqué depuis la position de suivi toujours non résolu.

**Preuves attendues :** dossiers effectifs par niveau selon le tableau, avec limites et blocages explicites. Aucune preuve d'exécution produite par cette spécification ; aucun passage autorisé ni Go mobile humain.

#### Sujet 2 — Cas et critères applicables par niveau

**Organisation validée par l'utilisateur le 2026-10-30 :** réutiliser les matrices approuvées et les sections 5/7 dans une matrice de passage documentaire, sans créer de tests ni de nouveaux comportements.

Chaque obligation est reliée à sa décision source et à son statut exact (exigence validée, objectif à qualifier ou choix technique ouvert), ses scénarios/préconditions/niveaux pertinents, son attendu, ses actions interdites et sa convention de frontière, sa preuve nécessaire (logiciel SH-09, mesure Pi SH-10, audio réel ou propriété physique), ses blocages et limites de conclusion.

| Niveau | Cas à y rattacher |
|---|---|
| Sans propulsion | Logique, demandes invalides, transitions, concurrence, échéances et non-régression SH-09 ; optique, performances Pi et audio réel dans des volets distincts, selon les réalisations disponibles |
| Banc protégé | Défaillances de contrôle, coupure/rétablissement, inhibition, réarmement et absence de départ spontané. Les injections dangereuses ne sont pas reportées près d'un porteur |
| Cibles inertes | Couverture, dynamique, arrêts, frontières de commande et mouvements effectivement candidats à la qualification ; audio sous motorisation réelle dans son volet propre |
| Éventuel porteur | Seulement les scénarios compatibles avec le domaine déjà qualifié et le futur Go explicite. Aucun scénario de la matrice générale n'autorise implicitement une mise en danger humaine |

- Chiffres de la section 5 conservant leur statut, jamais tous transformés en seuils obligatoires qualifiés par recopie. Le minimum provisoire de 0,8 m ne fixe pas la distance de sécurité ; les objectifs de délais restent à confronter aux mesures et au budget d'arrêt. Exigences déjà validées obligatoires avec leur portée exacte.
- Cas obligatoire non exécuté, critère nécessaire encore ouvert ou preuve inadéquate empêchant la conformité du périmètre concerné.
- Cas déclaré non applicable justifié, sans supprimer une obligation : sa vérification reste rattachée au niveau approprié.

**Conséquence :** couverture jugée par obligation et nature de preuve, pas par taux global de réussite ; aucune obligation physique remplacée par une simulation ni scénario dangereux déplacé vers le porteur.

**Choix techniques restant ouverts :** format concret, scénarios détaillés, instrumentation et valeurs encore à justifier.

**Preuves attendues :** couverture traçable de chaque obligation, avec attendus et blocages explicites. Aucune matrice exécutable ni test créé ; aucun essai ni Go mobile humain.

#### Sujet 3 — Déroulement, interruption et remise en état

**Organisation validée par l'utilisateur le 2026-10-30 :** chaque futur essai dispose d'une fiche établie avant exécution : niveau, objectif, configuration figée, prérequis effectivement vérifiés, scénario, moyens d'observation, conditions d'interruption et procédure de remise en état.

| Étape | Règles validées |
|---|---|
| Avant l'essai | Vérifier la porte du niveau et l'organisation solo. Aucun second opérateur présumé, aucun accès improvisé à l'interrupteur ; moyens de protection adaptés au cas effectivement disponibles. Toute modification pertinente impose de réexaminer les prérequis affectés |
| Pendant l'essai | Rester dans le scénario et le domaine autorisés. Écart obligatoire, protection requise indisponible, sortie du domaine ou observation indispensable perdue : interruption du cas et blocage des cas qui dépendent de sa sûreté ou de sa preuve. Demander l'arrêt sans attendre audio, journal ou LLM ; en cas de perte du pilotage, seule la protection indépendante prévue et qualifiée pour l'essai peut être créditée de l'inhibition |
| Après l'essai | Établir l'état réellement observable, sans assimiler demande d'arrêt à immobilisation. Aucune approche des roues, manipulation ou remise sous puissance sur la seule foi d'une commande nulle. L'accès et la remise en état suivent la procédure protégée propre au montage, encore à concevoir |

- Panne volontairement injectée distincte d'un échec du cas : réaction attendue à démontrer et protections propres à l'essai restant effectives. Perte de ces protections ou référence de mesure défaillante interdisant de poursuivre comme si le cas était probant.
- Après anomalie : cause et premier échec conservés, correction puis revalidation des prérequis et nouvelle exécution explicitement décidée.
- Aucun départ différé, réessai humain automatique ou réarmement implicite ; reprise d'une mission exactement selon SH-01/SH-06/SH-07.

**Conséquence :** la campagne ne repose ni sur une intervention improvisée de l'opérateur seul ni sur un compte rendu logiciel supposé disponible après perte du pilotage. Le comportement attendu face à une panne injectée ne dispense pas de protéger l'essai lui-même.

**Choix techniques restant ouverts :** montage du banc, gestes et moyens sûrs d'intervention, critères techniques encore à établir.

**Preuves attendues :** fiche préparée, chronologie réelle, motif d'interruption, état final et remise en état vérifiables. Rien exécuté par cette spécification.

#### Sujet 4 — Dossier de preuves et rapport de campagne

**Organisation validée par l'utilisateur le 2026-10-30 :** dossier par configuration et domaine éprouvés reliant les décisions de passage aux preuves effectives ; aucun rapport d'essai produit pendant cette spécification.

| Partie | Contenu attendu |
|---|---|
| Références | Versions, montage, calibration, paramètres, protections, audio, conditions de sol/charge/batterie et configuration Pi pertinentes |
| Couverture | Obligations et critères avec leur statut exact, cas prévus/exécutés/non exécutés, non-applicabilités justifiées, blocages et dépendances |
| Résultats | Attendus/obtenus, chronologies, moyens de mesure, horloges, références d'injection et incertitudes ; effectifs, distributions utiles, maxima et chaque dépassement obligatoire |
| Provenance | Logiciel SH-09, performances Pi SH-10, audio réel et physique séparés. Aucun intervalle revendiqué si ses bornes ne sont pas observables |
| Historique | Échecs initiaux, corrections, nouvelles configurations, revalidations et restrictions ; aucune répétition favorable effaçant un échec |
| Synthèse vérifiable | Conclusions par propriété, niveau et configuration, preuves manquantes et limites ; jamais une simple mention « tout fonctionne » |

- Référence manquante ou observateur défaillant : conclusion concernée indisponible, jamais favorable par défaut.
- Distinguer ce que le logiciel demande, ce qui est transmis/appliqué, l'inhibition effectivement confirmée et l'immobilisation mesurée.
- Lecture achevée distincte d'audition ; événement écrit distinct de persistance garantie.
- Politique SH-08 strictement identique : données locales minimales, aucun média ou texte brut réel par défaut, aucun export automatique ; clôture explicite puis suppression des traces après rapport produit et vérifié, rapport jusqu'à suppression explicite, sans nouvelle durée calendaire.

**Conséquence :** chaque conclusion doit rester justifiable par ses preuves utiles et leurs limites, y compris après suppression des traces détaillées ; absence de preuve jamais transformée en réussite.

**Choix techniques restant ouverts :** format, instruments et vérification concrète du dossier.

**Preuves attendues :** rapport contrôlé permettant de justifier le verdict après suppression des traces détaillées. Aucun rapport d'essai ni collecte produit aujourd'hui.

#### Sujet 5 — Verdict de recette et décision Go/No-Go

**Règles validées par l'utilisateur le 2026-10-30 :** verdict sur les résultats distinct de la décision d'autoriser un essai précis.

| Verdict de recette | Condition |
|---|---|
| Conforme dans le périmètre déclaré | Toutes ses obligations applicables démontrées, critères nécessaires établis et justifiés, résultats exploitables et rapport vérifié ; aucun échec ni cas obligatoire manquant |
| Non conforme | Au moins un écart observé à une exigence obligatoire ; manques et blocages également rapportés |
| Incomplet / bloqué | Conclusion impossible faute de réalisation, prérequis, critère établi, cas obligatoire ou preuve exploitable. Un écart déjà observé reste explicitement non conforme |

- Caractérisation exploratoire rapportable, sans qualification d'un réglage encore ouvert.
- Go seulement après revue des preuves requises et validation explicite de la porte concernée. Niveau, configuration, domaine, protocole et restrictions identifiés ; décision datée et attribuée à l'utilisateur.
- No-Go si une exigence ou protection nécessaire échoue, reste inconnue/non qualifiée, ou si une preuve obligatoire manque. Motifs et conditions de réexamen consignés.
- Verdict conforme distinct de Go ; Go pour le banc ou les cibles inertes jamais assimilé à un Go humain.
- Restriction sans dispense d'obligation nécessaire. Réduction du domaine exigeant décision explicite et preuves adaptées ; aucune conformité rétroactive du domaine initial.
- Go préalable à un éventuel essai humain distinct de validation de l'usage général ; bilan après cet essai distinct.

**Conséquence actuelle : aucun Go mobile humain**, notamment parce que l'inhibition et la surveillance indépendante restent à concevoir et qualifier et que l'accès sûr à la coupure depuis la position de suivi reste non résolu.

**Choix techniques restant ouverts :** valeurs et qualifications manquantes, support concret de la décision.

**Preuves attendues :** verdict et décision motivés, reliés au dossier, sans seuil inventé ni dérogation implicite. Aucun verdict d'essai produit ni Go donné pendant cette spécification.

#### Sujet 6 — Validité, clôture et passage à la suite

**Règles et prochaine étape validées par l'utilisateur le 2026-10-30 :**

- Preuves et éventuelle autorisation valables uniquement pour la configuration et le domaine documentés. Modification pertinente du logiciel, montage, calibration, paramètres, alimentation, protection, audio ou charge Pi : analyser les propriétés affectées, revalider ce qui est nécessaire et réexaminer l'autorisation avant l'essai concerné. Ni maintien automatique d'un Go ni reprise automatique d'une mission.
- Après échec, historique conservé ; correction, nouvelle série identifiée et régressions pertinentes. Un nouvel essai ne gomme pas l'échec initial.
- Clôture documentaire : six décisions approuvées et consignées, backlog et reprise cohérents. Clôture uniquement de cette étude de spécification.
- Clôture technique SH-11 : réalisations et dépendances effectivement traitées, preuves obligatoires du périmètre convenu produites, écarts résolus, rapport vérifié et décision explicite. Campagne partielle ou bloquée insuffisante. No-Go utile comme décision, mais ni recette réussie ni autorisation ; aucun essai humain imposé pour « terminer ».
- Aucune poursuite automatique vers SH-12, aucun achat, code, test, mesure ou essai déclenché par cette clôture.

**Prochaine étape explicitement retenue :** revenir à la conception détaillée documentaire SH-02 des protections et de l'organisation solo, en lien avec SH-05 : inhibition, surveillance indépendante, coupure/rétablissement et accès sûr depuis la position de suivi. Réutiliser les exigences déjà approuvées sans les rouvrir ; examiner solutions et preuves à prévoir, sujet par sujet, sans installation, achat, manipulation matérielle ni qualification. Ne pas commencer cette étape dans la présente session.

**Conséquence :** ne pas préparer une campagne en présumant disponibles des protections encore à concevoir ou un accès non résolu. La spécification SH-11 ne satisfait aucune dépendance technique ni porte d'entrée.

**Choix techniques restant ouverts :** solutions concrètes et analyse d'impact des futurs changements.

**Preuves attendues ultérieurement :** revalidations nécessaires, dossier final et décision motivée. Aujourd'hui : uniquement la spécification, aucun Go mobile humain.

#### SH-11 — Statut et travaux techniques restants

**Six sujets de spécification validés avec l'utilisateur le 2026-10-30 ; étude documentaire terminée. Conception détaillée, réalisations et exécution de la recette à faire.** Ticket technique et dépendances SH-09/SH-10 non clôturés ; préconditions physiques SH-02/SH-05 effectivement requises selon le niveau.

| Travail restant | Livrable / preuve attendu |
|---|---|
| Établir les portes réelles | Configuration, réalisations et résultats disponibles ; protection du banc et organisation solo vérifiées, protections et accès à la coupure qualifiés selon le niveau ; aucune dépendance satisfaite par documentation seule |
| Décliner la couverture | Obligations/cas/critères issus des décisions approuvées, statut exact et frontières, niveau et nature de preuve, non-applicabilités justifiées et blocages visibles |
| Préparer les protocoles protégés | Fiches préalables, moyens d'observation et d'interruption, protection propre aux injections, remise en état et nouvelle exécution explicitement décidée |
| Réaliser les campagnes autorisées | SH-09 logiciel, SH-10 Pi, optique/audio réels et propriétés physiques distincts ; banc puis cibles inertes ; éventuel porteur seulement après qualifications et Go explicite |
| Produire et vérifier le dossier | Références, attendus/obtenus, chronologies, incertitudes, maxima/dépassements, échecs et historique ; rapport probant avec politique SH-08 inchangée |
| Statuer et maintenir la validité | Verdict limité au périmètre démontré, Go/No-Go distinct et motivé ; revalidation après changements, aucune clôture sur campagne partielle ou sur approbation documentaire |

Aucun code ni test créé ; aucun test, mesure, acquisition matérielle, charge, installation, manipulation matérielle ou essai moteur exécuté pendant cette spécification. Six décisions détaillées de chacun des tickets SH-05 à SH-10 préservées intégralement. Inhibition et surveillance indépendante restent à concevoir et qualifier ; accès sûr à l'interrupteur embarqué depuis la position de suivi en solo non résolu. Aucun Go mobile humain. Prochaine étape documentaire SH-02 retenue au sujet 6 ; réalisée depuis, le 2026-10-30, en conception fonctionnelle (voir SH-02 en section 4), sans clôture technique.

### Lot A — Réalisation isolée du 2026-10-30

Autorisation : demande explicite de réalisation isolée dans la session courante.
Les décisions documentaires ci-dessus restent historiques et intégralement applicables.
Référence propre avant modification : `a5c397b483fc0eda0938e5d444ecf1a3968430f9`,
aucun changement local préexistant constaté.

- A1/A2, choix dérivés validés automatiquement : ports logiques typés, L2 dans
  `RobotController`, façade de mission liée à des identifiants immuables ; pas
  de délégation ni d'accès public au driver dans le chemin protégé. Directions,
  commandes temporisées, vitesse et restauration passent par le même garde.
- A3/A4, choix dérivés validés automatiquement : horloge monotone injectée,
  retour P5 daté à sa source et transition datée ; observation inhibée puis
  transition armée postérieure au verrou exigées, sans ordre numérique des jetons.
  Nouvelle demande seulement après observation de cet armement : celle qui
  déclenche sa première observation est refusée, jamais conservée. Admission
  humaine sans échéance explicite refusée ; échéance inchangée à la reprise.
  Les paramètres de campagne sont fictifs, sans valeur de réglage réel.
- Présence historique omise = absente ; valeur explicite invalide ou ports
  manquants = erreur de configuration. Présence, qualification et environnement
  synthétique restent distincts. Aucune option live d'autorisation humaine.
- A1 réalisé : P5 en lecture seule et préconditions humaines invalides par
  défaut ; aucun port de réarmement. Les faits nominaux qualifiés des fixtures
  sont explicitement synthétiques, sans qualification physique.
- A2 réalisé : runtime commun raccordé à l'exécuteur, au contrôleur de langage
  et au garde L2. Driver et comportement balle inchangés. Refus humain avant
  routage objet, filtrage d'étape malformée et expansion de plan ; aucune
  perception marqueur, loi SH-06 ou intégration naturelle complète SH-07.
- A3 réalisé, choix dérivés validés automatiquement : lancement `-I -S`,
  gardes avant imports/collecte, plugins/conftest automatiques exclus, paquets
  locaux ajoutés explicitement après les gardes sans exécuter les `.pth`.
  Aucune installation. Borne externe 120 s et synchronisations 2 s uniquement
  pour borner le harnais, sans qualification de délai Pi.
- A4 réalisé, choix dérivés validés automatiquement : garde courte d'émission
  distincte du verrou d'évaluation ; stop/P1 atteignent le double sans attendre
  une précondition bloquée. Génération de contrôleur plus identifiants
  mission/contexte/armement ; postériorité vérifiée par dates/observations,
  aucun ordre numérique des jetons. Preuve uniquement après cycle évalué,
  boucle synchrone au repos, aucun renouvellement par listener pour worker
  bloqué. Réservation après worker terminé, état utile et échéance conservés
  à la reprise, aucun réessai humain ou demande différée.
- A5 effectivement démontré : **121 cas du lot réussis**, oracles A-O1 à A-O12,
  intégrations et replays recalculés ; **214 tests historiques réussis sur la
  référence puis sur la version livrée**, sept cas de préchauffage hors sélection.
  Contrat indépendant complémentaire : quatre tests réussis sur chaque version.
  Toutes campagnes finales : zéro accès interdit observé, zéro thread résiduel ;
  trois sondes synthétiques des gardes refusées sans opération réelle.
- A6 : **conforme dans le seul périmètre logiciel isolé déclaré**, rapport
  [SH-09 vérifié](08_lot_a_rapport_sh09.md), erreurs intermédiaires et corrections
  conservées, aucune attente historique modifiée pour masquer une régression.
  Les critères de fin du lot ne clôturent pas SH-05/SH-09 globalement.

Non exécutés : suite globale, intégration LLM/modèles/serveur, matériel,
Pi/charge, audio réel et toute recette physique. Les fichiers/configurations
temporaires synthétiques sont nettoyés ; aucune collecte réelle ni export.
Politique SH-08 inchangée, pas de clôture utilisateur de campagne présumée.
Arrêt demandé, tentative de zéro, zéro reçu par double et inhibition attestée
par double P5 restent distincts ; aucune immobilisation physique mesurée.

Blocages hors lot maintenus : P2/P3/P4/P5/P6 à réaliser/qualifier, famille P6 non
choisie, accès sûr solo non démontré, budget/délais et réglages réels ouverts,
perception, audio réel, SH-10 et recette physique. Ni proximité ni audio ne
démontrent l'accès. **Suivi humain moteur réel toujours refusé ; aucun Go mobile
humain.** Prochaine étape seulement proposée : revue/validation explicite du
rapport puis choix de la suite, sans la commencer.

## 5. Critères mesurables proposés

Ces nombres sont des **objectifs de recette initiaux**, pas des capacités constatées ni des garanties de sécurité. Les paramètres d'usage de l'étape 4 de SH-01 sont validés comme cibles ; leur faisabilité et les autres seuils techniques restent à qualifier, notamment en SH-02, avant programmation des limites.

| Critère | Objectif initial et méthode |
|---|---|
| Domaine visuel | Marqueur exploitable entre 1 et 2,5 m, angles de lacet testés jusqu'à ±30°, éclairage consigné ; dimensions définitives après essai |
| Distance de confort | Consigne 1,5 m de dégagement nominal pare-chocs–porteur ; 95 % des mesures de référence dans ±0,3 m en suivi stabilisé |
| Distance demandable | 1,2 à 2 m dans la plage qualifiée ; limites incluses à tester ; hors plage : refus explicite, sans correction silencieuse |
| Distance minimale d'essai | Seuil provisoire à confirmer en SH-02 : jamais moins de 0,8 m du porteur dans le protocole ; arrêt/restriction du domaine dès violation ; ce n'est pas une consigne demandable |
| Vitesse | Plafond physique initial 0,15 m/s mesuré au sol ; un PWM de 0,5 ne constitue pas une vitesse en m/s |
| Durée de session | 60 s par défaut, demande de 10 à 300 s après qualification ; hors plage : refus explicite. Chronomètre à l'activation après acquisition, maintien et suspensions inclus ; ni prolongation automatique ni remise à zéro à la reprise |
| Acquisition | Au moins 3 trames distinctes cohérentes, dernière capture âgée de 200 ms maximum |
| Vision | Au moins 10 observations nouvelles/s et latence capture→observation p95 ≤ 150 ms sous charge représentative |
| Péremption | Observation âgée de plus de 200 ms : interdiction d'avance, arrêt demandé sans attendre le budget de recherche objet |
| Arrêt logiciel | Demande d'arrêt → consigne moteur nulle ≤ 100 ms sur tous les essais ; perte de visibilité → consigne nulle ≤ 300 ms |
| Arrêt physique | Mesurer délai et distance jusqu'à immobilisation sur sol/batterie/charge retenus ; seuils arrêtés en SH-02 avant roulage près d'une personne |
| Identité | Aucun basculement de cible dans 20 essais avec marqueurs concurrents ; doublon de l'identifiant attendu → arrêt |
| Trajet | 5 parcours consécutifs de 60 s, ligne droite puis virages doux, sans contact, sans recul et sans intervention hors scénario |
| Régression | Scénarios balle, primitives, stop et traces existants inchangés ; règles du suivi humain sélectionnées par intention dans le runtime commun, sans mode utilisateur supplémentaire |

Les moyennes et p95 servent à qualifier les performances, **pas à excuser un dépassement de sécurité**. Rapporter aussi maxima, rejets et nombre d'essais ; une campagne réussie ne constitue pas une certification.

Budget conservateur à vérifier : distance de garde ≥ vitesse maximale × délai maximal de détection/réaction + distance de freinage mesurée + incertitude + marge. Un seuil frontal fixe de 20 cm, présent dans le driver, ne valide pas ce budget à lui seul.

Si le Pi ne tient pas les délais : réduire vitesse/résolution ou éloigner l'inférence LLM de la boucle critique, puis refaire les mesures. Si la couverture obstacle, le freinage ou l'arrêt indépendant restent insuffisants, pas de Go près d'un humain.

## 6. Nouveau backlog

SH-01 est **validé et terminé pour le cadrage**, selon le tableau de la section 1 ; SH-02 est **en cours : exigences et protocole validés, conception fonctionnelle détaillée des protections et de l'organisation solo validée en six sujets ; conception électrique, réalisation et qualification restantes** ; SH-03 est **spécifié : exigences et recette validées, choix techniques et qualification à faire**, sans clôture de sa dépendance à SH-02 ; SH-04 est **spécifié : contrat/cycle/recette validés, conception détaillée et vérification à faire**, sous réserve des résultats SH-03 ; SH-05 est **spécifié : six sujets d'exigences et de recette validés en section 4, conception détaillée, réalisation et qualification à faire** ; SH-06 est **spécifié : six sujets d'exigences et de recette validés en section 4, conception détaillée, réalisation et qualification à faire** ; SH-07 est **spécifié : six sujets d'exigences et de recette validés en section 4, conception détaillée, réalisation et qualification à faire** ; SH-08 est **spécifié : six sujets et orientations validés en section 4, conception détaillée, réalisation et qualification à faire** ; SH-09 est **spécifié : six sujets de validation hors matériel et de non-régression approuvés en section 4, conception détaillée, réalisation et exécution de recette à faire** ; SH-10 est **spécifié : six sujets de mesure intégrée sur Pi approuvés en section 4, conception détaillée, réalisation et mesures à faire** ; SH-11 est **spécifié : six sujets de recette progressive et Go/No-Go validés en section 4, conception détaillée, réalisations et recette à faire** ; SH-12 est **à faire**. Cela ne vaut ni implémentation ni qualification matérielle. P0 = nécessaire au MVP ; P1 = après MVP. Les tailles S/M/L sont relatives, pas des engagements calendaires ; chiffrer après les essais de faisabilité.

**Avancement transversal du lot A :** cadrage et réalisation isolée terminés dans la frontière A2 ; décisions dérivées consignées en section 4. Preuves effectives et limites dans le [rapport SH-09 du lot A](08_lot_a_rapport_sh09.md). Sous-ensemble logiciel SH-02/SH-05/SH-09 uniquement ; aucune qualification physique et aucun ticket global ou dépendance matérielle clôturé. SH-03 à SH-11 conservent leurs décisions et travaux restants détaillés.

| ID | Priorité / taille | Ticket et livrable | Dépendances | Critères d'acceptation |
|---|---|---|---|---|
| SH-01 | P0 / S | Valider le contrat d'usage et les paramètres | Aucune | Périmètre, association « moi », reprise explicite, feedback, distance/durée/vitesse et scénarios hors domaine approuvés ; capacité du même assistant sans mode à sélectionner ; aucune assimilation implicite à la balle |
| SH-02 | P0 / M | Qualifier le matériel et le domaine de sécurité | SH-01 | Inventaire réel, champ caméra, gabarit, protection obstacle, arrêt physique, stratégie watchdog, budget d'arrêt et protocole protégés documentés ; sortie audio, contrôle de disponibilité et intelligibilité qualifiés ; achats éventuels identifiés |
| SH-03 | P0 / M | Valider le marqueur et la distance, moteurs déconnectés | SH-01, SH-02 | Selon la spécification de section 4 : choix motivés, calibration/support reproductibles ; distances d'usage 1,2/1,5/2 m, caractérisation à 1/2,5 m ; par condition nominale ≥100 images nouvelles, acceptation ≥95 %, erreur de dégagement ≤20 cm pour ≥95 % des observations acceptées ; maxima, biais, pertes et ambiguïtés consignés ; référence indépendante et incertitude ; aucune formule balle réutilisée |
| SH-04 | P0 / M | Définir les observations et l'association de session | SH-03 | Contrat section 4 : identité famille/dictionnaire + ID verrouillée, observations typées et statuts explicites, fraîcheur de capture/trames distinctes, contexte isolé, acquisitions ≤10 s, cycle et nettoyage ; recette déterministe des frontières/défauts et régression balle/stop, sans mode supplémentaire |
| SH-05 | P0 / L | Implémenter les garde-fous du suivi humain | SH-02, SH-04 | Selon les six sujets validés de section 4 : préconditions de départ et de chaque mouvement, arbitrage sans défaut masqué, vitesse/mouvements bornés, aucun recul/balayage, inhibition indépendante et réarmement, propagation au runtime sans relance, traces et recette ; injection de panne, y compris arrêt/blocage du pilotage et indisponibilité du Pi, validée sur banc protégé ; aucune clôture sur la seule spécification |
| SH-06 | P0 / M | Développer le comportement de suivi déterministe | SH-04, SH-05 | Selon les six sujets validés de section 4 : états/causes/transitions testés par horloge simulée ; approche/maintien avec hystérésis, consigne/précision/minimum de sécurité distincts ; orientation et avance bornées et qualifiées, aucun mouvement interdit ; redépart normal distinct de reprise explicite, échéance inchangée ; commandes obsolètes invalidées, interruptions et fins explicites au runtime ; recette déterministe et régression balle/stop ; aucune clôture sur la seule spécification |
| SH-07 | P0 / M | Relier la commande naturelle au comportement | SH-01, SH-06 | Selon les six sujets validés de section 4 : commandes humaines autonomes et reprise/stop locaux, `follow_person` distinct de balle sans `yellow` par défaut ; paramètres/alias/unités et schéma stricts sans réparation silencieuse ; prompt, lexique, parser, validator, gardes, planner, registre, budgets et assemblage raccordés dans le runtime existant ; perception/caméra partagées, admission unique même en suspension ; échéance préservée sans réessai automatique ; recette d'intégration sans moteurs et non-régression balle/stop ; aucune clôture sur la seule spécification |
| SH-08 | P0 / S | Rendre le suivi observable et compréhensible | SH-01, SH-06 | Selon les six sujets validés de section 4 : catalogue fermé et synthèse locale, paramètres retenus et temps restant exacts ; audio bidirectionnel et Jabra candidat à qualifier, stop pendant annonce sans auto-commande ; priorité/invalidation/budgets qualifiés sans retarder l'arrêt ; JSONL corrélé et niveaux de preuve distincts, journal obligatoire indisponible : refus ou arrêt/suspension ; collecte minimale locale sans médias/textes bruts par défaut, conservation par campagne et suppression vérifiable ; recette simulée distincte d'audio réel et de qualification physique ; aucune clôture sur la seule spécification |
| SH-09 | P0 / M | Valider hors roulage et préserver l'existant | SH-05, SH-06, SH-07, SH-08 | Selon les six sujets validés de section 4 : tests unitaires, intégration simulée et replay recalculant les décisions, sans matériel/réseau ni découverte automatique ; exigences/scénarios/attendus indépendants, frontières et concurrence ; composants logiciels réels à périphériques simulés, même runtime et non-régression balle/primitives/stop ; commandes d'arrêt observées selon les moyens disponibles, sans trace ni arrêt physique inventés ; rapports/provenances et données SH-08, verdict conforme/non conforme/incomplet justifié ; fonctions/réglages/preuves manquants bloquants, aucune clôture sur la seule spécification |
| SH-10 | P0 / M | Mesurer le système intégré sur Pi | SH-03, SH-07, SH-08 | Selon les six sujets validés de section 4 : prérequis réels et première étape sans propulsion isolée ; charge intégrée vision/audio/LLM/journal et concurrence autorisée, conditions reproductibles ; débit/âge depuis capture, intervalles/horloges, CPU/RAM/température, incertitudes et maxima/dépassements ; dégradations bornées, simulation/réel distincts ; dossier vérifié, réglages identifiés et échecs conservés, données SH-08 ; verdict limité au périmètre démontré et blocages explicites, aucune qualification physique ni clôture sur la seule spécification |
| SH-11 | P0 / L | Effectuer la recette progressive et décider Go/No-Go | SH-09, SH-10 | Selon les six sujets validés de section 4 : portes d'entrée et preuves distinctes sans propulsion, banc protégé, cibles inertes, puis éventuel porteur après qualifications et Go explicite ; préconditions SH-02/SH-05 effectivement vérifiées selon le niveau, organisation solo et accès sûr à la coupure démontrés ; cas/critères des sections 5/7 et matrices approuvées rattachés aux niveaux pertinents avec leur statut exact, sans seuil inventé ni obligation supprimée ; préparation/interruption/remise en état protégées ; dossier vérifié et données SH-08 ; verdict de recette distinct de Go/No-Go daté et attribué, limites et décision signées ; changements réévalués et propriétés affectées revalidées. Conception détaillée, réalisations et recette à faire ; aucune dépendance clôturée par la spécification ni Go mobile humain |
| SH-12 | P1 / L | Étudier le suivi naturel et la navigation avancée | SH-11 | Étude séparée sans marqueur : sélection de personne, identités croisées, occultation, profondeur/capteurs, besoin odométrie/contournement et nouveau domaine de sécurité ; aucun élargissement implicite du MVP |

SH-02 et SH-03 sont des portes de décision : si la sécurité ou la perception échouent, réviser matériel/domaine avant de poursuivre le contrôle mobile. SH-07 et SH-08 peuvent avancer en parallèle après leurs prérequis ; ne pas attendre la recette pour ajouter les traces.

### Définition de terminé commune

- Préconditions, erreurs et motifs d'arrêt explicites ; aucun défaut transformé en succès normal.
- Tests déterministes puis preuve matérielle pour toute propriété physique.
- Documentation/configuration et procédure opérateur alignées ; paramètres bornés.
- Aucun changement des comportements objet existants ; les règles spécifiques au suivi humain sont déclenchées par l'intention, sans mode utilisateur supplémentaire.
- Aucun mouvement réel autorisé par le seul fait que les tests Mac passent.

## 7. Matrice de recette minimale

| Famille | Scénarios obligatoires | Résultat attendu |
|---|---|---|
| Nominal | Départ arrêté, avance lente, arrêt du porteur, virages doux, fin de durée | Bonne cible, distance/vitesse dans les limites, fin immobile |
| Proximité | Porteur qui revient vers le robot, brusque arrêt devant lui | Arrêt sans contact, aucun recul |
| Visibilité | Marqueur caché/retourné, flou, faible lumière, sortie du champ | Arrêt dans le budget, pas de recherche motorisée |
| Identité | Autre ID, deux cibles, doublon du bon ID, transfert du marqueur | Autre ID ignoré, ambiguïté arrêtée ; limite du transfert explicitement démontrée |
| Fraîcheur | Caméra figée sur une image valide, lenteur, trames répétées | Aucune confiance artificielle ; arrêt sur âge de capture |
| Distance | Pose oblique, estimation absente/incohérente, montage déplacé | Avance interdite, recalibration requise si montage changé |
| Obstacles | Obstacle frontal et obstacle dans le volume de rotation | Arrêt ; si non détecté, essai en échec et matériel/domaine à revoir |
| Infrastructure | Capteur absent/timeout, caméra débranchée, LLM indisponible/en charge, processus bloqué/tué | Refus ou arrêt explicite ; arrêt indépendant vérifié pour perte de processus |
| Commandes | Stop vocal sous bruit/moteurs actifs, stop texte, annulation, reprise | Arrêt prioritaire sans LLM, reprise explicite après acquisition ; coupe-circuit disponible si voix inaudible |
| Assistant commun | Dans le même runtime : mission balle terminée, puis « suis-moi », puis nouvelle mission balle après fin du suivi ; nouvelle demande pendant une mission | Aucun changement de mode ni redémarrage ; bonne intention et bonne perception ; aucun pilote matériel ou mission motrice concurrente ; politique existante des demandes pendant une mission préservée |
| Retour vocal | Annonces dos au robot, stop pendant une annonce, audio absent au démarrage ou en panne détectée en session | Messages intelligibles et cohérents avec l'état/temps restant, aucune auto-commande ; arrêt jamais retardé ; refus sans audio initial, suspension sur panne détectée |
| Endurance | Sessions répétées, batterie et température variées dans le domaine retenu | Pas de dépassement des limites ni reprise spontanée après défaut |

Pour chaque essai : version logicielle, configuration, matériel, lumière/sol, référence de mesure, chronologie, distances, latences maximales et verdict. Les événements injectés doivent avoir un horodatage de référence indépendant de la seule détection logicielle. Tests d'obstacle d'abord avec cibles inertes, pas avec les jambes d'une personne.

## 8. Ordre de réalisation et décisions restantes

1. **Cadrage :** SH-01 terminé ; poursuivre avec SH-02 pour qualifier le matériel, la sortie audio et la sécurité au regard du contrat d'usage validé.
2. **Faisabilité immobile :** SH-03 puis SH-04 ; choisir taille/dictionnaire/montage du marqueur et démontrer la distance.
3. **Sécurité et comportement :** SH-05 puis SH-06 ; preuves sur banc avant proximité humaine.
4. **Intégration :** SH-07/SH-08, puis SH-09/SH-10.
5. **Recette :** SH-11 ; SH-12 reste une évolution distincte.

Progression au 2026-10-30 : cadres SH-02 à SH-11 approuvés, qualifications et réalisations hors lot ouvertes. Conception documentaire SH-02 en six sujets et cadrage A1–A6 préservés en section 4. Réalisation isolée du lot A désormais effectuée sur autorisation explicite, avec résultats et historique dans le [rapport SH-09 limité au lot](08_lot_a_rapport_sh09.md). Aucune autorisation de campagne matérielle ni qualification déduite ; SH-05/SH-09 globalement non clôturés.

Le choix « marqueur accepté » et les cinq étapes de SH-01 sont acquis : périmètre d'usage, association fixe, arrêts/reprises, paramètres cibles et retour vocal. Les choix techniques et autres seuils proposés ne sont pas validés par cette clôture du cadrage ; la qualification physique reste nécessaire. Aucun achat, dépendance, modification du code ou essai moteur n'est autorisé par ce document seul.

## 9. Reprise — lot A logiciel isolé livré et vérifié, aucune activation humaine réelle

Point de reprise au 2026-10-30 : **lot A réalisé et vérifié exclusivement en logiciel isolé**, sur demande explicite de l'utilisateur, après constat d'un arbre propre à la référence indiquée au rapport. Les six sujets SH-02 et les six décisions détaillées de chacun des tickets SH-05 à SH-11 restent intégralement préservés en section 4, comparaison effectuée avec la référence. Aucun composant, montage électrique, famille P6 ou réglage réel choisi ; conception électrique, réalisation/qualification P2–P6 et accès sûr solo toujours ouverts. Aucune spécification ou double ne satisfait une dépendance physique. Aucun accès matériel/réseau, acquisition, charge Pi, achat, installation ou essai moteur exécuté. Aucun Go mobile humain.

### Lot A cadré — décisions et bilan à reprendre

L'étape A explicitement retenue est terminée pour le seul cadrage documentaire. Lire les six sujets détaillés « Lot A — Cadrage documentaire du premier lot logiciel isolé » en section 4, sans remplacer les décisions sources SH-02 à SH-11 par ce résumé :

1. **A1 — Périmètre :** P5/L2, preuve après cycle réellement évalué, demande d'inhibition à sens unique, priorité 1, armement postérieur et déclaration de présence. Validé automatiquement par délégation ; aucune protection réalisée.
2. **A2 — Frontière :** L2 dans `RobotController`, admission/verrous dans le runtime commun ; driver et comportement balle préservés, missions humaines synthétiques et garde de refus réel, sans réalisation complète SH-06/SH-07. **Validé explicitement par l'utilisateur le 2026-10-30.**
3. **A3 — Doubles :** P5, sortie de preuve, demande d'inhibition et horloge/attentes explicites ; périphériques complémentaires factices, zéro matériel/réseau y compris imports/découverte ; présence distincte d'armement/qualification. Validé automatiquement par délégation.
4. **A4 — Cycles/verrous :** évaluation même au repos, aucune preuve autonome ; contexte/commandes obsolètes invalidés, priorité 1 propagée sans succès apparent ni réessai, postériorité d'armement démontrée ; réservation/échéance et stop/reprise locaux préservés. Validé automatiquement par délégation.
5. **A5 — Preuves :** douze oracles A-O1 à A-O12 indépendants, chaîne réelle du socle et replay recalculant les décisions ; non-régression balle/primitives/stop absente puis présente. Cadrage validé par délégation, désormais exécuté : 121 cas du lot et 214 tests historiques ciblés réussis, référence et compléments explicités au rapport.
6. **A6 — Fin :** réalisation et résultats effectifs sans obligation manquante, isolation et non-régression démontrées, rapport vérifié ; verdict limité au lot, aucune qualification physique/Pi/audio ni clôture globale SH-05/SH-09. Validé automatiquement par délégation.

**Réalisé et démontré :** ports P5/L2, identifiants et invalidations, cycles complets dont repos, demande d'inhibition, admission/verrous, réservation/contexte/échéance, stop/reprise locaux synthétiques, refus humain réel, non-régression ciblée et rapport vérifié. **Non exécuté :** suite globale, sept tests de préchauffage, intégration LLM réelle, matériel, audio/Pi et recette physique. **Bloqué hors lot :** P2–P6 réels, famille/ergonomie P6 et accès sûr solo, budget/délais/qualification des réglages, perception et capacités humaines complètes. Aucune dépendance technique n'est satisfaite par documentation ou doubles. P5 sans adaptateur réel = pas d'autorisation ; suivi humain moteur toujours refusé sur le robot. Aucun Go mobile humain.

### Conception SH-02 des protections validée — détails à préserver en section 4

1. **Architecture fonctionnelle :** P1 coupure manuelle, P2 inhibition indépendante verrouillée inhibée par défaut, P3 surveillance indépendante hors Pi, P4 réarmement manuel sans mouvement, P5 retour d'état en lecture seule (inconnu = inhibé), L1 supervision logicielle, L2 point unique d'émission moteur, O quatre niveaux de preuve (arrêt demandé, commande nulle, inhibition confirmée, immobilisation physique mesurée), H procédure opérateur. Arrêts/démarrages courants à la voix ou en ligne de commande, arrêts physiques exceptionnels sans réduction d'exigence. Ne pas rouvrir.
2. **Inhibition et surveillance :** états `inhibé-verrouillé` avec cause / `armé-à-l'arrêt` ; preuve de fonctionnement émise par L2 après chaque cycle réellement évalué, changeante, figée = absente ; délai P3 issu du budget d'arrêt ; demande d'inhibition logicielle à sens unique réservée à la priorité 1 ; arrêts courants sans réarmement matériel ; P2 non contournable par les GPIO du Pi. Ne pas rouvrir.
3. **Séquences sans départ spontané :** mise sous tension inhibée, demande d'inhibition au démarrage du programme, coupure/rétablissement/perte de pilotage verrouillés, inhibition inattendue en mission = priorité 1, suspension ordinaire inchangée, toute transition d'armement invalide les commandes antérieures. Ne pas rouvrir.
4. **Accès solo :** arrêt opérateur porté P6, actionnable depuis la position de suivi, agissant directement sur P2, à sécurité positive (perte de liaison = priorité 1), sans réarmement ; P1 réservé à la préparation/remise en état ; famille non choisie ; aucun essai avec porteur sans P6 qualifié. Ne pas rouvrir.
5. **Contrat logiciel :** ports P5, preuve de cycle, demande d'inhibition, L2 avec identifiants mission/contexte/armement ; autorisation recalculée à chaque cycle ; nouvelle admission après priorité 1 seulement avec armement postérieur ; premier lot sans adaptateur P5 réel, donc suivi humain moteur refusé sur le robot ; balle inchangée tant que la protection est déclarée absente, puis respect de P5 sans autre changement. Ne pas rouvrir.
6. **Organisation solo et bilan :** séquence de préparation au robot puis position de suivi ; interfaces suffisantes pour proposer un premier lot logiciel isolé avec doubles explicites ; blocages matériels, temporels, audio, Pi et perception maintenus. Ne pas rouvrir.

### État à préserver

- SH-01 : contrat d'usage validé.
- SH-02 : exigences et protocole validés ; conception fonctionnelle des protections et de l'organisation solo validée (P6 retenu comme principe d'accès solo, famille non choisie) ; conception électrique, réalisation, accès effectif à la coupure en solo et qualification non terminés.
- SH-03 : exigences et recette optique validées ; montage, taille, dictionnaire/ID et performances à déterminer après essais.
- SH-04 : contrat de perception, cycle de mission et recette validés ; conception détaillée, implémentation et vérification à faire.
- SH-05 : six sujets d'exigences et de recette validés, détails et travaux techniques restants en section 4 ; conception, réalisation et qualification ouvertes.
- SH-06 : six sujets d'exigences et de recette validés, décisions détaillées et travaux techniques restants en section 4. Réutiliser les états et règles acquis sans les rouvrir ; conception, réalisation et qualification ouvertes, aucune clôture technique.
- SH-07 : six sujets d'exigences et de recette validés, décisions détaillées et travaux techniques restants en section 4 ; conception, réalisation et qualification ouvertes, dépendances SH-01/SH-06 inchangées.
- SH-08 : six sujets et orientations validés en section 4, travaux techniques restants explicités ; conception détaillée, réalisation et qualification à faire. Dépendances SH-01/SH-06 inchangées, aucune clôture technique.
- SH-09 : six sujets validés en section 4, travaux techniques restants explicités ; conception détaillée, réalisation et exécution de recette à faire. Dépendances SH-05/SH-06/SH-07/SH-08 inchangées, aucune clôture technique ni preuve physique.
- SH-10 : six sujets de spécification validés et détaillés en section 4 ; conception détaillée, réalisation et mesures à faire. Dépendances SH-03/SH-07/SH-08 inchangées et non satisfaites par leurs seules spécifications.
- SH-11 : six sujets spécifiés et validés, décisions détaillées et travaux techniques restants en section 4. Conception détaillée, réalisations et recette à faire ; dépendances SH-09/SH-10 inchangées et non satisfaites par leurs seules spécifications. Préconditions physiques SH-02/SH-05 toujours requises selon le niveau d'essai. Aucun Go mobile humain.
- Aucun code, achat, acquisition caméra ou essai moteur effectué dans cette étude ; aucun Go mobile humain.
- Un seul assistant/runtime : « suis-moi » et « cherche la balle jaune » sont des commandes naturelles, sans mode supplémentaire. « Rapproche-toi des autres robots » reste un besoin futur hors MVP.
- Les arrêts logiciels sur obstacle et commande vocale sont déjà disponibles et déclarés testés : les réutiliser, pas les présenter comme manquants.

### Sujets SH-05 validés — détails à préserver en section 4

1. Préconditions de départ et de chaque mouvement : cible/contexte valides, fraîcheur, distance, protection obstacle, audio, configuration qualifiée et autorisation motrice. **Validé ; décision détaillée en section 4.**
2. Priorité et arbitrage des événements simultanés : urgence, coupure, perte de contrôle, obstacle, perception/audio invalides, échéance et maintien normal ; aucun défaut masqué par un succès. **Validé ; décision détaillée en section 4.**
3. Actions autorisées : absence de recul et de balayage, bornage de vitesse/rotation/accélération selon qualification, protection du volume balayé. **Validé ; décision détaillée en section 4.**
4. Répartition entre supervision logicielle et inhibition indépendante ; verrouillage, réarmement et non-redémarrage au retour d'énergie, du programme ou des périphériques. **Validé ; décision détaillée en section 4.**
5. Propagation des interruptions jusqu'au runtime : suspension ou fin selon les décisions acquises, aucune relance automatique ou étape suivante après défaut ; conservation de l'échéance. **Validé ; décision détaillée en section 4.**
6. Traces, motifs, annonces non bloquantes, tests déterministes et injections de pannes sur banc protégé ; preuves nécessaires avant Go. **Validé ; décision détaillée en section 4.**

Ne pas transformer les objectifs provisoires en garanties matérielles. Les dispositifs d'inhibition et de surveillance indépendante ne sont pas choisis ni déclarés installés ; l'interrupteur embarqué prévu n'a pas d'accessibilité qualifiée depuis la position de suivi.

### Sujets SH-06 validés — détails à préserver en section 4

1. États et transitions du comportement : acquisition, suivi, maintien, suspension et fin ; distinguer état, motif et action de reprise. Cycle SH-04 et priorités SH-05 réutilisés. **Validé ; décision détaillée en section 4.**
2. Approche et maintien de la distance demandée : zone de confort, ralentissement et immobilisation, seuils/hystérésis à justifier ; distinguer consigne, objectif de précision et distance minimale de sécurité. **Validé ; décision détaillée en section 4.**
3. Correction d'orientation et coordination avec l'avance : cible exploitable et dégagement valide, corrections bornées et volume balayé protégé ; aucune autorisation implicite de rotation sur place, aucun recul, balayage ou contournement. **Validé ; décision détaillée en section 4.**
4. Redépart normal lorsque le porteur s'éloigne et reprise explicite après interruption : ne pas les confondre ; même cible, nouvelle acquisition lorsque requise, préconditions et échéance initiale conservées. **Validé ; décision détaillée en section 4.**
5. Commandes, interruptions et sortie du comportement : arrêt prioritaire, aucune commande obsolète, aucun défaut transformé en succès ni relance automatique ; propagation au runtime commun sans régression balle/stop. **Validé ; décision détaillée en section 4.**
6. Recette déterministe par horloge et observations simulées : états/transitions, frontières de distance/orientation/temps, défauts simultanés et absence de mouvement interdit ; distinguer preuves logicielles et qualification physique ultérieure. **Validé ; décision détaillée en section 4.**

Les paramètres d'usage SH-01 restent acquis : dégagement demandé par défaut 1,5 m, plage demandable 1,2 à 2 m dans le domaine qualifié, objectif stabilisé ±30 cm, plafond physique initial 0,15 m/s, durée par défaut 60 s et plage 10 à 300 s après qualification. Ils ne déterminent pas à eux seuls les seuils de commande, l'hystérésis, le freinage ou les bornes de rotation. Ne pas inventer ces valeurs ni convertir le seuil provisoire de 0,8 m en garantie.

### Sujets SH-07 validés — détails à préserver en section 4

1. **Contrat des commandes et distinction des capacités :** « suis-moi » désigne le porteur du marqueur configuré, pas une balle ; départ autonome, reprise locale explicite et arrêt selon les cycles acquis ; ambiguïtés humaines refusées, aucun enchaînement moteur humain MVP ni permission différée. Aucun identifiant inventé par le LLM, aucune cible `yellow` par défaut. **Validé ; décision détaillée en section 4.**
2. **Paramètres, valeurs par défaut et validation :** extraction de distance/durée, unités, normalisation et alias ; respect des paramètres SH-01 dans le domaine qualifié ; demandes invalides ou hors plage refusées explicitement, sans correction silencieuse ni relèvement vocal du plafond. Une reprise ne modifie pas les paramètres de la session. **Validé ; décision détaillée en section 4.**
3. **Contrat d'intention et chaîne de validation :** `follow_person`, schéma fermé et demande complète contrôlée sans nettoyage réparateur ; reprise/stop locaux, replis techniques strictement validés ; inspecter les surfaces existantes avant adaptation. **Validé ; décision détaillée en section 4.**
4. **Raccordement au runtime commun :** planner, registre, assemblage matériel et sélection automatique de perception ; caméra et moteurs partagés sans pilotes concurrents ; admission unique et mission réservée pendant suspension, reprise sans reset ni contournement de verrouillage. **Validé ; décision détaillée en section 4.**
5. **Budgets et cycle de mission :** budgets techniques distincts de l'échéance monotone unique ; attentes bornées, acquisition/reprise selon SH-04, aucun reset, prolongement ou réessai automatique d'exécution humaine ; défaut technique jamais masqué en fin normale. **Validé ; décision détaillée en section 4.**
6. **Recette d'intégration sans moteurs :** formulations nominales/ambiguës/invalides, valeurs par défaut et frontières, départ/reprise/stop, résultats LLM invalides ou tardifs, absence de substitution et non-régression balle ; scénarios dans le même runtime sans bascule manuelle ni redémarrage. **Validé ; décision détaillée en section 4.**

### Sujets SH-08 validés — détails à préserver en section 4

1. **Catalogue des annonces : validé, décision détaillée en section 4.** Correspondance avec états, transitions, motifs et action attendue ; paramètres réellement retenus et temps restant, distinction maintien/suspension/fin, reprises et refus. Ne pas rouvrir.
2. **Production et disponibilité audio : validé, décision détaillée en section 4.** Synthèse locale sur catalogue fermé, Jabra candidat à qualifier ; contrôle des deux sens, limites de détection et aucun repli silencieux. Ne pas rouvrir.
3. **Priorité et validité des annonces : validé, décision détaillée en section 4.** Arrêt indépendant, priorité SH-05, invalidation des messages périmés, temps restant, budgets à qualifier, stop pendant lecture sans auto-commande. Ne pas rouvrir.
4. **Contrat de traces corrélées : validé, décision détaillée en section 4.** JSONL versionné, corrélations et chronologies, niveaux de preuve distincts ; journal obligatoire indisponible : refus avant activation ou arrêt/suspension en session. Ne pas rouvrir.
5. **Données et conservation : validé, décision détaillée en section 4.** Collecte structurée minimale et locale ; aucun média ou texte brut par défaut ; traces jusqu'à clôture explicite puis suppression après rapport vérifié, rapports jusqu'à suppression explicite. Aucune durée maximale calendaire fixée. Ne pas rouvrir.
6. **Recette d'observabilité : validé, décision détaillée en section 4.** Matrice simulée sans moteurs puis chaîne audio/journal réelle sans propulsion ; motorisation selon protocoles protégés ultérieurs. Attendus/obtenus, maxima et échecs, budgets/preuves manquants bloquants ; aucun faux succès ni Go implicite. Ne pas rouvrir.

Les six sujets SH-08 sont validés. Les valeurs des budgets, moteur/voix, moyens de contrôle audio, schéma concret JSONL et mécanismes de journalisation restent à concevoir et qualifier ; la politique de conservation par événement est approuvée sans durée maximale calendaire. L'audio ne remplace ni coupure ni surveillance indépendante ; Pi/audio/journal indisponible : ne pas prétendre avoir annoncé ou tracé ce qui ne pouvait l'être.

### Sujets SH-09 validés — détails à préserver en section 4

1. **Périmètre et niveaux de preuve : validé, décision détaillée en section 4.** Tests unitaires, intégration simulée et replay recalculant les décisions ; aucun accès matériel réel, aucune qualification audio/physique ni clôture des dépendances. Ne pas rouvrir.
2. **Jeux de scénarios et oracles : validé, décision détaillée en section 4.** Traçabilité exigences/cas/attendus indépendants ; actions interdites vérifiées, frontières et ordres concurrents explicites, paramètres fictifs distincts des réglages qualifiés. Ne pas rouvrir.
3. **Isolation et reproductibilité : validé, décision détaillée en section 4.** Doubles explicites, aucun accès matériel/réseau ni découverte automatique ; temps/tâches contrôlés, corrélations préservées, borne externe distincte et échecs visibles. Ne pas rouvrir.
4. **Intégration et non-régression : validé, décision détaillée en section 4.** Composants logiciels réels à périphériques simulés ; même instance du runtime, réservation/reprise/fin et commandes locales ; référence de non-régression explicite, comportements balle distincts préservés. Ne pas rouvrir.
5. **Rapports et couverture : validé, décision détaillée en section 4.** Traçabilité par obligation, attendus/obtenus, provenances et limites ; résultat du système distinct du résultat du test, observation indépendante du journal testé ; données minimales SH-08. Ne pas rouvrir.
6. **Verdict et passage aux qualifications suivantes : validé, décision détaillée en section 4.** Conforme dans le périmètre logiciel déclaré, non conforme ou incomplet/bloqué ; aucun échec masqué par répétitions, réglages réels ouverts bloquants, dépendances maintenues, aucune qualification physique ni lancement automatique de SH-10. Ne pas rouvrir.

Les six sujets SH-09 sont validés ; outillage, doubles, instrumentation, matrice concrète, rapports et résultats restent à réaliser. Aucune exécution autorisée par la validation documentaire ; une réussite simulée ne qualifie ni l'audio réel, ni les protections, ni les performances du Pi.

### Sujets SH-10 validés — détails à préserver en section 4

1. **Périmètre et prérequis des mesures : validé, décision détaillée en section 4.** Première étape sans propulsion explicitement isolée ; éventuels essais sous puissance selon protocole protégé distinct et prérequis réels ; conclusions limitées aux propriétés mesurées, aucune qualification physique ni Go humain implicite. Aucune dépendance déclarée satisfaite par sa spécification.
2. **Charges et scénarios représentatifs : validé, décision détaillée en section 4.** Références séparées, charge intégrée réelle, transitions, concurrence autorisée et enchaînements/répétitions reproductibles ; activité réelle distincte des ressources en mémoire, simulation signalée, durées et nombres à justifier.
3. **Mesures et références temporelles : validé, décision détaillée en section 4.** Intervalles/horloges et sources explicites, vision/audio/arrêt/Pi/journal distincts, références indépendantes lorsque nécessaires, incertitudes et coût d'instrumentation ; maxima/dépassements visibles, aucun nouveau seuil ni preuve physique déduite.
4. **Dégradations et limites : validé, décision détaillée en section 4.** Injections contrôlées d'abord sans propulsion, simulation/panne réelle distinctes, moyens bornés/isolés, réactions acquises et budgets ouverts explicites ; perte de contrôle sous puissance selon protocoles protégés.
5. **Rapports et gestion des réglages : validé, décision détaillée en section 4.** Dossier traçable/vérifiable, configurations identifiées, échecs conservés après correction, revalidation des propriétés affectées ; aucun changement silencieux de seuil/périmètre, données selon SH-08.
6. **Verdict et articulation avec SH-11 : validé, décision détaillée en section 4.** Conforme dans le périmètre mesuré, non conforme ou incomplet/bloqué selon les preuves ; caractérisation exploratoire distincte de qualification ; aucune clôture technique ni autorisation humaine déduite de la spécification ; prochaine session documentaire SH-11 uniquement.

Les six sujets SH-10 sont validés ; instrumentation, scénarios concrets, budgets ouverts, réalisations, mesures et verdicts restent à produire. Aucun instrument ni seuil nouveau choisi, aucune charge ni acquisition autorisée implicitement.

### Sujet 1 SH-11 validé — détails à préserver en section 4

Portes d'entrée et preuves requises pour chaque niveau : sans propulsion, banc protégé, cibles inertes, puis éventuel porteur humain uniquement après qualifications, accès sûr à la coupure en solo et Go explicite. Décision détaillée validée en section 4 : protection propre du banc avant qualification des dispositifs essayés, caractérisation physique distincte de validation des réglages, aucun passage automatique. Preuves logicielles SH-09, performances Pi SH-10, audio réel et propriétés physiques distincts ; résultats absents, paramètres fictifs et dépendances ouvertes restent bloquants selon le périmètre. Validation documentaire uniquement, aucune autorisation d'essai ; aucun Go mobile humain.

### Sujet 2 SH-11 validé — détails à préserver en section 4

Sélection des cas et critères applicables à chaque niveau : sections 5/7 et matrices détaillées approuvées réutilisées, statut exact des critères conservé, chaque obligation reliée à ses cas/niveaux/preuves. Non-applicabilité justifiée sans suppression d'obligation ; cas obligatoire manquant ou critère nécessaire ouvert bloquant. Décision détaillée validée en section 4, aucune exécution.

### Sujet 3 SH-11 validé — détails à préserver en section 4

Fiche d'essai préalable, portes revérifiées, organisation solo sans intervention improvisée, interruption et blocage des cas dépendants en cas d'écart ou preuve/protection perdue ; panne injectée distincte d'échec du cas, remise en état protégée et nouvelle exécution explicitement décidée. Règles de mission inchangées, aucune exécution.

### Sujet 4 SH-11 validé — détails à préserver en section 4

Dossier par configuration/domaine, couverture et résultats traçables, provenances séparées, maxima/dépassements et historique des échecs conservés ; références manquantes et limites explicites. Rapport vérifiable après suppression des traces détaillées ; politique SH-08 inchangée. Aucun rapport d'essai ni collecte produit.

### Sujet 5 SH-11 validé — détails à préserver en section 4

Verdict conforme dans le périmètre déclaré / non conforme / incomplet-bloqué selon les preuves ; écart observé jamais masqué par un blocage. Go distinct, explicite, daté et attribué, limité au niveau/configuration/domaine/protocole ; preuves ou protections nécessaires manquantes imposant No-Go. Aucun Go mobile humain, aucune autorisation d'usage général déduite d'un Go d'essai.

### Sujet 6 SH-11 validé — détails à préserver en section 4

Validité limitée à la configuration et au domaine, analyse d'impact et revalidation après changements, historique des échecs conservé. Clôture documentaire distincte de clôture technique, campagne partielle/bloquée insuffisante et No-Go distinct de recette réussie. Prochaine étape documentaire SH-02 explicitement retenue, réalisée depuis en conception fonctionnelle ; aucune poursuite automatique vers SH-12.

### Autorisation historique du lot A — réalisation isolée effectuée

La réalisation du lot A borné par A1–A6, précédemment retenue pour une session ultérieure, a été explicitement autorisée puis effectuée dans cette session. Référence et état local inspectés avant modification ; choix internes consignés, socle raccordé, preuves exécutées et rapport produit/vérifié. Aucun élargissement à SH-06/SH-07 complets, adaptateur matériel, réseau, modèle/serveur réel, acquisition, audio réel, charge/mesure Pi, achat, installation, manipulation matérielle, essai moteur ou SH-12.

**Historique conservé :** décision explicite du 2026-10-30 avec l'outil de questions, puis demande de réalisation dans la présente session. Cela ne clôture aucun ticket global ni dépendance matérielle. Suivi humain moteur toujours refusé, aucune protection ni délai qualifié et aucun Go mobile humain.

### Prochaine étape proposée — à validation explicite, non commencée

Revoir et valider le [rapport du lot A](08_lot_a_rapport_sh09.md), puis choisir
explicitement le prochain lot logiciel isolé ou l'étude documentaire des
protections. Aucune suite engagée automatiquement ; aucune famille P6 choisie,
aucune recette matérielle/Pi/audio ou activation humaine autorisée.

### Méthode de poursuite

À la reprise, lire les décisions détaillées de section 4, le bilan de réalisation et le rapport, puis vérifier l'autorisation explicite de la prochaine étape et sa portée avant toute action. Ne refaire ni le cadrage A1–A6 ni les acquis. Conserver la méthode sujet par sujet : expliquer les choix et conséquences, poser une seule question avec l'outil pour les choix structurants, valider automatiquement les choix dérivés en le signalant et les consigner. Distinguer exigence, choix technique et preuve effective. Le lot A ne clôture pas SH-05/SH-09 globalement ni leurs dépendances physiques. La présente session a produit du code, des tests exécutés et un rapport uniquement logiciels isolés ; aucune mesure/acquisition matérielle, charge Pi, installation, manipulation matérielle ou essai moteur. Toute suite exige sa frontière et son autorisation propres ; aucun Go mobile humain.

Le chantier différé à examiner après le suivi humain est suivi séparément dans le [backlog de simplification](09_simplification_architecture_backlog.md).
