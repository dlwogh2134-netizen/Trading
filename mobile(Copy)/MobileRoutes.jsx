import { Navigate, Route, Routes } from 'react-router-dom'
import Login from '../pages/Login'
import Signup from '../pages/Signup'
import Inquiry from '../pages/Inquiry'
import Settings from '../pages/Settings'
import MobileHome from '../pages/mobile/MobileHome.jsx'
import MobileDashboard from '../pages/mobile/MobileDashboard.jsx'
import MobileNews from '../pages/mobile/MobileNews.jsx'
import MarketRankings from '../pages/MarketRankings'
import AdminMlData from '../pages/AdminMlData'
import AssetDetail from '../pages/AssetDetail'
import SearchNotFound from '../pages/SearchNotFound'
import { INQUIRY_ROUTES } from '../dashboardConstants.js'
import MobileBottomNavigation from '../components/mobile/MobileBottomNavigation.jsx'
import MobileHeader from '../components/mobile/MobileHeader.jsx'

export default function MobileRoutes({
  isLoggedIn,
  userEmail,
  handleLogout,
  userProfile,
  setUserProfile,
}) {
  const protectedInquiryElement = isLoggedIn ? (
    <div className="min-h-screen bg-obsidian-bg px-3 py-4 font-inter text-[#e2e2ec]">
      <MobileHeader isLoggedIn={isLoggedIn} handleLogout={handleLogout} />
      <Inquiry
        isLoggedIn={isLoggedIn}
        userEmail={userEmail}
        handleLogout={handleLogout}
        hideHeader
        mobileLayout
      />
    </div>
  ) : (
    <Navigate to="/login" replace />
  )

  return (
    // 전체 모바일 화면의 바깥 배경
    <div className="min-h-screen bg-obsidian-bg">
      {/*
        실제 모바일 화면 영역
        max-w-[430px] 때문에 PC 브라우저에서도 모바일처럼 좁게 보임
        mx-auto 때문에 가운데 정렬됨
        pb-24는 하단 모바일 네비게이션에 내용이 가리지 않도록 여백 추가
      */}
      <div className="mx-auto min-h-screen w-full max-w-[430px] overflow-x-hidden bg-obsidian-bg pb-24">
        <Routes>
          <Route
            path="/"
            element={(
              <MobileHome
                isLoggedIn={isLoggedIn}
                userEmail={userEmail}
                handleLogout={handleLogout}
              />
            )}
          />
          <Route
            path="/dashboard"
            element={(
              <MobileDashboard
                isLoggedIn={isLoggedIn}
                userEmail={userEmail}
                handleLogout={handleLogout}
                userProfile={userProfile}
                setUserProfile={setUserProfile}
              />
            )}
          />
          <Route
            path="/market-rankings"
            element={(
              <MarketRankings
                isLoggedIn={isLoggedIn}
                userEmail={userEmail}
                handleLogout={handleLogout}
              />
            )}
          />
          <Route
            path="/news"
            element={(
              <MobileNews
                isLoggedIn={isLoggedIn}
                userEmail={userEmail}
                handleLogout={handleLogout}
              />
            )}
          />
          {Object.values(INQUIRY_ROUTES).map((path) => (
            <Route key={path} path={path} element={protectedInquiryElement} />
          ))}
          <Route
            path="/settings"
            element={(
              <div className="min-h-screen bg-obsidian-bg px-3 py-4 font-inter text-[#e2e2ec]">
                <MobileHeader isLoggedIn={isLoggedIn} handleLogout={handleLogout} />
                <Settings
                  isLoggedIn={isLoggedIn}
                  userEmail={userEmail}
                  handleLogout={handleLogout}
                  userProfile={userProfile}
                  setUserProfile={setUserProfile}
                  hideHeader
                  mobileLayout
                />
              </div>
            )}
          />
          <Route
            path="/admin/ml-data"
            element={(
              <AdminMlData
                isLoggedIn={isLoggedIn}
                userEmail={userEmail}
                handleLogout={handleLogout}
              />
            )}
          />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route
            path="/asset/:assetType"
            element={(
              <SearchNotFound
                isLoggedIn={isLoggedIn}
                userEmail={userEmail}
                handleLogout={handleLogout}
              />
            )}
          />
          <Route
            path="/asset/:assetType/:symbol"
            element={(
              <AssetDetail
                isLoggedIn={isLoggedIn}
                userEmail={userEmail}
                handleLogout={handleLogout}
                userProfile={userProfile}
              />
            )}
          />
          <Route
            path="/search/not-found"
            element={(
              <SearchNotFound
                isLoggedIn={isLoggedIn}
                userEmail={userEmail}
                handleLogout={handleLogout}
              />
            )}
          />
        </Routes>

        {/* 모바일 하단 네비게이션도 430px 영역 안에 들어오게 이동 */}
        <MobileBottomNavigation isLoggedIn={isLoggedIn} />
      </div>
    </div>
  )
}
