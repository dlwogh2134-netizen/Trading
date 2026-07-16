import { useState } from 'react'

import { formatRelativeTime as formatTime } from './assetDetailModel.js'

export default function AssetDetailCommunityPanel({
  isActive,
  displayName,
  isLoggedIn,
  userProfile,
  communityPosts,
  communityProfiles,
  communityCurrentUserId,
  communityDraft,
  setCommunityDraft,
  communityReplyParentId,
  setCommunityReplyParentId,
  communityReplyDraft,
  setCommunityReplyDraft,
  communityLoading,
  communitySubmitting,
  communityActionId,
  communityMessage,
  communityRootPosts,
  communityReplyMap,
  onSubmitCommunityPost,
  onSubmitCommunityReply,
  onUpdateCommunityStatus,
}) {
  const [expandedReplyPostIds, setExpandedReplyPostIds] = useState(() => new Set())

  const toggleReplies = (postId) => {
    setExpandedReplyPostIds((currentIds) => {
      const nextIds = new Set(currentIds)
      if (nextIds.has(postId)) {
        nextIds.delete(postId)
      } else {
        nextIds.add(postId)
      }
      return nextIds
    })
  }

  const toggleReplyComposer = (postId) => {
    const shouldOpen = communityReplyParentId !== postId
    setCommunityReplyParentId(shouldOpen ? postId : '')
    setCommunityReplyDraft('')
    if (shouldOpen) {
      setExpandedReplyPostIds((currentIds) => {
        const nextIds = new Set(currentIds)
        nextIds.add(postId)
        return nextIds
      })
    }
  }

  return (
    <>
              {isActive && (
                <div className="max-h-[420px] overflow-y-auto pr-1">
                  <section className="min-h-[260px] rounded-lg border border-[#1f2945]/70 bg-[#07111f]/70 p-4">
                    <div className="mb-3 flex flex-col gap-2 border-b border-[#1f2945]/50 pb-3 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <h3 className="text-sm font-bold text-cyan-200">커뮤니티</h3>
                        <p className="mt-1 text-[11px] text-slate-500">{displayName} 의견을 남기고 확인합니다.</p>
                      </div>
                      <span className="w-fit rounded-full border border-cyan-500/30 bg-cyan-950/30 px-2.5 py-1 text-[11px] font-bold text-cyan-100">
                        총 {communityPosts.length}개
                      </span>
                    </div>

                    <form onSubmit={onSubmitCommunityPost} className="mb-4 flex flex-col gap-2">
                      <textarea
                        value={communityDraft}
                        onChange={(event) => setCommunityDraft(event.target.value)}
                        maxLength={500}
                        placeholder={isLoggedIn ? '이 종목에 대한 의견을 입력해 주세요.' : '로그인 후 커뮤니티 글을 작성할 수 있습니다.'}
                        disabled={!isLoggedIn || communitySubmitting}
                        className="min-h-[88px] w-full resize-none rounded border border-[#1f2945] bg-slate-950/50 px-3 py-2 text-xs leading-5 text-slate-100 outline-none transition focus:border-cyan-500/50 disabled:cursor-not-allowed disabled:opacity-60"
                      />
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <span className={`text-[11px] ${communityDraft.trim().length > 500 ? 'text-rose-300' : 'text-slate-500'}`}>
                          {communityDraft.trim().length}/500
                        </span>
                        <button
                          type="submit"
                          disabled={!isLoggedIn || communitySubmitting || communityDraft.trim().length === 0}
                          className="rounded border border-cyan-500/40 bg-cyan-950/30 px-3 py-2 text-[11px] font-bold text-cyan-200 transition hover:bg-cyan-900/30 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {communitySubmitting ? '등록 중...' : '글 등록'}
                        </button>
                      </div>
                    </form>

                    {communityMessage.text ? (
                      <p className={`mb-3 rounded border px-3 py-2 text-[11px] leading-5 ${communityMessage.isError ? 'border-rose-500/30 bg-rose-950/20 text-rose-200' : 'border-cyan-500/30 bg-cyan-950/20 text-cyan-200'}`}>
                        {communityMessage.text}
                      </p>
                    ) : null}

                    <div className="flex flex-col gap-3">
                      {communityLoading ? (
                        <div className="py-8 text-center text-xs font-mono text-cyan-400/80 animate-pulse">
                          커뮤니티 로드 중...
                        </div>
                      ) : communityRootPosts.length > 0 ? (
                        communityRootPosts.map((post) => {
                          const profile = communityProfiles[post.user_id] || {}
                          const canDelete = communityCurrentUserId && communityCurrentUserId === post.user_id
                          const canHide = userProfile?.role === 'ADMIN' && !canDelete
                          const replies = communityReplyMap[post.id] || []
                          const repliesExpanded = expandedReplyPostIds.has(post.id)
                          const replyListId = `community-replies-${post.id}`
                          return (
                            <article key={post.id} className="rounded border border-[#1f2945]/60 bg-[#1b253b]/35 p-3">
                              <div className="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:justify-between">
                                <div className="flex min-w-0 flex-wrap items-center gap-1.5 text-[10px]">
                                  <span className="max-w-[160px] truncate font-bold text-cyan-300">
                                    {profile.nickname || '익명 사용자'}
                                  </span>
                                  <span className="text-slate-500">{formatTime(post.created_at)}</span>
                                </div>
                                <div className="flex shrink-0 gap-1.5">
                                  {isLoggedIn ? (
                                    <button
                                      type="button"
                                      onClick={() => toggleReplyComposer(post.id)}
                                      className="rounded border border-cyan-500/25 px-2 py-1 text-[10px] font-bold text-cyan-300 transition hover:bg-cyan-950/30"
                                    >
                                      답글
                                    </button>
                                  ) : null}
                                  {(canDelete || canHide) ? (
                                    <>
                                    {canDelete ? (
                                      <button
                                        type="button"
                                        disabled={communityActionId === post.id}
                                        onClick={() => onUpdateCommunityStatus(post, 'DELETED')}
                                        className="rounded border border-slate-700 px-2 py-1 text-[10px] font-bold text-slate-400 transition hover:border-rose-500/40 hover:text-rose-200 disabled:cursor-not-allowed disabled:opacity-50"
                                      >
                                        삭제
                                      </button>
                                    ) : null}
                                    {canHide ? (
                                      <button
                                        type="button"
                                        disabled={communityActionId === post.id}
                                        onClick={() => onUpdateCommunityStatus(post, 'HIDDEN')}
                                        className="rounded border border-amber-600/40 px-2 py-1 text-[10px] font-bold text-amber-300 transition hover:bg-amber-950/30 disabled:cursor-not-allowed disabled:opacity-50"
                                      >
                                        숨김
                                      </button>
                                    ) : null}
                                    </>
                                  ) : null}
                                </div>
                              </div>
                              <p className="mt-2 whitespace-pre-wrap break-words text-xs leading-5 text-[#e2e2ec]">
                                {post.content}
                              </p>
                              {replies.length > 0 ? (
                                <div className="mt-2">
                                  <button
                                    type="button"
                                    aria-expanded={repliesExpanded}
                                    aria-controls={replyListId}
                                    onClick={() => toggleReplies(post.id)}
                                    className="rounded border border-slate-700/70 bg-slate-950/30 px-2.5 py-1 text-[10px] font-bold text-slate-300 transition hover:border-cyan-500/40 hover:text-cyan-200"
                                  >
                                    {repliesExpanded ? `답글 ${replies.length}개 접기` : `답글 ${replies.length}개 보기`}
                                  </button>
                                </div>
                              ) : null}
                              {communityReplyParentId === post.id ? (
                                <form onSubmit={(event) => onSubmitCommunityReply(event, post)} className="mt-3 rounded border border-cyan-500/20 bg-cyan-950/10 p-2">
                                  <textarea
                                    value={communityReplyDraft}
                                    onChange={(event) => setCommunityReplyDraft(event.target.value)}
                                    maxLength={500}
                                    placeholder="답글을 입력해 주세요."
                                    disabled={communitySubmitting}
                                    className="min-h-[64px] w-full resize-none rounded border border-[#1f2945] bg-slate-950/60 px-2.5 py-2 text-[11px] leading-5 text-slate-100 outline-none transition focus:border-cyan-500/50 disabled:cursor-not-allowed disabled:opacity-60"
                                  />
                                  <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                                    <span className="text-[10px] text-slate-500">{communityReplyDraft.trim().length}/500</span>
                                    <div className="flex justify-end gap-2">
                                      <button
                                        type="button"
                                        onClick={() => {
                                          setCommunityReplyParentId('')
                                          setCommunityReplyDraft('')
                                        }}
                                        className="rounded border border-slate-700 px-2.5 py-1 text-[10px] font-bold text-slate-400 transition hover:text-slate-200"
                                      >
                                        취소
                                      </button>
                                      <button
                                        type="submit"
                                        disabled={communitySubmitting || communityReplyDraft.trim().length === 0}
                                        className="rounded border border-cyan-500/40 bg-cyan-950/30 px-2.5 py-1 text-[10px] font-bold text-cyan-200 transition hover:bg-cyan-900/30 disabled:cursor-not-allowed disabled:opacity-50"
                                      >
                                        {communitySubmitting ? '등록 중...' : '답글 등록'}
                                      </button>
                                    </div>
                                  </div>
                                </form>
                              ) : null}
                              {repliesExpanded && replies.length > 0 ? (
                                <div id={replyListId} className="mt-3 flex flex-col gap-2 border-l-2 border-cyan-500/20 pl-3">
                                  {replies.map((reply) => {
                                    const replyProfile = communityProfiles[reply.user_id] || {}
                                    const canDeleteReply = communityCurrentUserId && communityCurrentUserId === reply.user_id
                                    const canHideReply = userProfile?.role === 'ADMIN' && !canDeleteReply
                                    return (
                                      <div key={reply.id} className="rounded border border-[#1f2945]/50 bg-slate-950/30 p-2.5">
                                        <div className="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:justify-between">
                                          <div className="flex min-w-0 flex-wrap items-center gap-1.5 text-[10px]">
                                            <span className="text-cyan-400">↳</span>
                                            <span className="max-w-[140px] truncate font-bold text-cyan-300">
                                              {replyProfile.nickname || '익명 사용자'}
                                            </span>
                                            <span className="text-slate-500">{formatTime(reply.created_at)}</span>
                                          </div>
                                          {(canDeleteReply || canHideReply) ? (
                                            <div className="flex shrink-0 gap-1.5">
                                              {canDeleteReply ? (
                                                <button
                                                  type="button"
                                                  disabled={communityActionId === reply.id}
                                                  onClick={() => onUpdateCommunityStatus(reply, 'DELETED')}
                                                  className="rounded border border-slate-700 px-2 py-1 text-[10px] font-bold text-slate-400 transition hover:border-rose-500/40 hover:text-rose-200 disabled:cursor-not-allowed disabled:opacity-50"
                                                >
                                                  삭제
                                                </button>
                                              ) : null}
                                              {canHideReply ? (
                                                <button
                                                  type="button"
                                                  disabled={communityActionId === reply.id}
                                                  onClick={() => onUpdateCommunityStatus(reply, 'HIDDEN')}
                                                  className="rounded border border-amber-600/40 px-2 py-1 text-[10px] font-bold text-amber-300 transition hover:bg-amber-950/30 disabled:cursor-not-allowed disabled:opacity-50"
                                                >
                                                  숨김
                                                </button>
                                              ) : null}
                                            </div>
                                          ) : null}
                                        </div>
                                        <p className="mt-1.5 whitespace-pre-wrap break-words text-[11px] leading-5 text-[#e2e2ec]">
                                          {reply.content}
                                        </p>
                                      </div>
                                    )
                                  })}
                                </div>
                              ) : null}
                            </article>
                          )
                        })
                      ) : (
                        <div className="rounded border border-[#1f2945] bg-[#070b19] px-3 py-8 text-center">
                          <p className="text-xs text-slate-500 font-mono">
                            아직 이 종목의 커뮤니티 글이 없습니다.
                          </p>
                        </div>
                      )}
                    </div>
                  </section>
                </div>
              )}
    </>
  )
}
