import assert from 'node:assert/strict'
import test from 'node:test'

import { buildCombinedResultNotices } from './chatbotCombinedNotice.js'

test('builds a disclosure target notice for combined news and disclosure results', () => {
  const notices = buildCombinedResultNotices({
    source: 'NEWS_DISCLOSURE_COMBINED',
    news: {
      source: 'NAVER_API',
      items: [{ title: '이노스페이스 뉴스' }],
    },
    disclosure: {
      source: 'NO_RESULT',
      reason: 'disclosure_target_not_recognized',
      query: '스타후르츠 공시',
    },
  })

  assert.deepEqual(notices, [
    "'스타후르츠 공시'에 해당하는 공시 대상 종목을 인식하지 못했습니다. 종목명을 확인해서 다시 요청해 주세요.",
  ])
})
