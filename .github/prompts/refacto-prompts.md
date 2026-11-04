# Prompts de simplification : package `irobot`

Ce fichier est lu par `simplifier.prompt.md` (commande `/simplifier` dans Copilot Chat). Chaque section `## Prompt N` est autonome. Tu peux aussi copier-coller son bloc à la main.

Objectif : supprimer les méthodes « passe-plat », les `Callable` inutiles, le code mort et les duplications, **sans changer le comportement**.

## Règles communes

Ces règles s'appliquent à tous les prompts.

```text
RÈGLES COMMUNES
- Ne change ni le comportement, ni les signatures publiques, ni l'ordre des vérifications de sécurité (arrêt d'urgence, obstacle).
- Avant de supprimer ou renommer quoi que ce soit, fais une recherche de références dans tout le dépôt, tests inclus. Si un test ou un autre module l'utilise, mets-le à jour ou demande-moi.
- N'ajoute aucune classe, couche ou fonction autre que celles explicitement autorisées dans le prompt.
- Conserve time_fn et sleep_fn (injection utile pour les tests).
- Procède en 2 étapes :
  (A) un tableau « élément | problème | action proposée | risque », sans rien modifier, puis attends mon accord ;
  (B) après mon accord, applique un changement à la fois et résume à la fin.
- Si un cas est ambigu, pose-moi la question plutôt que de deviner.
```

## Suivi et ordre conseillé

Un commit par prompt (`git commit -m "refacto: simplifie <fichier>"`), tests lancés avant chaque commit.

| N° | Fichier cible | Priorité | Fait |
|----|---------------|----------|------|
| 0 | `src/irobot/domain/numbers.py` (nouveau) + 4 fichiers | haute | [ X] |
| 1 | `src/irobot/interfaces/voice_llm_transport.py` | haute | [ X] |
| 2 | `src/irobot/interfaces/intent/llm_intent_parser.py` | haute | [ X] |
| 3 | `src/irobot/domain/skills/behaviors/target_tracking.py` | haute | [ X] |
| 4 | `src/irobot/domain/skills/primitives/base_motion_primitive.py` | moyenne | [ X] |
| 5 | `src/irobot/domain/skills/behaviors/follow_object.py` | moyenne | [ ] |
| 6 | `src/irobot/domain/skills/behaviors/approach_target.py` | haute | [ ] |
| 7 | `src/irobot/domain/orchestrator/planner.py` | moyenne | [ ] |
| 8 | `src/irobot/interfaces/language_controller.py` | moyenne | [ ] |
| 9 | `src/irobot/interfaces/robot_controller.py` | haute | [ ] |
| 10 | `src/irobot/domain/orchestrator/mission_orchestrator.py` | haute | [ ] |
| 11 | `src/irobot/interfaces/command_service.py` | haute | [ ] |
| 12 | `src/irobot/interfaces/voice_runtime.py` | haute | [ ] |
| 13 | `src/irobot/domain/orchestrator/executor.py` | basse | [ ] |
| 14 | `src/irobot/domain/skills/blackboard_state.py` | basse | [ ] |

Fais le prompt 0 en premier : les prompts 3, 4, 6 et 10 s'appuient sur la fonction `to_float` qu'il crée. Ensuite, suis l'ordre des numéros (des fichiers feuilles vers les couches hautes).

---

## Prompt 0

**Fichier cible :** `src/irobot/domain/numbers.py` (nouveau)
**Fichiers liés :** `src/irobot/domain/skills/behaviors/target_tracking.py`, `src/irobot/domain/skills/primitives/base_motion_primitive.py`, `src/irobot/domain/orchestrator/mission_orchestrator.py`, `src/irobot/interfaces/intent/plan_validator.py`, `approach_target.py`, `follow_object.py`

```text
Supprime la duplication de la conversion en float. `_to_float` est réécrit dans 4 fichiers.

Autorisé : créer `src/irobot/domain/numbers.py` avec UNE seule fonction
`to_float(value: Any, default: float | None = None, *, require_finite: bool = False) -> float | None`
- float(value) ; TypeError ou ValueError -> default ;
- si require_finite=True et que le nombre n'est pas fini (NaN, inf) -> default.

Remplace les copies locales en conservant exactement leur comportement :
- TargetTrackingMixin._to_float (target_tracking.py) : default obligatoire, pas de contrôle de finitude. Ses appelants sont approach_target.py et follow_object.py (self._to_float(...)) : remplace par to_float(...).
- BaseMotionPrimitiveSkill._to_float (base_motion_primitive.py) : default None, pas de contrôle de finitude.
- MissionOrchestrator._to_float (mission_orchestrator.py) : require_finite=True. L'appel `ApproachTargetSkill._to_float(...)` (méthode privée d'une autre classe) devient to_float(...) sans contrôle de finitude, comme avant.
- IntentPlanValidator._to_float (plan_validator.py) : require_finite=True.

Signale-moi aussi `_num` dans src/irobot/interfaces/plan_guards.py (probablement similaire) sans le modifier.
Si un type checker se plaint que le résultat peut être None, ajoute deux @overload plutôt que de changer la logique.
Mets à jour les tests qui référencent les anciens `_to_float`.
```

---

## Prompt 1

**Fichier cible :** `src/irobot/interfaces/voice_llm_transport.py`
**Fichiers liés :** `src/irobot/interfaces/voice_runtime.py`, `src/irobot/interfaces/intent/llm_intent_parser.py`, `src/irobot/config/llm_settings.py`

```text
Simplifie src/irobot/interfaces/voice_llm_transport.py.
1. Supprime les constantes inutilisées ailleurs : LLM_MODEL, LLM_CONNECT_TIMEOUT_SECONDS, LLM_READ_TIMEOUT_SECONDS, LLM_HTTP_TIMEOUT et _LLM_SETTINGS_AT_IMPORT. Cela supprime aussi l'appel load_llm_settings() exécuté à l'import.
2. reset_response_format_cache est un passe-plat de PLAN_RESPONSE_FORMATS.reset(). Remplace ses appelants (voir voice_runtime.py et les tests) puis supprime-la, ou garde-la si un test en dépend.
3. Les fonctions _post_llm_chat, _llm_payload, _select_formats, _parse_llm_json_payload et _llm_error_reason sont importées depuis d'autres modules : propose de retirer le underscore (nom public) sans changer leur logique.
4. Type le paramètre `environ: Any = None` de llm_response_format_mode et llm_warmup_wait_seconds avec `Mapping[str, str] | None`.
5. Garde le Protocol LLMPost et la classe ResponseFormatChain (utiles).
```

---

## Prompt 2

**Fichier cible :** `src/irobot/interfaces/intent/llm_intent_parser.py`
**Fichiers liés :** `src/irobot/interfaces/command_service.py`, `src/irobot/interfaces/voice_runtime.py`

```text
Simplifie src/irobot/interfaces/intent/llm_intent_parser.py.
1. Supprime warm_up_llm_async : elle n'est utilisée nulle part (seulement importée dans voice_runtime.py ; retire aussi cet import).
2. Dans ask_llm_for_intent_plan_with_trace, la closure `_fallback` est passée comme Callable à _interpret_plan_response. Remplace-la par une fonction de module `_fallback_plan(text, normalized_text, meta, console_reason, **trace)` appelée directement, et retire le paramètre `fallback: Callable[..., ...]`.
3. _intent_from_llm_step et _normalize_llm_step répètent la même validation (step dict, parameters dict ou None). Factorise cette partie commune dans une seule petite fonction.
4. LLMIntentParser est un passe-plat (parse_plan_with_trace appelle seulement self._parse_with_trace). Analyse si la classe est nécessaire à l'interface IntentPlanParser. Si oui, garde-la, sinon propose de l'enlever de command_service.py.
5. Les Callable[[str], tuple[list[Intent], dict[str, Any]]] répétés peuvent utiliser un alias unique (par exemple LLMPlanParser, défini aujourd'hui dans command_service.py) : place-le ici pour éviter un import circulaire.

Autorisé : la fonction _fallback_plan et une fonction de validation commune.
```

---

## Prompt 3

**Fichier cible :** `src/irobot/domain/skills/behaviors/target_tracking.py`
**Fichiers liés :** `approach_target.py`, `follow_object.py`, `src/irobot/interfaces/robot_controller.py`
**Prérequis :** prompt 0

```text
Simplifie src/irobot/domain/skills/behaviors/target_tracking.py (TargetTrackingMixin) et ses utilisateurs approach_target.py et follow_object.py.
1. _is_emergency_stop_requested cherche d'abord le nom privé `_is_emergency_stop_requested` puis `is_emergency_stop_requested` sur le robot. Utilise uniquement le nom public `is_emergency_stop_requested`. Conserve le comportement fail-safe : une exception retourne True.
2. _pulse_motion utilise getattr(context.robot, f"{direction}_for") puis getattr(context.robot, direction). Type `direction` avec Literal["forward", "backward", "left", "right"] et documente le repli sur la méthode sans durée.
3. Garde l'annotation `sleep_fn: Callable[[float], None]` : c'est un usage légitime de Callable.
4. Remplace la copie locale de _to_float par la fonction to_float du prompt 0 (si elle n'existe pas, arrête-toi et dis-le-moi).
```

---

## Prompt 4

**Fichier cible :** `src/irobot/domain/skills/primitives/base_motion_primitive.py`
**Prérequis :** prompt 0

```text
Simplifie src/irobot/domain/skills/primitives/base_motion_primitive.py.
1. Remplace la copie locale de _to_float par la fonction to_float du prompt 0.
2. `SETTINGS = load_runtime_settings()` est évalué à l'import du module. Signale le risque pour les tests et propose de le lire à l'exécution (par exemple via un attribut de classe injectable), sans changer les valeurs.
3. command_method et command_for_method sont des chaînes utilisées avec getattr. Type-les avec un Literal des noms valides ("forward", "backward", "left", "right" et leur variante "_for").
4. Ne touche pas aux sous-classes move_forward, move_backward, turn_left et turn_right : ce sont de simples fichiers de configuration.
```

---

## Prompt 5

**Fichier cible :** `src/irobot/domain/skills/behaviors/follow_object.py`
**Fichiers liés :** `approach_target.py`, `target_tracking.py`

```text
Simplifie src/irobot/domain/skills/behaviors/follow_object.py.
1. _result a un paramètre `context` inutilisé et ne fait que construire un SkillResult : supprime ce paramètre.
2. La property `settings` (chargement paresseux) est identique à celle de approach_target.py. Signale la duplication et propose de la déplacer dans TargetTrackingMixin (autorisé).
3. CONTROL_LOOP_PERIOD_S est défini à l'identique dans follow_object et approach_target : place la constante dans TargetTrackingMixin pour les deux skills.
4. Remplace `assert duration_s is not None` en fin de _run par une structure qui rend ce cas impossible évident.
```

---

## Prompt 6

**Fichier cible :** `src/irobot/domain/skills/behaviors/approach_target.py`
**Fichiers liés :** `target_tracking.py`, `follow_object.py`, `mission_orchestrator.py`
**Prérequis :** prompts 0 et 5

```text
Simplifie src/irobot/domain/skills/behaviors/approach_target.py : execute() fait environ 275 lignes.
1. Les blocs « stop + motion="stop" + follow_target_state + SkillResult » sont répétés pour : obstacle (×2), arrêt d'urgence, cible atteinte (×2), cible perdue. Extrais une méthode privée `_halt(context, phase, message, data, confidence, **state)` qui les construit.
2. Le mode sans perception live (un seul pas, environ lignes 97 à 185) et le mode boucle partagent une partie de leur logique. Extrais ce mode dans une méthode `_single_step`. Ne fusionne pas les deux modes si cela change les status ou les confidences.
3. Supprime la property `settings` dupliquée (voir prompt 5) et la CONTROL_LOOP_PERIOD_S dupliquée.
4. Les status ("failed", "success", "in_progress"), les confidences (0.99, 0.95, 0.7...) et les messages ne changent pas.
5. Remplace les appels à self._to_float par to_float (prompt 0).

Autorisé : _halt et _single_step.
```

---

## Prompt 7

**Fichier cible :** `src/irobot/domain/orchestrator/planner.py`
**Fichiers liés :** `src/irobot/domain/orchestrator/registry.py`, `src/irobot/interfaces/language_controller.py`

```text
Simplifie src/irobot/domain/orchestrator/planner.py. Analyse d'abord, ne modifie rien sans mon accord.
1. plan_with_target n'est appelée nulle part : confirme par recherche de références (tests inclus) puis supprime-la.
2. SkillPlanner.__init__ accepte `skills` et `registry`, et plan() renvoie self.skills si le registre ne trouve rien. Signale ce repli surprenant et vérifie si un appelant l'utilise.
3. MAX_PLAN_STEPS = load_runtime_settings().max_plan_steps est évalué à l'import : signale-le et vérifie son usage.
4. Ne change pas la logique d'expansion des intents (_expand_*).
```

---

## Prompt 8

**Fichier cible :** `src/irobot/interfaces/language_controller.py`
**Fichiers liés :** `src/irobot/interfaces/command_service.py`, `src/irobot/domain/skills/blackboard_state.py`

```text
Simplifie src/irobot/interfaces/language_controller.py.
1. handle_intent n'est appelée nulle part : confirme par recherche de références (tests inclus) puis supprime-la.
2. Si handle_intent disparaît, handle_planned_step n'a plus de raison d'exister séparément de _execute_planned_step : propose de fusionner _intent_rejection et _execute_planned_step si cela ne change pas l'ordre (rejet avant exécution).
3. Dans _execute_planned_step, BlackboardState reçoit explicitement last_camera_position=None, last_object_position=None et last_ball_position=None : ce sont déjà les valeurs par défaut, supprime-les.
4. _should_prioritize_obstacle_stop répète le getattr(robot, "check_obstacle") de RobotController : garde-le pour l'instant et signale-moi la duplication.
5. Type robot, camera et sensor (actuellement sans annotation).
```

---

## Prompt 9

**Fichier cible :** `src/irobot/interfaces/robot_controller.py`
**Fichiers liés :** `target_tracking.py` (nom de la méthode d'arrêt d'urgence), `voice_runtime.py`, `command_service.py`, `src/irobot/hardware/runtime_factory.py`

```text
Simplifie src/irobot/interfaces/robot_controller.py sans changer son comportement.
1. Supprime la property `speed` : __getattr__ délègue déjà `speed` à _robot.
2. Fusionne is_emergency_stop_requested et _is_emergency_stop_requested en une seule méthode publique. Fais une recherche de références : target_tracking.py doit déjà utiliser le nom public (prompt 3) ; aligne tout appelant restant.
3. Remplace le Callable `start_motion` de _run_motion_for par `direction: Literal["forward", "backward", "left", "right"]` ; type _start_motion avec le même Literal.
4. Extrais "arrêt d'urgence, obstacle, arrêt d'urgence" dans `_abort_reason(check_obstacle)` en gardant exactement le même ordre, et le bloc de validation de duration_seconds dans une fonction `_validate_duration`.
5. Supprime le `if sensor is None` inatteignable de _check_distance_sensor.
6. Remplace les 4 logging.getLogger(__name__) par un LOGGER de module.
7. Garde time_fn et sleep_fn.
8. Signale __getattr__ (risque de récursion infinie si _robot n'est pas encore défini) sans le supprimer : le code s'en sert pour check_obstacle, is_protected_result_current, etc. Demande-moi avant de réduire la liste des 4 noms de détecteurs d'arrêt.

Autorisé : _abort_reason et _validate_duration.
```

---

## Prompt 10

**Fichier cible :** `src/irobot/domain/orchestrator/mission_orchestrator.py`
**Fichiers liés :** `src/irobot/interfaces/command_service.py`, `approach_target.py`
**Prérequis :** prompt 0

```text
Simplifie src/irobot/domain/orchestrator/mission_orchestrator.py.
1. Les trois callables execute_step, stop_requested et on_event sont transmis tels quels à travers execute -> _run_steps -> _execute_planned_step_with_retry -> _execute_attempt. Regroupe-les dans une seule dataclass privée `_StepRunner` créée dans execute(), pour réduire les signatures.
2. `if on_event is not None: on_event({...})` est répété 4 fois : encapsule dans une méthode `_emit(event)` de cette dataclass.
3. Remplace la copie locale de _to_float et l'appel à `ApproachTargetSkill._to_float` par la fonction to_float du prompt 0.
4. Signale les dict[str, Any] des résultats de step ("status", "reason") comme candidat à une dataclass, sans le faire (changement trop large).
5. Ne change pas les chaînes de status ni l'ordre des vérifications d'arrêt.

Autorisé : la dataclass _StepRunner (avec sa méthode _emit).
```

---

## Prompt 11

**Fichier cible :** `src/irobot/interfaces/command_service.py`
**Fichiers liés :** `voice_runtime.py`, `llm_intent_parser.py`, `language_controller.py`

```text
Simplifie src/irobot/interfaces/command_service.py.
1. _ask_plan ne fait que déléguer à self.llm_parser.parse_plan_with_trace : appelle-le directement dans _collect_plan et supprime la méthode.
2. self.planner = self.controller.planner est un alias : remplace ses usages par self.controller.planner, ou garde-le seulement s'il est utilisé en dehors de la classe (recherche de références).
3. handle_text construit 4 fois un dict de rejet presque identique : extrais une méthode privée `_rejection(text, trace_path, plan_trace, reason, **extra)`.
4. _trace_raw_plan écrit 14 clés .get(...) à la main : remplace par une boucle sur un tuple de noms de clés, sans changer les clés écrites.
5. _emergency_stop_requested et safe_stop répètent le getattr/try-except de RobotController : garde-les mais signale-moi la duplication. VoiceRuntime lit _emergency_event de cette classe (attribut privé) : propose une méthode publique à la place.
6. Garde l'alias LLMPlanParser (ou déplace-le comme prévu au prompt 2).

Autorisé : la méthode _rejection.
```

---

## Prompt 12

**Fichier cible :** `src/irobot/interfaces/voice_runtime.py`
**Fichiers liés :** `command_service.py`, `src/irobot/hardware/runtime_factory.py`, `src/irobot/hardware/audio/`

```text
Simplifie src/irobot/interfaces/voice_runtime.py.
1. Les fonctions de module ask_llm_for_intent_plan_with_trace, transcribe_loop, resolve_input_device, build_hardware_runtime et close_hardware_runtime sont des passe-plats avec import local. Vérifie pour chacune si l'import local est nécessaire (dépendances matérielles absentes hors Raspberry Pi). Si oui, garde l'import paresseux mais retire la fonction intermédiaire quand c'est possible ; sinon supprime-la. Fais une recherche de références : les tests peuvent les mocker.
2. Supprime les imports inutilisés : llm_response_format_mode, warm_up_llm_async, et post_llm_chat s'il n'est plus utilisé après le point 1. (Prompt 1 déjà fait : reset_response_format_cache n'existe plus et _post_llm_chat s'appelle désormais post_llm_chat dans voice_llm_transport.py. Le test test_voice_runtime_structure.py monkeypatche `voice_runtime.post_llm_chat` : si tu retires cet import, adapte le test pour patcher `llm_intent_parser` ou `voice_llm_transport`.)
3. VoiceRuntime._safe_stop et handle_text_as_plan sont des passe-plats vers command_service : remplace les appels par self.command_service.safe_stop() et handle_text(), sauf si un test les mocke.
4. _call_robot(method: str) appelle getattr(self.robot, nom) par chaîne : remplace par deux appels directs justifiés, en gardant le try/except et le log d'erreur.
5. `self._emergency_event = self.command_service._emergency_event` accède à un attribut privé : ne le change pas sans mon accord (lié au prompt 11).
6. Ne change pas la gestion du stop pendant une mission.
```

---

## Prompt 13

**Fichier cible :** `src/irobot/domain/orchestrator/executor.py`

```text
Simplifie src/irobot/domain/orchestrator/executor.py.
Le test `callable(validate_result) and not validate_result()` est répété 3 fois avec le même type de SkillResult d'échec : extrais-le dans une petite méthode `_supervision_fault(message)` qui retourne un SkillResult ou None.
Conserve les 3 points de contrôle (avant la validation de la skill, après elle, après execute) et leurs messages exacts.

Autorisé : la méthode _supervision_fault.
```

---

## Prompt 14

**Fichier cible :** `src/irobot/domain/skills/blackboard_state.py`
**Fichiers liés :** `base_skill.py`, `src/irobot/domain/intent.py`

```text
Simplifie src/irobot/domain/skills/blackboard_state.py.
1. KNOWN_FIELDS recopie à la main la liste des champs du dataclass : calcule-le une fois à partir de dataclasses.fields (sans "extra") pour supprimer la double maintenance.
2. __iter__ itère sur un set (ordre non déterministe) : utilise un tuple ordonné.
3. Type `active_intent: Intent | None` et `last_skill_result: SkillResult | None` au lieu de Any, avec TYPE_CHECKING pour éviter les imports circulaires.
4. Ne change pas le comportement de __getitem__, __setitem__, __delitem__ (un champ connu supprimé repasse à None).
```
