function DetailSection({ title, description, className = '', children }) {
  return (
    <section className={className || 'contents'} aria-label={title}>
      {description ? <p className="sr-only">{description}</p> : null}
      {children}
    </section>
  )
}

export function MobileAssetChartSection({ children }) {
  return (
    <DetailSection title="차트" description="종목 가격 차트와 차트 관련 요약 정보입니다.">
      {children}
    </DetailSection>
  )
}

export function MobileAssetOrderSection({ children }) {
  return (
    <DetailSection title="주문 및 판매" description="매수, 매도, 청산, 보유 현황을 처리하는 주문 영역입니다.">
      {children}
    </DetailSection>
  )
}

export function MobileAssetNewsDisclosureSection({ children }) {
  return (
    <DetailSection title="뉴스 및 공시" description="선택 종목의 뉴스와 공시 정보를 확인하는 영역입니다.">
      {children}
    </DetailSection>
  )
}

export function MobileAssetCommunitySection({ children }) {
  return (
    <DetailSection title="커뮤니티" description="선택 종목에 대한 사용자 의견과 답글 영역입니다.">
      {children}
    </DetailSection>
  )
}
