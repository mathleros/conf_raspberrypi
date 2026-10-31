# Prompts de poursuite — suivi humain

Mis à jour le 2026-10-31. Prompts conçus pour avancer par blocs compacts, sans rouvrir les décisions validées ni réduire les vérifications utiles.

## Estimation de l'avancement

- **Implémentation logicielle : environ 40 %**, estimation indicative, non métrique. Le socle isolé, le cycle/runtime protégé et la frontière trame→observation sont en place ; le replay bout en bout demandé ci-dessous, le comportement SH-06 et les intégrations SH-04/07/08 restent à faire.
- **Prêt pour un essai de suivi avec mouvement réel : 0 %**. Les protections et qualifications SH-02/03/05/10/11 ne sont pas démontrées comme achevées. Les résultats logiciels, même reproduits, ne lèvent pas ces portes.

L'avancement est évalué par rapport à l'implémentation et à la validation complète attendues, pas au nombre de tests ni aux seules lignes de code. Les jalons récents et leurs résultats sont dans le [rapport SH-09](../specs/backlog/08_lot_a_rapport_sh09.md), notamment les sections 12–13, et le [protocole de campagne isolée](test-campaign/lot-a-campagne-strictement-isolee.md).

## Mode d'emploi

1. Lancer le prompt 1 **dans la conversation actuelle**, qui contient déjà le contexte de la frontière SH-04.
2. Après chaque bloc terminé, ouvrir **une nouvelle conversation** pour le prompt suivant, sauf si celui-ci dépend immédiatement de détails non consignés par le bloc précédent ; dans ce cas, rester dans la même conversation. Chaque prompt demande de lire les documents de suivi à jour.
3. Ne lancer que le prompt dont les dépendances sont satisfaites. Un bloc logiciel peut avancer avec des doubles si une qualification matérielle bloque ; ne pas simuler une preuve réelle.
4. Les prompts ne sont pas des autorisations matérielles. Toute action sur Pi, caméra, câblage, moteur, robot ou personne doit attendre une autorisation explicite, distincte et limitée à cette action.

## Prompt 1 — Replay frontière → cycle et annonces

**Session : même conversation actuelle.**

> Poursuis le suivi humain à partir de l'état réel du dépôt. Lis les sections 12–13 de `specs/backlog/08_lot_a_rapport_sh09.md`, `docs/test-campaign/lot-a-campagne-strictement-isolee.md` et les instructions de `.github/copilot-instructions.md`. Réalise uniquement le replay synthétique de `observe_frame` jusqu'au cycle humain et aux annonces, sous doubles : couvre résultats retardés/en vol invalidés après suspension, stop et échéance, sans activation réelle et sans lever le refus de production `follow_person`. Réutilise les contrats/helpers existants ; n'ajoute pas de fournisseur caméra ni de seuil de production. Lance les tests ciblés, puis les trois commandes isolées documentées si les surfaces protégées ou leurs tests changent. Consigne brièvement changements, résultats, limites et prochain bloc dans les documents de suivi concernés. Aucun accès Pi/matériel.

## Prompt 2 — SH-02 : fermer le dossier de qualification des protections

**Session : nouvelle conversation.**

> Lis l'état à jour du backlog SH et du rapport SH-09. Traite SH-02 en réutilisant les décisions déjà validées : vérifie les informations réellement disponibles, identifie précisément les preuves, choix matériels et opérations encore manquants pour P1–P6, puis prépare un plan de qualification concis avec critères d'arrêt et preuves attendues. N'invente ni composant ni seuil. Distingue faits observés, déclarations utilisateur et inconnues. Ne prétends pas qualifier le matériel et n'exécute aucune action matérielle ; si une inspection ou manipulation est nécessaire, demande une autorisation séparée décrivant l'action exacte et ses préconditions. Mets à jour le suivi uniquement avec des faits vérifiés.

## Prompt 3 — SH-03 : qualification optique statique

**Session : nouvelle conversation, après satisfaction des préconditions SH-02.**

> À partir des choix et preuves déjà consignés, prépare puis réalise uniquement la prochaine étape SH-03 de perception statique, sans propulsion ni personne dans la zone. Commence par vérifier les préconditions et l'autorisation explicite couvrant précisément l'ouverture caméra et la campagne envisagée ; si elles manquent, arrête-toi au protocole et demande l'autorisation, sans ouvrir l'appareil. Ne confonds pas détection d'une trame avec calibration ou qualification : applique les critères SH-03 et conserve les échecs/incertitudes. N'ajoute aucun réglage de production avant justification. Consigne version, montage, protocole, résultats, limites et décision de passage.

## Prompt 4 — SH-04 : fournisseur perception et cycle de mission

**Session : nouvelle conversation, après disponibilité des résultats SH-03 nécessaires.**

> Implémente le raccordement SH-04 entre le fournisseur de perception et le cycle humain/runtime en réutilisant `HumanPerceptionFrame`, `observe_frame`, acquisition et contexte de mission existants. Prends uniquement les paramètres et preuves qualifiés consignés ; si un paramètre requis ne l'est pas, refuse explicitement le raccordement de production et continue seulement avec doubles lorsque c'est indépendant. Vérifie flux interrompu/renouvelé, données périmées, ambiguïté, contexte obsolète et nettoyage. Ne raccorde pas une caméra réelle et ne déclenche aucun mouvement. Tests ciblés puis campagne isolée pertinente ; documente l'état exact.

## Prompt 5 — SH-05 : garde-fous du suivi humain

**Session : nouvelle conversation, après les contrats SH-02/04 applicables.**

> Complète l'implémentation logicielle SH-05 à partir des exigences validées du backlog et des protections/raccordements existants. Couvre admission et émission à chaque cycle, priorités, propagation des défauts, invalidation des résultats/commandes obsolètes, arrêts et refus sans succès apparent. Utilise des doubles indépendants pour les sorties et observateurs ; conserve le refus humain de production tant que les protections réelles ne sont pas qualifiées. Ne modifie pas les décisions acquises et n'active aucun moteur. Tests ciblés, puis campagne isolée et non-régression des surfaces touchées ; consigne les preuves et blocages physiques séparément.

## Prompt 6 — SH-06 : comportement déterministe

**Session : nouvelle conversation, après les fondations logicielles SH-04/05.**

> Implémente le comportement déterministe SH-06 sur le cycle/runtime existant : états, transitions, maintien de distance, orientation/avance bornées selon les seules valeurs qualifiées, distinction maintien/reprise explicite et échéance conservée. Teste avec horloge, observations et actionneurs factices, y compris événements simultanés et défauts ; aucun recul, balayage, contournement ou mouvement réel. Si une valeur ou règle n'est pas qualifiée, garde-la configurable/indisponible selon les patterns existants plutôt que d'inventer une valeur de production. Exécute tests ciblés, campagne isolée et non-régression pertinentes ; mets à jour le suivi.

## Prompt 7 — SH-07 : commande naturelle et intégration runtime

**Session : nouvelle conversation, après SH-06 vérifié.**

> Relie progressivement la commande naturelle au comportement humain dans l'assistant/runtime existant, selon SH-07. Garde `follow_person` distinct des capacités objet, sans repli vers `yellow`, réparation silencieuse, plan partiel ou second mode utilisateur. Commence par parsing/validation avec LLM et entrées factices ; le chemin réel doit continuer à refuser toute activation tant que les portes SH-02/05/11 ne sont pas satisfaites. Préserve balle, stop et primitives. Tests ciblés puis campagnes isolées/non-régression concernées ; rapporte séparément ce qui est livré et ce qui reste bloqué.

## Prompt 8 — SH-08 : observabilité

**Session : nouvelle conversation, après les contrats runtime concernés.**

> Implémente les parties logicielles SH-08 encore manquantes : catalogue d'annonces déterministes, priorités/invalidation, traces corrélées et erreurs explicites, selon les décisions validées. Utilise sorties audio/journaux factices ; aucun audio live, média brut ou donnée personnelle persistée par défaut. Vérifie qu'une annonce ou une erreur de journal ne retarde jamais le stop et ne valide pas une action obsolète. Tests ciblés et non-régression ; distingue explicitement preuve simulée et qualification audio réelle.

## Prompt 9 — SH-09 : validation hors roulage complète

**Session : nouvelle conversation, après intégration logicielle SH-04 à SH-08.**

> Complète SH-09 hors roulage : matrice exigences/scénarios/attendus indépendants, replays recalculés, injections de pannes, observateurs distincts du journal, non-régression du runtime commun et rapport de provenance. Réutilise le lanceur strict `-I -S` et les trois commandes du protocole ; n'exécute pas pytest global, n'installe rien et ne transforme pas une campagne interrompue en succès. Corrige les défauts trouvés dans le même bloc puis rejoue les contrôles affectés et la série finale. Aucun matériel/réseau. Conclus uniquement sur le périmètre effectivement éprouvé.

## Prompt 10 — SH-10 : mesures intégrées sur Pi

**Session : nouvelle conversation, après disponibilité des qualifications et autorisation d'accès Pi.**

> Prépare SH-10 en vérifiant d'abord les préconditions, les versions synchronisées et l'autorisation explicite pour chaque opération Pi prévue. Si l'autorisation ou une porte d'entrée manque, produis le protocole et arrête-toi sans connexion ni exécution. Sinon, mesure uniquement les charges/scénarios autorisés, d'abord sans propulsion lorsque requis ; consigne versions, horloges, distributions/maxima, incertitudes et échecs. N'infère aucune performance physique d'un test Mac ou d'une mesure rapportée. Ne modifie pas les réglages de production sans justification et validation.

## Prompt 11 — SH-11 : recette progressive et décision Go/No-Go

**Session : nouvelle conversation, après preuves SH-02/05/09/10 exigées par le niveau visé.**

> Évalue les portes SH-11 à partir des preuves effectivement disponibles et propose le niveau d'essai maximal justifié. N'interprète ni l'objectif utilisateur ni ce prompt comme un Go. Si une porte manque, donne les blocages et n'engage pas l'essai. Pour toute étape physique, demande d'abord une autorisation explicite distincte précisant matériel, zone, cible, action, durée, supervision et arrêt ; commence par le niveau sans personne et ne passe jamais au niveau suivant automatiquement. Documente les critères, résultats, incidents et verdict limité au domaine testé. Aucun suivi d'une personne sans Go explicite conforme aux prérequis.
