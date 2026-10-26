"""Explicit private local fixtures; game files are never supplied by the repo."""
import os
from pathlib import Path
def game_file(relative=""):
 value=os.environ.get('ZGTA_GAME_MIRROR')
 if not value:raise RuntimeError('Set ZGTA_GAME_MIRROR to your own matching prepared game folder for fixture-dependent tests.')
 return Path(value).expanduser()/relative
