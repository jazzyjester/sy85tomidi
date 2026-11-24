"""Tests on synthetic SY85 data (no Yamaha or user files needed)."""
import mido
import pytest

from sy85tomidi import SY85File, convert
from sy85tomidi.format import parse_track_body, split_track_blocks, TRACK_AREA, SONG_BLOCK
from sy85tomidi.gm import gm_program, kit_to_gm, GM_KIT_REFERENCE
from sy85tomidi import effects

# track body: song 0 / track 0, then events
#   delta 0 | gate 24*4, note 60, vel 100 | delta 96 | gate 24*4, note 62 (high bit -> velocity 64)
#   delta 96 | bar line | delta 0 | CC 7 = 80 | delta 0 | pitch bend lsb 0 msb 0x50 | delta 0
BODY = bytes([0x00, 0x00, 0x98, 60, 100, 0x60, 0x98, 0x80 | 62, 0x60, 0xF5, 0x00,
              0xFB, 7, 80, 0x00, 0xFE, 0x00, 0x50, 0x00])


def make_file(tempo=120, name=b'TESTSONG', meter=3):
    d = bytearray(0x4000)
    d[0:7] = b'SY85SEQ'
    blk = bytearray(SONG_BLOCK)
    blk[0x31:0x39] = name
    blk[0x39:0x42] = bytes(range(8)) + bytes([15])          # track n -> part n, rhythm -> part 16
    blk[0x42] = meter
    blk[0x44], blk[0x45] = tempo // 128, tempo % 128
    for p in range(16):                                      # part: I1 voice C6, vol 100, centre
        blk[0x46 + 8 * p:0x4E + 8 * p] = bytes([0, 0xC0 | 21, 100, 0x40, 0x40, 0x20, 0x3F, 64])
    d[0x40:0x40 + SONG_BLOCK] = blk
    t = TRACK_AREA
    d[t:t + 1] = b'\xF0'
    d[t + 1:t + 1 + len(BODY)] = BODY
    d[t + 1 + len(BODY)] = 0xF2
    d[t + 2 + len(BODY):t + 2 + len(BODY) + 16] = b'\xF8' * 16
    return bytes(d)


def test_parse_track_body():
    ev, bars, end = parse_track_body(BODY)
    notes = [e for e in ev if e.kind == 'note']
    assert [(e.time, e.a, e.b, e.gate) for e in notes] == [(0, 60, 100, 96), (96, 62, 64, 96)]
    assert bars == [192]
    cc = [e for e in ev if e.kind == 'cc'][0]
    assert (cc.time, cc.a, cc.b) == (192, 7, 80)
    pb = [e for e in ev if e.kind == 'pb'][0]
    assert pb.a == 0x50 << 7
    assert end == 192


def test_two_byte_gate():
    body = bytes([0x00, 0x00, 0xC1, 0x10, 0x80 | 60, 0x00])   # gate ((1 << 7) | 16) * 4 = 576
    ev, _, _ = parse_track_body(body)
    assert ev[0].gate == 576 and ev[0].a == 60 and ev[0].b == 64


def test_split_blocks_stops_at_free_memory():
    data = b'\xF0\x00\x00\xF2\xF8\xF0\x01\x00\xF2'
    assert split_track_blocks(data, 0) == [b'\x00\x00']


def test_song_settings():
    f = SY85File(make_file(tempo=105))
    s = f.song(0)
    assert s.name == 'TESTSONG' and s.tempo == 105 and s.meter_code == 3
    p = s.part_for_track(0)
    assert p.is_voice and p.bank == 0 and p.number == 21 and p.label == 'I1-C6'
    assert p.volume == 100 and p.pan == 0 and p.send_level == 64
    assert f.songs_with_notes() == [0]
    assert f.rhythm_chain(0) is None


def test_convert_gm():
    f = SY85File(make_file(tempo=105))
    mid, info = convert(f, 0)
    assert info.tempo == 105 and info.meter == '2/4'
    ons = [m for m in mid.tracks[1] if m.type == 'note_on']
    assert [m.note for m in ons] == [60, 62]
    tempos = [m for m in mid.tracks[0] if m.type == 'set_tempo']
    assert round(mido.tempo2bpm(tempos[0].tempo)) == 105


def test_not_sy85():
    with pytest.raises(ValueError):
        SY85File(b'\x00' * 100)


def test_gm_program():
    assert gm_program('BA Frtls') == 35
    assert gm_program('AP Grand') == 0
    assert gm_program('WN Tenor') == 66
    assert gm_program('XX Whatever') == 0


def test_kit_to_gm_identity_on_reference():
    m = kit_to_gm(GM_KIT_REFERENCE)
    assert m[36] == 36 and m[38] == 38 and m[42] == 42


def test_effects_decode():
    b = bytearray(49)
    b[1], b[2], b[3] = 1, 8, 21
    b[10:12] = (0, 25)
    d = effects.decode(bytes(b))
    assert d['mode'] == 'serial'
    assert d['effect1']['name'] == 'Rev. Plate' and d['effect2']['name'] == 'Pit Chnge2'
    assert d['effect1']['params'][0] == 25
