from bologna_civic_dt.pins import WordPin, words
from civic_engagement.pins import MIN_SIZE, checked


def test_words():
    listed = words()
    assert len(listed) == len(set(listed)) >= 1000
    assert all(word.isascii() and word.isalpha() and word.islower() for word in listed)
    # BIP-0039's: no two words alike in their first four letters.
    assert len({word[:4] for word in listed}) == len(listed)
    assert WordPin().example[:-3] in listed


def test_word_pins():
    pins = checked(WordPin())
    assert pins.size >= MIN_SIZE
    pin = pins.generate(set())
    word, digits = pin[:-3], pin[-3:]
    assert word in words() and digits.isdigit()
    assert pins.distinct(pins.normalise(pin)) == word
    for typed in ("Gabbiano 515", "gabbiano-515", " 515 GABBIANO ", "gabbiàno515"):
        assert pins.normalise(typed) == "gabbiano515"
    # A word in use isn't given again.
    taken = set(words()) - {"zuppa"}
    assert pins.generate(taken).startswith("zuppa")
