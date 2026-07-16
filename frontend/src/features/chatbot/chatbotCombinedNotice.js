function normalizeNoticeText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim()
}

function buildNoResultNotice(section, result) {
  if (normalizeNoticeText(result?.source).toUpperCase() !== 'NO_RESULT') {
    return ''
  }

  const message = normalizeNoticeText(result?.message)
  if (message) return message

  const query = normalizeNoticeText(result?.query)
  if (section === 'disclosure' && result?.reason === 'disclosure_target_not_recognized') {
    return `'${query || '공시'}'에 해당하는 공시 대상 종목을 인식하지 못했습니다. 종목명을 확인해서 다시 요청해 주세요.`
  }

  if (section === 'disclosure') {
    return query
      ? `'${query}'에 맞는 DART 공시 결과를 찾지 못했습니다.`
      : '조건에 맞는 DART 공시 결과를 찾지 못했습니다.'
  }

  return query
    ? `'${query}'에 맞는 최신 뉴스를 찾지 못했습니다.`
    : '조건에 맞는 최신 뉴스를 찾지 못했습니다.'
}

export function buildCombinedResultNotices(toolResult) {
  if (toolResult?.source !== 'NEWS_DISCLOSURE_COMBINED') {
    return []
  }

  return [
    buildNoResultNotice('news', toolResult.news),
    buildNoResultNotice('disclosure', toolResult.disclosure),
  ].filter(Boolean)
}
