export function preserveMobileDeviceParam(path) {
  if (typeof window === 'undefined') return path

  const currentParams = new URLSearchParams(window.location.search)
  if (currentParams.get('device') !== 'mobile') return path

  const [pathname, query = ''] = String(path).split('?')
  const nextParams = new URLSearchParams(query)
  nextParams.set('device', 'mobile')

  return `${pathname}?${nextParams.toString()}`
}
