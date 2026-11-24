"""Low-level reader for Yamaha SY85 disk files (sequencer songs, rhythm patterns, voices, performances).

See FORMAT.md in the project root for the full description of the binary layout.
All offsets here were reverse-engineered; nothing in this module depends on Yamaha data.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

PPQ = 96                      # sequencer resolution (ticks per quarter note)
SONG_BLOCK = 198              # bytes per song/multi block
N_SONGS = 10
TRACK_AREA = 0x3400           # offset of the track data inside the SEQ section
PATTERN_BASE = 0x0CC6         # offset of rhythm pattern / chain data inside the SEQ section
VOICE_BANKS = (0x2BEA, 0x55F0, 0xABEA, 0xD5F0)   # I1..I4, offsets inside the ALL section
PERF_BANKS = (0x014A, 0x814A)                    # performance banks I1, I2
VOICE_SIZE, DRUM_VOICE_SIZE, PERF_SIZE = 162, 552, 168
METER = {1: (2, 4), 2: (3, 4), 3: (4, 4), 4: (5, 4), 5: (12, 8)}   # meter codes (songs and patterns)
SLOTS = 'ABCDEFGH'


def slot_name(n: int) -> str:
    """0..63 -> 'A1'..'H8' as shown on the SY85 display."""
    return f'{SLOTS[n // 8]}{n % 8 + 1}'


def _u16(d: bytes, o: int) -> int:
    return (d[o] << 8) | d[o + 1]


def _find_aligned(d: bytes, sigs) -> int | None:
    for sig in sigs:
        start = 0
        while True:
            i = d.find(sig, start)
            if i < 0:
                break
            if i % 0x10000 == 0:
                return i
            start = i + 1
    return None


# ------------------------------------------------------------------ voices and performances
class VoiceSet:
    """Voice and performance banks of an SY85 'ALL' file."""

    def __init__(self, data: bytes):
        base = _find_aligned(data, (b'SY85ALL', b'SY85NALL', b'SY85SYNALL'))
        if base is None:
            raise ValueError('not an SY85 ALL file (no voice data)')
        self.d, self.base = data, base

    def voice_record(self, bank: int, voice: int) -> bytes:
        o = self.base + VOICE_BANKS[bank] + VOICE_SIZE * voice
        return self.d[o:o + (DRUM_VOICE_SIZE if voice == 63 else VOICE_SIZE)]

    def voice_name(self, bank: int, voice: int) -> str:
        return self.voice_record(bank, voice)[0x31:0x39].decode('latin-1').rstrip()

    def voice_note_shift(self, bank: int, voice: int) -> int:
        """Voice-level note shift in semitones (e.g. -12 for many basses). Drum voices: 0."""
        if voice == 63:
            return 0
        return self.voice_record(bank, voice)[89] - 0x40

    def perf_record(self, bank: int, perf: int) -> bytes:
        o = self.base + PERF_BANKS[bank] + PERF_SIZE * perf
        return self.d[o:o + PERF_SIZE]

    def perf_name(self, bank: int, perf: int) -> str:
        return self.perf_record(bank, perf)[0x31:0x39].decode('latin-1').rstrip()

    def perf_layers(self, bank: int, perf: int) -> list[tuple[int, int]]:
        """Active layers of a performance as (voice bank, voice number)."""
        r = self.perf_record(bank, perf)
        out = []
        for layer in range(4):
            bk, vb = r[0x3C + 28 * layer], r[0x3D + 28 * layer]
            if vb & 0x80:
                out.append((bk & 3, vb & 0x3F))
        return out

    def drum_keys(self, bank: int) -> dict[int, tuple[int, int]]:
        """Drum voice (slot H8) key map: key 36..84 -> (wave number, pitch)."""
        r = self.voice_record(bank, 63)
        return {36 + k: (r[0x3F + 10 * k], r[0x42 + 10 * k]) for k in range(49)}


# ------------------------------------------------------------------ song (multi) block
@dataclass
class Part:
    """One of the 16 multi parts of a song."""
    index: int
    bank: int
    is_voice: bool            # False = performance
    number: int               # voice/performance number 0..63
    volume: int               # 0..127
    note_shift: int           # semitones
    tune: int                 # -63..+63, ~1.17 cent steps
    pan: int | None           # -31..+31, None = use the voice's own pan ("vce")
    send_switches: int        # bits: 1a,1b,2a,2b,dry1,dry2 ; 0x40 = send source is the voice ("VCE")
    send_level: int           # 0..127

    @classmethod
    def from_bytes(cls, index: int, p: bytes) -> 'Part':
        pan = None if (p[5] >= 0x40 or p[5] == 0) else p[5] - 0x20
        return cls(index, p[0] & 3, bool(p[1] & 0x40), p[1] & 0x3F, p[2], p[3] - 0x40, p[4] - 0x40,
                   pan, p[6], p[7])

    @property
    def perf_bank(self) -> int:
        return 0 if self.bank == 0 else 1

    @property
    def label(self) -> str:
        if self.is_voice:
            return f'I{self.bank + 1}-{slot_name(self.number)}'
        return f'Perf I{self.perf_bank + 1}-{slot_name(self.number)}'


@dataclass
class Song:
    number: int               # 0..9
    name: str
    tempo: int                # BPM
    meter_code: int
    track_channels: list[int]  # 9 entries: tracks 1-8 + rhythm -> part number (low nibble)
    parts: list[Part]
    effect_bytes: bytes       # raw 49-byte effect block (see effects.py)
    raw: bytes = field(repr=False, default=b'')

    @classmethod
    def from_block(cls, number: int, blk: bytes) -> 'Song':
        return cls(number=number,
                   name=blk[0x31:0x39].decode('latin-1').rstrip('\x00 '),
                   tempo=blk[0x44] * 128 + blk[0x45],
                   meter_code=blk[0x42],
                   track_channels=list(blk[0x39:0x42]),
                   parts=[Part.from_bytes(i, blk[0x46 + 8 * i:0x4E + 8 * i]) for i in range(16)],
                   effect_bytes=bytes(blk[:0x31]), raw=bytes(blk))

    def part_for_track(self, track: int) -> Part:
        """track 0..7, or 8 for the rhythm track."""
        return self.parts[self.track_channels[track] & 15]


# ------------------------------------------------------------------ track events
@dataclass
class Event:
    time: int                 # ticks (96 ppq)
    kind: str                 # 'note', 'cc', 'pb', 'pc'
    a: int = 0                # note / controller / pitch-bend value (0..16383) / program
    b: int = 0                # velocity / controller value
    gate: int = 0             # note length in ticks


@dataclass
class Track:
    song: int
    track: int                # 0..7
    events: list[Event]
    bar_lengths: list[int]    # ticks between bar markers
    end: int                  # tick of the end of the track
    raw: bytes = field(repr=False, default=b'')


def parse_track_body(body: bytes) -> tuple[list[Event], list[int], int]:
    """Decode one track block body (the bytes between F0 and F2, starting with the song/track byte)."""
    ev: list[Event] = []
    bars: list[int] = []
    t = 0
    lastbar = 0
    i = 1
    n = len(body)

    def delta() -> int:
        nonlocal i
        v = 0
        while i < n and body[i] < 0x80:
            v = v * 128 + body[i]
            i += 1
        return v

    t += delta()
    while i < n:
        b = body[i]
        if b == 0xF8:                       # prefix / filler inside a track
            i += 1
            continue
        if 0x80 <= b <= 0xEF:               # note: gate, note[, velocity]
            if b >= 0xC0:
                gate = (((b & 0x3F) << 7) | body[i + 1]) * 4
                i += 2
            else:
                gate = (b & 0x3F) * 4
                i += 1
            note = body[i]
            i += 1
            if note >= 0x80:
                note &= 0x7F
                vel = 64
            else:
                vel = body[i]
                i += 1
            ev.append(Event(t, 'note', note, vel, max(gate, 2)))
        elif b == 0xF5:                     # bar line
            i += 1
            bars.append(t - lastbar)
            lastbar = t
        elif b == 0xFB:                     # control change
            ev.append(Event(t, 'cc', body[i + 1], body[i + 2]))
            i += 3
        elif b == 0xFE:                     # pitch bend lsb, msb
            ev.append(Event(t, 'pb', (body[i + 2] << 7) | body[i + 1]))
            i += 3
        elif b == 0xFC:                     # program change
            ev.append(Event(t, 'pc', body[i + 1]))
            i += 2
        else:
            i += 1
        t += delta()
    return ev, bars, t


def split_track_blocks(data: bytes, start: int, stop_at_fill: bool = True) -> list[bytes]:
    """Return the bodies of all F0 ... F2 track blocks from `start`."""
    out = []
    i = start
    while i < len(data):
        if data[i] == 0xF0:
            j = data.find(b'\xF2', i)
            if j < 0:
                break
            out.append(data[i + 1:j])
            i = j + 1
        elif stop_at_fill and data[i] == 0xF8 and i > 0 and data[i - 1] == 0xF2:
            break
        else:
            i += 1
    return out


# ------------------------------------------------------------------ rhythm patterns
@dataclass
class Pattern:
    number: int
    hits: list[tuple[int, int, int]]   # (tick at 96 ppq, instrument 0..48, velocity)
    bars: int
    meter_code: int
    name: str


# ------------------------------------------------------------------ the file
class SY85File:
    """An SY85 disk file containing sequencer data (SY85SEQ section, standalone or inside an ALL file)."""

    def __init__(self, data: bytes, name: str = ''):
        self.data, self.name = data, name
        self.seq = _find_aligned(data, (b'SY85SEQ',))
        if self.seq is None:
            raise ValueError(f'{name or "file"}: no SY85 sequencer data found')
        try:
            self.voices: VoiceSet | None = VoiceSet(data)
        except ValueError:
            self.voices = None

    @classmethod
    def open(cls, path: str) -> 'SY85File':
        import os
        with open(path, 'rb') as f:
            return cls(f.read(), os.path.basename(path))

    # songs ----------------------------------------------------------
    def song(self, n: int) -> Song:
        o = self.seq + 0x40 + SONG_BLOCK * n
        return Song.from_block(n, self.data[o:o + SONG_BLOCK])

    def tracks(self) -> list[Track]:
        out = []
        for body in split_track_blocks(self.data, self.seq + TRACK_AREA):
            ev, bars, end = parse_track_body(body)
            out.append(Track(body[0] >> 4, body[0] & 15, ev, bars, end, body))
        return out

    def songs_with_notes(self) -> list[int]:
        return sorted({t.song for t in self.tracks() if any(e.kind == 'note' for e in t.events)})

    def song_hash(self, n: int) -> str:
        h = hashlib.sha1()
        for b in sorted(t.raw for t in self.tracks() if t.song == n):
            h.update(b)
        return h.hexdigest()

    # rhythm -----------------------------------------------------------
    def _pattern_table(self):
        d, s = self.data, self.seq
        ptr = [_u16(d, s + 0x800 + 2 * k) & 0x7FFF for k in range(100)]
        chains = [_u16(d, s + 0x8C8 + 2 * k) for k in range(10)]
        end = _u16(d, s + 0x8DC) & 0x7FFF
        starts = sorted(set(ptr + [c & 0x7FFF for c in chains if c & 0x8000] + [end]))
        return ptr, chains, end, starts

    def _segment(self, start: int, starts: list[int], end: int) -> bytes:
        nxt = min([p for p in starts if p > start] + [end])
        b = self.seq + PATTERN_BASE
        return self.data[b + start:b + nxt]

    def pattern(self, k: int) -> Pattern:
        ptr, _, end, starts = self._pattern_table()
        pb = self._segment(ptr[k], starts, end)
        hits, t = [], 0
        i = 1 if pb[:1] == b'\x80' else 0
        while i < len(pb):
            x = pb[i]
            if x >= 0x80:                    # delta in 48-ppq steps
                t += x & 0x7F
                i += 1
            elif i + 1 < len(pb):
                hits.append((t * 2, x, pb[i + 1]))
                i += 2
            else:
                break
        s = self.seq
        return Pattern(k, hits, self.data[s + 0x942 + k] + 1, self.data[s + 0x8DE + k],
                       self.data[s + 0x9A6 + 8 * k:s + 0x9AE + 8 * k].decode('latin-1').rstrip())

    def rhythm_chain(self, song: int) -> list[int] | None:
        """Pattern numbers played by a song's rhythm track, with repeats expanded (None = no rhythm)."""
        ptr, chains, end, starts = self._pattern_table()
        if not chains[song] & 0x8000:
            return None
        toks = list(self._segment(chains[song] & 0x7FFF, starts, end))

        def run(i):
            out = []
            while i < len(toks):
                x = toks[i]
                if x == 0xC8:                     # repeat block: C8 ... C9 n C9
                    body, i = run(i + 1)
                    cnt = toks[i + 1] if i + 1 < len(toks) else 0
                    i += 3
                    out += body * (cnt + 1)
                elif x == 0xC9:
                    return out, i
                elif x == 0xCA:                   # CA x CA  (setting, skipped)
                    i += 3
                elif x == 0xCB:                   # CB x y CB (setting, skipped)
                    i += 4
                elif x < 100:
                    out.append(x)
                    i += 1
                else:
                    i += 1
            return out, i

        return run(0)[0]


def read_qx_song(data: bytes) -> tuple[int, list[bytes]]:
    """'QX5FD'-style song file (seen with .A15 extension) holding SY85 track blocks.
    Returns (tempo, track block bodies). Track numbers in these blocks are 1-based."""
    if not data.startswith(b'QX5FD') and b'QX5FD' not in data[:64]:
        raise ValueError('not a QX5FD song file')
    return data[0x21], split_track_blocks(data, 0x200, stop_at_fill=False)
