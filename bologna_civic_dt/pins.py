"""The urban pack's PINs (see the core's civic_engagement/pins.py): an
Italian word and three digits, "gabbiano515" — easy to say across a table
and to type on a phone. The word is the distinct part: no two PINs of a
site share it, so a word misheard is a wrong PIN, not someone else's.

The words, 1078 nouns, are in words_it.txt; 1,078,000 PINs.
"""

import re
import secrets
import unicodedata
from functools import cache
from pathlib import Path

from civic_engagement.pins import PinFormat

WORDS_FILE = Path(__file__).with_name("words_it.txt")


@cache
def words() -> tuple[str, ...]:
    lines = WORDS_FILE.read_text().splitlines()
    return tuple(line.strip() for line in lines if line.strip() and not line.startswith("#"))


class WordPin(PinFormat):
    example = "gabbiano515"

    @property
    def size(self) -> int:
        return len(words()) * 1000

    def generate(self, taken: set[str]) -> str:
        free = [word for word in words() if word not in taken]
        if not free:
            raise ValueError(f"all {len(words())} words are in use")
        return f"{secrets.choice(free)}{secrets.randbelow(1000):03d}"

    def normalise(self, text: str) -> str:
        """Forgiving: capitals, accents, spaces, hyphens, the digits first —
        "Gabbiano 515", "gabbiano-515" and "515 gabbiano" are "gabbiano515"."""
        plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
        return "".join(re.findall(r"[a-z]", plain)) + "".join(re.findall(r"[0-9]", plain))

    def distinct(self, pin: str) -> str:
        return re.match(r"[a-z]*", pin).group()
