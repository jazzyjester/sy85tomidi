"""Build Standard MIDI Files from SY85 songs."""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

import mido

from .format import PPQ, METER, SY85File, Song, Track, VoiceSet, parse_track_body, slot_name
from .gm import COMBI_CATEGORIES, FACTORY_PTN_TO_GM, GM_BY_NAME, gm_program, kit_to_gm
from . import effects


@dataclass
class TrackInfo:
    track: str                # '1'..'8' or 'R'
    sound: str                # e.g. 'I1-C6 BA Frtls' or 'Perf I1-G6 BA Guppy'
    gm: str                   # 'GM 35' or 'drums'
    notes: int


@dataclass
class SongInfo:
    name: str
    tempo: int
    meter: str
    bars: int
    seconds: float = 0.0
    tracks: list[TrackInfo] = field(default_factory=list)
    effects: dict = field(default_factory=dict)


def _flush(track: mido.MidiTrack, abs_events):
    abs_events.sort(key=lambda x: (x[0], x[1]))
    last = 0
    for t, _, m in abs_events:
        track.append(m.copy(time=t - last))
        last = t


def convert(src: SY85File, song_no: int, voices: VoiceSet | None = None, mode: str = 'gm',
            tracks: list[Track] | None = None, tempo: int | None = None, title: str | None = None):
    """Convert one song to a mido.MidiFile.

    src      file holding the song settings (mixer, tempo, effects, rhythm patterns)
    voices   voice/performance names; defaults to the voice data inside `src` (ALL files)
    mode     'gm'     - General MIDI: GM programs, GM drum notes, voice note-shifts applied
             'native' - SY85 names per track, original SY85 drum keys and pitches, no program changes
                        (for playback on a real SY85/TG500 or a sampled SY85 instrument)
    tracks   override the track data (e.g. tracks from a QX5FD file); default: the song's tracks in `src`
    """
    if mode not in ('gm', 'native'):
        raise ValueError("mode must be 'gm' or 'native'")
    native = mode == 'native'
    vs = voices or src.voices
    song: Song = src.song(song_no)
    if tracks is None:
        tracks = [t for t in src.tracks() if t.song == song_no]
    tempo = tempo or song.tempo or 120

    def voice_name(bank, v):
        return vs.voice_name(bank, v) if vs else ''

    mid = mido.MidiFile(type=1, ticks_per_beat=PPQ)
    meta = mido.MidiTrack()
    mid.tracks.append(meta)
    meta.append(mido.MetaMessage('track_name', name=title or song.name, time=0))
    meta.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(tempo), time=0))

    barlens = [b for t in tracks for b in t.bar_lengths]
    bar = statistics.mode(barlens) if barlens else PPQ * 4
    if bar % PPQ == 0:
        num, den = bar // PPQ, 4
    else:
        num, den = bar // (PPQ // 2), 8
    meta.append(mido.MetaMessage('time_signature', numerator=num, denominator=den, time=0))
    song_end = max([t.end for t in tracks] + [0])
    info = SongInfo(song.name, tempo, f'{num}/{den}', round(song_end / bar) if bar else 0,
                    effects=effects.decode(song.effect_bytes))

    used = set()

    def alloc(want):
        c = want
        while c in used or c == 9:
            c = (c + 1) % 16
        used.add(c)
        return c

    for tr in sorted(tracks, key=lambda t: t.track):
        ev = tr.events
        notes = [e for e in ev if e.kind == 'note']
        if not notes and not any(e.kind in ('cc', 'pb') for e in ev):
            continue
        part = song.part_for_track(tr.track)
        if part.is_voice:
            layer = (part.bank, part.number)
            name = voice_name(*layer)
            gm_name = name
        else:
            name = vs.perf_name(part.perf_bank, part.number) if vs else ''
            layers = vs.perf_layers(part.perf_bank, part.number) if vs else []
            layer = layers[0] if layers else (0, 8)
            gm_name = name
            if vs and (name[:2] in COMBI_CATEGORIES or name[:2] not in GM_BY_NAME):
                gm_name = voice_name(*layer)
        label = f'{part.label} {name}'.strip()
        drum = layer[1] == 63
        shift = part.note_shift
        if vs and not drum and not native:
            shift += vs.voice_note_shift(*layer)

        mt = mido.MidiTrack()
        mid.tracks.append(mt)
        mt.append(mido.MetaMessage('track_name', name=f'Trk{tr.track + 1} {label}', time=0))
        out = []
        if drum:
            ch = 9
            if native:
                keymap = {k: k for k in range(128)}
            elif vs:
                keymap = kit_to_gm(vs.drum_keys(layer[0]))
            else:
                keymap = FACTORY_PTN_TO_GM
        else:
            ch = alloc(tr.track)
            if not native:
                out.append((0, 0, mido.Message('program_change', channel=ch, program=gm_program(gm_name))))
        out.append((0, 0, mido.Message('control_change', channel=ch, control=7, value=min(part.volume, 127))))
        if ch != 9:
            pan = 64 if part.pan is None else max(0, min(127, 64 + part.pan * 2))
            out.append((0, 0, mido.Message('control_change', channel=ch, control=10, value=pan)))
            out.append((0, 0, mido.Message('control_change', channel=ch, control=91, value=part.send_level // 2)))
        for e in ev:
            if e.kind == 'note':
                n = e.a
                if drum:
                    n = keymap.get(n)
                    if n is None:
                        continue
                else:
                    n += shift
                    while n < 0:
                        n += 12
                    while n > 127:
                        n -= 12
                out.append((e.time, 1, mido.Message('note_on', channel=ch, note=n, velocity=max(1, e.b))))
                out.append((e.time + e.gate, 0, mido.Message('note_off', channel=ch, note=n, velocity=0)))
            elif e.kind == 'cc' and not drum and e.a not in (0, 32):
                out.append((e.time, 0, mido.Message('control_change', channel=ch, control=e.a, value=e.b)))
            elif e.kind == 'pb' and not drum:
                out.append((e.time, 0, mido.Message('pitchwheel', channel=ch, pitch=e.a - 8192)))
        _flush(mt, out)
        info.tracks.append(TrackInfo(str(tr.track + 1), label, 'drums' if drum else f'GM {gm_program(gm_name)}',
                                     len(notes)))

    # rhythm track (pattern chain)
    chain = src.rhythm_chain(song_no)
    if chain and song_end > 0:
        part = song.part_for_track(8)
        rbank = part.bank if (part.is_voice and part.number == 63) else 0
        kit = voice_name(rbank, 63) or 'DR PTN'
        if native:
            keymap = {k: k for k in range(128)}
        elif vs:
            keymap = kit_to_gm(vs.drum_keys(rbank))
        else:
            keymap = FACTORY_PTN_TO_GM
        mt = mido.MidiTrack()
        mid.tracks.append(mt)
        mt.append(mido.MetaMessage('track_name', name=f'Rhythm I{rbank + 1}-H8 {kit}', time=0))
        out = [(0, 0, mido.Message('control_change', channel=9, control=7, value=min(part.volume, 127)))]
        t0, count, cache = 0, 0, {}
        for p in chain:
            if t0 >= song_end:
                break
            pat = cache.get(p) or cache.setdefault(p, src.pattern(p))
            pn, pd = METER.get(pat.meter_code, (num, den))
            pbar = pn * PPQ * 4 // pd
            for t, inst, vel in pat.hits:
                key = keymap.get(36 + inst)
                if key is None or t0 + t >= song_end or t >= pat.bars * pbar:
                    continue
                out.append((t0 + t, 1, mido.Message('note_on', channel=9, note=key, velocity=max(1, min(127, vel)))))
                out.append((t0 + t + 24, 0, mido.Message('note_off', channel=9, note=key, velocity=0)))
                count += 1
            t0 += pat.bars * pbar
        _flush(mt, out)
        info.tracks.append(TrackInfo('R', f'Rhythm I{rbank + 1}-H8 {kit}', 'drums', count))

    info.seconds = mid.length
    return mid, info
