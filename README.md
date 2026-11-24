# sy85tomidi

Convert **Yamaha SY85** sequencer disk files to **Standard MIDI Files**, so songs recorded on an SY85
can be played, edited and archived without the instrument.

The SY85 saves its songs in an undocumented binary format. This tool reads it directly: the 8 sequencer
tracks, the rhythm track (drum patterns and pattern chains), tempo, time signature and the song's mixer
(sound per part, volume, pan, note shift, effect send).

* Pure Python, one dependency ([mido](https://github.com/mido/mido)), runs on Windows, macOS and Linux
* No Yamaha data needed at runtime
* Two output modes:
  * **gm** (default): General MIDI. Every track gets a GM instrument chosen from the SY85 sound name,
    drum kits are remapped to GM drum notes, so the file plays on any computer, phone or DAW.
  * **native**: keeps the SY85 sound name on each track, the original drum keys and pitches, and no
    program changes. Use this to play the song on a real SY85/TG500 or with a sampled SY85 instrument.

## Accuracy

The note decoding was checked against a MIDI file that an SY85 exported for the same song:
2554 of 2560 notes are identical in pitch, start, length and velocity. The 6 that differ are
overlapping repeated notes where the SY85's own export is ambiguous.

The format was reverse-engineered from real disk files. It has been tested on a few dozen songs; if a file
of yours does not convert correctly, please open an issue (you can describe the problem without sharing
the file).

## Install

```
pip install sy85tomidi              # once published on PyPI
# or, from a checkout of this repository:
pip install .
```

## Usage

```
sy85tomidi SONGS.G01                       # every song in the file -> ./SONGS - song1 - NAME.mid ...
sy85tomidi *.G?? -o midi/                  # many files into a folder
sy85tomidi SONGS.G01 --list                # show songs, sounds and note counts without writing
sy85tomidi SONGS.G01 --song 3              # only song 3
sy85tomidi SONGS.G01 --voices MYSET.G01    # take sound names from an ALL file (see below)
sy85tomidi SONGS.G01 --mode native         # keep SY85 sound names / drum keys (for SY85 or TG500 playback)
sy85tomidi SONGS.G01 --json catalog.json   # also write a JSON summary (tracks, sounds, effects)
```

`python -m sy85tomidi ...` works as well.

### Which files?

SY85 floppy disks are MS-DOS formatted; the files can be copied with any USB floppy drive or from a
floppy-emulator (Gotek) image.

| File | Contents | Converted |
|---|---|---|
| `NAME.Gnn` sequencer file (starts with `SY85SEQ`) | up to 10 songs + 100 rhythm patterns | yes |
| `NAME.Gnn` ALL file (`SY85ALL...`, 128 KB) | voices + performances + sequencer | yes (uses its own voices) |
| `NAME.Xnn` | sequencer data in the same format | yes |
| `NAME.Ann` starting with `QX5FD` | one song's tracks, without mixer settings | yes, with `--settings-from FILE:SONG` |
| MIDI files exported by the SY85 | already MIDI | no need |

### Sound names and `--voices`

A sequencer-only file stores *which slot* each part plays (for example "internal bank 1, C6") but not
the name of the sound in that slot, which lives in the instrument's voice memory. To get proper
instrument choices pass an ALL file with `--voices`:

* your own ALL-file backup, if you have one (it matches the sounds the songs were made with), or
* the SY85 factory set, if the songs used factory sounds.

Without `--voices`, sequencer-only files still convert with all notes, tempo, mixer and drums, but tracks
default to piano and the drum kit is assumed to be the factory "DR PTN" kit.

### Duplicates

Songs that are byte-identical to one already converted (common when the same song was saved to several
disks) are skipped; use `--keep-duplicates` to write them anyway.

## What is not converted

* The sounds themselves: the SY85 voices are AWM samples in the instrument's ROM. In `gm` mode they are
  approximated with General MIDI instruments.
* Song effects (reverb, chorus, ...) are decoded and reported in `--json` output but not rendered;
  the per-part effect send is written as CC 91.
* Pitch-bend range is left at the receiver's default.

## As a library

```python
from sy85tomidi import SY85File, convert

f = SY85File.open('SONGS.G01')
for n in f.songs_with_notes():
    mid, info = convert(f, n, mode='gm')
    print(info.name, info.tempo, info.meter, [t.sound for t in info.tracks])
    mid.save(f'{info.name}.mid')
```

## File format

[FORMAT.md](FORMAT.md) documents everything that was decoded: song/multi blocks, track events, rhythm
patterns and chains, voice and performance banks, and the song effect block.

## Credits

* Christopher Arndt's notes on the SY85 disk/SysEx layout
  ([YamahaMusicians forum](https://yamahamusicians.com/forum/threads/sy85-sysex-data-research.3231/))
  describe the overall file layout and were the starting point for this work.
* Parameter ranges and effect lists come from the Yamaha SY85 Owner's Manual (not included here).

Yamaha, SY85 and TG500 are trademarks of Yamaha Corporation. This project is not affiliated with or
endorsed by Yamaha.

## License

MIT, see [LICENSE](LICENSE).
