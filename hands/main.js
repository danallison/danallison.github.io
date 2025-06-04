
document.addEventListener('DOMContentLoaded', () => {
  // // Initialize the Ace Editor
  // var editor = ace.edit("editor");
  // editor.setTheme("ace/theme/monokai");
  // editor.session.setMode("ace/mode/yaml");

  const textarea = document.createElement('textarea')
  textarea.setAttribute('rows', 26)
  textarea.value = window.localStorage.getItem('text')
  const keyupHandler = () => {
    const text = textarea.value
    window.localStorage.setItem('text', text)
    const cursor = textarea.selectionStart
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

    manus.removeAllConstellations()

    manus.renderWord('left', parentWord || currentWord)
    manus.renderWord('right', parentWord ? currentWord : '')
  }
  textarea.addEventListener('keyup', keyupHandler)
  document.body.appendChild(textarea)

  const svg = manus.generateSVG()
  document.body.appendChild(svg)
  keyupHandler() // Initial call to set up the constellations
})