---
mode: agent
description: Simplifier un fichier Python (passe-plats, Callable inutiles)
---
Fais un refactoring de SIMPLIFICATION de ${file}, sans changer son comportement.

Repère et corrige les problèmes suivants.

PROBLÈMES À REPÉRER

1. Méthodes passe-plat
   - Méthode ou property qui ne fait que déléguer à une autre avec les mêmes arguments, sans validation, conversion, logique ni logging.
   - Paire méthode publique / méthode privée où la publique se contente d'appeler la privée : les fusionner en une seule.
   - Property qui duplique ce que __getattr__ ou un héritage fournit déjà.

2. Callable inutiles
   - Fonction passée en paramètre alors que tous les appelants passent la même méthode : la remplacer par un appel direct ou par un paramètre explicite (Literal, Enum).
   - À conserver : l'injection utile pour les tests (time_fn, sleep_fn), les vrais callbacks et les key=. Si tu en gardes un, donne-lui un type précis ou un alias.

3. Indirections opaques
   - Appels par chaîne de caractères (getattr(obj, "nom")()) : les remplacer par un appel direct, ou typer les valeurs possibles avec un Literal.
   - Boucles de getattr sur plusieurs noms "au cas où" : signale-les et propose de ne garder que le nom réellement utilisé (demande-moi lequel).
   - __getattr__ de délégation magique : signale-le, indique ce qu'il expose implicitement et le risque de récursion infinie si l'attribut délégué n'est pas encore défini. Ne le supprime pas sans mon accord.

4. Code redondant
   - Branches inatteignables (ex. vérification de None dans une méthode que l'on n'appelle que si la valeur existe).
   - Séquence de vérifications dupliquée à plusieurs endroits : l'extraire en une petite méthode au nom explicite.
   - logging.getLogger(__name__) répété : un LOGGER unique au niveau du module.
   - Bloc de validation long au milieu d'une méthode : l'extraire en fonction nommée.

5. Typage
   - Paramètre typé Any qui est en réalité utilisé via un petit ensemble de méthodes : proposer un Protocol qui documente ce qui est attendu.

PROCÉDURE

A. D'abord, sans rien modifier, donne-moi un tableau : élément | problème | action proposée | risque.
   Signale tout cas où un test ou un autre module pourrait dépendre de l'élément (mock, appel externe). Utilise la recherche de références pour vérifier chaque usage avant toute suppression.

B. Attends mon accord, puis applique les changements un par un.

RÈGLES

- Ne change ni les signatures publiques, ni le comportement, ni l'ordre des vérifications de sécurité (arrêt d'urgence, capteurs), sauf si je te le demande.
- N'ajoute aucune nouvelle classe, couche d'abstraction ou fonction utilitaire autre que celles listées ci-dessus.
- Garde des type hints complets et des noms explicites.
- Si un cas est ambigu, pose-moi la question plutôt que de deviner.
- À la fin, résume les changements et dis-moi quoi lancer pour vérifier que rien n'est cassé.