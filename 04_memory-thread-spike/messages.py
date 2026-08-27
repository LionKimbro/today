"""Shared transaction records for the three-thread architecture spike."""

from __future__ import annotations

from pprint import pformat

def create_transaction(record):
    """Create one travelling transaction as its history list."""
    return [_empty_record_fields() | record]


def append_record(transaction, record):
    """Append a new immutable record and return its history index."""
    transaction.append(_empty_record_fields() | record)
    return len(transaction) - 1


def _empty_record_fields():
    return {
        "destination": None,
        "operation": None,
        "payload": None,
        "response_destination": None,
        "response_operation": None,
        "response_to": None,
        "continuation": None,
    }


def summarize_transaction(transaction):
    """Return the actual history list as a readable Python data structure."""
    return "transaction: history list\n" + pformat(transaction, sort_dicts=False, width=120)
