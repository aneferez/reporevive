"""AI layer: provider abstraction, grounded findings, and cited chat.

Everything here is designed to degrade gracefully when no Gemini key is
configured, and to never transmit unredacted secrets (PRD sections 7, 16).
"""
