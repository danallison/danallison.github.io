window.manus = {}

manus.hands = {
    left: {
        transform: 'translate(-140, 128), scale(0.86), rotate(-20)'
    },
    right: {
        transform: 'scale(-1,1), translate(-800), translate(-140, 128), scale(0.86), rotate(-20)'
    }
}
manus.letterCoordinates = {
  a: {
    x: 160,
    y: 100
  },
  b: {
    x: 150,
    y: 170
  },
  c: {
    x: 140,
    y: 250
  },
  d: {
    x: 240,
    y: 230
  },
  e: {
    x: 300,
    y: 195
  },
  f: {
    x: 335,
    y: 150
  },
  g: {
    x: 380,
    y: 100
  },
  h: {
    x: 420,
    y: 55
  },
  i: {
    x: 510,
    y: 95
  },
  j: {
    x: 450,
    y: 140
  },
  k: {
    x: 395,
    y: 190
  },
  l: {
    x: 350,
    y: 230
  },
  m: {
    x: 365,
    y: 270
  },
  n: {
    x: 410,
    y: 240
  },
  o: {
    x: 460,
    y: 200
  },
  p: {
    x: 520,
    y: 155
  },
  q: {
    x: 525,
    y: 245
  },
  r: {
    x: 470,
    y: 280
  },
  s: {
    x: 420,
    y: 310
  },
  t: {
    x: 375,
    y: 330
  },
  u: {
    x: 315,
    y: 370
  },
  v: {
    x: 245,
    y: 410
  },
  w: {
    x: 195,
    y: 320
  },
  x: {
    x: 255,
    y: 295
  },
  y: {
    x: 300,
    y: 275
  },
  z: {
    x: 270,
    y: 335
  }
}
manus.letters = 'abcdefghijklmnopqrstuvwxyz'.split('')
manus.vowels = 'aeiou'.split('')
manus.numbers = manus.letters.map((letter, i) => i)
manus.numberCoordinates = manus.letters.map(letter => manus.letterCoordinates[letter])
manus.width = 640 * 2
manus.height = 480

manus.createSVGElement = (tag, attrs) => {
    const el = document.createElementNS("http://www.w3.org/2000/svg", tag)
    if (attrs) Object.keys(attrs).forEach(key => {
        el.setAttribute(key, attrs[key])
    })
    return el
}

manus.circle = (xy, attrs = {}) => {
    if (typeof xy === 'string') xy = manus.letterCoordinates[xy]
    return manus.createSVGElement('circle', {
        cx: xy.x,
        cy: xy.y,
        r: 10,
        ...attrs
    })
}

manus.line = (xy1, xy2, attrs) => {
    if (manus.letterCoordinates[xy1]) {
        xy1 = manus.letterCoordinates[xy1]
    }
    if (manus.letterCoordinates[xy2]) {
        xy2 = manus.letterCoordinates[xy2]
    }
    return manus.createSVGElement('line', {
        x1: xy1.x,
        y1: xy1.y,
        x2: xy2.x,
        y2: xy2.y,
        stroke: 'black',
        'stroke-width': 5,
        ...attrs
    })
}

manus.svgText = (text, attrs) => {
    console.assert(attrs.x && attrs.y)
    const textEl = manus.createSVGElement('text', attrs)
    textEl.textContent = text
    return textEl
}

manus.draw = (parent, el) => {
    if (!el) {
        el = parent
        parent = document.getElementById('hand')
    }
    if (Array.isArray(el)) {
        const children = el
        el = manus.createSVGElement('g')
        parent.appendChild(el)
        parent = el
        children.map(child => manus.draw(parent, child))
    } else {
        parent.appendChild(el)
    }
    return parent
}

manus.doc = {
    title: 'test',
    list: [
        {
            title: 'this',
            list: []
        },
        {
            title: 'is',
            list: []
        },
        {
            title: 'test',
            list: [
                { title: 'hello', list: [] }
            ]
        }
    ]
}

manus.generateSVG = () => {
  const svg = manus.createSVGElement('svg', {
    width: manus.width,
    height: manus.height,
  })
  const leftHandImage = manus.createSVGElement('image', {
    href: "left-hand-with-letters-and-numbers_bw-blur.png",
    height: manus.height
  })
  const rightHandImage = manus.createSVGElement('image', {
    href: "left-hand-with-letters-and-numbers_bw-blur.png",
    height: manus.height,
    transform: 'scale(-1,1), translate(-800)'
  })
  manus.draw(svg, [leftHandImage, rightHandImage])

  // const handsImage = manus.createSVGElement('image', {
  //   href: "drawn-hands2.png",
  //   height: manus.height
  // })
  // manus.draw(svg, handsImage)
  const clickState = { path: [], currentNode: manus.doc }
  const leftHandCircles = manus.letters.map((letter, i) => {
    const coords = manus.letterCoordinates[letter]
    const circ = manus.circle(coords)
    circ.setAttribute('data-letter', letter)
    if (manus.vowels.indexOf(letter) >= 0) circ.setAttribute('fill', 'crimson')
    circ.addEventListener('click', () => {
        clickState.currentNode = clickState.currentNode.list[i]
        if (clickState.currentNode) {
            clickState.path.push(i)
            console.log(clickState.currentNode)
            manus.removeAllConstellations()
            manus.constellation(clickState.currentNode.title)
        } else {
            clickState.currentNode = clickState.path.reduce((node, step) => {
                return node.list[step]
            }, manus.doc)
        }

        // manus.constellation(clickState.path.join(''))
    })
    // const label = manus.svgText(`${i}`, {
    //     x: coords.x, y: coords.y, fill: 'white'
    // })
    return circ
  })
  // setInterval(() => {
  //   clickState.path.forEach((p, i) => {
  //       const r = +leftHandCircles[p].getAttribute('r')
  //       if (r == 10) {
  //           leftHandCircles[p].setAttribute('r', Math.max(0, 2 - i) * 7)
  //       } else {
  //           leftHandCircles[p].setAttribute('r', 10)
  //       }
  //   })
  // }, 140)
  const rightHandCircles = manus.letters.map((letter, i) => {
    const coords = manus.letterCoordinates[letter]
    const circ = manus.circle(coords)
    circ.setAttribute('data-letter', letter)
    if (manus.vowels.indexOf(letter) >= 0) circ.setAttribute('fill', 'crimson')
    return circ
  })
  const g = manus.draw(svg, [leftHandCircles])
  g.setAttribute('transform', manus.hands.left.transform)
  g.setAttribute('id', 'left-hand')
  g.children[0].style.display = 'none'
  const rg = manus.draw(svg, [rightHandCircles])
  rg.setAttribute('transform', manus.hands.right.transform)
  rg.setAttribute('id', 'right-hand')
  rg.children[0].style.display = 'none'
  manus.draw(svg, [manus.createSVGElement('g', {id: `left-word-grid-container`})])
  manus.draw(svg, [manus.createSVGElement('g', {id: `right-word-grid-container`})])
  return svg
}

manus.constellation = (side, word) => {
    const id = `${side}-constellation-${word}`
    const existingConstellation = document.getElementById(id)
    if (existingConstellation) return existingConstellation
    const letters = word.split('')//.slice(0, 5)
    const letterPairs = letters.slice(1).map((letter, i) => [letters[i], letter])
    const lines = letterPairs.map(([l1, l2], i) => {
        const thirdLine = ((i + 1) % 3) === 0
        return manus.line(l1, l2, {
            // 'stroke': side === 'left' ? 'black' : 'white',
            'stroke': 'black',
            'stroke-width': 2,
            // 'stroke-dasharray': thirdLine ? '5 2' : 'none',
            // 'opacity': thirdLine ? '0.2' : '1'
            'opacity': i > 1 ? '0.2' : '1'
        })
    }).flat()
    // lines.push(manus.circle(letters[letters.length - 1], { fill: 'white'}))
    if (lines[0]) lines[0].setAttribute('stroke-width', 10)
    if (lines[1]) lines[1].setAttribute('stroke-width', 5)
    // lines.slice(2, 5).forEach((line, i) => line.setAttribute('stroke', 'blue'))
    // lines.slice(3 * 2).forEach((line, i) => line.setAttribute('stroke-dasharray', '5 2'))
    const hand = document.getElementById(`${side}-hand`)
    const rings = letters.map((letter, i) => {
        const group = Math.floor(i / 3)
        const groupIndex = i % 3
        // const color = ['yellow','skyblue','crimson','green','pink'][group] || 'gray'
        return manus.circle(letter, {
            r: Math.max(10, 20 - groupIndex * 7),
            // fill: side === 'left' ? 'black' : 'white',
            fill: 'black',
            stroke: 'none',//color,
            // 'stroke-width': 10 - groupIndex * 4,
            opacity: group > 0 ? '0.2' : '1'
        })
    })
    const whiteDots = [
        manus.circle(letters[0], {
          // fill: side === 'right' ? 'black' : 'white',
          fill: 'white',
          r: 5,
          id: `${side}-white-dot`
        }),
        // manus.circle(letters[letters.length - 1], {
        //     fill: 'transparent', stroke: 'white', 'stroke-width': 2,
        //     r: 5
        // })
    ]
    // const text = letters.map(letter => {
    //     return manus.svgText(letter.toUpperCase(), {
    //         fill: 'white',
    //         ...manus.letterCoordinates[letter]
    //     })
    // })
    const g = manus.draw(hand, [lines, rings.reverse(), whiteDots].flat())
    g.setAttribute('id', id)
    g.setAttribute('class', 'constellation')
    return g
}

// let wdr = 5
// setInterval(() => {
//     const lwd = document.getElementById('left-white-dot')
//     wdr = wdr >= 5 ? 4 : 6
//     lwd.setAttribute('r', wdr)
// }, 80)

manus.removeAllConstellations = () => {
    const rh = document.getElementById('right-hand')
    const lh = document.getElementById('left-hand')
    const rightConstellations = Array.prototype.flat.call(
        rh.getElementsByClassName('constellation')
    )
    const leftConstellations = Array.prototype.flat.call(
        lh.getElementsByClassName('constellation')
    )
    rightConstellations.forEach(constellation => {
        rh.removeChild(constellation)
    })
    leftConstellations.forEach(constellation => {
        lh.removeChild(constellation)
    })
    try {
      document.getElementById('left-word-grid').remove()
      document.getElementById('right-word-grid').remove()
    } catch (e) {}
}

manus.renderWord = (side, word) => {
  manus.constellation(side, word)
  // const gridAttrs = {
  //   x: side === 'right' ? 690 : 10,
  //   y: 10,
  //   width: 100,
  //   height: 100,
  // }
  // const colors = side === 'right' ? ['black', 'white'] : ['white', 'black']
  // manus.grid.render(side, word, {gridAttrs, colors})

  // const textEl = manus.createSVGElement('text', {
  //   x: side === 'left' ? 300 : 600,
  //   y: 10
  // })
  // textEl.textContent = word
  // manus.draw(document.getElementById(`${side}-hand`), textEl)
}

manus.text = {}

// manus.text.parseOutline = (text) => {
//   const lines = text.split('\n').map(line => {
//     const indentation = line.length - line.trimLeft().length
//     return {
//       indentation: indentation,
//       text: line.trim(),
//       children: []
//     }
//   })
//   const tree = { text: null, children: [], indentation: -1 }
//   const parseTree = (tree, lines) => {
//     if (!lines[0]) return tree
//     let [nextTree, nextLines] = parseTree(lines[0], lines.slice(1))
//     while (lines[i].indentation > tree.indentation) {
//       tree.children.push(lines[i])
//       i += 1
//       next =
//     }
//     if (lines[0].indentation > tree.indentation) {
//       tree.children.push(next)
//       return parseTree(tree, lines.slice(1))
//     } else {
//       return parseTree(lines[0], lines.slice(1))
//     }
//   }
//   return parseTree(tree, lines)
// }