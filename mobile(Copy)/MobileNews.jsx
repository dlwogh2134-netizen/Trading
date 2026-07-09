import MobileHeader from '../../components/mobile/MobileHeader.jsx'
import News from '../News.jsx'

export default function MobileNews({ isLoggedIn, userEmail, handleLogout }) {
  return (
    <div className="min-h-screen bg-obsidian-bg px-4 py-4 font-inter text-[#e2e2ec]">
      <MobileHeader isLoggedIn={isLoggedIn} handleLogout={handleLogout} />
      <News
        isLoggedIn={isLoggedIn}
        userEmail={userEmail}
        handleLogout={handleLogout}
        hideHeader
        maxVisiblePages={3}
        mobileLayout
      />
    </div>
  )
}
