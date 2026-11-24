"""Command line interface: sy85tomidi FILE [FILE ...] [-o DIR]"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict

from . import __version__
from .convert import convert
from .format import SY85File, VoiceSet, parse_track_body, read_qx_song, Track


def _safe(s: str) -> str:
    s = re.sub(r'[*/\\:!?._<>|"]+', ' ', s).strip()
    return re.sub(r'\s+', ' ', s) or 'untitled'


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog='sy85tomidi',
        description='Convert Yamaha SY85 sequencer disk files (songs, rhythm patterns) to Standard MIDI Files.')
    ap.add_argument('files', nargs='+', help='SY85 disk files (*.Gnn sequencer or ALL files, *.Xnn, QX5FD *.Ann)')
    ap.add_argument('-o', '--out', default='.', help='output directory (default: current directory)')
    ap.add_argument('-v', '--voices', help='SY85 ALL file to take voice/performance/drum-kit data from '
                    '(needed for sequencer-only files to get sound names and correct GM mapping)')
    ap.add_argument('-s', '--song', type=int, action='append', help='convert only this song number (1-10); repeatable')
    ap.add_argument('-m', '--mode', choices=('gm', 'native'), default='gm',
                    help="gm: General MIDI (default). native: keep SY85 sound names, drum keys and pitches")
    ap.add_argument('--settings-from', metavar='FILE:SONG',
                    help='for QX5FD files: take mixer/tempo settings from this SY85 file and song number')
    ap.add_argument('--keep-duplicates', action='store_true', help='also write songs identical to one already written')
    ap.add_argument('-l', '--list', action='store_true', help='only list the songs and their sounds')
    ap.add_argument('--json', metavar='PATH', help='write a JSON catalog of the converted songs')
    ap.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    a = ap.parse_args(argv)

    voices = None
    if a.voices:
        with open(a.voices, 'rb') as f:
            voices = VoiceSet(f.read())
    os.makedirs(a.out, exist_ok=True)
    seen, catalog, status = {}, [], 0

    for path in a.files:
        with open(path, 'rb') as f:
            data = f.read()
        base = os.path.basename(path)
        stem = re.sub(r'-{2,}', '-', os.path.splitext(base)[0].strip('-')) or 'song'

        if b'QX5FD' in data[:64]:                       # QX5FD song file with SY85 track data
            if not a.settings_from:
                print(f'{base}: QX5FD file - needs --settings-from FILE:SONG for the mixer settings', file=sys.stderr)
                status = 1
                continue
            sfile, sno = a.settings_from.rsplit(':', 1)
            src = SY85File.open(sfile)
            tempo, bodies = read_qx_song(data)
            tracks = []
            for body in bodies:
                ev, bars, end = parse_track_body(body)
                tracks.append(Track(int(sno) - 1, body[0] - 1, ev, bars, end, body))
            jobs = [(src, int(sno) - 1, tracks, tempo, f'{stem} - {_safe(src.song(int(sno) - 1).name)}')]
        else:
            try:
                src = SY85File(data, base)
            except ValueError as e:
                print(e, file=sys.stderr)
                status = 1
                continue
            songs = src.songs_with_notes()
            if a.song:
                songs = [s for s in songs if s + 1 in a.song]
            jobs = [(src, s, None, None, f'{stem} - song{s + 1} - {_safe(src.song(s).name)}') for s in songs]

        for src, s, tracks, tempo, outname in jobs:
            vs = voices or src.voices
            if vs is None:
                print(f'{base}: no voice data - sound names unknown, GM programs default to piano '
                      f'(use --voices ALLFILE)', file=sys.stderr)
            if tracks is None and not a.keep_duplicates:
                h = src.song_hash(s)
                if h in seen:
                    print(f'{base} song {s + 1}: identical to {seen[h]} - skipped')
                    catalog.append({'file': base, 'song': s + 1, 'duplicate_of': seen[h]})
                    continue
            mid, info = convert(src, s, vs, a.mode, tracks=tracks, tempo=tempo, title=outname)
            if a.list:
                print(f'{base} song {s + 1}: {info.name!r} {info.tempo} BPM {info.meter}, {info.bars} bars, '
                      f'{int(info.seconds) // 60}:{int(info.seconds) % 60:02d}')
                for t in info.tracks:
                    print(f'   track {t.track:>2}  {t.sound:28} {t.gm:7} {t.notes:5} notes')
                continue
            fn = outname + ('' if a.mode == 'gm' else ' (SY85)') + '.mid'
            mid.save(os.path.join(a.out, fn))
            if tracks is None:
                seen[src.song_hash(s)] = fn
            catalog.append({'file': base, 'song': s + 1, 'midi': fn, **asdict(info)})
            print(f'{fn:60} {info.tempo:3} BPM {info.meter:5} {int(info.seconds) // 60}:{int(info.seconds) % 60:02d}')

    if a.json:
        with open(a.json, 'w') as f:
            json.dump(catalog, f, indent=1)
    return status


if __name__ == '__main__':
    sys.exit(main())
