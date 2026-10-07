"""T013 move extraction tests. Values copied from pokeplatinum/res/moves/*/data.json."""

from platsim.decomp.moves import load_moves, normalise


def test_quick_attack_priority():
    m = load_moves()["MOVE_QUICK_ATTACK"]
    assert m.priority == 1  # res/moves/quick_attack/data.json:20 "priority": 1
    assert m.power == 40  # res/moves/quick_attack/data.json:12


def test_swift_never_misses():
    m = load_moves()["MOVE_SWIFT"]
    assert m.accuracy == 0  # res/moves/swift/data.json:12 "accuracy": 0
    assert m.power == 60  # res/moves/swift/data.json:11


def test_earthquake_fields():
    m = load_moves()["MOVE_EARTHQUAKE"]
    # res/moves/earthquake/data.json:2,10-24
    assert m.name == "Earthquake"
    assert m.category == "CLASS_PHYSICAL"  # :9
    assert m.type == "TYPE_GROUND"  # :10
    assert m.power == 100  # :11
    assert m.accuracy == 100  # :12
    assert m.pp == 10  # :13
    assert m.effect == "BATTLE_EFFECT_DOUBLE_DAMAGE_DIG"  # :15
    assert m.effect_chance == 0  # :16
    assert m.range == "RANGE_ALL_ADJACENT"  # :18
    assert m.priority == 0  # :19
    assert m.flags == [  # :20-24
        "MOVE_FLAG_CAN_PROTECT",
        "MOVE_FLAG_CAN_MIRROR_MOVE",
        "MOVE_FLAG_TRIGGERS_KINGS_ROCK",
    ]
    assert m.id == 89  # generated/moves.txt:90 MOVE_EARTHQUAKE (0-based line index)


def test_normalisation_rules():
    # tools/dataproc/src/moveproc.c:136-142 status power -> 0; :144-148 accuracy clamp;
    # :150-154 chance clamp. No shipped move triggers these, so test the rule directly.
    assert normalise("CLASS_STATUS", 50, 255, 200) == (0, 100, 100)
    assert normalise("CLASS_PHYSICAL", 50, 90, 30) == (50, 90, 30)


def test_count():
    # generated/moves.txt: 469 lines = MOVE_NONE + 467 moves + MAX_MOVES sentinel.
    assert len(load_moves()) == 467
