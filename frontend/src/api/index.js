import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({ baseURL: '/api', timeout: 120000 })

http.interceptors.request.use(config => {
  const token = localStorage.getItem('gh_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  resp => resp.data,
  err => {
    const msg = err.response?.data?.detail || err.message || '请求失败'
    if (err.response?.status === 401) {
      localStorage.removeItem('gh_token')
      window.location.href = '/login'
    } else {
      ElMessage.error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    }
    return Promise.reject(err)
  }
)

export default {
  // auth
  login: (data) => http.post('/auth/login', data),
  register: (data) => http.post('/auth/register', data),
  me: () => http.get('/auth/me'),
  // accounts
  listAccounts: () => http.get('/accounts'),
  createAccount: (data) => http.post('/accounts', data),
  checkAccount: (id) => http.get(`/accounts/${id}/check`),
  refreshAccount: (id) => http.post(`/accounts/${id}/refresh`),
  testProxy: (id) => http.post(`/accounts/${id}/test-proxy`),
  updateAccount: (id, data) => http.put(`/accounts/${id}`, data),
  deleteAccount: (id) => http.delete(`/accounts/${id}`),
  loginStart: (mode) => http.post('/accounts/login/start', { mode }),
  loginStatus: (sid) => http.get(`/accounts/login/${sid}`),
  loginSubmit: (sid, data) => http.post(`/accounts/login/${sid}/submit`, data),
  loginRefreshCode: (sid) => http.post(`/accounts/login/${sid}/refresh_code`),
  loginRefresh: (sid) => http.post(`/accounts/login/${sid}/refresh`),
  loginImport: (sid, data) => http.post(`/accounts/login/${sid}/import`, data),
  // works
  listWorks: (accountId, page = 1, size = 20) => http.get('/works', { params: { account_id: accountId, page, size } }),
  syncWorks: (accountId) => http.post(`/works/${accountId}/sync`),
  deleteWork: (accountId, workId) => http.delete(`/works/${accountId}/${workId}`),
  editWorkUrl: (accountId, workId) => http.get(`/works/${accountId}/${workId}/edit-url`),
  editWorkContent: (accountId, workId) => http.get(`/works/${accountId}/${workId}/edit-content`),
  editWork: (accountId, workId, data) => http.post(`/works/${accountId}/${workId}/edit`, data),
  editTopics: (accountId, workId, session, tabId = '1', cursor = '1') => http.get(`/works/${accountId}/${workId}/topics`, { params: { session, tab_id: tabId, cursor } }),
  editTopicsSearch: (accountId, workId, session, keyword, cursor = '1') => http.get(`/works/${accountId}/${workId}/topics/search`, { params: { session, keyword, cursor } }),
  editItems: (accountId, workId, session, taskId, cursor = '', size = 20) => http.get(`/works/${accountId}/${workId}/items`, { params: { session, task_id: taskId, cursor, size } }),
  editSearchItems: (accountId, workId, session, keyword, cursor = '', size = 15) => http.get(`/works/${accountId}/${workId}/search-items`, { params: { session, keyword, cursor, size } }),
  topWork: (accountId, workId, top) => http.post(`/works/${accountId}/${workId}/top`, null, { params: { top } }),
  setPrivacy: (accountId, workId, private_) => http.post(`/works/${accountId}/${workId}/privacy`, null, { params: { private: private_ } }),
  // videos（发布流程用）
  uploadVideoFile: (file, title) => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('title', title || '')
    return http.post('/videos/upload-file', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  addRemoteVideo: (url, title) => http.post('/videos/remote', null, { params: { url, title } }),
  importXhs: (url) => http.post('/videos/import-xhs', null, { params: { url } }),
  // publish (two-phase)
  preparePublish: (data) => http.post('/publish/prepare', data),
  getDraft: (id) => http.get(`/publish/draft/${id}`),
  draftItems: (id, keyword = '', cursor = '') => http.get(`/publish/draft/${id}/items`, { params: { keyword, cursor } }),
  searchDraftItems: (id, keyword, cursor = '', size = 15) => http.get(`/publish/draft/${id}/search-items`, { params: { keyword, cursor, size } }),
  draftTopics: (id, tabId = '1', cursor = '1') => http.get(`/publish/draft/${id}/topics`, { params: { tab_id: tabId, cursor } }),
  draftTopicsSearch: (id, keyword, cursor = '1') => http.get(`/publish/draft/${id}/topics/search`, { params: { keyword, cursor } }),
  uploadCoverFile: (accountId, file) => {
    const fd = new FormData()
    fd.append('file', file)
    return http.post('/publish/upload-cover', fd, { headers: { 'Content-Type': 'multipart/form-data' }, params: { account_id: accountId } })
  },
  uploadCoverUrl: (accountId, url) => http.post('/publish/upload-cover-url', null, { params: { account_id: accountId, url } }),
  submitPublish: (data) => http.post('/publish/submit', data),
  // commission & dashboard
  commission: (accountId, cursor = '1', size = 20) => http.get('/commission', { params: { account_id: accountId, cursor, size } }),
  commissionSearch: (accountId, keyword, size = 20) => http.get('/commission/search', { params: { account_id: accountId, keyword, size } }),
  dashboard: (accountId, days = 7) => http.get('/dashboard', { params: { account_id: accountId, days } }),
}
