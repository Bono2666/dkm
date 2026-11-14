# -*- coding: utf-8 -*-
"""Minimal Fonnte (https://fonnte.com) WhatsApp gateway client."""

import logging
import re

import requests

_logger = logging.getLogger(__name__)

FONNTE_SEND_URL = 'https://api.fonnte.com/send'
FONNTE_TIMEOUT = 15


def normalize_wa_number(raw):
    """Return an Indonesian WhatsApp number as digits with the 62 prefix.

    Accepts ``0812-3456-7890``, ``+62 812 3456 7890``, ``62812...`` and
    ``812...``. Returns an empty string when nothing usable is left.
    """
    digits = re.sub(r'\D', '', raw or '')
    if not digits:
        return ''
    if digits.startswith('0'):
        digits = '62' + digits[1:]
    elif digits.startswith('8'):
        digits = '62' + digits
    if len(digits) < 10 or len(digits) > 15:
        return ''
    return digits


def send_message(token, target, message):
    """Send one WhatsApp text through Fonnte.

    Returns ``(ok, detail)``; never raises, so a gateway problem can only
    degrade delivery and never break an approval transaction.
    """
    if not token:
        return False, "Token Fonnte belum diisi di Pengaturan."
    if not target:
        return False, "Nomor WhatsApp tujuan kosong atau tidak valid."
    try:
        response = requests.post(
            FONNTE_SEND_URL,
            headers={'Authorization': token},
            data={'target': target, 'message': message, 'countryCode': '62'},
            timeout=FONNTE_TIMEOUT,
        )
    except requests.RequestException as exc:
        _logger.warning("Fonnte request failed: %s", exc)
        return False, "Gagal menghubungi Fonnte: %s" % exc
    try:
        payload = response.json()
    except ValueError:
        return False, "Respon Fonnte tidak valid (HTTP %s)." % response.status_code
    if response.ok and payload.get('status'):
        return True, str(payload.get('id') or payload.get('detail') or 'OK')
    reason = payload.get('reason') or payload.get('detail') or response.text
    return False, "Fonnte menolak: %s" % reason
