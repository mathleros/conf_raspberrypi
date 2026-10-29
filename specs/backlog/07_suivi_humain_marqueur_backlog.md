# Étude et backlog — Suivre un humain comme un chien

Date de création : 2026-10-29. Mise à jour : 2026-10-30. Statut : SH-01 validé ; exigences et protocole SH-02 validés, conception des protections et qualification ouvertes ; aucun développement engagé.

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
| Début du chronomètre | À l'activation du suivi, après acquisition initiale ; l'attente d'acquisition a son propre délai technique borné, restant à définir |
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

Spécification engagée avec l'utilisateur le 2026-10-30 ; aucun code, acquisition caméra ou essai physique réalisé. SH-02 reste ouvert. Cette préparation documentaire et optique ne clôture pas la dépendance de qualification.

| Sujet | Décision / statut | Suite requise |
|---|---|---|
| Géométrie caméra–marqueur | L'utilisateur souhaite décider après observation du champ réel, moteurs déconnectés ; ni rehausse/inclinaison caméra ni emplacement porté plus bas ne sont choisis | Relever référence caméra et champ après orientation de l'image ; observer les emplacements candidats aux distances d'usage, puis choisir et documenter le montage avant calibration |

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
| Régression | Scénarios balle, primitives, stop et traces existants inchangés hors activation explicite du nouveau mode |

Les moyennes et p95 servent à qualifier les performances, **pas à excuser un dépassement de sécurité**. Rapporter aussi maxima, rejets et nombre d'essais ; une campagne réussie ne constitue pas une certification.

Budget conservateur à vérifier : distance de garde ≥ vitesse maximale × délai maximal de détection/réaction + distance de freinage mesurée + incertitude + marge. Un seuil frontal fixe de 20 cm, présent dans le driver, ne valide pas ce budget à lui seul.

Si le Pi ne tient pas les délais : réduire vitesse/résolution ou éloigner l'inférence LLM de la boucle critique, puis refaire les mesures. Si la couverture obstacle, le freinage ou l'arrêt indépendant restent insuffisants, pas de Go près d'un humain.

## 6. Nouveau backlog

SH-01 est **validé et terminé pour le cadrage**, selon le tableau de la section 1 ; SH-02 est **en cours : exigences et protocole validés, conception détaillée et qualification restantes**, selon la section 4 ; la **spécification de SH-03 est engagée sans propulsion**, sans clôture de sa dépendance à SH-02 ; tous les autres tickets sont **à faire**. Cela ne vaut ni implémentation ni qualification matérielle. P0 = nécessaire au MVP ; P1 = après MVP. Les tailles S/M/L sont relatives, pas des engagements calendaires ; chiffrer après les essais de faisabilité.

| ID | Priorité / taille | Ticket et livrable | Dépendances | Critères d'acceptation |
|---|---|---|---|---|
| SH-01 | P0 / S | Valider le contrat d'usage et les paramètres | Aucune | Périmètre, association « moi », reprise explicite, feedback, distance/durée/vitesse et scénarios hors domaine approuvés ; capacité du même assistant sans mode à sélectionner ; aucune assimilation implicite à la balle |
| SH-02 | P0 / M | Qualifier le matériel et le domaine de sécurité | SH-01 | Inventaire réel, champ caméra, gabarit, protection obstacle, arrêt physique, stratégie watchdog, budget d'arrêt et protocole protégés documentés ; sortie audio, contrôle de disponibilité et intelligibilité qualifiés ; achats éventuels identifiés |
| SH-03 | P0 / M | Valider le marqueur et la distance, moteurs désactivés | SH-01, SH-02 | Choix technique motivé, calibration et support reproductibles ; mesures de référence à 1/1,5/2/2,5 m et différents angles ; erreurs de distance ≤ 20 cm sur 95 % des mesures acceptées, rejets/ambiguïtés consignés ; aucune formule balle réutilisée |
| SH-04 | P0 / M | Définir les observations et l'association de session | SH-03 | Horodatage de capture, trame distincte, qualité, identifiant verrouillé, distance avec référence physique documentée ; tests trame répétée/périmée, mauvais ID, doublon et reset session |
| SH-05 | P0 / L | Implémenter les garde-fous du suivi humain | SH-02, SH-04 | Refus sans caméra/protection valides, arrêt sur défaut/péremption, vitesse bornée, recul interdit, pas de balayage, arrêt prioritaire et réarmement explicite ; injection de panne, y compris arrêt du processus, validée sur banc protégé |
| SH-06 | P0 / M | Développer le comportement de suivi déterministe | SH-04, SH-05 | États et transitions testés par horloge simulée ; confort/approche/orientation bornés ; aucune translation sans distance valide ; perte/obstacle/fin rendent statut et motif explicites |
| SH-07 | P0 / M | Relier la commande naturelle au comportement | SH-01, SH-06 | Prompt, schéma JSON, lexique, paramètres autorisés, alias, normalisation, parser local, validator, planner, registre, budgets mission/étape et assemblage matériel raccordés dans le runtime existant ; commandes balle et « suis-moi » accessibles sans bascule manuelle ni redémarrage ; perception sélectionnée automatiquement, acquisition caméra partagée, aucune mission motrice concurrente ; « suis-moi » ne démarre jamais `yellow` par défaut |
| SH-08 | P0 / S | Rendre le suivi observable et compréhensible | SH-01, SH-06 | Messages vocaux déterministes et non bloquants selon la section 1 ; absence audio au démarrage : refus, panne détectée en cours : suspension ; stop reconnu pendant les annonces et aucune auto-commande vocale ; traces avec état, ID, âge/qualité/distance, consigne, arrêt et latences ; aucun flux vidéo enregistré par défaut ; rétention des traces définie |
| SH-09 | P0 / M | Valider hors roulage et préserver l'existant | SH-05, SH-06, SH-07, SH-08 | Tests unitaires/intégration portables, simulations/replay sans moteurs, seuils et transitions couverts ; suivi balle et stop inchangés ; chaque défaut laisse une commande d'arrêt observable |
| SH-10 | P0 / M | Mesurer le système intégré sur Pi | SH-03, SH-07, SH-08 | Vision + audio + LLM sous charge, CPU/RAM/température, latences/maxima, débit et vieillissement mesurés ; version/config et échecs archivés ; réglages corrigés jusqu'au respect des objectifs |
| SH-11 | P0 / L | Effectuer la recette progressive et décider Go/No-Go | SH-09, SH-10 | Préconditions SH-02 revérifiées ; banc puis cible inerte mobile puis porteur accompagné ; critères section 5 et matrice section 7 satisfaits ; rapport, limites et décision signés |
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
