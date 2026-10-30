# Étude et backlog — Suivre un humain comme un chien

Date de création : 2026-10-29. Mise à jour : 2026-10-30. Statut : SH-01 validé ; cadres d'exigences et protocoles SH-02/SH-03/SH-04/SH-05/SH-06/SH-07/SH-08 validés ; orientations SH-08 consignées, choix techniques restants, réalisations et qualifications ouverts ; aucun développement engagé.

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
| Concevoir la coupure, le réarmement et la surveillance indépendante | Choix des composants/dispositifs, schéma, états d'inhibition, détection de coupure, défaillances couvertes et délais | Mécanismes répondant aux exigences validées puis éprouvés sur banc ; aucun redémarrage au rétablissement ou au réarmement seul |
| Résoudre l'accès physique en essai solo | Solution et protocole compatibles avec le porteur devant le robot | Accès sûr démontré sans rejoindre la trajectoire ou les roues ; l'interrupteur embarqué actuel n'est pas considéré suffisant sur la seule proximité déclarée |
| Vérifier le domaine visuel sans propulsion | Champ réel et géométrie du montage ; données d'entrée pour le choix du marqueur SH-03 | Visibilité non supposée à partir de la seule présence de caméra ; choix final et calibration détaillée en SH-03 |
| Qualifier les obstacles | Mesures de couverture/angles morts et domaine des mouvements permis | Volume balayé protégé ou restrictions/protections complémentaires définies et vérifiées |
| Qualifier le Jabra | Résultats simultanéité, stop pendant annonce, perte/reconnexion, moyens et limites de détection | Exigences audio démontrées dans le domaine retenu, pas seulement micro et sortie testés séparément |
| Mesurer la dynamique et fixer les seuils | Vitesses, maxima de latence, distances de freinage et budget conservateur, sur conditions retenues | Seuils et délais numériques justifiés ; plafond respecté ; toute insuffisance entraîne restriction ou révision explicite avant essai humain |
| Statuer sur le passage aux essais | Rapport avec configuration/version, moyens de mesure, résultats bruts, maxima, échecs, restrictions et verdict | Aucun Go mobile humain tant qu'une protection obligatoire ou l'accès à la coupure reste non qualifié |

Ordre validé : moteurs déconnectés pour caméra/audio ; banc protégé pour coupure, réarmement et perte de contrôle ; cible inerte pour couverture obstacle et dynamique ; porteur humain uniquement après qualification des protections. Les essais sous puissance exigent leur propre protocole protégé ; ce document n'autorise pas de manipulations improvisées.

**Statut de sortie documentaire :** le cadre d'exigences et le protocole de SH-02 sont spécifiés et validés, mais la conception détaillée des protections, les relevés et les mesures ne sont pas terminés. SH-02 reste donc ouvert pour sa qualification. Les données visuelles peuvent préparer SH-03 sans propulsion ; cela ne supprime pas sa dépendance à SH-02 pour la qualification complète ni n'autorise un suivi mobile.

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
| Concevoir l'inhibition et la surveillance indépendante avec SH-02 | Dispositifs, schéma, détection, réarmement, défaillances couvertes, délais et limites documentés puis éprouvés |
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

SH-01 est **validé et terminé pour le cadrage**, selon le tableau de la section 1 ; SH-02 est **en cours : exigences et protocole validés, conception détaillée et qualification restantes** ; SH-03 est **spécifié : exigences et recette validées, choix techniques et qualification à faire**, sans clôture de sa dépendance à SH-02 ; SH-04 est **spécifié : contrat/cycle/recette validés, conception détaillée et vérification à faire**, sous réserve des résultats SH-03 ; SH-05 est **spécifié : six sujets d'exigences et de recette validés en section 4, conception détaillée, réalisation et qualification à faire** ; SH-06 est **spécifié : six sujets d'exigences et de recette validés en section 4, conception détaillée, réalisation et qualification à faire** ; SH-07 est **spécifié : six sujets d'exigences et de recette validés en section 4, conception détaillée, réalisation et qualification à faire** ; SH-08 est **spécifié : six sujets et orientations validés en section 4, conception détaillée, réalisation et qualification à faire** ; tous les autres tickets sont **à faire**. Cela ne vaut ni implémentation ni qualification matérielle. P0 = nécessaire au MVP ; P1 = après MVP. Les tailles S/M/L sont relatives, pas des engagements calendaires ; chiffrer après les essais de faisabilité.

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
| SH-09 | P0 / M | Valider hors roulage et préserver l'existant | SH-05, SH-06, SH-07, SH-08 | Tests unitaires/intégration portables, simulations/replay sans moteurs, seuils et transitions couverts ; suivi balle et stop inchangés ; chaque défaut laisse une commande d'arrêt observable |
| SH-10 | P0 / M | Mesurer le système intégré sur Pi | SH-03, SH-07, SH-08 | Vision + audio + LLM sous charge, CPU/RAM/température, latences/maxima, débit et vieillissement mesurés ; version/config et échecs archivés ; réglages corrigés jusqu'au respect des objectifs |
| SH-11 | P0 / L | Effectuer la recette progressive et décider Go/No-Go | SH-09, SH-10 | Préconditions SH-02 revérifiées ; banc puis cible inerte mobile puis porteur uniquement après qualification des protections et de l'accès sûr à la coupure dans une organisation compatible avec l'opérateur seul, sans second opérateur présumé ; critères section 5 et matrice section 7 satisfaits ; rapport, limites et décision signés |
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

Le choix « marqueur accepté » et les cinq étapes de SH-01 sont acquis : périmètre d'usage, association fixe, arrêts/reprises, paramètres cibles et retour vocal. Les choix techniques et autres seuils proposés ne sont pas validés par cette clôture du cadrage ; la qualification physique reste nécessaire. Aucun achat, dépendance, modification du code ou essai moteur n'est autorisé par ce document seul.

## 9. Reprise dans une nouvelle session — prochaine spécification SH-09

Point de reprise au 2026-10-30 : **spécifier SH-09 avec l'utilisateur, pas l'implémenter ni exécuter sa recette**. Commencer par le périmètre et les niveaux de preuve de la validation hors roulage, en réutilisant les protocoles SH-04 à SH-08 sans les rouvrir. Cette suite est uniquement préparée pour une nouvelle session ; aucun nouveau choix détaillé SH-09 n'est approuvé et l'étude SH-09 n'a pas commencé. Les six sujets de chacun des tickets SH-05, SH-06, SH-07 et SH-08 sont validés et intégralement consignés en section 4. Conception, réalisation et qualification restent ouvertes, ainsi que toutes les dépendances techniques ; la spécification de SH-05 à SH-08 ne satisfait pas les prérequis techniques de SH-09. Aucun code, test, installation ou essai moteur autorisé par cette reprise ; aucun Go mobile humain.

### État à préserver

- SH-01 : contrat d'usage validé.
- SH-02 : exigences et protocole validés ; conception des protections, accès à la coupure en solo et qualification non terminés.
- SH-03 : exigences et recette optique validées ; montage, taille, dictionnaire/ID et performances à déterminer après essais.
- SH-04 : contrat de perception, cycle de mission et recette validés ; conception détaillée, implémentation et vérification à faire.
- SH-05 : six sujets d'exigences et de recette validés, détails et travaux techniques restants en section 4 ; conception, réalisation et qualification ouvertes.
- SH-06 : six sujets d'exigences et de recette validés, décisions détaillées et travaux techniques restants en section 4. Réutiliser les états et règles acquis sans les rouvrir ; conception, réalisation et qualification ouvertes, aucune clôture technique.
- SH-07 : six sujets d'exigences et de recette validés, décisions détaillées et travaux techniques restants en section 4 ; conception, réalisation et qualification ouvertes, dépendances SH-01/SH-06 inchangées.
- SH-08 : six sujets et orientations validés en section 4, travaux techniques restants explicités ; conception détaillée, réalisation et qualification à faire. Dépendances SH-01/SH-06 inchangées, aucune clôture technique.
- SH-09 : prochaine spécification documentaire ; nouveaux choix détaillés non encore validés. Ticket technique à faire, dépendances SH-05/SH-06/SH-07/SH-08 inchangées et non satisfaites par leurs seules spécifications.
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

### Sujets proposés pour spécifier SH-09

1. **Périmètre et niveaux de preuve :** distinguer tests unitaires, intégration simulée et replay sans moteurs, prérequis techniques réels et propriétés non démontrables hors roulage ; réutiliser les matrices acquises sans les rouvrir.
2. **Jeux de scénarios et oracles :** relier exigences SH-04 à SH-08, cas nominaux/négatifs, frontières et événements concurrents aux résultats attendus ; paramètres fictifs de simulation distincts des seuils qualifiés.
3. **Isolation et reproductibilité :** horloge et périphériques factices explicitement identifiés, aucun accès matériel implicite, versions/configurations et chronologies reproductibles ; moyens concrets encore à choisir.
4. **Intégration et non-régression :** runtime commun balle/humain, stop/reprise locaux, admission unique et suspension réservée, refus intégraux, aucune relance, substitution, demande différée ou résultat obsolète.
5. **Rapports et couverture :** états, causes, commandes, annonces et traces attendus/obtenus, erreurs explicites, niveaux de preuve et données minimales selon SH-08 ; défaut du journal ou logiciel indisponible sans preuve inventée.
6. **Verdict et passage aux qualifications suivantes :** critères de conformité, cas bloqués et échecs, dépendances non qualifiées et preuves restant à fournir sur Pi puis en protocoles protégés. Aucun succès Mac/simulé valant Go humain.

Cet ordre propose des sujets de discussion SH-09, pas des décisions approuvées ni une autorisation d'exécution. Ne pas choisir d'outillage, créer de tests ou lancer de scénario implicitement.

### Méthode de poursuite

SH-08 est spécifié ; aucune question restante pour cette étape documentaire. Dans la nouvelle session, lire les décisions détaillées puis commencer SH-09 par le périmètre et les niveaux de preuve, sans rouvrir les acquis ni commencer une implémentation. Conserver la méthode : expliquer une proposition et ses conséquences, poser une seule question de validation à la fois avec l'outil de questions, attendre la réponse, la consigner dans ce fichier et passer au sujet suivant. Distinguer exigence approuvée, choix technique ouvert et preuve à obtenir. Ne pas clôturer un ticket technique sur sa seule validation documentaire. Ne créer aucun code, test ou dépendance ; ne lancer aucun test, acquisition matérielle ni essai moteur pendant cette spécification.
