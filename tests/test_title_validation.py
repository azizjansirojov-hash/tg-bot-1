"""Title validation constant alignment."""

from __future__ import annotations

from bot.constants import TITLE_MAX_LEN
from bot.db.models import Movie


def test_title_max_len_matches_model() -> None:
    # movies.title is String(255)
    col = Movie.__table__.c.title
    assert col.type.length == TITLE_MAX_LEN
