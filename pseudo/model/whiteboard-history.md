# Whiteboard history

Canonical panel fields: `text` is HEAD; `history` is newest-first snapshots.
Each snapshot has `text` and `timestamp`.

Core's `history-cursor` is `0` for HEAD, or `1..n` for a snapshot.
It remains with that whiteboard while another panel is hosted.

- `SNAPSHOT` preserves HEAD.
- Moving the cursor only changes the view.
- First text edit from history snapshots the prior HEAD, makes the edited
  historical text the new HEAD, and returns the cursor to `0`.
