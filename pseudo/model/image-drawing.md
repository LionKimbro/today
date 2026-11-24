# Image drawing and ordinary close

OWNS: the drawing/save boundary shared by Tk, Core, Mem, and Disk.

Tk owns the Pen toggle, immediate canvas feedback, and the unfinished stroke.
At release or leave/close, send a completed stroke to Core. Coordinates are
normalized against the displayed, orientation-corrected image, not the canvas;
width is a fraction of its shorter dimension. One red pen, no export/flatten.

Core owns working `image-strokes`, dirty state, and edit/save generations.
Mem owns accepted stroke data in the panel; Disk serializes it with the day.
Original asset files never change. Old records without strokes mean empty.

Reset one 60-second Tk save timer per panel after each completed stroke;
cancel it while actively drawing. Leaving/tab/day change finishes any active
stroke and submits pending drawing saves without a Disk acknowledgement.
Widget teardown also submits any unfinished/pending drawing before destruction.

Ordinary close finishes strokes and requests all dirty panel commits. Core
remains alive until latest generations are accepted by Mem, then sends its
existing stop effects. Mem flushes before its join, Disk drains before its
sentinel/join. A commit conflict during close is an error, not a saved exit.
Fatal worker shutdown retains its existing lossy, controlled exit policy.

ENSURES: a save snapshot cannot be mutated by subsequent strokes; late preview
results cannot erase ink; scaling/multiple hosts preserve image-relative marks.
Clear image removes both the reference and strokes. No drawing history,
eraser, export, clipboard flattening, recovery, or worker hang timeout.
