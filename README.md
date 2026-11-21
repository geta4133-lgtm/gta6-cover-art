# gta6-cover-art-01

A fully deterministic, dependency-free cover-art generator that renders a
GTA VI themed poster in the style of a neon Miami sunset — as a 1080x1350
(4:5 portrait) PNG.

Everything is procedural:

- Hand-rolled PNG encoder — raw scanlines + `zlib` compression, IHDR/IDAT/IEND
  chunks with CRCs written manually. No PIL, no image libs.
- Software rasterizer — gradients, circle fill, scanline polygon fill, DDA
  lines, and glow blending implemented from scratch in `main.py`.
- Neon Miami sunset palette — indigo→purple→hot pink→orange sky, retro
  slatted sun with a glow halo, pink/cyan perspective grid ocean, and a sun
  reflection column.
- Palm tree silhouettes — curved trunks, 9-frond fans, coconuts; seeded
  randomization so output is byte-identical across runs.
- Bold title block — "GTA VI" in a custom 5x7 pixel bitmap font scaled up,
  with a neon drop shadow, cyan/hot-pink keylines, a "VICE ISLES" subtitle,
  and a footer credit line.
- Neon inner frame with corner ticks.

No copyrighted assets, logos, fonts, or artwork are embedded — all shapes and
glyphs are original code-generated approximations (fan-art style).

## Run

```bash
python3 main.py
```

Output: `gta6-cover-art-01.png` (1080x1350, 8-bit RGB PNG).

## Determinism

Uses only Python stdlib (`math`, `struct`, `zlib`, `random` with fixed seeds).
Run it twice — the files are byte-identical:

```bash
python3 main.py && sha256sum gta6-cover-art-01.png
python3 main.py && sha256sum gta6-cover-art-01.png
```

## License

MIT — see `LICENSE`.
