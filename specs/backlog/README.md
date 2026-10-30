# Backlog d'implémentation

Ce dossier contient le backlog opérationnel pour passer de la logique validée sur Mac (LLM + runtime + mocks) à un pilotage réel sur Raspberry Pi.

Il contient aussi une étude et un backlog distincts pour le suivi humain avec marqueur, sans modification du code à ce stade. Le backlog historique ne constitue pas un état à jour des fonctionnalités déjà livrées.

## Documents

- [01_runtime_pi_implementation_backlog.md](01_runtime_pi_implementation_backlog.md) : plan détaillé par milestones avec tickets, DoD et estimations.
- [02_runtime_pi_integration_report_template.md](02_runtime_pi_integration_report_template.md) : template prêt à remplir pour le rapport d'intégration Raspberry Pi.
- [03_pre_run_checklist_mac_to_pi.md](03_pre_run_checklist_mac_to_pi.md) : check-list opérationnelle avant passage Mac -> Pi.
- [04_standard_scenarios_protocol_mac.md](04_standard_scenarios_protocol_mac.md) : protocole de validation des scénarios standards sur Mac.
- [05_measurements_tolerance_sheet.md](05_measurements_tolerance_sheet.md) : feuille de mesure/tolérance à compléter pendant les tests terrain.
- [06_calibration_non_lineaire_pi.md](06_calibration_non_lineaire_pi.md) : optimisation différée des conversions distance/angle selon l'amplitude demandée, avec observations terrain et critères de validation.
- [07_suivi_humain_marqueur_backlog.md](07_suivi_humain_marqueur_backlog.md) : besoin « suis-moi », écarts avec le suivi de balle actuel, architecture proposée, sécurité, tickets SH-01 à SH-12 et critères de recette ; marqueur accepté, autres hypothèses à valider.
- [09_simplification_architecture_backlog.md](09_simplification_architecture_backlog.md) : étude différée des options de simplification de l'architecture, à examiner après le travail engagé sur le suivi humain.
