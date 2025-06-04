document.addEventListener('DOMContentLoaded', () => {
    const svg = manus.grid.generateGridSVG()
    document.body.appendChild(svg)

    const top25GermanWords = [
        'das',//the
        'sein',//to be
        'und',//and
        'zu',//to
        'von',//of
        'ein',//a
        'ich',//I
        'im',//in
        'haben',//to have
        'Das',//that
        'er',//he
        'nicht',//not
        'seine',//his
        'ihr',//her
        'es',//it
        'Sie',//you
        'mit',//with
        'zum',//for
        'machen',//to do
        'sie',//she
        'wie',//as
        'auf',//on
        'sagen',//to say
        'beim',//at
        'ihm',//him
    ]
    top25GermanWords.forEach((word, i) => {
        const {matrixSize} = manus.grid.constants
        const rowIndex = Math.floor(i / matrixSize)
        const colIndex = i % matrixSize
        const colors = (rowIndex + colIndex) % 2 === 0 ? ['white', 'black'] : ['black', 'white']
        manus.grid.render([rowIndex, colIndex], word, colors)
    })
  })