# Positions and panels

## Positions

`positions` maps a position id to one position record.

| Field | Meaning |
| --- | --- |
| `id` | Position identity |
| `tab-id` | Tab containing the position |
| `panel-id` | Panel currently hosted there |

`positions["position-1"]["panel-id"]` may be `"panel-1"` or `"panel-2"`.

## Panels

Mem canonically owns `panels`, mapping a panel id to its record.

Core may retain a visible panel snapshot; Mem remains canonical.

| Field | Meaning |
| --- | --- |
| `id` | Panel identity |
| `type` | Panel kind: currently `WHITEBOARD` |
| `label` | Visible label |
| `text` | Whiteboard contents |
| `revision` | Canonical update revision |

## Hosting

`position["panel-id"]` names the panel hosted by that position.

Changing the field changes hosting. The position and both panel records remain.

Core's snapshot may additionally hold `dirty`, `awaiting`, `edit-generation`,
and `save-generation`. Those are working facts, never canonical Mem fields.
