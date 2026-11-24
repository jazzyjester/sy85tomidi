# Yamaha SY85 disk file format (sequencer, voices, performances)

Reverse-engineered from SY85 disk files and checked against a Standard MIDI File exported by the SY85
for the same song (2554/2560 notes identical). Offsets are hexadecimal. Multi-byte values are big-endian
unless noted. "?" marks bytes whose meaning is unknown.

Status: everything needed to reproduce the music is decoded. Some settings bytes are not.

## 1. Files

| Signature at offset | File type | Size |
|---|---|---|
| `SY85SEQ` at 0x0000 | sequencer only (songs + rhythm patterns) | variable |
| `SY85ALL` / `SY85NALL` / `SY85SYNALL` at 0x0000, `SY85SEQ` at 0x10000 | ALL: voices + performances + sequencer | 0x10000 + SEQ |
| `QX5FD` at 0x0000 | single song tracks (seen with `.Ann` extension) | variable |

The signatures are always at a 64 KB boundary (0x0000 or 0x10000). Below, offsets in the SEQ section are
relative to the start of `SY85SEQ`, offsets in the ALL section relative to `SY85...ALL`.

## 2. SEQ section

| Offset | Size | Contents |
|---|---|---|
| 0x0000 | 7 | `SY85SEQ` |
| 0x0040 | 10 × 198 | song/multi blocks (section 3) |
| 0x0800 | 100 × 2 | rhythm pattern start pointers (`0x8000 | offset`, relative to 0x0CC6) |
| 0x08C8 | 10 × 2 | song rhythm-chain pointers (bit 15 set = song has a rhythm track) |
| 0x08DC | 2 | end-of-pattern-data pointer |
| 0x08DE | 100 | pattern meter codes |
| 0x0942 | 100 | pattern lengths (bars − 1) |
| 0x09A6 | 100 × 8 | pattern names (ASCII) |
| 0x0CC6 | … | pattern and chain data (section 5) |
| 0x3400 | … | track data (section 4) |

Meter codes (songs and patterns): 1 = 2/4, 2 = 3/4, 3 = 4/4, 4 = 5/4, 5 = 12/8.

## 3. Song / multi block (198 bytes)

| Offset | Size | Contents |
|---|---|---|
| 0x00 | 49 | effect settings (section 7) |
| 0x31 | 8 | song name (ASCII) |
| 0x39 | 9 | track → part table: tracks 1–8 and the rhythm track; low nibble = part 0–15 |
| 0x42 | 1 | meter code |
| 0x43 | 1 | ? |
| 0x44 | 2 | tempo in BPM, 14-bit (`hi * 128 + lo`) |
| 0x46 | 16 × 8 | parts (below) |

Part (8 bytes):

| Byte | Contents |
|---|---|
| 0 | bank: voices 0–3 = I1–I4; performances 0 = I1, 2 = I2 |
| 1 | `0x80` + `0x40` if a voice (clear = performance) + number 0–63 (slot A1 = 0 … H8 = 63) |
| 2 | volume 0–127 |
| 3 | note shift + 0x40 (semitones) |
| 4 | tune + 0x40 (−63…+63, about 1.17 cent per step) |
| 5 | pan: 0x01–0x3F = −31…+31 around 0x20; 0x40 = use the voice's own pan ("vce") |
| 6 | effect send switches: bit0 1a, bit1 1b, bit2 2a, bit3 2b, bit4 dry 1, bit5 dry 2; bit6 = send source is the voice ("VCE") |
| 7 | effect send level 0–127 |

Voice slot 63 (H8) of every bank is the bank's drum kit.

## 4. Tracks

Track data starts at SEQ+0x3400 as a list of blocks:

```
F0  <song << 4 | track>  <delta>  events...  F2
```

`track` is 0–7. A run of `F8` bytes after the last `F2` marks free memory (end of data).

Times are in ticks at **96 per quarter note**. A *delta* is a sequence of bytes < 0x80 forming a 7-bit
big-endian number (zero bytes = no delta). Each event is followed by a delta to the next event.

| Bytes | Event |
|---|---|
| `80`–`BF` | note: gate = `(b & 0x3F) × 4` ticks, followed by the note byte |
| `C0`–`EF` `lo` | note with long gate: gate = `((b & 0x3F) << 7 | lo) × 4` ticks, then the note byte |
| note byte | `0x00`–`0x7F`: note number, followed by a velocity byte; `0x80`–`0xFF`: note `& 0x7F` with velocity 64 (no velocity byte) |
| `F5` | bar line |
| `FB cc val` | control change |
| `FE lsb msb` | pitch bend (14-bit, centre 0x2000) |
| `FC prog` | program change |
| `F8` | prefix/filler, ignored |

Example: `00 98 3C 64 60` = at the current time, note 60, velocity 100, gate 24 × 4 = 96 ticks;
then advance 96 ticks.

Note numbers are as played; the part's note shift and the voice's own note shift (voice record byte 89)
apply on playback.

## 5. Rhythm patterns and chains

**Pattern** data (at 0x0CC6 + pointer): an optional leading `0x80`, then pairs `[instrument][velocity]`.
Bytes ≥ 0x80 between pairs advance time by `b & 0x7F` steps of 1/48 quarter note. Instrument *n* plays
key 36 + *n* of the rhythm part's drum kit. Hits beyond the pattern's length (from 0x0942 and the meter at
0x08DE) are not played.

**Chain** (song rhythm track, at 0x0CC6 + chain pointer): a list of pattern numbers 0–99 played in order,
with:

| Tokens | Meaning |
|---|---|
| `C8 … C9 n C9` | repeat the enclosed part *n* + 1 times (can be nested) |
| `CA x CA` | setting (skipped) |
| `CB x y CB` | setting (skipped) |

The rhythm track uses the part assigned to track 9 in the song's track table. Its chain usually runs past
the end of the recorded tracks; converters stop it at the end of the song.

## 6. ALL section: voices and performances

| Offset | Contents |
|---|---|
| 0x014A | performance bank I1: 64 × 168 bytes |
| 0x814A | performance bank I2: 64 × 168 bytes |
| 0x2BEA, 0x55F0, 0xABEA, 0xD5F0 | voice banks I1–I4: 63 × 162-byte voices, then a 552-byte drum voice (H8) |

Voice (162 bytes): name at +0x31 (8 ASCII chars, the first two being the category, e.g. `BA Frtls`);
note shift + 0x40 at +89.

Drum voice (552 bytes): name at +0x31; 49 key records of 10 bytes from +0x3E for keys 36–84;
in each, byte 1 = AWM wave number, byte 4 = pitch (0x40 = original), byte 7 = effect send level.

Performance (168 bytes): name at +0x31; four layers of 28 bytes from +0x3C: byte 0 = voice bank,
byte 1 = `0x80` (layer on) + voice number.

## 7. Song effect block (song bytes 0x00–0x30)

| Offset | Contents |
|---|---|
| 0x01 | mode: 0 off, 1 serial, 2 parallel |
| 0x02 | effect 1 type (0–90) |
| 0x03 | effect 2 type (0–90) |
| 0x04–0x09 | controller assignments (not fully decoded) |
| 0x0A–0x11 | effect 1 parameters 1–4 (16-bit, signed) |
| 0x12–0x15 | effect 1 parameters 5–8 (8-bit) |
| 0x16, 0x17 | effect 1 output levels a, b (0–100) |
| 0x18–0x1F | effect 2 parameters 1–4 (16-bit, signed) |
| 0x20–0x23 | effect 2 parameters 5–8 (8-bit) |
| 0x24, 0x25 | effect 2 output levels a, b |
| 0x26, 0x27 | output 1 / output 2 wet % (dry = 100 − wet) |
| 0x28–0x30 | mix/insert levels, LFO, … (not fully decoded) |

Parameter values are raw. Many are table indexes; for reverb time, index *n* = 0.3 s + 0.1 s × *n* in
the low range (the manual's "InitSong" default index 11 = 1.4 s). Some parameters use offsets, for
example pitch-change fine tune is stored + 100 and feedback gain + 99.
The meaning of parameters 1–8 for each effect type is listed in the SY85 manual. Effect type numbers
follow the manual's list (1 Rev. Hall1 … 8 Rev. Plate … 21 Pit Chnge2 … 34 Cho→Rev … 90 Pha & Pha).

## 8. QX5FD song files

Seen with an `.Ann` extension: a header starting with `QX5FD`, tempo in BPM at 0x21, and SY85 track blocks
(section 4) from about 0x200. The track number byte in these blocks is 1-based (`01` = track 1).
The file holds no mixer settings; take them from a song in a sequencer file.

## 9. Unknown

* Song block byte 0x43 and parts of the effect block (0x04–0x09, 0x28–0x30).
* `CA` / `CB` chain settings (probably tempo/volume changes in the rhythm chain).
* Most of the voice and performance parameters (elements, envelopes, filters), which aren't needed to
  reproduce the notes.
