"""FSM states for admin video capture flow."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AdminAddMovie(StatesGroup):
    """
    Multi-step conversation after an admin forwards a video from the storage channel.

    Flow:
      1. waiting_for_code  — admin enters a unique numeric code
      2. confirming_overwrite — (via callback) only if code already exists
      3. waiting_for_title — admin enters a title, or "-" to skip
      4. confirming_save — (via callback) explicit Ha/Yo'q before DB write
    """

    waiting_for_code = State()
    waiting_for_title = State()
    confirming_overwrite = State()
    confirming_save = State()
