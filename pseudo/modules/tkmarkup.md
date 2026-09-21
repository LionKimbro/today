# `tkmarkup.py`

OWNS: TkMarkup lexical recognition, temporary dict/list element records,
idempotent GUID normalization, and UUID-targeted line mutations.

DOES NOT OWN: panels, revisions, Core state, Tk widgets/modes, or thread seams.

Text remains line-preserving. Reference: `docs/raw/0400__tkmarkup.txt`.
