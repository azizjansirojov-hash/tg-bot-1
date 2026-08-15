"""FSM states for admin broadcast."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AdminBroadcast(StatesGroup):
    """
    /broadcast flow:

      1. waiting_for_text — admin sends the plain-text body
      2. confirming — inline Yes/No; send starts only after Yes
    """

    waiting_for_text = State()
    confirming = State()
