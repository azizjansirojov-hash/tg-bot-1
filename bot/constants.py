"""Shared validation constants used across handlers and middleware."""

from __future__ import annotations

import re

# Max length for numeric movie codes accepted from users/admins.
# DB column is String(64); we enforce a stricter processing bound.
CODE_MAX_LEN = 32

CODE_RE = re.compile(rf"^\d{{1,{CODE_MAX_LEN}}}$")

# Max length for movie titles (matches movies.title String(255)).
TITLE_MAX_LEN = 255

# Telegram sendMessage text limit.
BROADCAST_TEXT_MAX_LEN = 4096

# Outbound broadcast pace (messages to distinct chats per second).
BROADCAST_SENDS_PER_SECOND = 25
