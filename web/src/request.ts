export async function request(url: string, options: RequestInit = {}) {
  try {
    return await fetch(url, { ...options, signal: options.signal ?? AbortSignal.timeout(20000) })
  } catch (error) {
    throw new Error(error instanceof DOMException && error.name === 'TimeoutError'
      ? 'Die Antwort dauert zu lange. Bitte lade den Status erneut.'
      : 'Die Verbindung ist unterbrochen. Bitte versuche es erneut.')
  }
}
