"""Decode the effect settings stored in an SY85 song block (first 49 bytes).

Only the layout is decoded here (types, routing, raw parameter values, levels); the effects
themselves are not emulated. Parameter meanings per effect type are listed in the SY85 manual
("The Effects & Their Parameters").
"""
from __future__ import annotations

EFFECT_NAMES = [
    'Through', 'Rev. Hall1', 'Rev. Hall2', 'Rev. Room1', 'Rev. Room2', 'Rev. Room3', 'Rev. Stage1',
    'Rev. Stage2', 'Rev. Plate', 'Rev. WhRoom', 'Rev. Tunnel', 'Rev. Canyon', 'Rev. Basmnt', 'Early Ref1',
    'Early Ref2', 'Gate Rev.', 'Revrs Gate', 'Dly L,R', 'Dly L,C,R', 'St. Echo', 'Pit Chnge1', 'Pit Chnge2',
    'Pit Chnge3', 'Aural Exc.', 'EG Flanger', 'EG Chorus', 'EG Sympho', 'EG Phaser', 'Rotary SP.', 'Ring Mod.',
    'D.Flt (Wah)', 'Dly->Rev', 'Echo->Rev', 'Flg->Rev', 'Cho->Rev', 'Sym->Rev', 'Pha->Rev', 'Pit->Rev',
    'Exc->Rev', 'Dist->Rev', 'Pan->Rev', 'Flg->Dly', 'Cho->Dly', 'Sym->Dly', 'Pha->Dly', 'Pit->Dly',
    'Exc->Dly', 'Dist->Dly', 'Pan->Dly', 'Dist->Echo', 'EQ->Rev1', 'EQ->Rev2', 'EQ->ER', 'EQ->Dly',
    'EQ->Echo', 'EQ->Flg', 'EQ->Cho', 'EQ->Sym', 'EQ->Pha', 'EQ->Pit', 'EQ->Pan', 'Hall & Plate',
    'Echo & Rev', 'Flg & Rev', 'Cho & Rev', 'Sym & Rev', 'Pha & Rev', 'Pit & Rev', 'Exc & Rev', 'Dist & Rev',
    'Pan & Rev', 'Dly & Rev', 'Dly & Dly', 'Flg & Dly', 'Cho & Dly', 'Sym & Dly', 'Pha & Dly', 'Pit & Dly',
    'Exc & Dly', 'Dist & Dly', 'Pan & Dly', 'Flg & Flg', 'Flg & Cho', 'Flg & Sym', 'Flg & Pha', 'Cho & Cho',
    'Cho & Sym', 'Cho & Pha', 'Sym & Sym', 'Sym & Pha', 'Pha & Pha',
]
MODES = {0: 'off', 1: 'serial', 2: 'parallel'}


def _s16(b: bytes, i: int) -> int:
    v = (b[i] << 8) | b[i + 1]
    return v - 0x10000 if v & 0x8000 else v


def effect_name(n: int) -> str:
    return EFFECT_NAMES[n] if 0 <= n < len(EFFECT_NAMES) else f'#{n}'


def decode(effect_bytes: bytes) -> dict:
    """Decode the 49-byte effect block of a song.

    Parameters 1-4 of each effect are 16-bit values, parameters 5-8 are 8-bit values. Values are raw
    (table indexes for times/frequencies; e.g. reverb time index n = 0.3 s + 0.1 s * n in the low range).
    """
    b = effect_bytes
    return {
        'mode': MODES.get(b[1], b[1]),
        'effect1': {'type': b[2], 'name': effect_name(b[2]),
                    'params': [_s16(b, 10 + 2 * k) for k in range(4)] + list(b[18:22]),
                    'output_level': [b[22], b[23]], 'wet_percent': b[38]},
        'effect2': {'type': b[3], 'name': effect_name(b[3]),
                    'params': [_s16(b, 24 + 2 * k) for k in range(4)] + list(b[32:36]),
                    'output_level': [b[36], b[37]], 'wet_percent': b[39]},
    }
