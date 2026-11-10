// Interior layout for "You are loved. You are free." books.
// Built by scripts/build_book.py, which passes the resolved book data as JSON in
// sys.inputs.book (drawing sizes already computed) and the bleed in inches.
//
// Positions are baselines measured from the top of the trimmed page, matching the
// Volume 1 interior (originally laid out in Google Docs).

#let book = json(bytes(sys.inputs.book))
#let bleed = float(sys.inputs.at("bleed", default: "0")) * 1in
#let trim-w = book.trim.width * 1in
#let trim-h = book.trim.height * 1in
#let margin = 1in
// Line pitch as a multiple of font size (Google Docs' default line spacing).
#let pitch = 1.426em

#set document(title: book.title + " Volume " + str(book.volume), author: book.author)
#set page(width: trim-w + 2 * bleed, height: trim-h + 2 * bleed, margin: 0pt)
// Baseline-to-baseline text boxes make `leading` the exact line pitch.
#set text(font: "Libre Baskerville", size: 10pt, lang: "en", hyphenate: false,
          top-edge: "baseline", bottom-edge: "baseline")
#set par(leading: pitch, spacing: 2 * pitch, linebreaks: "simple")

// Place content so its first baseline sits at `y` below the top of the trimmed page.
#let at(y, body, x: 0in, width: trim-w) = place(top + left, dx: bleed + x, dy: bleed + y,
                                                 block(width: width, body))
#let text-width = trim-w - 2 * margin
#let markup(s) = eval(s, mode: "markup")

// A drawing centered on the page. With `crop` ([x, y, w, h] fractions of the frame), that
// part of the image (its ink) is what's centered at d.width × d.height; the rest of the
// image is still drawn around it, not clipped.
#let centered(d) = {
  let (x, y, w, h) = if d.crop == none { (0, 0, 1, 1) } else { d.crop }
  let full-w = d.width * 1in / w
  let full-h = d.height * 1in / h
  place(top + left,
        dx: bleed + (trim-w - d.width * 1in) / 2 - x * full-w + d.dx * 1in,
        dy: bleed + (trim-h - d.height * 1in) / 2 - y * full-h + d.dy * 1in,
        image(d.path, width: full-w, height: full-h))
}

// Title page
#at(3.629in, align(center, text(size: 19pt, book.title)))
#at(4.005in, align(center, text(size: 19pt, weight: "bold")[Volume #book.volume]))
#at(4.631in, align(center, text(size: 14pt)[by #book.author]))
#pagebreak()

// Copyright page
#at(2.398in, x: margin, width: text-width, align(center, markup(book.copyright)))
#pagebreak()

// Dedication
#at(2.451in, x: margin, width: text-width,
    align(center, text(size: 11pt, style: "italic", book.dedication)))

// Preface (flows onto more pages if needed)
#page(margin: (left: bleed + margin, right: bleed + margin, top: bleed + 1.212in, bottom: bleed + margin))[
  #block(below: 1.531in - 1.212in, text(size: 16pt, weight: 600)[Preface])
  #set par(justify: true)
  #markup(book.preface)
]

// Drawings, one per page, numbered from 1
#for (i, d) in book.drawings.enumerate() {
  page[
    #at(0.631in, align(center, book.title))
    #centered(d)
    #at(7.704in, align(center, str(i + 1)))
  ]
}

// End mark
#if book.at("end_mark", default: none) != none {
  page(centered(book.end_mark))
}
