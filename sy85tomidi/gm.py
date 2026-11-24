"""General MIDI mapping for SY85 voices and drum kits.

SY85 voice names start with a 2-letter category (AP piano, KY keys, BA bass, ST strings, ...) followed by
a 5-character name. The program is chosen from the category plus keywords in the name.

Drum kits are mapped to GM drum notes by comparing the AWM wave numbers each key plays with the
wave numbers of the SY85 factory kit "DR GMIDI", which is laid out in GM key order. That reference is
stored below as a plain table, so no Yamaha file is needed at runtime.
"""
from __future__ import annotations

GM_BY_NAME = {
    'AP': (0, {'Rock': 1, 'Dance': 1, 'Tack': 3, 'Chors': 1, 'Brght': 1, 'Honky': 3}),
    'KY': (4, {'Clav': 7, 'Hrpsi': 6, 'Cemb': 6, 'Acrdn': 21, 'Acrd': 21, 'Cali': 82, 'Digi': 5, 'EP 1 ': 4,
               'EP 2': 5, 'EP 8': 4, 'Funky': 4, 'Roady': 4, 'Jerry': 5, 'Piano': 0, 'Loud': 0}),
    'OR': (16, {'Pipes': 19, 'Pipe': 19, 'Dist': 18, 'Rock': 18, 'Click': 17, 'Perc': 17, 'Jaz': 17, 'Bee': 16}),
    'BA': (33, {'Wood': 32, 'Pitz': 32, 'Fingr': 33, 'Pick': 34, 'Frtls': 35, 'Thump': 36, 'Slap': 37,
                'Syn': 38, 'Swap': 34, 'Guppy': 38}),
    'ST': (48, {'Pizz': 45, 'Violn': 40, 'Viola': 41, 'Cello': 42, 'Contr': 43, 'Treml': 44,
                'Brite': 48, 'Sectn': 48, 'Synth': 50, 'Anlog': 50, 'Tron': 50, 'Sizzl': 50, 'Deep': 49}),
    'GT': (25, {'Nylon': 24, 'Nyln': 24, 'Steel': 25, '12Str': 25, 'Jazz': 26, 'Strt': 27, 'Strat': 27,
                'Comp': 27, 'Mute': 28, 'Wah': 28, 'Dist': 30, 'Amped': 29, 'Harm': 31, 'Warm': 26, 'Phunk': 27}),
    'BR': (61, {'Trump': 56, 'Trpt': 56, 'Miles': 56, 'Tromb': 57, 'Trmb': 57, 'Tuba': 58, 'Mute': 59,
                'Horn': 60, 'Syn': 62, 'Saw': 62, 'CS80': 62, 'Toto': 62, 'Rezz': 62, 'Wow': 62, 'Reeds': 65}),
    'WN': (73, {'Sopr': 64, 'Alto': 65, 'Tenor': 66, 'Tenr': 66, 'Bari': 67, 'Sax': 66, 'Sacks': 66,
                'Oboe': 68, 'EnglH': 69, 'Basso': 70, 'Clari': 71, 'Picc': 72, 'Flute': 73, 'Flt': 73,
                'Recor': 74, 'Pan': 75, 'Bottl': 76, 'Dudel': 109}),
    'CH': (52, {'Ooh': 53, 'Vox': 54, 'Voc': 54, 'Vespa': 54, 'Ghost': 91, 'Pure': 52, 'Breth': 52}),
    'SP': (89, {'SawSt': 90, 'Poly': 90, 'Glass': 92, 'Movie': 95, 'Sweep': 95, 'Phaze': 95, 'Space': 91,
                'Abyss': 94, 'Sqare': 80, 'Carol': 91, 'Venus': 91, 'Aztec': 89, 'Ace': 90}),
    'SC': (90, {'Bell': 98, 'Clav': 7, 'Pan': 75, 'Vocal': 85, 'Vox': 85, 'Spike': 81, 'Buzz': 81}),
    'SL': (81, {'Squar': 80, 'Sync': 84, 'Dist': 84, 'Cali': 82, 'Whisl': 79, 'Hamma': 80, 'Pulse': 80}),
    'ME': (11, {'Mello': 52, 'Orch': 55, 'Kali': 108, 'Hand': 14, 'Tink': 112, 'Templ': 14, 'Voics': 54,
                'Glitz': 98, 'Orion': 98}),
    'TP': (11, {'Timp': 47, 'Glock': 9, 'Hands': 14, 'Mrmba': 12, 'Steel': 114, 'Tubal': 14, 'Vibes': 11,
                'Xylo': 13, 'Loggy': 115, 'SynDr': 118}),
    'FI': (46, {'Harp': 46, 'Sitar': 104, 'Kalim': 108, 'Dulc': 15, 'Banjo': 105, 'Santo': 25, 'Pan': 75}),
    'PL': (46, {'Harp': 46, 'Sitar': 104, 'Kalim': 108, 'Dulc': 15, 'Banjo': 105}),
    'SE': (99, {'Chou': 91, 'Delay': 99, 'Indus': 99}),
    'MI': (99, {}),
    'MW': (99, {}),
    'CO': (89, {}),
}
# Categories that describe a performance's style rather than an instrument: use the first layer's voice.
COMBI_CATEGORIES = ('CO', 'SE', 'MI', 'MW')


def gm_program(name: str) -> int:
    """GM program number (0..127) for an SY85 voice name such as 'BA Frtls'."""
    cat, rest = name[:2], name[3:]
    if cat not in GM_BY_NAME:
        return 0
    default, table = GM_BY_NAME[cat]
    for k, v in table.items():
        if rest.startswith(k) or k in rest:
            return v
    return default


# GM drum note -> (AWM wave number, pitch) of the SY85 factory "DR GMIDI" kit (keys 36..84).
GM_KIT_REFERENCE = {
    36: (151, 64), 37: (168, 66), 38: (160, 64), 39: (193, 65), 40: (166, 65), 41: (169, 56), 42: (174, 65),
    43: (169, 58), 44: (172, 64), 45: (169, 61), 46: (171, 66), 47: (169, 66), 48: (169, 71), 49: (176, 64),
    50: (169, 76), 51: (177, 64), 52: (176, 60), 53: (178, 64), 54: (198, 62), 55: (176, 72), 56: (196, 64),
    57: (176, 64), 58: (191, 64), 59: (177, 62), 60: (187, 67), 61: (187, 62), 62: (190, 64), 63: (189, 69),
    64: (189, 64), 65: (201, 64), 66: (201, 59), 67: (186, 64), 68: (186, 59), 69: (188, 64), 70: (197, 64),
    71: (204, 62), 72: (204, 60), 73: (195, 64), 74: (179, 64), 75: (194, 60), 76: (192, 64), 77: (194, 54),
    78: (184, 64), 79: (185, 64), 80: (203, 64), 81: (203, 64), 82: (183, 64), 83: (183, 68), 84: (218, 64),
}

# Key map of the factory "DR PTN" kit (I1-H8, the default rhythm kit), derived with kit_to_gm().
# Used when a song file has no voice data and no --voices file is given.
FACTORY_PTN_TO_GM = {
    38: 36, 39: 36, 40: 43, 41: 45, 42: 47, 43: 48, 44: 36, 45: 36, 46: 38, 47: 45, 48: 47, 49: 38, 50: 48,
    51: 37, 52: 38, 53: 50, 54: 39, 55: 56, 56: 69, 57: 44, 58: 42, 59: 46, 60: 49, 61: 49, 62: 51, 63: 53,
    64: 64, 65: 62, 66: 58, 67: 61, 68: 60, 69: 66, 70: 65, 71: 54, 72: 75, 73: 65, 74: 68, 75: 67, 76: 71,
    77: 38, 78: 73, 79: 38, 80: 74, 81: 40, 82: 74, 83: 40,
}


def kit_to_gm(drum_keys: dict[int, tuple[int, int]]) -> dict[int, int]:
    """Map each key of an SY85 drum kit to a GM drum note by matching wave numbers (then pitch)."""
    by_wave: dict[int, list[tuple[int, int]]] = {}
    for note, (w, p) in GM_KIT_REFERENCE.items():
        by_wave.setdefault(w, []).append((p, note))
    waves = sorted(by_wave)
    out = {}
    for key, (w, p) in drum_keys.items():
        if w in by_wave:
            cands = by_wave[w]
        else:
            near = min(waves, key=lambda x: abs(x - w))
            if abs(near - w) > 3:
                continue
            cands = by_wave[near]
        out[key] = min(cands, key=lambda c: abs(c[0] - p))[1]
    return out
