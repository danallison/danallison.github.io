// Paperback cover for "You are loved. You are free." books: back, spine and front on one
// sheet, with bleed. Built by scripts/build_book.py (build_cover), which passes the resolved
// cover data as JSON in sys.inputs.cover (sizes in inches, drawing sizes already computed).
//
// Positions and font sizes match the Volume 1 cover (Lulu, 2025), measured from the trim
// edges. Baselines are used for text, as in interior.typ.

#let c = json(bytes(sys.inputs.cover))
#let bleed = c.bleed * 1in
#let w = c.trim.width * 1in
#let h = c.trim.height * 1in
#let spine = c.spine * 1in
#let margin = 0.55in       // from the trim edges to the text and face mark
#let title-margin = 0.57in // from the front's right trim edge to the right-aligned title
#let mark-size = 0.425in   // face mark beside the author name (its frame; ink is 0.41")
#let cap-height = 0.175in  // of 15pt Libre Baskerville; centres the face mark on the text

#set document(title: c.title + " Volume " + str(c.volume) + " (cover)", author: c.author)
#set page(width: 2 * w + spine + 2 * bleed, height: h + 2 * bleed, margin: 0pt)
#set text(font: "Libre Baskerville", size: 15pt, lang: "en", hyphenate: false,
          top-edge: "baseline", bottom-edge: "baseline")

#let back-x = bleed
#let spine-x = bleed + w
#let front-x = bleed + w + spine

// A drawing with its ink box centred at (cx, cy), moved by its dx/dy. Not clipped.
#let drawing(d, cx, cy) = {
  let (x, y, cw, ch) = d.crop
  let full-w = d.width * 1in / cw
  let full-h = d.height * 1in / ch
  place(top + left,
        dx: cx - d.width * 1in / 2 - x * full-w + d.dx * 1in,
        dy: cy - d.height * 1in / 2 - y * full-h + d.dy * 1in,
        image(d.path, width: full-w, height: full-h))
}

// Text whose baseline sits at (x, y). With `width`, the text is aligned within that width.
#let line-at(x, y, body, width: auto, alignment: left) = place(top + left, dx: x, dy: y,
  block(width: width, align(alignment, body)))

#let mark(size) = image(c.face_mark, width: size)

// ---- Front ----

#line-at(front-x, bleed + 0.731in, width: w - title-margin, alignment: right, c.title)
#line-at(front-x, bleed + 1.009in, width: w - title-margin, alignment: right,
         text(weight: "bold")[Volume #c.volume])
#drawing(c.front, front-x + w / 2, bleed + h / 2)
#let author-baseline = bleed + h - 0.674in
#place(top + left, dx: front-x + margin,
       dy: author-baseline - cap-height / 2 - mark-size / 2, mark(mark-size))
#line-at(front-x + margin + mark-size + 0.155in, author-baseline, c.author)

// ---- Back ----

#drawing(c.back, back-x + w / 2, bleed + h / 2)

// ---- Spine (reads top to bottom) ----

// Laid out horizontally as a strip the length of the spine, then rotated a quarter turn
// clockwise: the strip's top edge becomes the spine's front-cover side.
#let spine-mark = calc.min(mark-size, spine - 0.145in)  // keeps 1/16" clear of each fold
#let strip = block(width: h, height: spine, {
  let base = spine / 2 + cap-height / 2 - 0.006in
  line-at(margin, base, [#text(size: 16.5pt, c.title)#box(width: 0.02in) #text(weight: "bold")[Volume #c.volume]])
  context {
    let name-w = measure(c.author).width
    let name-x = h - margin - name-w
    line-at(name-x, base, c.author)
    place(top + left, dx: name-x - 0.167in - spine-mark, dy: (spine - spine-mark) / 2,
          mark(spine-mark))
  }
})
#place(top + left, dx: spine-x, dy: bleed, rotate(90deg, reflow: true, strip))

// ---- Guides (proof only) ----

#if c.guides {
  let thin = 0.5pt
  let trim = (paint: rgb("#e0457b"), thickness: thin)
  let fold = (paint: rgb("#e0457b"), thickness: thin, dash: "dashed")
  let safe = (paint: rgb("#4da3ff"), thickness: thin, dash: "dotted")
  place(top + left, dx: bleed, dy: bleed, rect(width: 2 * w + spine, height: h, stroke: trim))
  for x in (spine-x, front-x) {
    place(top + left, dx: x, dy: 0pt, line(length: h + 2 * bleed, angle: 90deg, stroke: fold))
  }
  for x in (back-x, front-x) {
    place(top + left, dx: x + 0.125in, dy: bleed + 0.125in,
          rect(width: w - 0.25in, height: h - 0.25in, stroke: safe))
  }
  place(top + left, dx: spine-x + 0.0625in, dy: bleed + 0.125in,
        rect(width: spine - 0.125in, height: h - 0.25in, stroke: safe))
  if c.barcode != none {
    let b = c.barcode
    place(top + left, dx: spine-x - (b.inset + b.width) * 1in, dy: bleed + h - (b.inset + b.height) * 1in,
          rect(width: b.width * 1in, height: b.height * 1in, fill: rgb(255, 200, 0, 60),
               stroke: (paint: rgb("#d08a00"), thickness: thin),
               align(center + horizon, text(size: 8pt, top-edge: "cap-height", fill: rgb("#a06000"))[barcode])))
  }
}
