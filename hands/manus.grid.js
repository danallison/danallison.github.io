manus.grid = {}
manus.grid.constants = {
    offset: 10,
    matrixSize: 5,
}
manus.grid.baseRectAttrs = {
    x: 5, y: 5,
    width: manus.height/manus.grid.constants.matrixSize, height: manus.height/manus.grid.constants.matrixSize,
    stroke: 'black', 'stroke-width': 3, fill: 'white'
}

manus.grid.getSquareCoords = (rowIndex, colIndex) => ({
    x: colIndex * (manus.height / manus.grid.constants.matrixSize) + manus.grid.constants.offset / 2,
    y: rowIndex * (manus.height / manus.grid.constants.matrixSize) + manus.grid.constants.offset / 2,
    width: manus.height / manus.grid.constants.matrixSize - manus.grid.constants.offset,
    height: manus.height / manus.grid.constants.matrixSize - manus.grid.constants.offset,
})

manus.grid.generateGridSVG = () => {
    const svg = manus.createSVGElement('svg', {
        width: manus.height, // intentional to form square instead of rectangle
        height: manus.height,
        id: 'svg',
    })
    const baseMatrix = Array.from(Array(manus.grid.constants.matrixSize)).map(() => {
        return Array.from(Array(manus.grid.constants.matrixSize))
    })
    const squares = baseMatrix.map((row, rowIndex) => {
        return row.map((cell, colIndex) => {
            return manus.createSVGElement('rect', {
                ...manus.grid.baseRectAttrs,
                ...manus.grid.getSquareCoords(rowIndex, colIndex),
                id: `square-${rowIndex}-${colIndex}`
            })
        })
    })
    manus.draw(svg, squares)
    return svg
}

// manus.grid.gridPair = ()

manus.grid.render = (side, word, options = {gridAttrs: {}, colors: ['white', 'black']}) => {
    word = word.toLowerCase()
    const colors  = options.colors || ['white', 'black']
    const matrix = [
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
    ]
    const matIndices = (letter) => {
        let letterIndex = manus.letters.indexOf(letter)
        if (letter === 'z') letterIndex -= 1
        const rowIndex = Math.floor(letterIndex / matrix.length)
        const colIndex = letterIndex % matrix[rowIndex].length
        return [rowIndex, colIndex]
    }
    word.split('').forEach((letter, i) => {
        const [rowIndex, colIndex] = matIndices(letter)
        matrix[rowIndex][colIndex] += i < 3 ? 1 : 0.2
    })
    const gridAttrs = {
        ...manus.grid.baseRectAttrs,
        ...manus.grid.getSquareCoords(side[0], side[1]),
        stroke: colors[1], 'stroke-width': 3, fill: colors[0],
        ...options.gridAttrs
    }
    if (side === 'right') {
        gridAttrs.x = 690
    }
    const grid = manus.createSVGElement('rect', gridAttrs)
    const cells = matrix.map((row, rowIndex) => {
        return row.map((cell, colIndex) => {
        return manus.createSVGElement('rect', {
            x: gridAttrs.x + colIndex * (gridAttrs.width / row.length),
            y: gridAttrs.y + rowIndex * (gridAttrs.height / matrix.length),
            width: gridAttrs.width / row.length,
            height: gridAttrs.height / matrix.length,
            stroke: 'none', fill: cell ? colors[1] : 'none',
            opacity: cell,
        })
        })
    })
    const [c0rowIndex, c0colIndex] = matIndices(word[0])
    const c0cellWidth = gridAttrs.width / matrix[0].length
    const c0offset = c0cellWidth * 0.65
    const c0 = manus.createSVGElement('rect', {
        x: c0offset/2 + gridAttrs.x + c0colIndex * (gridAttrs.width / matrix[c0rowIndex].length),
        y: c0offset/2 + gridAttrs.y + c0rowIndex * (gridAttrs.height / matrix.length),
        width: (gridAttrs.width / matrix[c0rowIndex].length) - c0offset,
        height: (gridAttrs.height / matrix.length) - c0offset,
        stroke: 'none', fill: colors[0],
        opacity: 1,
    })
    cells.push(c0)
    const containerId = side === 'left' || side === 'right' ? `${side}-word-grid-container` : 'svg'
    const gg = manus.draw(document.getElementById(containerId), [grid, cells])
    gg.setAttribute('id', `${side}-word-grid`)
    return [grid, cells]
}
  
