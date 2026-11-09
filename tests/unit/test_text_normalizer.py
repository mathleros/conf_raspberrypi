"""Non-régression de text_normalizer.preprocess (sorties figées avant refactoring)."""

from __future__ import annotations

import pytest

from irobot.app.interfaces.text_normalizer import preprocess

CASES = [
    ('avance de un mètre', 'avance de 100 centimètres'),
    ('avance de une seconde', 'avance de 1 seconde'),
    ('recule de deux mètres', 'recule de 200 centimètres'),
    ('tourne de soixante-dix degrés', 'tourne de 70 degrés'),
    ('avance de quatre-vingt-dix-sept centimètres', 'avance de 97 centimètres'),
    ('tourne de quatre-vingts degrés', 'tourne de 80 degrés'),
    ('avance de vingt et un centimètres', 'avance de 21 centimètres'),
    ('avance de vingt-deux centimètres', 'avance de 22 centimètres'),
    ('avance de trente et un centimètres', 'avance de 31 centimètres'),
    ('avance de soixante et onze centimètres', 'avance de 71 centimètres'),
    ('avance de quatre-vingt-un centimètres', 'avance de 81 centimètres'),
    ('avance de quatre-vingt-onze centimètres', 'avance de 91 centimètres'),
    ('avance de dix-sept secondes', 'avance de 17 secondes'),
    ('avance de seize secondes', 'avance de 16 secondes'),
    ('avance de zéro seconde', 'avance de 0 seconde'),
    ('avance de cent mètres', 'avance de 10000 centimètres'),
    ('avance de deux cents centimètres', 'avance de 200 centimètres'),
    ('avance de cent vingt-trois centimètres', 'avance de 123 centimètres'),
    ('avance de trois cent quarante-cinq centimètres', 'avance de 345 centimètres'),
    ('avance de mille mètres', 'avance de 100000 centimètres'),
    ('avance de deux mille cinq cents mètres', 'avance de 250000 centimètres'),
    ('avance de mille deux cent trente-quatre centimètres', 'avance de 1234 centimètres'),
    ('un robot avance', 'un robot avance'),
    ("j'ai une idée", "j' ai une idée"),
    ('avance un peu', 'avance un peu'),
    ('avance de une minute trente secondes', 'avance de 90 secondes'),
    ('avance de un mètre cinquante', 'avance de 150 centimètres'),
    ('avance de deux minutes et quinze secondes', 'avance de 135 secondes'),
    ('avance de trois et quatre', 'avance de 3 4'),
    ('avance de cinq six', 'avance de 5 6'),
    ('avance de deux trois mètres', 'avance de 2 300 centimètres'),
    ('tourne de quatre-vingt-dix degrés à gauche', 'tourne de 90 degrés à gauche'),
    ('tourne à droite', 'tourne à droite'),
    ('bonjour robot', 'bonjour robot'),
    ("avance de d'un mètre", "avance de d' 100 centimètres"),
    ('avance de 20 centimètres', 'avance de 20 centimètres'),
    ('avance de dix secondes puis tourne de quarante-cinq degrés', 'avance de 10 secondes puis tourne de 45 degrés'),
    ('recule de vingt mètres', 'recule de 2000 centimètres'),
    ('avance de soixante-quinze centimètres', 'avance de 75 centimètres'),
    ('avance de quatre-vingt-dix-neuf centimètres', 'avance de 99 centimètres'),
    ('avance de cent un centimètres', 'avance de 101 centimètres'),
    ('avance de six cents mètres', 'avance de 60000 centimètres'),
    ('', ''),
]


@pytest.mark.parametrize(("text", "expected"), CASES)
def test_preprocess_golden(text: str, expected: str) -> None:
    assert preprocess(text) == expected
