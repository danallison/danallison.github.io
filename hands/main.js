
document.addEventListener('DOMContentLoaded', () => {
  const mainDiv = document.createElement('div');
  mainDiv.style.height = '100vh'
  mainDiv.style.paddingLeft = 'calc(50vw - 400px)'
  const sides = ['left', 'right']
  const inputs = sides.map((side) => {
    const input = document.createElement('input')
    input.setAttribute('type', 'text')
    input.setAttribute('placeholder', side)
    input.value = window.localStorage.getItem(`text-${side}`) || ''
    input.style.width = '400px' // half of the svg width
    input.style.fontSize = '2em'
    input.style.backgroundColor = 'transparent'
    input.style.border = 'none'
    input.style.fontFamily = 'monospace'
    input.style.resize = 'none'
    input.style.textAlign = 'center'
    input.style.lineHeight = '1.5'
    const keyupHandler = () => {
      const text = input.value || side;
      window.localStorage.setItem(`text-${side}`, text)
      const cursor = input.selectionStart
      const lines = text.split('\n')
      const currentLineIndex = text.slice(0, cursor).split('\n').length - 1
      const currentLine = lines[currentLineIndex]
      const currentWord = currentLine.trim().split(':')[0]
      // const currentWords = text.split('\n')[currentLineIndex].split(' ')
      // const tree = jsyaml.load(text)
      const getIndentation = (line) => line.length - line.trimStart().length
      const currentIndentation = getIndentation(currentLine)
      const parentWord = (() => {
        let i = currentLineIndex - 1
        while (lines[i] && getIndentation(lines[i]) >= currentIndentation) i -= 1
        return lines[i] || ''
      })().trim().split(':')[0]

      manus.removeAllConstellations(side)

      // manus.renderWord('left', parentWord || currentWord)
      // manus.renderWord('right', parentWord ? currentWord : '')
      manus.renderWord(side, currentWord || parentWord || '')
    }
    input.addEventListener('keyup', keyupHandler);
    input.addEventListener('click', () => {
      input.select()
    });
    input.addEventListener('focus', () => {
      input.select()
    });

    setTimeout(() => {
      keyupHandler() // Initial call to set up the constellations
    }, 10)
    return input;
  })
  // const topDiv = document.createElement('div')
  // topDiv.style.height = 'calc(100vh - 800px)'
  // mainDiv.appendChild(topDiv);
  mainDiv.appendChild(inputs[0])
  mainDiv.appendChild(inputs[1])
  const breakDiv = document.createElement('div')
  breakDiv.style.height = '20px'
  mainDiv.appendChild(breakDiv);
  const svg = manus.generateSVG()
  mainDiv.appendChild(svg);
  document.body.appendChild(mainDiv);
  setTimeout(() => {
    inputs[0].focus()
    inputs[0].select()
  }, 100)
})