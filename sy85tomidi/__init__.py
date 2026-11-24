"""sy85tomidi - convert Yamaha SY85 sequencer disk files to Standard MIDI Files."""
__version__ = '0.1.0'

from .format import SY85File, VoiceSet, Song, Part, Track, Event, Pattern  # noqa: F401
from .convert import convert  # noqa: F401
