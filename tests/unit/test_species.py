"""T012 species extraction tests (SC-005: 20 species).

The EXPECTED literals below were copied out of each pokeplatinum data.json (mechanically, by a
scratch copy script, not hand-typed); every field cites `path:line`. base_stats are reordered to
hp/atk/def/spa/spd/spe from the file's hp/attack/defense/speed/special_attack/special_defense order,
and slot-2 ABILITY_NONE is written as None. `evolutions` keeps the raw array from data.json; the
array-shape semantics are asserted separately below.
"""

from platsim.decomp.species import Evolution, evolution_shapes, form_order, load_species

EXPECTED = {
    # res/pokemon/spiritomb/data.json
    'spiritomb': {
        # res/pokemon/spiritomb/data.json:2
        'base_stats': {'hp': 50, 'atk': 92, 'def': 108, 'spa': 92, 'spd': 108, 'spe': 35},
        # res/pokemon/spiritomb/data.json:10
        'types': ['TYPE_GHOST', 'TYPE_DARK'],
        # res/pokemon/spiritomb/data.json:30 (raw: ['ABILITY_PRESSURE', 'ABILITY_NONE'])
        'abilities': ['ABILITY_PRESSURE', None],
        # res/pokemon/spiritomb/data.json:28
        'exp_rate': 'EXP_RATE_MEDIUM_FAST',
        # res/pokemon/spiritomb/data.json:36
        'learnset_level': [(1, 'MOVE_CURSE'), (1, 'MOVE_PURSUIT'), (1, 'MOVE_CONFUSE_RAY'), (1, 'MOVE_SPITE'), (1, 'MOVE_SHADOW_SNEAK'), (7, 'MOVE_FAINT_ATTACK'), (13, 'MOVE_HYPNOSIS'), (19, 'MOVE_DREAM_EATER'), (25, 'MOVE_OMINOUS_WIND'), (31, 'MOVE_SUCKER_PUNCH'), (37, 'MOVE_NASTY_PLOT'), (43, 'MOVE_MEMENTO'), (49, 'MOVE_DARK_PULSE')],
        # res/pokemon/spiritomb/data.json:51
        'learnset_tm': ['TM03', 'TM04', 'TM06', 'TM10', 'TM11', 'TM12', 'TM15', 'TM17', 'TM18', 'TM21', 'TM27', 'TM29', 'TM30', 'TM32', 'TM34', 'TM39', 'TM41', 'TM42', 'TM43', 'TM44', 'TM45', 'TM46', 'TM49', 'TM58', 'TM61', 'TM62', 'TM63', 'TM68', 'TM70', 'TM77', 'TM78', 'TM79', 'TM82', 'TM83', 'TM85', 'TM87', 'TM90'],
        # res/pokemon/spiritomb/data.json:90
        'learnset_tutor': ['MOVE_ICY_WIND', 'MOVE_OMINOUS_WIND', 'MOVE_SNORE', 'MOVE_SPITE', 'MOVE_TRICK', 'MOVE_SUCKER_PUNCH', 'MOVE_UPROAR'],
        # res/pokemon/spiritomb/data.json:99
        'egg_moves': ['MOVE_DESTINY_BOND', 'MOVE_PAIN_SPLIT', 'MOVE_SMOKE_SCREEN', 'MOVE_IMPRISON', 'MOVE_GRUDGE', 'MOVE_SHADOW_SNEAK'],
        # res/pokemon/spiritomb/data.json:108
        'evolutions': [],
    },
    # res/pokemon/roserade/data.json
    'roserade': {
        # res/pokemon/roserade/data.json:2
        'base_stats': {'hp': 60, 'atk': 70, 'def': 55, 'spa': 125, 'spd': 105, 'spe': 90},
        # res/pokemon/roserade/data.json:10
        'types': ['TYPE_GRASS', 'TYPE_POISON'],
        # res/pokemon/roserade/data.json:30 (raw: ['ABILITY_NATURAL_CURE', 'ABILITY_POISON_POINT'])
        'abilities': ['ABILITY_NATURAL_CURE', 'ABILITY_POISON_POINT'],
        # res/pokemon/roserade/data.json:28
        'exp_rate': 'EXP_RATE_MEDIUM_SLOW',
        # res/pokemon/roserade/data.json:36
        'learnset_level': [(1, 'MOVE_WEATHER_BALL'), (1, 'MOVE_POISON_STING'), (1, 'MOVE_MEGA_DRAIN'), (1, 'MOVE_MAGICAL_LEAF'), (1, 'MOVE_SWEET_SCENT')],
        # res/pokemon/roserade/data.json:43
        'learnset_tm': ['TM06', 'TM09', 'TM10', 'TM11', 'TM15', 'TM17', 'TM18', 'TM19', 'TM21', 'TM22', 'TM27', 'TM30', 'TM32', 'TM36', 'TM42', 'TM43', 'TM44', 'TM45', 'TM53', 'TM58', 'TM68', 'TM70', 'TM75', 'TM77', 'TM78', 'TM82', 'TM83', 'TM84', 'TM86', 'TM87', 'TM90', 'HM01'],
        # res/pokemon/roserade/data.json:77
        'learnset_tutor': ['MOVE_MUD_SLAP', 'MOVE_FURY_CUTTER', 'MOVE_SNORE', 'MOVE_SYNTHESIS', 'MOVE_SEED_BOMB', 'MOVE_SWIFT'],
        'egg_moves': [],
        # res/pokemon/roserade/data.json:86
        'evolutions': [],
    },
    # res/pokemon/togekiss/data.json
    'togekiss': {
        # res/pokemon/togekiss/data.json:2
        'base_stats': {'hp': 85, 'atk': 50, 'def': 95, 'spa': 120, 'spd': 115, 'spe': 80},
        # res/pokemon/togekiss/data.json:10
        'types': ['TYPE_NORMAL', 'TYPE_FLYING'],
        # res/pokemon/togekiss/data.json:30 (raw: ['ABILITY_HUSTLE', 'ABILITY_SERENE_GRACE'])
        'abilities': ['ABILITY_HUSTLE', 'ABILITY_SERENE_GRACE'],
        # res/pokemon/togekiss/data.json:28
        'exp_rate': 'EXP_RATE_FAST',
        # res/pokemon/togekiss/data.json:36
        'learnset_level': [(1, 'MOVE_SKY_ATTACK'), (1, 'MOVE_EXTREME_SPEED'), (1, 'MOVE_AURA_SPHERE'), (1, 'MOVE_AIR_SLASH')],
        # res/pokemon/togekiss/data.json:42
        'learnset_tm': ['TM01', 'TM03', 'TM06', 'TM10', 'TM11', 'TM15', 'TM16', 'TM17', 'TM18', 'TM20', 'TM21', 'TM22', 'TM27', 'TM29', 'TM30', 'TM31', 'TM32', 'TM33', 'TM34', 'TM35', 'TM38', 'TM40', 'TM42', 'TM43', 'TM44', 'TM45', 'TM47', 'TM51', 'TM56', 'TM58', 'TM60', 'TM62', 'TM68', 'TM70', 'TM73', 'TM77', 'TM78', 'TM82', 'TM83', 'TM85', 'TM86', 'TM87', 'TM88', 'TM90', 'HM02', 'HM05', 'HM06'],
        # res/pokemon/togekiss/data.json:91
        'learnset_tutor': ['MOVE_MUD_SLAP', 'MOVE_ROLLOUT', 'MOVE_OMINOUS_WIND', 'MOVE_SNORE', 'MOVE_AIR_CUTTER', 'MOVE_ENDEAVOR', 'MOVE_ANCIENT_POWER', 'MOVE_SIGNAL_BEAM', 'MOVE_ZEN_HEADBUTT', 'MOVE_TWISTER', 'MOVE_LAST_RESORT', 'MOVE_TRICK', 'MOVE_HEAT_WAVE', 'MOVE_SWIFT'],
        'egg_moves': [],
        # res/pokemon/togekiss/data.json:108
        'evolutions': [],
    },
    # res/pokemon/lucario/data.json
    'lucario': {
        # res/pokemon/lucario/data.json:2
        'base_stats': {'hp': 70, 'atk': 110, 'def': 70, 'spa': 115, 'spd': 70, 'spe': 90},
        # res/pokemon/lucario/data.json:10
        'types': ['TYPE_FIGHTING', 'TYPE_STEEL'],
        # res/pokemon/lucario/data.json:30 (raw: ['ABILITY_STEADFAST', 'ABILITY_INNER_FOCUS'])
        'abilities': ['ABILITY_STEADFAST', 'ABILITY_INNER_FOCUS'],
        # res/pokemon/lucario/data.json:28
        'exp_rate': 'EXP_RATE_MEDIUM_SLOW',
        # res/pokemon/lucario/data.json:36
        'learnset_level': [(1, 'MOVE_DARK_PULSE'), (1, 'MOVE_QUICK_ATTACK'), (1, 'MOVE_FORESIGHT'), (1, 'MOVE_DETECT'), (1, 'MOVE_METAL_CLAW'), (6, 'MOVE_COUNTER'), (11, 'MOVE_FORCE_PALM'), (15, 'MOVE_FEINT'), (19, 'MOVE_BONE_RUSH'), (24, 'MOVE_METAL_SOUND'), (29, 'MOVE_ME_FIRST'), (33, 'MOVE_SWORDS_DANCE'), (37, 'MOVE_AURA_SPHERE'), (42, 'MOVE_CLOSE_COMBAT'), (47, 'MOVE_DRAGON_PULSE'), (51, 'MOVE_EXTREME_SPEED')],
        # res/pokemon/lucario/data.json:54
        'learnset_tm': ['TM01', 'TM03', 'TM04', 'TM05', 'TM06', 'TM08', 'TM10', 'TM11', 'TM15', 'TM17', 'TM18', 'TM21', 'TM23', 'TM26', 'TM27', 'TM28', 'TM29', 'TM30', 'TM31', 'TM32', 'TM39', 'TM42', 'TM43', 'TM44', 'TM45', 'TM52', 'TM56', 'TM58', 'TM59', 'TM60', 'TM65', 'TM66', 'TM68', 'TM71', 'TM75', 'TM78', 'TM79', 'TM80', 'TM82', 'TM83', 'TM84', 'TM87', 'TM90', 'TM91', 'HM04', 'HM06', 'HM08'],
        # res/pokemon/lucario/data.json:103
        'learnset_tutor': ['MOVE_MUD_SLAP', 'MOVE_FURY_CUTTER', 'MOVE_THUNDER_PUNCH', 'MOVE_ICE_PUNCH', 'MOVE_SNORE', 'MOVE_HELPING_HAND', 'MOVE_ZEN_HEADBUTT', 'MOVE_VACUUM_WAVE', 'MOVE_IRON_DEFENSE', 'MOVE_MAGNET_RISE', 'MOVE_SWIFT'],
        'egg_moves': [],
        # res/pokemon/lucario/data.json:117
        'evolutions': [],
    },
    # res/pokemon/milotic/data.json
    'milotic': {
        # res/pokemon/milotic/data.json:2
        'base_stats': {'hp': 95, 'atk': 60, 'def': 79, 'spa': 100, 'spd': 125, 'spe': 81},
        # res/pokemon/milotic/data.json:10
        'types': ['TYPE_WATER', 'TYPE_WATER'],
        # res/pokemon/milotic/data.json:30 (raw: ['ABILITY_MARVEL_SCALE', 'ABILITY_NONE'])
        'abilities': ['ABILITY_MARVEL_SCALE', None],
        # res/pokemon/milotic/data.json:28
        'exp_rate': 'EXP_RATE_ERRATIC',
        # res/pokemon/milotic/data.json:36
        'learnset_level': [(1, 'MOVE_WATER_GUN'), (1, 'MOVE_WRAP'), (5, 'MOVE_WATER_SPORT'), (9, 'MOVE_REFRESH'), (13, 'MOVE_WATER_PULSE'), (17, 'MOVE_TWISTER'), (21, 'MOVE_RECOVER'), (25, 'MOVE_CAPTIVATE'), (29, 'MOVE_AQUA_TAIL'), (33, 'MOVE_RAIN_DANCE'), (37, 'MOVE_HYDRO_PUMP'), (41, 'MOVE_ATTRACT'), (45, 'MOVE_SAFEGUARD'), (49, 'MOVE_AQUA_RING')],
        # res/pokemon/milotic/data.json:52
        'learnset_tm': ['TM03', 'TM06', 'TM07', 'TM10', 'TM13', 'TM14', 'TM15', 'TM17', 'TM18', 'TM20', 'TM21', 'TM23', 'TM27', 'TM32', 'TM42', 'TM43', 'TM44', 'TM45', 'TM58', 'TM59', 'TM68', 'TM72', 'TM77', 'TM78', 'TM82', 'TM83', 'TM87', 'TM90', 'HM03', 'HM07'],
        # res/pokemon/milotic/data.json:84
        'learnset_tutor': ['MOVE_DIVE', 'MOVE_MUD_SLAP', 'MOVE_ICY_WIND', 'MOVE_IRON_HEAD', 'MOVE_AQUA_TAIL', 'MOVE_SNORE', 'MOVE_TWISTER', 'MOVE_SWIFT'],
        'egg_moves': [],
        # res/pokemon/milotic/data.json:95
        'evolutions': [],
    },
    # res/pokemon/garchomp/data.json
    'garchomp': {
        # res/pokemon/garchomp/data.json:2
        'base_stats': {'hp': 108, 'atk': 130, 'def': 95, 'spa': 80, 'spd': 85, 'spe': 102},
        # res/pokemon/garchomp/data.json:10
        'types': ['TYPE_DRAGON', 'TYPE_GROUND'],
        # res/pokemon/garchomp/data.json:30 (raw: ['ABILITY_SAND_VEIL', 'ABILITY_NONE'])
        'abilities': ['ABILITY_SAND_VEIL', None],
        # res/pokemon/garchomp/data.json:28
        'exp_rate': 'EXP_RATE_SLOW',
        # res/pokemon/garchomp/data.json:36
        'learnset_level': [(1, 'MOVE_FIRE_FANG'), (1, 'MOVE_TACKLE'), (1, 'MOVE_SAND_ATTACK'), (1, 'MOVE_DRAGON_RAGE'), (1, 'MOVE_SANDSTORM'), (3, 'MOVE_SAND_ATTACK'), (7, 'MOVE_DRAGON_RAGE'), (13, 'MOVE_SANDSTORM'), (15, 'MOVE_TAKE_DOWN'), (19, 'MOVE_SAND_TOMB'), (28, 'MOVE_SLASH'), (33, 'MOVE_DRAGON_CLAW'), (40, 'MOVE_DIG'), (48, 'MOVE_CRUNCH'), (55, 'MOVE_DRAGON_RUSH')],
        # res/pokemon/garchomp/data.json:53
        'learnset_tm': ['TM02', 'TM05', 'TM06', 'TM10', 'TM11', 'TM15', 'TM17', 'TM18', 'TM21', 'TM23', 'TM26', 'TM27', 'TM28', 'TM31', 'TM32', 'TM35', 'TM37', 'TM38', 'TM39', 'TM40', 'TM42', 'TM43', 'TM44', 'TM45', 'TM54', 'TM56', 'TM58', 'TM59', 'TM65', 'TM68', 'TM71', 'TM75', 'TM76', 'TM78', 'TM80', 'TM82', 'TM83', 'TM84', 'TM87', 'TM90', 'HM01', 'HM03', 'HM04', 'HM06', 'HM08'],
        # res/pokemon/garchomp/data.json:100
        'learnset_tutor': ['MOVE_MUD_SLAP', 'MOVE_FURY_CUTTER', 'MOVE_IRON_HEAD', 'MOVE_AQUA_TAIL', 'MOVE_SNORE', 'MOVE_OUTRAGE', 'MOVE_EARTH_POWER', 'MOVE_TWISTER', 'MOVE_SWIFT'],
        'egg_moves': [],
        # res/pokemon/garchomp/data.json:112
        'evolutions': [],
    },
    # res/pokemon/gible/data.json
    'gible': {
        # res/pokemon/gible/data.json:2
        'base_stats': {'hp': 58, 'atk': 70, 'def': 45, 'spa': 40, 'spd': 45, 'spe': 42},
        # res/pokemon/gible/data.json:10
        'types': ['TYPE_DRAGON', 'TYPE_GROUND'],
        # res/pokemon/gible/data.json:30 (raw: ['ABILITY_SAND_VEIL', 'ABILITY_NONE'])
        'abilities': ['ABILITY_SAND_VEIL', None],
        # res/pokemon/gible/data.json:28
        'exp_rate': 'EXP_RATE_SLOW',
        # res/pokemon/gible/data.json:36
        'learnset_level': [(1, 'MOVE_TACKLE'), (3, 'MOVE_SAND_ATTACK'), (7, 'MOVE_DRAGON_RAGE'), (13, 'MOVE_SANDSTORM'), (15, 'MOVE_TAKE_DOWN'), (19, 'MOVE_SAND_TOMB'), (25, 'MOVE_SLASH'), (27, 'MOVE_DRAGON_CLAW'), (31, 'MOVE_DIG'), (37, 'MOVE_DRAGON_RUSH')],
        # res/pokemon/gible/data.json:48
        'learnset_tm': ['TM02', 'TM05', 'TM06', 'TM10', 'TM11', 'TM17', 'TM18', 'TM21', 'TM26', 'TM27', 'TM28', 'TM32', 'TM35', 'TM37', 'TM38', 'TM39', 'TM40', 'TM42', 'TM43', 'TM44', 'TM45', 'TM58', 'TM59', 'TM65', 'TM71', 'TM76', 'TM78', 'TM80', 'TM82', 'TM83', 'TM87', 'TM90', 'HM01', 'HM04', 'HM06', 'HM08'],
        # res/pokemon/gible/data.json:86
        'learnset_tutor': ['MOVE_MUD_SLAP', 'MOVE_FURY_CUTTER', 'MOVE_IRON_HEAD', 'MOVE_SNORE', 'MOVE_OUTRAGE', 'MOVE_EARTH_POWER', 'MOVE_TWISTER', 'MOVE_SWIFT'],
        # res/pokemon/gible/data.json:96
        'egg_moves': ['MOVE_DRAGON_BREATH', 'MOVE_OUTRAGE', 'MOVE_TWISTER', 'MOVE_SCARY_FACE', 'MOVE_DOUBLE_EDGE', 'MOVE_THRASH', 'MOVE_METAL_CLAW', 'MOVE_SAND_TOMB', 'MOVE_BODY_SLAM', 'MOVE_IRON_HEAD'],
        # res/pokemon/gible/data.json:109
        'evolutions': [['EVO_LEVEL', 24, 'SPECIES_GABITE']],
    },
    # res/pokemon/gabite/data.json
    'gabite': {
        # res/pokemon/gabite/data.json:2
        'base_stats': {'hp': 68, 'atk': 90, 'def': 65, 'spa': 50, 'spd': 55, 'spe': 82},
        # res/pokemon/gabite/data.json:10
        'types': ['TYPE_DRAGON', 'TYPE_GROUND'],
        # res/pokemon/gabite/data.json:30 (raw: ['ABILITY_SAND_VEIL', 'ABILITY_NONE'])
        'abilities': ['ABILITY_SAND_VEIL', None],
        # res/pokemon/gabite/data.json:28
        'exp_rate': 'EXP_RATE_SLOW',
        # res/pokemon/gabite/data.json:36
        'learnset_level': [(1, 'MOVE_TACKLE'), (1, 'MOVE_SAND_ATTACK'), (3, 'MOVE_SAND_ATTACK'), (7, 'MOVE_DRAGON_RAGE'), (13, 'MOVE_SANDSTORM'), (15, 'MOVE_TAKE_DOWN'), (19, 'MOVE_SAND_TOMB'), (28, 'MOVE_SLASH'), (33, 'MOVE_DRAGON_CLAW'), (40, 'MOVE_DIG'), (49, 'MOVE_DRAGON_RUSH')],
        # res/pokemon/gabite/data.json:49
        'learnset_tm': ['TM02', 'TM05', 'TM06', 'TM10', 'TM11', 'TM17', 'TM18', 'TM21', 'TM23', 'TM26', 'TM27', 'TM28', 'TM32', 'TM35', 'TM37', 'TM38', 'TM39', 'TM40', 'TM42', 'TM43', 'TM44', 'TM45', 'TM58', 'TM59', 'TM65', 'TM71', 'TM76', 'TM78', 'TM80', 'TM82', 'TM83', 'TM87', 'TM90', 'HM01', 'HM04', 'HM06', 'HM08'],
        # res/pokemon/gabite/data.json:88
        'learnset_tutor': ['MOVE_MUD_SLAP', 'MOVE_FURY_CUTTER', 'MOVE_IRON_HEAD', 'MOVE_SNORE', 'MOVE_OUTRAGE', 'MOVE_EARTH_POWER', 'MOVE_TWISTER', 'MOVE_SWIFT'],
        'egg_moves': [],
        # res/pokemon/gabite/data.json:99
        'evolutions': [['EVO_LEVEL', 48, 'SPECIES_GARCHOMP']],
    },
    # res/pokemon/bulbasaur/data.json
    'bulbasaur': {
        # res/pokemon/bulbasaur/data.json:2
        'base_stats': {'hp': 45, 'atk': 49, 'def': 49, 'spa': 65, 'spd': 65, 'spe': 45},
        # res/pokemon/bulbasaur/data.json:10
        'types': ['TYPE_GRASS', 'TYPE_POISON'],
        # res/pokemon/bulbasaur/data.json:30 (raw: ['ABILITY_OVERGROW', 'ABILITY_NONE'])
        'abilities': ['ABILITY_OVERGROW', None],
        # res/pokemon/bulbasaur/data.json:28
        'exp_rate': 'EXP_RATE_MEDIUM_SLOW',
        # res/pokemon/bulbasaur/data.json:36
        'learnset_level': [(1, 'MOVE_TACKLE'), (3, 'MOVE_GROWL'), (7, 'MOVE_LEECH_SEED'), (9, 'MOVE_VINE_WHIP'), (13, 'MOVE_POISON_POWDER'), (13, 'MOVE_SLEEP_POWDER'), (15, 'MOVE_TAKE_DOWN'), (19, 'MOVE_RAZOR_LEAF'), (21, 'MOVE_SWEET_SCENT'), (25, 'MOVE_GROWTH'), (27, 'MOVE_DOUBLE_EDGE'), (31, 'MOVE_WORRY_SEED'), (33, 'MOVE_SYNTHESIS'), (37, 'MOVE_SEED_BOMB')],
        # res/pokemon/bulbasaur/data.json:52
        'learnset_tm': ['TM06', 'TM09', 'TM10', 'TM11', 'TM17', 'TM19', 'TM21', 'TM22', 'TM27', 'TM32', 'TM36', 'TM42', 'TM43', 'TM44', 'TM45', 'TM53', 'TM58', 'TM70', 'TM75', 'TM78', 'TM82', 'TM83', 'TM86', 'TM87', 'TM90', 'HM01', 'HM04', 'HM06'],
        # res/pokemon/bulbasaur/data.json:82
        'learnset_tutor': ['MOVE_MUD_SLAP', 'MOVE_FURY_CUTTER', 'MOVE_SNORE', 'MOVE_SYNTHESIS', 'MOVE_SEED_BOMB', 'MOVE_KNOCK_OFF'],
        # res/pokemon/bulbasaur/data.json:90
        'egg_moves': ['MOVE_LIGHT_SCREEN', 'MOVE_SKULL_BASH', 'MOVE_SAFEGUARD', 'MOVE_CHARM', 'MOVE_PETAL_DANCE', 'MOVE_MAGICAL_LEAF', 'MOVE_GRASS_WHISTLE', 'MOVE_CURSE', 'MOVE_INGRAIN', 'MOVE_NATURE_POWER', 'MOVE_AMNESIA', 'MOVE_LEAF_STORM'],
        # res/pokemon/bulbasaur/data.json:105
        'evolutions': [['EVO_LEVEL', 16, 'SPECIES_IVYSAUR']],
    },
    # res/pokemon/kadabra/data.json
    'kadabra': {
        # res/pokemon/kadabra/data.json:2
        'base_stats': {'hp': 40, 'atk': 35, 'def': 30, 'spa': 120, 'spd': 70, 'spe': 105},
        # res/pokemon/kadabra/data.json:10
        'types': ['TYPE_PSYCHIC', 'TYPE_PSYCHIC'],
        # res/pokemon/kadabra/data.json:30 (raw: ['ABILITY_SYNCHRONIZE', 'ABILITY_INNER_FOCUS'])
        'abilities': ['ABILITY_SYNCHRONIZE', 'ABILITY_INNER_FOCUS'],
        # res/pokemon/kadabra/data.json:28
        'exp_rate': 'EXP_RATE_MEDIUM_SLOW',
        # res/pokemon/kadabra/data.json:36
        'learnset_level': [(1, 'MOVE_TELEPORT'), (1, 'MOVE_KINESIS'), (1, 'MOVE_CONFUSION'), (16, 'MOVE_CONFUSION'), (18, 'MOVE_DISABLE'), (22, 'MOVE_MIRACLE_EYE'), (24, 'MOVE_PSYBEAM'), (28, 'MOVE_REFLECT'), (30, 'MOVE_RECOVER'), (34, 'MOVE_PSYCHO_CUT'), (36, 'MOVE_ROLE_PLAY'), (40, 'MOVE_PSYCHIC'), (42, 'MOVE_FUTURE_SIGHT'), (46, 'MOVE_TRICK')],
        # res/pokemon/kadabra/data.json:52
        'learnset_tm': ['TM01', 'TM04', 'TM06', 'TM10', 'TM11', 'TM12', 'TM16', 'TM17', 'TM18', 'TM20', 'TM21', 'TM23', 'TM27', 'TM29', 'TM30', 'TM32', 'TM33', 'TM34', 'TM41', 'TM42', 'TM43', 'TM44', 'TM45', 'TM46', 'TM48', 'TM49', 'TM53', 'TM56', 'TM57', 'TM58', 'TM60', 'TM63', 'TM67', 'TM70', 'TM73', 'TM77', 'TM78', 'TM82', 'TM83', 'TM85', 'TM86', 'TM87', 'TM90', 'TM92'],
        # res/pokemon/kadabra/data.json:98
        'learnset_tutor': ['MOVE_THUNDER_PUNCH', 'MOVE_FIRE_PUNCH', 'MOVE_ICE_PUNCH', 'MOVE_SNORE', 'MOVE_SIGNAL_BEAM', 'MOVE_ZEN_HEADBUTT', 'MOVE_TRICK', 'MOVE_KNOCK_OFF'],
        'egg_moves': [],
        # res/pokemon/kadabra/data.json:109
        'evolutions': [['EVO_TRADE', 'SPECIES_ALAKAZAM']],
    },
    # res/pokemon/alakazam/data.json
    'alakazam': {
        # res/pokemon/alakazam/data.json:2
        'base_stats': {'hp': 55, 'atk': 50, 'def': 45, 'spa': 135, 'spd': 85, 'spe': 120},
        # res/pokemon/alakazam/data.json:10
        'types': ['TYPE_PSYCHIC', 'TYPE_PSYCHIC'],
        # res/pokemon/alakazam/data.json:30 (raw: ['ABILITY_SYNCHRONIZE', 'ABILITY_INNER_FOCUS'])
        'abilities': ['ABILITY_SYNCHRONIZE', 'ABILITY_INNER_FOCUS'],
        # res/pokemon/alakazam/data.json:28
        'exp_rate': 'EXP_RATE_MEDIUM_SLOW',
        # res/pokemon/alakazam/data.json:36
        'learnset_level': [(1, 'MOVE_TELEPORT'), (1, 'MOVE_KINESIS'), (1, 'MOVE_CONFUSION'), (16, 'MOVE_CONFUSION'), (18, 'MOVE_DISABLE'), (22, 'MOVE_MIRACLE_EYE'), (24, 'MOVE_PSYBEAM'), (28, 'MOVE_REFLECT'), (30, 'MOVE_RECOVER'), (34, 'MOVE_PSYCHO_CUT'), (36, 'MOVE_CALM_MIND'), (40, 'MOVE_PSYCHIC'), (42, 'MOVE_FUTURE_SIGHT'), (46, 'MOVE_TRICK')],
        # res/pokemon/alakazam/data.json:52
        'learnset_tm': ['TM01', 'TM04', 'TM06', 'TM10', 'TM11', 'TM12', 'TM15', 'TM16', 'TM17', 'TM18', 'TM20', 'TM21', 'TM23', 'TM27', 'TM29', 'TM30', 'TM32', 'TM33', 'TM34', 'TM41', 'TM42', 'TM43', 'TM44', 'TM45', 'TM46', 'TM48', 'TM49', 'TM52', 'TM53', 'TM56', 'TM57', 'TM58', 'TM60', 'TM63', 'TM67', 'TM68', 'TM70', 'TM73', 'TM77', 'TM78', 'TM82', 'TM83', 'TM85', 'TM86', 'TM87', 'TM90', 'TM92'],
        # res/pokemon/alakazam/data.json:101
        'learnset_tutor': ['MOVE_THUNDER_PUNCH', 'MOVE_FIRE_PUNCH', 'MOVE_ICE_PUNCH', 'MOVE_SNORE', 'MOVE_SIGNAL_BEAM', 'MOVE_ZEN_HEADBUTT', 'MOVE_TRICK', 'MOVE_KNOCK_OFF'],
        'egg_moves': [],
        # res/pokemon/alakazam/data.json:112
        'evolutions': [],
    },
    # res/pokemon/onix/data.json
    'onix': {
        # res/pokemon/onix/data.json:2
        'base_stats': {'hp': 35, 'atk': 45, 'def': 160, 'spa': 30, 'spd': 45, 'spe': 70},
        # res/pokemon/onix/data.json:10
        'types': ['TYPE_ROCK', 'TYPE_GROUND'],
        # res/pokemon/onix/data.json:30 (raw: ['ABILITY_ROCK_HEAD', 'ABILITY_STURDY'])
        'abilities': ['ABILITY_ROCK_HEAD', 'ABILITY_STURDY'],
        # res/pokemon/onix/data.json:28
        'exp_rate': 'EXP_RATE_MEDIUM_FAST',
        # res/pokemon/onix/data.json:36
        'learnset_level': [(1, 'MOVE_MUD_SPORT'), (1, 'MOVE_TACKLE'), (1, 'MOVE_HARDEN'), (1, 'MOVE_BIND'), (6, 'MOVE_SCREECH'), (9, 'MOVE_ROCK_THROW'), (14, 'MOVE_RAGE'), (17, 'MOVE_ROCK_TOMB'), (22, 'MOVE_SANDSTORM'), (25, 'MOVE_SLAM'), (30, 'MOVE_ROCK_POLISH'), (33, 'MOVE_DRAGON_BREATH'), (38, 'MOVE_CURSE'), (41, 'MOVE_IRON_TAIL'), (46, 'MOVE_SAND_TOMB'), (49, 'MOVE_DOUBLE_EDGE'), (54, 'MOVE_STONE_EDGE')],
        # res/pokemon/onix/data.json:55
        'learnset_tm': ['TM05', 'TM06', 'TM10', 'TM11', 'TM12', 'TM17', 'TM21', 'TM23', 'TM26', 'TM27', 'TM28', 'TM32', 'TM37', 'TM39', 'TM41', 'TM42', 'TM43', 'TM44', 'TM45', 'TM58', 'TM59', 'TM64', 'TM66', 'TM69', 'TM71', 'TM74', 'TM76', 'TM77', 'TM78', 'TM80', 'TM82', 'TM83', 'TM87', 'TM90', 'TM91', 'HM04', 'HM06', 'HM08'],
        # res/pokemon/onix/data.json:95
        'learnset_tutor': ['MOVE_MUD_SLAP', 'MOVE_ROLLOUT', 'MOVE_IRON_HEAD', 'MOVE_SNORE', 'MOVE_ANCIENT_POWER', 'MOVE_EARTH_POWER', 'MOVE_TWISTER'],
        # res/pokemon/onix/data.json:104
        'egg_moves': ['MOVE_ROCK_SLIDE', 'MOVE_FLAIL', 'MOVE_EXPLOSION', 'MOVE_BLOCK', 'MOVE_DEFENSE_CURL', 'MOVE_ROLLOUT', 'MOVE_ROCK_BLAST'],
        # res/pokemon/onix/data.json:114
        'evolutions': [['EVO_TRADE_WITH_HELD_ITEM', 'ITEM_METAL_COAT', 'SPECIES_STEELIX']],
    },
    # res/pokemon/steelix/data.json
    'steelix': {
        # res/pokemon/steelix/data.json:2
        'base_stats': {'hp': 75, 'atk': 85, 'def': 200, 'spa': 55, 'spd': 65, 'spe': 30},
        # res/pokemon/steelix/data.json:10
        'types': ['TYPE_STEEL', 'TYPE_GROUND'],
        # res/pokemon/steelix/data.json:30 (raw: ['ABILITY_ROCK_HEAD', 'ABILITY_STURDY'])
        'abilities': ['ABILITY_ROCK_HEAD', 'ABILITY_STURDY'],
        # res/pokemon/steelix/data.json:28
        'exp_rate': 'EXP_RATE_MEDIUM_FAST',
        # res/pokemon/steelix/data.json:36
        'learnset_level': [(1, 'MOVE_THUNDER_FANG'), (1, 'MOVE_ICE_FANG'), (1, 'MOVE_FIRE_FANG'), (1, 'MOVE_MUD_SPORT'), (1, 'MOVE_TACKLE'), (1, 'MOVE_HARDEN'), (1, 'MOVE_BIND'), (6, 'MOVE_SCREECH'), (9, 'MOVE_ROCK_THROW'), (14, 'MOVE_RAGE'), (17, 'MOVE_ROCK_TOMB'), (22, 'MOVE_SANDSTORM'), (25, 'MOVE_SLAM'), (30, 'MOVE_ROCK_POLISH'), (33, 'MOVE_DRAGON_BREATH'), (38, 'MOVE_CURSE'), (41, 'MOVE_IRON_TAIL'), (46, 'MOVE_CRUNCH'), (49, 'MOVE_DOUBLE_EDGE'), (54, 'MOVE_STONE_EDGE')],
        # res/pokemon/steelix/data.json:58
        'learnset_tm': ['TM05', 'TM06', 'TM10', 'TM11', 'TM12', 'TM15', 'TM17', 'TM21', 'TM23', 'TM26', 'TM27', 'TM28', 'TM32', 'TM37', 'TM39', 'TM41', 'TM42', 'TM43', 'TM44', 'TM45', 'TM58', 'TM59', 'TM64', 'TM66', 'TM68', 'TM69', 'TM71', 'TM74', 'TM76', 'TM77', 'TM78', 'TM79', 'TM80', 'TM82', 'TM83', 'TM87', 'TM90', 'TM91', 'HM01', 'HM04', 'HM06', 'HM08'],
        # res/pokemon/steelix/data.json:102
        'learnset_tutor': ['MOVE_MUD_SLAP', 'MOVE_ROLLOUT', 'MOVE_IRON_HEAD', 'MOVE_AQUA_TAIL', 'MOVE_SNORE', 'MOVE_ANCIENT_POWER', 'MOVE_EARTH_POWER', 'MOVE_TWISTER', 'MOVE_MAGNET_RISE'],
        'egg_moves': [],
        # res/pokemon/steelix/data.json:114
        'evolutions': [],
    },
    # res/pokemon/piloswine/data.json
    'piloswine': {
        # res/pokemon/piloswine/data.json:2
        'base_stats': {'hp': 100, 'atk': 100, 'def': 80, 'spa': 60, 'spd': 60, 'spe': 50},
        # res/pokemon/piloswine/data.json:10
        'types': ['TYPE_ICE', 'TYPE_GROUND'],
        # res/pokemon/piloswine/data.json:30 (raw: ['ABILITY_OBLIVIOUS', 'ABILITY_SNOW_CLOAK'])
        'abilities': ['ABILITY_OBLIVIOUS', 'ABILITY_SNOW_CLOAK'],
        # res/pokemon/piloswine/data.json:28
        'exp_rate': 'EXP_RATE_SLOW',
        # res/pokemon/piloswine/data.json:36
        'learnset_level': [(1, 'MOVE_ANCIENT_POWER'), (1, 'MOVE_PECK'), (1, 'MOVE_ODOR_SLEUTH'), (1, 'MOVE_MUD_SPORT'), (1, 'MOVE_POWDER_SNOW'), (4, 'MOVE_MUD_SPORT'), (8, 'MOVE_POWDER_SNOW'), (13, 'MOVE_MUD_SLAP'), (16, 'MOVE_ENDURE'), (20, 'MOVE_MUD_BOMB'), (25, 'MOVE_ICY_WIND'), (28, 'MOVE_ICE_FANG'), (32, 'MOVE_TAKE_DOWN'), (33, 'MOVE_FURY_ATTACK'), (40, 'MOVE_EARTHQUAKE'), (48, 'MOVE_MIST'), (56, 'MOVE_BLIZZARD'), (65, 'MOVE_AMNESIA')],
        # res/pokemon/piloswine/data.json:56
        'learnset_tm': ['TM05', 'TM06', 'TM07', 'TM10', 'TM13', 'TM14', 'TM15', 'TM16', 'TM17', 'TM18', 'TM21', 'TM26', 'TM27', 'TM28', 'TM32', 'TM33', 'TM37', 'TM39', 'TM42', 'TM43', 'TM44', 'TM45', 'TM58', 'TM68', 'TM71', 'TM72', 'TM76', 'TM78', 'TM80', 'TM82', 'TM83', 'TM87', 'TM90', 'HM04', 'HM06'],
        # res/pokemon/piloswine/data.json:93
        'learnset_tutor': ['MOVE_MUD_SLAP', 'MOVE_ICY_WIND', 'MOVE_SUPERPOWER', 'MOVE_SNORE', 'MOVE_ENDEAVOR', 'MOVE_ANCIENT_POWER', 'MOVE_EARTH_POWER'],
        'egg_moves': [],
        # res/pokemon/piloswine/data.json:103
        'evolutions': [['EVO_LEVEL_KNOW_MOVE', 'MOVE_ANCIENT_POWER', 'SPECIES_MAMOSWINE']],
    },
    # res/pokemon/mamoswine/data.json
    'mamoswine': {
        # res/pokemon/mamoswine/data.json:2
        'base_stats': {'hp': 110, 'atk': 130, 'def': 80, 'spa': 70, 'spd': 60, 'spe': 80},
        # res/pokemon/mamoswine/data.json:10
        'types': ['TYPE_ICE', 'TYPE_GROUND'],
        # res/pokemon/mamoswine/data.json:30 (raw: ['ABILITY_OBLIVIOUS', 'ABILITY_SNOW_CLOAK'])
        'abilities': ['ABILITY_OBLIVIOUS', 'ABILITY_SNOW_CLOAK'],
        # res/pokemon/mamoswine/data.json:28
        'exp_rate': 'EXP_RATE_SLOW',
        # res/pokemon/mamoswine/data.json:36
        'learnset_level': [(1, 'MOVE_ANCIENT_POWER'), (1, 'MOVE_PECK'), (1, 'MOVE_ODOR_SLEUTH'), (1, 'MOVE_MUD_SPORT'), (1, 'MOVE_POWDER_SNOW'), (4, 'MOVE_MUD_SPORT'), (8, 'MOVE_POWDER_SNOW'), (13, 'MOVE_MUD_SLAP'), (16, 'MOVE_ENDURE'), (20, 'MOVE_MUD_BOMB'), (25, 'MOVE_HAIL'), (28, 'MOVE_ICE_FANG'), (32, 'MOVE_TAKE_DOWN'), (33, 'MOVE_DOUBLE_HIT'), (40, 'MOVE_EARTHQUAKE'), (48, 'MOVE_MIST'), (56, 'MOVE_BLIZZARD'), (65, 'MOVE_SCARY_FACE')],
        # res/pokemon/mamoswine/data.json:56
        'learnset_tm': ['TM05', 'TM06', 'TM07', 'TM10', 'TM13', 'TM14', 'TM15', 'TM16', 'TM17', 'TM18', 'TM21', 'TM26', 'TM27', 'TM28', 'TM32', 'TM33', 'TM37', 'TM39', 'TM42', 'TM43', 'TM44', 'TM45', 'TM58', 'TM68', 'TM71', 'TM72', 'TM76', 'TM78', 'TM80', 'TM82', 'TM83', 'TM87', 'TM90', 'HM04', 'HM06', 'HM08'],
        # res/pokemon/mamoswine/data.json:94
        'learnset_tutor': ['MOVE_MUD_SLAP', 'MOVE_FURY_CUTTER', 'MOVE_ICY_WIND', 'MOVE_SUPERPOWER', 'MOVE_IRON_HEAD', 'MOVE_SNORE', 'MOVE_ENDEAVOR', 'MOVE_ANCIENT_POWER', 'MOVE_EARTH_POWER', 'MOVE_KNOCK_OFF'],
        'egg_moves': [],
        # res/pokemon/mamoswine/data.json:107
        'evolutions': [],
    },
    # res/pokemon/mantyke/data.json
    'mantyke': {
        # res/pokemon/mantyke/data.json:2
        'base_stats': {'hp': 45, 'atk': 20, 'def': 50, 'spa': 60, 'spd': 120, 'spe': 50},
        # res/pokemon/mantyke/data.json:10
        'types': ['TYPE_WATER', 'TYPE_FLYING'],
        # res/pokemon/mantyke/data.json:30 (raw: ['ABILITY_SWIFT_SWIM', 'ABILITY_WATER_ABSORB'])
        'abilities': ['ABILITY_SWIFT_SWIM', 'ABILITY_WATER_ABSORB'],
        # res/pokemon/mantyke/data.json:28
        'exp_rate': 'EXP_RATE_SLOW',
        # res/pokemon/mantyke/data.json:36
        'learnset_level': [(1, 'MOVE_TACKLE'), (1, 'MOVE_BUBBLE'), (4, 'MOVE_SUPERSONIC'), (10, 'MOVE_BUBBLE_BEAM'), (13, 'MOVE_HEADBUTT'), (19, 'MOVE_AGILITY'), (22, 'MOVE_WING_ATTACK'), (28, 'MOVE_WATER_PULSE'), (31, 'MOVE_TAKE_DOWN'), (37, 'MOVE_CONFUSE_RAY'), (40, 'MOVE_BOUNCE'), (46, 'MOVE_AQUA_RING'), (49, 'MOVE_HYDRO_PUMP')],
        # res/pokemon/mantyke/data.json:51
        'learnset_tm': ['TM03', 'TM06', 'TM07', 'TM10', 'TM13', 'TM14', 'TM17', 'TM18', 'TM21', 'TM26', 'TM27', 'TM32', 'TM40', 'TM42', 'TM43', 'TM44', 'TM45', 'TM58', 'TM78', 'TM82', 'TM83', 'TM87', 'TM90', 'HM03', 'HM07'],
        # res/pokemon/mantyke/data.json:78
        'learnset_tutor': ['MOVE_DIVE', 'MOVE_MUD_SLAP', 'MOVE_ICY_WIND', 'MOVE_SNORE', 'MOVE_AIR_CUTTER', 'MOVE_HELPING_HAND', 'MOVE_BOUNCE', 'MOVE_SWIFT'],
        # res/pokemon/mantyke/data.json:88
        'egg_moves': ['MOVE_TWISTER', 'MOVE_HYDRO_PUMP', 'MOVE_HAZE', 'MOVE_SLAM', 'MOVE_MUD_SPORT', 'MOVE_ROCK_SLIDE', 'MOVE_MIRROR_COAT', 'MOVE_WATER_SPORT', 'MOVE_SPLASH', 'MOVE_SIGNAL_BEAM'],
        # res/pokemon/mantyke/data.json:101
        'evolutions': [['EVO_LEVEL_SPECIES_IN_PARTY', 'SPECIES_REMORAID', 'SPECIES_MANTINE']],
    },
    # res/pokemon/eevee/data.json
    'eevee': {
        # res/pokemon/eevee/data.json:2
        'base_stats': {'hp': 55, 'atk': 55, 'def': 50, 'spa': 45, 'spd': 65, 'spe': 55},
        # res/pokemon/eevee/data.json:10
        'types': ['TYPE_NORMAL', 'TYPE_NORMAL'],
        # res/pokemon/eevee/data.json:30 (raw: ['ABILITY_RUN_AWAY', 'ABILITY_ADAPTABILITY'])
        'abilities': ['ABILITY_RUN_AWAY', 'ABILITY_ADAPTABILITY'],
        # res/pokemon/eevee/data.json:28
        'exp_rate': 'EXP_RATE_MEDIUM_FAST',
        # res/pokemon/eevee/data.json:36
        'learnset_level': [(1, 'MOVE_TAIL_WHIP'), (1, 'MOVE_TACKLE'), (1, 'MOVE_HELPING_HAND'), (8, 'MOVE_SAND_ATTACK'), (15, 'MOVE_GROWL'), (22, 'MOVE_QUICK_ATTACK'), (29, 'MOVE_BITE'), (36, 'MOVE_BATON_PASS'), (43, 'MOVE_TAKE_DOWN'), (50, 'MOVE_LAST_RESORT'), (57, 'MOVE_TRUMP_CARD')],
        # res/pokemon/eevee/data.json:49
        'learnset_tm': ['TM06', 'TM10', 'TM11', 'TM17', 'TM18', 'TM21', 'TM23', 'TM27', 'TM28', 'TM30', 'TM32', 'TM42', 'TM43', 'TM44', 'TM45', 'TM58', 'TM78', 'TM82', 'TM83', 'TM87', 'TM90'],
        # res/pokemon/eevee/data.json:72
        'learnset_tutor': ['MOVE_MUD_SLAP', 'MOVE_SNORE', 'MOVE_HELPING_HAND', 'MOVE_LAST_RESORT', 'MOVE_SWIFT'],
        # res/pokemon/eevee/data.json:79
        'egg_moves': ['MOVE_CHARM', 'MOVE_FLAIL', 'MOVE_ENDURE', 'MOVE_CURSE', 'MOVE_TICKLE', 'MOVE_WISH', 'MOVE_YAWN', 'MOVE_FAKE_TEARS', 'MOVE_COVET'],
        # res/pokemon/eevee/data.json:91
        'evolutions': [['EVO_LEVEL_MOSS_ROCK', 'SPECIES_LEAFEON'], ['EVO_LEVEL_ICE_ROCK', 'SPECIES_GLACEON'], ['EVO_USE_ITEM', 'ITEM_THUNDERSTONE', 'SPECIES_JOLTEON'], ['EVO_USE_ITEM', 'ITEM_WATER_STONE', 'SPECIES_VAPOREON'], ['EVO_USE_ITEM', 'ITEM_FIRE_STONE', 'SPECIES_FLAREON'], ['EVO_LEVEL_HAPPINESS_DAY', 'SPECIES_ESPEON'], ['EVO_LEVEL_HAPPINESS_NIGHT', 'SPECIES_UMBREON']],
    },
    # res/pokemon/nincada/data.json
    'nincada': {
        # res/pokemon/nincada/data.json:2
        'base_stats': {'hp': 31, 'atk': 45, 'def': 90, 'spa': 30, 'spd': 30, 'spe': 40},
        # res/pokemon/nincada/data.json:10
        'types': ['TYPE_BUG', 'TYPE_GROUND'],
        # res/pokemon/nincada/data.json:30 (raw: ['ABILITY_COMPOUND_EYES', 'ABILITY_NONE'])
        'abilities': ['ABILITY_COMPOUND_EYES', None],
        # res/pokemon/nincada/data.json:28
        'exp_rate': 'EXP_RATE_ERRATIC',
        # res/pokemon/nincada/data.json:36
        'learnset_level': [(1, 'MOVE_SCRATCH'), (1, 'MOVE_HARDEN'), (5, 'MOVE_LEECH_LIFE'), (9, 'MOVE_SAND_ATTACK'), (14, 'MOVE_FURY_SWIPES'), (19, 'MOVE_MIND_READER'), (25, 'MOVE_FALSE_SWIPE'), (31, 'MOVE_MUD_SLAP'), (38, 'MOVE_METAL_CLAW'), (45, 'MOVE_DIG')],
        # res/pokemon/nincada/data.json:48
        'learnset_tm': ['TM06', 'TM10', 'TM11', 'TM17', 'TM19', 'TM21', 'TM22', 'TM27', 'TM28', 'TM30', 'TM32', 'TM37', 'TM40', 'TM42', 'TM43', 'TM44', 'TM54', 'TM58', 'TM70', 'TM81', 'TM82', 'TM83', 'TM87', 'TM90', 'HM01'],
        # res/pokemon/nincada/data.json:75
        'learnset_tutor': ['MOVE_MUD_SLAP', 'MOVE_FURY_CUTTER', 'MOVE_SNORE', 'MOVE_SPITE'],
        # res/pokemon/nincada/data.json:81
        'egg_moves': ['MOVE_ENDURE', 'MOVE_FAINT_ATTACK', 'MOVE_GUST', 'MOVE_SILVER_WIND', 'MOVE_BUG_BUZZ', 'MOVE_NIGHT_SLASH', 'MOVE_BUG_BITE'],
        # res/pokemon/nincada/data.json:91
        'evolutions': [['EVO_LEVEL_NINJASK', 20, 'SPECIES_NINJASK'], ['EVO_LEVEL_SHEDINJA', 20, 'SPECIES_SHEDINJA']],
    },
    # res/pokemon/shedinja/data.json
    'shedinja': {
        # res/pokemon/shedinja/data.json:2
        'base_stats': {'hp': 1, 'atk': 90, 'def': 45, 'spa': 30, 'spd': 30, 'spe': 40},
        # res/pokemon/shedinja/data.json:10
        'types': ['TYPE_BUG', 'TYPE_GHOST'],
        # res/pokemon/shedinja/data.json:30 (raw: ['ABILITY_WONDER_GUARD', 'ABILITY_NONE'])
        'abilities': ['ABILITY_WONDER_GUARD', None],
        # res/pokemon/shedinja/data.json:28
        'exp_rate': 'EXP_RATE_ERRATIC',
        # res/pokemon/shedinja/data.json:36
        'learnset_level': [(1, 'MOVE_SCRATCH'), (1, 'MOVE_HARDEN'), (5, 'MOVE_LEECH_LIFE'), (9, 'MOVE_SAND_ATTACK'), (14, 'MOVE_FURY_SWIPES'), (19, 'MOVE_MIND_READER'), (25, 'MOVE_SPITE'), (31, 'MOVE_CONFUSE_RAY'), (38, 'MOVE_SHADOW_SNEAK'), (45, 'MOVE_GRUDGE'), (52, 'MOVE_HEAL_BLOCK'), (59, 'MOVE_SHADOW_BALL')],
        # res/pokemon/shedinja/data.json:50
        'learnset_tm': ['TM06', 'TM10', 'TM11', 'TM15', 'TM17', 'TM19', 'TM21', 'TM22', 'TM27', 'TM28', 'TM30', 'TM32', 'TM37', 'TM40', 'TM42', 'TM43', 'TM44', 'TM46', 'TM54', 'TM58', 'TM61', 'TM65', 'TM68', 'TM70', 'TM81', 'TM82', 'TM83', 'TM85', 'TM87', 'TM90', 'HM01'],
        # res/pokemon/shedinja/data.json:83
        'learnset_tutor': ['MOVE_MUD_SLAP', 'MOVE_FURY_CUTTER', 'MOVE_SNORE', 'MOVE_SPITE', 'MOVE_TRICK', 'MOVE_SUCKER_PUNCH'],
        'egg_moves': [],
        # res/pokemon/shedinja/data.json:92
        'evolutions': [],
    },
    # res/pokemon/rotom/forms/wash/data.json
    'rotom_wash': {
        # res/pokemon/rotom/forms/wash/data.json:2
        'base_stats': {'hp': 50, 'atk': 65, 'def': 107, 'spa': 105, 'spd': 107, 'spe': 86},
        # res/pokemon/rotom/forms/wash/data.json:10
        'types': ['TYPE_ELECTRIC', 'TYPE_GHOST'],
        # res/pokemon/rotom/forms/wash/data.json:30 (raw: ['ABILITY_LEVITATE', 'ABILITY_NONE'])
        'abilities': ['ABILITY_LEVITATE', None],
        # res/pokemon/rotom/forms/wash/data.json:28
        'exp_rate': 'EXP_RATE_MEDIUM_FAST',
        # res/pokemon/rotom/forms/wash/data.json:36
        'learnset_level': [(1, 'MOVE_TRICK'), (1, 'MOVE_ASTONISH'), (1, 'MOVE_THUNDER_WAVE'), (1, 'MOVE_THUNDER_SHOCK'), (1, 'MOVE_CONFUSE_RAY'), (8, 'MOVE_UPROAR'), (15, 'MOVE_DOUBLE_TEAM'), (22, 'MOVE_SHOCK_WAVE'), (29, 'MOVE_OMINOUS_WIND'), (36, 'MOVE_SUBSTITUTE'), (43, 'MOVE_CHARGE'), (50, 'MOVE_DISCHARGE')],
        # res/pokemon/rotom/forms/wash/data.json:50
        'learnset_tm': ['TM06', 'TM10', 'TM11', 'TM16', 'TM17', 'TM18', 'TM21', 'TM24', 'TM25', 'TM27', 'TM30', 'TM32', 'TM33', 'TM34', 'TM42', 'TM43', 'TM44', 'TM46', 'TM49', 'TM57', 'TM58', 'TM61', 'TM70', 'TM73', 'TM77', 'TM79', 'TM82', 'TM83', 'TM85', 'TM87', 'TM90'],
        # res/pokemon/rotom/forms/wash/data.json:83
        'learnset_tutor': ['MOVE_MUD_SLAP', 'MOVE_OMINOUS_WIND', 'MOVE_SNORE', 'MOVE_SPITE', 'MOVE_SIGNAL_BEAM', 'MOVE_TRICK', 'MOVE_SUCKER_PUNCH', 'MOVE_SWIFT', 'MOVE_UPROAR'],
        'egg_moves': [],
        # res/pokemon/rotom/forms/wash/data.json:95
        'evolutions': [],
    },
}


def _evo(raw):
    return Evolution(raw[0], None, raw[1]) if len(raw) == 2 else Evolution(raw[0], raw[1], raw[2])


def test_twenty_species_full_records():
    assert len(EXPECTED) >= 20
    species = load_species()
    for key, exp in EXPECTED.items():
        s = species[key]
        assert s.base_stats == exp["base_stats"], key
        assert s.types == exp["types"], key
        assert s.abilities == exp["abilities"], key
        assert s.exp_rate == exp["exp_rate"], key
        assert s.learnset_level == exp["learnset_level"], key
        assert s.learnset_tm == exp["learnset_tm"], key
        assert s.learnset_tutor == exp["learnset_tutor"], key
        assert s.egg_moves == exp["egg_moves"], key
        assert s.evolutions == [_evo(e) for e in exp["evolutions"]], key
        assert s.src and all(":" in r for r in s.src), key


def test_names_and_ids():
    sp = load_species()
    # res/pokemon/garchomp/data.json pokedex_data.en.name; generated/species.txt:446 -> id 445
    assert sp["garchomp"].name == "GARCHOMP"
    assert sp["garchomp"].id == 445
    # Rotom-Wash: speciesproc.c:236 is position 8 of alt_forms_with_data (after the 496 lines of
    # generated/species.txt) -> 504; src/pokemon.c:4955 (Pokemon_GetFormNarcIndex) maps ROTOM form n to (503 - 1) + n, wash = 2.
    rw = sp["rotom_wash"]
    assert (rw.id, rw.form, rw.form_index, rw.base_species) == (504, "wash", 2, "rotom")


def test_mono_type_repeats_and_ability_slots():
    sp = load_species()
    # res/pokemon/milotic/data.json:10 "types": [ "TYPE_WATER", "TYPE_WATER" ]
    assert sp["milotic"].types == ["TYPE_WATER", "TYPE_WATER"]
    # res/pokemon/garchomp/data.json:30 [ "ABILITY_SAND_VEIL", "ABILITY_NONE" ]
    assert sp["garchomp"].abilities == ["ABILITY_SAND_VEIL", None]
    # res/pokemon/lucario/data.json:30 [ "ABILITY_STEADFAST", "ABILITY_INNER_FOCUS" ]
    assert sp["lucario"].abilities == ["ABILITY_STEADFAST", "ABILITY_INNER_FOCUS"]


def test_evolution_shapes():
    sp = load_species()
    # kadabra/data.json: [ "EVO_TRADE", "SPECIES_ALAKAZAM" ] -> 2-element shape (speciesproc.c:576)
    assert sp["kadabra"].evolutions == [Evolution("EVO_TRADE", None, "SPECIES_ALAKAZAM")]
    # onix/data.json: [ "EVO_TRADE_WITH_HELD_ITEM", "ITEM_METAL_COAT", "SPECIES_STEELIX" ]
    assert sp["onix"].evolutions == [
        Evolution("EVO_TRADE_WITH_HELD_ITEM", "ITEM_METAL_COAT", "SPECIES_STEELIX")
    ]
    # piloswine/data.json: [ "EVO_LEVEL_KNOW_MOVE", "MOVE_ANCIENT_POWER", "SPECIES_MAMOSWINE" ]
    assert sp["piloswine"].evolutions == [
        Evolution("EVO_LEVEL_KNOW_MOVE", "MOVE_ANCIENT_POWER", "SPECIES_MAMOSWINE")
    ]
    # mantyke/data.json: [ "EVO_LEVEL_SPECIES_IN_PARTY", "SPECIES_REMORAID", "SPECIES_MANTINE" ]
    assert sp["mantyke"].evolutions == [
        Evolution("EVO_LEVEL_SPECIES_IN_PARTY", "SPECIES_REMORAID", "SPECIES_MANTINE")
    ]
    # nincada/data.json: [ "EVO_LEVEL_NINJASK", 20, "SPECIES_NINJASK" ], [ "EVO_LEVEL_SHEDINJA", 20, ... ]
    assert sp["nincada"].evolutions == [
        Evolution("EVO_LEVEL_NINJASK", 20, "SPECIES_NINJASK"),
        Evolution("EVO_LEVEL_SHEDINJA", 20, "SPECIES_SHEDINJA"),
    ]
    assert len(sp["eevee"].evolutions) == 7
    shapes = evolution_shapes()
    # speciesproc.c:576 EVO_TRADE has no param; :598 EVO_TRADE_WITH_HELD_ITEM is an Item;
    # :608 EVO_LEVEL_KNOW_MOVE a Move; :613 EVO_LEVEL_SPECIES_IN_PARTY a Species; :583 EVO_LEVEL int
    assert shapes["EVO_TRADE"][0] == "none"
    assert shapes["EVO_TRADE_WITH_HELD_ITEM"][0] == "Item"
    assert shapes["EVO_LEVEL_KNOW_MOVE"][0] == "Move"
    assert shapes["EVO_LEVEL_SPECIES_IN_PARTY"][0] == "Species"
    assert shapes["EVO_LEVEL"][0] == "int"
    # Positive control: every method in generated/evolution_methods.txt (27 lines) has a handler.
    assert len(shapes) == 27


def test_total_count():
    # generated/species.txt has 496 lines: SPECIES_NONE + 493 species + SPECIES_EGG/BAD_EGG.
    # speciesproc.c:227-240 (array at 227, entries 228-239) lists 12 alternate forms with own data.
    assert len(form_order()) == 12
    assert len(load_species()) == 493 + 12


def test_json_serializable():
    import json

    json.dumps({k: v.to_json() for k, v in load_species().items()})
