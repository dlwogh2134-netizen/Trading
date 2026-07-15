const LOCAL_API_ORIGIN = 'http://localhost:5050'
const EC2_API_ORIGIN = 'http://52.79.188.213'
const PROXY_PREFIX = '/backend-api'

function isHttpsPage() {
  return typeof window !== 'undefined' && window.location.protocol === 'https:'
}

function shouldProxyUrl(urlText) {
  return urlText.startsWith(`${LOCAL_API_ORIGIN}/`) || urlText.startsWith(`${EC2_API_ORIGIN}/`)
}

function toProxyUrl(urlText) {
  if (urlText.startsWith(LOCAL_API_ORIGIN)) {
    return `${PROXY_PREFIX}${urlText.slice(LOCAL_API_ORIGIN.length)}`
  }
  if (urlText.startsWith(EC2_API_ORIGIN)) {
    return `${PROXY_PREFIX}${urlText.slice(EC2_API_ORIGIN.length)}`
  }
  return urlText
}

function normalizeFetchInput(input) {
  if (typeof input === 'string') {
    return input
  }
  if (input instanceof URL) {
    return input.toString()
  }
  if (typeof Request !== 'undefined' && input instanceof Request) {
    return input.url
  }
  return null
}

export function installApiProxyFetch() {
  if (typeof window === 'undefined' || typeof window.fetch !== 'function') {
    return
  }
  if (window.__aeApiProxyFetchInstalled) {
    return
  }

  const originalFetch = window.fetch.bind(window)
  window.fetch = (input, init) => {
    const requestUrl = normalizeFetchInput(input)
    if (!requestUrl || !isHttpsPage() || !shouldProxyUrl(requestUrl)) {
      return originalFetch(input, init)
    }

    const proxiedUrl = toProxyUrl(requestUrl)
    if (typeof input === 'string' || input instanceof URL) {
      return originalFetch(proxiedUrl, init)
    }
    if (typeof Request !== 'undefined' && input instanceof Request) {
      const proxiedRequest = new Request(proxiedUrl, input)
      return originalFetch(proxiedRequest, init)
    }
    return originalFetch(input, init)
  }

  window.__aeApiProxyFetchInstalled = true
}
