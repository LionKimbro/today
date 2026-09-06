# Tk / Core seam

Tk main thread → plain semantic event queue → Core thread.

Core thread → plain declarative command queue → Tk main thread.

Core blocks for events; Tk drains commands on a small `after()` cadence.

No Tk objects cross the seam.
