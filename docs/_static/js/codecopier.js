const hamburgerIcon = `
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M0 5.3335H24M0 12.0002H24M0 18.6668H24" stroke="#FFAE12" stroke-width="3"/>
  </svg>
`

const innersOfCopyDiv = `
  <p>Copy</p>
  <svg width="13" height="12" viewBox="0 0 13 12" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect x="4.95605" y="4.5" width="7" height="7" rx="1.5" stroke="#FD8F01"/>
    <path fill-rule="evenodd" clip-rule="evenodd" d="M0.456055 2C0.456055 0.895431 1.35149 0 2.45605 0H6.45605C7.56062 0 8.45605 0.895431 8.45605 2V3H7.45605V2C7.45605 1.44772 7.00834 1 6.45605 1H2.45605C1.90377 1 1.45605 1.44772 1.45605 2V6C1.45605 6.55228 1.90377 7 2.45605 7H3.45605V8H2.45605C1.35149 8 0.456055 7.10457 0.456055 6V2Z" fill="#FD8F01"/>
  </svg>
`

function formDiv(id) {
  return `
  <div class='copyDiv' data-identifier='${id}'>
    ${innersOfCopyDiv}
  </div>
`
}

// Extract the snippet text from a code-block container while excluding the
// injected .copyDiv button. On viewports below the breakpoint the visible
// "Copy" label otherwise leaks into the clipboard via innerText.
function extractSnippetText(container) {
  if (!container) {
    return ''
  }
  const preElement = container.querySelector('pre')
  if (preElement) {
    return preElement.innerText
  }
  // Fallback for any structure without a <pre>: clone the container,
  // remove every .copyDiv, then read innerText off the clone.
  const clone = container.cloneNode(true)
  clone.querySelectorAll('.copyDiv').forEach((node) => node.remove())
  return clone.innerText
}

$(document).ready(async function () {
  const codeSnippets = $(
    '.rst-content div[class^=highlight] div[class^=highlight], .rst-content pre.literal-block div[class^=highlight], .rst-content pre.literal-block div[class^=highlight]'
  )

  codeSnippets.each((index, el) => {
    el.insertAdjacentHTML('beforeend', formDiv(index))
  })

  const copyButton = $('.copyDiv')

  copyButton.click(async ({
    currentTarget
  }) => {
    const id = currentTarget.dataset.identifier
    const divWithNeededId = $(`div[data-identifier='${id}']`)
    // Read from the .copyDiv's parentElement (the inner .highlight div it was
    // injected into via insertAdjacentHTML('beforeend', ...)) rather than
    // currentTarget.offsetParent — offsetParent depends on CSS positioning
    // and would walk past .highlight if its `position: relative` is ever
    // dropped, picking up the wrong snippet.
    const textToCopy = extractSnippetText(currentTarget.parentElement)

    // Clear any state class left over from a previous click so a rapid
    // success-after-failure (or vice versa) doesn't end up with both
    // classes applied at once.
    divWithNeededId.removeClass('copiedNotifier copyFailedNotifier')

    // Cancel a pending revert timeout from a previous click so the new
    // click's 2-second window starts clean instead of being ended early.
    const previousTimeout = divWithNeededId.data('revertTimeout')
    if (previousTimeout) {
      clearTimeout(previousTimeout)
    }

    try {
      await navigator.clipboard.writeText(textToCopy)
      // Only flip the button into the success state when the write actually
      // resolves — earlier versions showed "Copied!" even on failure.
      divWithNeededId.addClass('copiedNotifier')
      divWithNeededId.html('<span>Copied!</span>')
    } catch (error) {
      console.error('Copying text failed, please try again', error)
      divWithNeededId.addClass('copyFailedNotifier')
      divWithNeededId.html('<span>Failed</span>')
    }

    const revertTimeout = setTimeout(() => {
      divWithNeededId.html(innersOfCopyDiv)
      divWithNeededId.removeClass('copiedNotifier copyFailedNotifier')
      divWithNeededId.removeData('revertTimeout')
    }, 2000)
    divWithNeededId.data('revertTimeout', revertTimeout)
  })

  // we edit the button that is added by readthedocs portal
  const readTheDocsButton = $('div.rst-versions')
  const navbar = $('nav[data-toggle=wy-nav-shift]')

  navbar.append(readTheDocsButton)

});
