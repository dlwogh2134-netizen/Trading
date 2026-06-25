import React, { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { supabase } from './supabaseClient'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import Signup from './pages/Signup'
import News from './pages/News'
import Settings from './pages/Settings'
import Home from './pages/Home'
import AdminMlData from './pages/AdminMlData'
import AssetDetail from './pages/AssetDetail'
import InvestmentSurveyModal from './components/InvestmentSurveyModal'

export default function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [userEmail, setUserEmail] = useState('')
  const [userId, setUserId] = useState('')
  const [userProfile, setUserProfile] = useState(null) // 유저 프로필 상세 정보 상태 추가
  
  // 1단계: 연락처/닉네임 추가정보 모달 플래그
  const [showAdditionalInfo, setShowAdditionalInfo] = useState(false)
  
  // 2단계: 투자 성향 설문조사 오버레이 플래그
  const [showSurvey, setShowSurvey] = useState(false)

  // 추가 정보 입력 폼 상태
  const [additionalInputs, setAdditionalInputs] = useState({
    nickname: '',
    phone: ''
  })
  const [infoSubmitLoading, setInfoSubmitLoading] = useState(false)



  // Supabase 인증 세션 및 프로필 유효성 실시간 동기화 (한글 주석 준수)
  useEffect(() => {
    const checkUserSession = async (session) => {
      if (session) {
        setIsLoggedIn(true)
        setUserEmail(session.user.email)
        setUserId(session.user.id)
        
        try {
          const { data, error } = await supabase
            .from('profiles')
            .select('nickname, phone, invest_type, invest_score, updated_at') // invest_score, updated_at 추가 조회
            .eq('id', session.user.id)
            .maybeSingle()

          if (data) {
            setUserProfile(data) // 프로필 상태 보존
          }

          // 1. 닉네임과 전화번호가 없는 경우 ➡️ 추가 정보 등록 모달 강제 노출
          if (!data || !data.nickname || !data.phone) {
            setShowAdditionalInfo(true)
            setAdditionalInputs({
              nickname: data?.nickname || session.user.user_metadata?.full_name || '',
              phone: data?.phone || ''
            })
            setShowSurvey(false)
          } 
          // 2. 추가 정보는 있으나 투자 성향 설문을 안 한 경우 ➡️ 투자 성향 오버레이 강제 노출
          else if (!data.invest_type) {
            setShowAdditionalInfo(false)
            setShowSurvey(true)
          } 
          // 3. 모두 입력 완료된 경우 ➡️ 팝업 해제
          else {
            setShowAdditionalInfo(false)
            setShowSurvey(false)
          }
        } catch (err) {
          console.error('프로필 검증 오류:', err.message)
        }
      } else {
        setIsLoggedIn(false)
        setUserEmail('')
        setUserId('')
        setUserProfile(null)
        setShowAdditionalInfo(false)
        setShowSurvey(false)
      }
    }

    // 초기 세션 확인
    supabase.auth.getSession().then(({ data: { session } }) => {
      checkUserSession(session)
    })

    // 세션 변경 리스너 구독
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      checkUserSession(session)
    })

    return () => {
      subscription?.unsubscribe()
    }
  }, [])

  // 로그아웃 수행 (Supabase Auth 연동)
  const handleLogout = async () => {
    try {
      const { error } = await supabase.auth.signOut()
      if (error) throw error
      setIsLoggedIn(false)
      setUserEmail('')
      setUserId('')
      setUserProfile(null)
      setShowAdditionalInfo(false)
      setShowSurvey(false)

    } catch (err) {
      console.error('로그아웃 에러:', err.message)
    }
  }

  // 연락처 자동 하이픈 포맷팅
  const handlePhoneFormatChange = (e) => {
    const value = e.target.value.replace(/[^0-9]/g, '')
    let formatted = value
    if (value.length > 3 && value.length <= 7) {
      formatted = `${value.slice(0, 3)}-${value.slice(3)}`
    } else if (value.length > 7) {
      formatted = `${value.slice(0, 3)}-${value.slice(3, 7)}-${value.slice(7, 11)}`
    }
    setAdditionalInputs(prev => ({ ...prev, phone: formatted }))
  }

  // 필수 추가 정보 저장 핸들러
  const handleAdditionalInfoSubmit = async (e) => {
    e.preventDefault()
    if (!additionalInputs.nickname || !additionalInputs.phone) {
      alert('닉네임과 연락처를 모두 입력해주세요.')
      return
    }

    if (additionalInputs.phone.length < 12) {
      alert('올바른 연락처 형식을 입력해주세요 (예: 010-0000-0000).')
      return
    }

    setInfoSubmitLoading(true)
    try {
      const { error } = await supabase
        .from('profiles')
        .update({
          nickname: additionalInputs.nickname,
          phone: additionalInputs.phone,
          updated_at: new Date().toISOString()
        })
        .eq('id', userId)

      if (error) throw error

      setShowAdditionalInfo(false)
      // 추가 정보 입력이 완료되었으니, 투자 성향 진단으로 상태 갱신
      setShowSurvey(true)
    } catch (err) {
      alert(`정보 등록 실패: ${err.message}`)
    } finally {
      setInfoSubmitLoading(false)
    }
  }



  return (
    <Router>
      {/* 1단계: 필수 추가정보 입력 오버레이 모달 (카카오 소셜 가입자 강제 온보딩) */}
      {showAdditionalInfo && (
        <div className="fixed inset-0 bg-[#07080c]/95 backdrop-blur-md flex items-center justify-center z-50 p-4">
          <div className="w-full max-w-md bg-[#0c0e15] border-2 border-ai-cyan/60 rounded-lg p-8 shadow-[0_0_50px_rgba(0,242,254,0.15)] flex flex-col gap-6 relative">
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-ai-cyan animate-pulse">lock_person</span>
                <h2 className="text-xl font-bold tracking-wider text-white uppercase">필수 추가정보 등록</h2>
              </div>
              <p className="text-xs text-slate-400">
                카카오 계정 로그인이 성공했습니다. 원활한 실시간 거래 알림(SMS)과 거래 관리를 위해 아래 추가정보를 필수로 등록해주셔야 대시보드 사용이 가능합니다.
              </p>
            </div>

            <form onSubmit={handleAdditionalInfoSubmit} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">닉네임</label>
                <input 
                  type="text" 
                  value={additionalInputs.nickname}
                  onChange={(e) => setAdditionalInputs(prev => ({ ...prev, nickname: e.target.value }))}
                  placeholder="닉네임 입력" 
                  className="w-full bg-[#11131a] border border-slate-700 text-[#e2e2ec] rounded px-4 py-2.5 text-sm focus:outline-none focus:border-ai-cyan focus:ring-1 focus:ring-ai-cyan transition-all"
                  required
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">연락처 (휴대폰 번호)</label>
                <input 
                  type="text" 
                  value={additionalInputs.phone}
                  onChange={handlePhoneFormatChange}
                  placeholder="010-0000-0000" 
                  maxLength="13"
                  className="w-full bg-[#11131a] border border-slate-700 text-[#e2e2ec] rounded px-4 py-2.5 text-sm focus:outline-none focus:border-ai-cyan focus:ring-1 focus:ring-ai-cyan transition-all"
                  required
                />
              </div>

              <button 
                type="submit" 
                disabled={infoSubmitLoading}
                className="w-full mt-2 bg-gradient-to-r from-blue-700 to-ai-cyan text-white text-sm font-bold py-3 rounded hover:opacity-90 active:scale-[0.99] transition-all cursor-pointer disabled:opacity-50"
              >
                {infoSubmitLoading ? '등록 중...' : '등록 완료 및 다음 단계 진행'}
              </button>
            </form>

            <div className="border-t border-slate-800 pt-4 flex justify-between items-center text-[10px]">
              <span className="text-slate-500">다른 계정으로 로그인하시겠습니까?</span>
              <button 
                onClick={handleLogout}
                className="text-red-400 hover:underline font-bold bg-transparent border-none cursor-pointer outline-none"
              >
                로그아웃 후 돌아가기
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 2단계: 투자 성향 설문조사 진단 오버레이 (공통 컴포넌트 통합) */}
      {showSurvey && (
        <InvestmentSurveyModal
          isMandatory={true}
          onLogout={handleLogout}
          onSuccess={(type, score) => {
            setUserProfile(prev => prev ? {
              ...prev,
              invest_type: type,
              invest_score: score,
              updated_at: new Date().toISOString()
            } : null)
            setShowSurvey(false)
          }}
        />
      )}

      <Routes>
        <Route
          path="/"
          element={
            <Home
              isLoggedIn={isLoggedIn}
              userEmail={userEmail}
              handleLogout={handleLogout}
            />
          }
        />
        <Route 
          path="/dashboard" 
          element={
            <Dashboard 
              isLoggedIn={isLoggedIn} 
              userEmail={userEmail} 
              handleLogout={handleLogout} 
              userProfile={userProfile} 
              setUserProfile={setUserProfile}
            />
          } 
        />
        <Route 
          path="/news" 
          element={
            <News 
              isLoggedIn={isLoggedIn} 
              userEmail={userEmail} 
              handleLogout={handleLogout} 
            />
          } 
        />
        <Route 
          path="/settings" 
          element={
            <Settings 
              isLoggedIn={isLoggedIn} 
              userEmail={userEmail} 
              handleLogout={handleLogout}
              userProfile={userProfile}
              setUserProfile={setUserProfile}
            />
          } 
        />
        <Route 
          path="/admin/ml-data" 
          element={
            <AdminMlData 
              isLoggedIn={isLoggedIn} 
              userEmail={userEmail} 
              handleLogout={handleLogout}
            />
          } 
        />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route 
          path="/asset/:assetType/:symbol" 
          element={
            <AssetDetail 
              isLoggedIn={isLoggedIn} 
              userEmail={userEmail} 
              handleLogout={handleLogout}
              userProfile={userProfile}
            />
          } 
        />
      </Routes>
    </Router>
  )
}
