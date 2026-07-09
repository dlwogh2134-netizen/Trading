import { Navigate, Route, Routes } from 'react-router-dom'
import Dashboard from '../pages/Dashboard'
import Login from '../pages/Login'
import Signup from '../pages/Signup'
import News from '../pages/News'
import Inquiry from '../pages/Inquiry'
import Settings from '../pages/Settings'
import Home from '../pages/Home'
import MarketRankings from '../pages/MarketRankings'
import AdminMlData from '../pages/AdminMlData'
import AssetDetail from '../pages/AssetDetail'
import SearchNotFound from '../pages/SearchNotFound'
import { INQUIRY_ROUTES } from '../dashboardConstants.js'

export default function DesktopRoutes({
  isLoggedIn,
  userEmail,
  handleLogout,
  userProfile,
  setUserProfile,
}) {
  const protectedInquiryElement = isLoggedIn ? (
    <Inquiry
      isLoggedIn={isLoggedIn}
      userEmail={userEmail}
      handleLogout={handleLogout}
    />
  ) : (
    <Navigate to="/login" replace />
  )

  return (
    <Routes>
      <Route
        path="/"
        element={(
          <Home
            isLoggedIn={isLoggedIn}
            userEmail={userEmail}
            handleLogout={handleLogout}
          />
        )}
      />
      <Route
        path="/dashboard"
        element={(
          <Dashboard
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
          <News
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
          <Settings
            isLoggedIn={isLoggedIn}
            userEmail={userEmail}
            handleLogout={handleLogout}
            userProfile={userProfile}
            setUserProfile={setUserProfile}
          />
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
  )
}
