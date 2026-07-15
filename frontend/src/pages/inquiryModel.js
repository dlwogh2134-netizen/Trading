export const inquiryTypes = [
  { value: '', label: '문의 유형을 선택해주세요' },
  { value: 'account', label: '계좌' },
  { value: 'order', label: '주문/체결' },
  { value: 'transfer', label: '입출금' },
  { value: 'domestic-stock', label: '국내주식' },
  { value: 'global-stock', label: '해외주식' },
  { value: 'crypto', label: '코인' },
  { value: 'system', label: '시스템 오류' },
  { value: 'etc', label: '기타' },
]

export const inquiryStatusLabels = {
  RECEIVED: '답변 대기',
  WAITING: '답변 대기',
  COMPLETED: '답변 완료',
  NEED_MORE: '추가 확인 필요',
  CANCELED: '취소됨',
}

export const inquiryStatusItems = [
  { key: 'all', label: '전체', dot: 'bg-ai-cyan' },
  { key: 'WAITING', label: inquiryStatusLabels.WAITING, dot: 'bg-amber-400' },
  { key: 'COMPLETED', label: inquiryStatusLabels.COMPLETED, dot: 'bg-emerald-400' },
]

export const summaryItems = [
  { key: 'total', label: '전체 문의', icon: 'inbox', tone: 'text-ai-cyan' },
  { key: 'waiting', label: '답변 대기', icon: 'clock', tone: 'text-amber-400' },
  { key: 'completed', label: '답변 완료', icon: 'check', tone: 'text-emerald-400' },
]

export const faqItems = [
  {
    question: '현재 연동할 수 있는 증권사와 거래소는 어디인가요?',
    answer: '현재 지원하는 증권사와 거래소만 연동할 수 있습니다. 지원 목록은 계좌 연동 화면에서 확인할 수 있습니다.',
  },
  {
    question: 'API 키가 필요한 이유와 발급·등록 방법은 무엇인가요?',
    answer: '왜 필요한가요?\nAPI 키는 계좌 잔고, 보유 종목, 시세, 주문 가능 여부를 증권사·거래소와 안전하게 연동하기 위해 필요합니다.\n\n발급·등록 방법\n1. 이용 중인 증권사 또는 거래소의 Open API/개발자 센터에 접속합니다.\n2. API 사용 신청 또는 앱 등록을 진행합니다.\n3. 발급된 API Key, Secret Key, 계좌번호 등 필요한 값을 확인합니다.\n4. ANTRY 설정 > API Key 입력 화면에서 해당 거래소/증권사를 선택하고 값을 입력합니다.\n5. 연결 테스트를 실행해 정상 연결 여부를 확인한 뒤 저장합니다.\n\n권한 주의\n조회 권한은 필수이고, 실거래/주문 권한은 필요한 경우에만 켜 주세요. 출금 권한은 사용하지 않는 것을 권장합니다.',
  },
  {
    question: '평가금액이나 수익률이 실제 계좌와 다르게 보일 때는 왜 그런가요?',
    answer: '실시간 시세 반영 시점이나 환율 적용 시점에 따라 일시적인 차이가 발생할 수 있습니다. 새로고침 후에도 문제가 지속되면 문의해 주세요.',
  },
  {
    question: '매수·매도 주문이 실패할 때 확인해야 할 원인은 무엇인가요?',
    answer: '잔고 부족, API 인증 만료, 거래 가능 시간 종료 또는 증권사·거래소 서버 문제 등 다양한 원인이 있을 수 있습니다.',
  },
  {
    question: '주식·코인 시세는 실시간으로 반영되나요?',
    answer: '가능한 범위 내에서 실시간 데이터를 제공합니다. 일부 데이터는 API 정책에 따라 지연될 수 있습니다.',
  },
  {
    question: '1:1 문의에 첨부할 수 있는 파일 형식과 용량 제한은 어떻게 되나요?',
    answer: '이미지(JPG, PNG) 및 문서(PDF 등)를 첨부할 수 있으며, 파일당 최대 5MB까지 업로드할 수 있습니다.',
  },
  {
    question: '개인정보와 API 키는 서비스에서 어떻게 보호하나요?',
    answer: '개인정보와 API 키는 보안 정책에 따라 안전하게 관리되며, 외부에 노출되지 않도록 보호됩니다.',
  },
  {
    question: '1:1 문의를 남기면 답변까지 보통 얼마나 걸리나요?',
    answer: '영업일 기준 1~3일 이내 답변을 드리는 것을 목표로 합니다.',
  },
]

export const inquiryColumns = [
  { key: 'title', label: '제목' },
  { key: 'type', label: '유형' },
  { key: 'status', label: '상태' },
  { key: 'createdAt', label: '작성일' },
]

export const inquiryHomeSections = {
  checklist: {
    title: '자주 묻는 질문',
    icon: 'info',
  },
  recent: {
    title: '최근 문의 목록',
    icon: 'document',
    emptyMessage: '최근 문의 사항이 없습니다.',
  },
}

export const customerCenterItems = [
  { label: '답변 시간', value: '영업일 기준 1~3일 이내' },
  { label: '문의 가능 항목', value: '계좌, 주문/체결, 입출금, 시스템 오류' },
  { label: '첨부파일', value: 'JPG, PNG, PDF, 문서 파일 지원' },
]

export const initialFormState = {
  type: '',
  title: '',
  content: '',
  fileName: '',
}

export const INQUIRY_FILE_BUCKET = 'inquiry-files'
export const MAX_INQUIRY_FILE_SIZE = 5 * 1024 * 1024
export const ALLOWED_INQUIRY_FILE_EXTENSIONS = new Set(['jpg', 'jpeg', 'png', 'pdf', 'txt', 'doc', 'docx', 'xls', 'xlsx'])
export const HISTORY_PAGE_SIZE = 10
export const INITIAL_FAQ_VISIBLE_COUNT = 3

export const inquiryTypeLabels = Object.fromEntries(
  inquiryTypes.filter((item) => item.value).map((item) => [item.value, item.label]),
)

export const getInquiryFileExtension = (fileName = '') => {
  const parts = fileName.split('.')
  return parts.length > 1 ? parts.pop().toLowerCase() : ''
}

export const validateInquiryFile = (file) => {
  if (!file) return ''

  const extension = getInquiryFileExtension(file.name)
  if (!ALLOWED_INQUIRY_FILE_EXTENSIONS.has(extension)) {
    return '첨부할 수 없는 파일 형식입니다. jpg, jpeg, png, pdf, txt, doc, docx, xls, xlsx 파일만 등록할 수 있습니다.'
  }

  if (file.size > MAX_INQUIRY_FILE_SIZE) {
    return '첨부파일은 최대 5MB까지 등록할 수 있습니다.'
  }

  return ''
}

export const createInquiryFilePath = (
  userId,
  inquiryId,
  file,
  createId = () => crypto.randomUUID(),
) => {
  const extension = getInquiryFileExtension(file.name)
  return `${userId}/${inquiryId}/${createId()}.${extension}`
}

export const formatInquiryDate = (value) => {
  const date = value ? new Date(value) : null
  if (!date || Number.isNaN(date.getTime())) return '-'
  return date.toLocaleDateString('ko-KR', {
    year: '2-digit',
    month: '2-digit',
    day: '2-digit',
  })
}

export const toInquiryViewItem = (row = {}) => ({
  id: row.id,
  type: inquiryTypeLabels[row.inquiry_type] || row.inquiry_type || '-',
  status: inquiryStatusLabels[row.status] || row.status || '-',
  statusCode: row.status,
  title: row.title || '-',
  content: row.content || '',
  answer: row.answer || '',
  fileName: row.file_name || '',
  attachmentPath: row.attachment_path || '',
  mimeType: row.mime_type || '',
  fileSize: row.file_size || null,
  createdAt: formatInquiryDate(row.created_at),
  createdAtValue: row.created_at || '',
})

export const sortInquiries = (inquiries, sortOrder = 'desc') => (
  [...inquiries].sort((left, right) => {
    const leftTime = new Date(left.createdAtValue).getTime() || 0
    const rightTime = new Date(right.createdAtValue).getTime() || 0
    return sortOrder === 'asc' ? leftTime - rightTime : rightTime - leftTime
  })
)

export const paginateInquiries = (inquiries, page, pageSize = HISTORY_PAGE_SIZE) => {
  const startIndex = (page - 1) * pageSize
  return inquiries.slice(startIndex, startIndex + pageSize)
}

export const filterRecentInquiries = (inquiries, statusFilter = 'all', limit = 5) => {
  const filtered = statusFilter === 'all'
    ? inquiries
    : statusFilter === 'WAITING'
      ? inquiries.filter((item) => item.statusCode === 'WAITING' || item.statusCode === 'RECEIVED')
      : inquiries.filter((item) => item.statusCode === statusFilter)

  return filtered.slice(0, limit)
}

export const getInquirySummaryCounts = (inquiries) => {
  const waiting = inquiries.filter((item) => item.statusCode === 'WAITING' || item.statusCode === 'RECEIVED')
  const completed = inquiries.filter((item) => item.statusCode === 'COMPLETED')

  return {
    total: inquiries.length,
    waiting: waiting.length,
    completed: completed.length,
  }
}

export const validateInquiryForm = ({ formState, selectedFile }) => ({
  type: formState.type ? '' : '문의 유형을 선택해주세요.',
  title: formState.title.trim() ? '' : '제목을 입력해주세요.',
  content: formState.content.trim() ? '' : '문의 내용을 입력해주세요.',
  file: validateInquiryFile(selectedFile),
})
