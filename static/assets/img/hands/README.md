# Gloved-hand renders

Photo-style renders of a blue nitrile glove, laid over the animal a bench draws.

| File | Used in | Pose |
|---|---|---|
| `scruff.webp` | Exp 01, routes of administration | Thumb and index finger lifting the scruff |
| `tail.webp` | Exp 04 Rota-Rod and Exp 09 actophotometer | A fist, drawn mirrored. The bench draws the tail itself, through the gap between the fingers |
| `hold.webp` | Exp 21, paw oedema | Thumb behind the neck, fingers round the chest (drawn mirrored, because the rat faces right) |

They are drawn by `handArt()` in `static/assets/js/animal-art.js`.

## Where they come from

AI renders (Google Gemini) made by the project owner, each showing a gloved hand holding a white rat.
Only the glove is kept: `tools/hand-sprites/cut.py` picks it out by its colour, fades the cut wrist
and saves the three files here. The full renders are kept in `tools/hand-sprites/renders/`, which is
not in the repository because of its size.

To replace a hand, put the new render in that folder under the same name (`a.png` scruff, `b.png`
holding upright, `d.png` hanging by the tail), run the script, then raise `HAND_VER` in
`animal-art.js` so browsers fetch the new file. A new render needs a blue glove on a pale background;
if the pose changes, the position in the bench has to be set again.
