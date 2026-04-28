import unittest

from app import (
    FIRST_REPLY_PROMPT,
    FOLLOW_UP_REPLY_PROMPT,
    app,
    build_messages,
    detect_emergency,
)


class CareBuddyAppTests(unittest.TestCase):
    def test_detect_emergency_when_red_flag_is_present(self):
        self.assertTrue(detect_emergency("I have chest pain and trouble breathing right now."))

    def test_detect_emergency_ignores_negated_red_flags(self):
        self.assertFalse(
            detect_emergency("Mostly a sore throat and low energy since yesterday, no trouble breathing or chest pain.")
        )

    def test_build_messages_uses_first_reply_prompt_without_history(self):
        with app.test_request_context("/"):
            messages = build_messages("I do not feel well.")
        self.assertEqual(messages[-2]["content"], FIRST_REPLY_PROMPT)

    def test_build_messages_uses_follow_up_prompt_after_assistant_reply(self):
        with app.test_request_context("/"):
            from flask import session

            session["chat_history"] = [
                {"role": "user", "content": "I do not feel well."},
                {"role": "assistant", "content": "What symptoms are you noticing?"},
            ]
            messages = build_messages("Mostly a sore throat and low energy since yesterday.")

        self.assertEqual(messages[-2]["content"], FOLLOW_UP_REPLY_PROMPT)


if __name__ == "__main__":
    unittest.main()
