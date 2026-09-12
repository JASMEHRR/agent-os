"""Inbox Agent — watches a mailbox and texts about what matters (stage A2).

The second module built *on* the platform rather than as part of it, after
`content_agent`. It reads mail read-only over IMAP, scores each new message
against rules first and a model only where the rules are unclear, and sends a
WhatsApp for the ones that earn an interruption.

What leaves the machine is bounded on purpose: subject, sender and a 600
character snippet, never a whole message, and never at all in rules-only mode.
"""

from inbox_agent.agent import Alert, InboxAgent, RunReport, Watermark
from inbox_agent.messages import Email
from inbox_agent.notify import CallMeBot, Console, Notifier, NotifyError, Twilio
from inbox_agent.sources import ImapSource, MailSource, to_email
from inbox_agent.triage import Importance, Signal, Triage, Verdict

__all__ = [
    "Alert",
    "CallMeBot",
    "Console",
    "Email",
    "ImapSource",
    "Importance",
    "InboxAgent",
    "MailSource",
    "Notifier",
    "NotifyError",
    "RunReport",
    "Signal",
    "Triage",
    "Twilio",
    "Verdict",
    "Watermark",
    "to_email",
]
