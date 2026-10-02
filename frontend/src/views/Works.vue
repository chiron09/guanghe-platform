<template>
  <div>
    <el-card>
      <div class="page-title">我的作品</div>

      <!-- 账号工具条 -->
      <div class="toolbar">
        <el-select v-model="accountId" placeholder="选择账号" style="width:280px" @change="onAccountChange">
          <el-option v-for="a in accounts" :key="a.id" :label="`${a.name}（${a.taobao_id}）`" :value="a.id" />
        </el-select>
        <el-button type="primary" plain @click="sync" :loading="syncing" :disabled="!accountId">同步作品</el-button>
        <span class="spacer"></span>
        <span class="hint">共 {{ totalCount }} 条作品<span v-if="filteredWorks.length !== totalCount">，筛选后 {{ filteredWorks.length }} 条</span></span>
      </div>

      <!-- 筛选区（仿官方） -->
      <div class="filter-sec">
        <div class="filter-brand">淘宝作品</div>
        <div class="filter-line"><span class="f-label">作品类型</span>
          <span v-for="o in typeOptions" :key="'t' + o" class="f-item" :class="{ on: fType === o }" @click="fType = o">{{ o }}</span>
        </div>
        <div class="filter-line"><span class="f-label">审核状态</span>
          <span v-for="o in statusOptions" :key="'s' + o.k" class="f-item" :class="{ on: fStatus === o.k }" @click="fStatus = o.k">{{ o.n }}</span>
        </div>
        <div class="filter-line"><span class="f-label">作品标签</span>
          <span v-for="o in tagOptions" :key="'g' + o.k" class="f-item" :class="{ on: fTag === o.k }" @click="fTag = o.k">{{ o.n }}</span>
        </div>
        <div class="filter-line">
          <span class="f-label">发布时间</span>
          <el-date-picker v-model="fRange" type="daterange" size="small" style="width:240px"
                          start-placeholder="起始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD" />
          <el-input v-model="fKeyword" size="small" placeholder="请输入作品ID或关键字" clearable style="width:220px;margin-left:16px" prefix-icon="Search" />
        </div>
      </div>

      <!-- 作品列表（卡片式，仿官方） -->
      <div class="works-list" v-loading="loading">
        <el-empty v-if="!filteredWorks.length && !loading" description="暂无作品" />
        <div v-for="w in pagedWorks" :key="w.work_id" class="work-row">
          <div class="thumb-box">
            <el-image :src="w.cover_url" fit="cover" class="thumb">
              <template #error><div class="thumb thumb-empty"></div></template>
            </el-image>
            <span v-if="w.duration" class="duration">{{ fmtDuration(w.duration) }}</span>
          </div>
          <div class="work-info">
            <div class="w-title" :title="w.title">{{ w.title || '（无标题）' }}</div>
            <div class="w-meta">ID:{{ w.work_id }} | {{ w.publish_time || '—' }}</div>
            <div class="w-stats">
              <span><el-icon><View /></el-icon> {{ fmt(w.play_count) }}</span>
              <span><el-icon><Pointer /></el-icon> {{ fmt(w.like_count) }}</span>
              <span><el-icon><Star /></el-icon> {{ fmt(w.collect_count) }}</span>
              <span><el-icon><ChatDotRound /></el-icon> {{ fmt(w.comment_count) }}</span>
              <el-tag v-if="w.high_quality" type="warning" size="small" effect="plain">优质</el-tag>
              <el-tag v-if="w.elite" type="success" size="small" effect="plain">精选</el-tag>
              <el-tag v-if="w.homepage_top" type="danger" size="small" effect="plain">已置顶</el-tag>
              <el-tag v-if="w.private_level !== 1" type="info" size="small" effect="plain">私密</el-tag>
            </div>
          </div>
          <div class="work-ops">
            <el-tag :type="statusTagType(w.status)" size="small">{{ statusText(w.status) }}</el-tag>
            <div class="op-btns">
              <el-button size="small" type="primary" plain @click="editWork(w)">编辑</el-button>
              <el-button size="small" @click="toggleTop(w)">{{ w.homepage_top ? '取消置顶' : '置顶' }}</el-button>
              <el-button size="small" @click="togglePrivacy(w)">{{ w.private_level !== 1 ? '设为公开' : '设为私密' }}</el-button>
              <el-button size="small" type="danger" plain @click="remove(w)">删除</el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 分页器（仿官方：共N条内容 上一页 页码 下一页 1/21 到第X页 确定） -->
      <div class="pager-wrap" v-if="filteredWorks.length">
        <span class="pg-total">共{{ filteredWorks.length }}条内容</span>
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="filteredWorks.length"
          layout="prev, pager, next"
          background
          class="pager"
        />
        <span class="pg-meta">
          <span class="pg-cur">{{ currentPage }}</span><span class="pg-sep">/</span><span>{{ pageCount }}</span>
          <span class="pg-jump-label">到第</span>
          <el-input v-model="jumpPage" size="small" class="pg-input" @keyup.enter="doJump" />
          <span class="pg-jump-label">页</span>
          <el-button size="small" @click="doJump">确定</el-button>
        </span>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { View, Pointer, Star, ChatDotRound, Search } from '@element-plus/icons-vue'
import api from '../api'

const route = useRoute()
const router = useRouter()
const accounts = ref([])
const accountId = ref(null)
const works = ref([])
const totalCount = ref(0)
const loading = ref(false)
const syncing = ref(false)

// 筛选（仿官方；auditStatus: 0=公域审核中, 1=通过, -1=不通过, -2=作品违规）
const typeOptions = ['全部', '视频', '图文']
const statusOptions = [
  { k: 'all', n: '全部' }, { k: 0, n: '公域审核中' }, { k: 1, n: '公域审核通过' },
  { k: -1, n: '公域审核不通过' }, { k: -2, n: '作品违规' },
]
const tagOptions = [{ k: 'all', n: '全部' }, { k: 'hq', n: '优质' }, { k: 'elite', n: '精选' }]
const fType = ref('全部')
const fStatus = ref('all')
const fTag = ref('all')
const fRange = ref(null)
const fKeyword = ref('')

const currentAccount = computed(() => accounts.value.find(a => a.id === accountId.value) || null)

const filteredWorks = computed(() => {
  return works.value.filter(w => {
    if (fType.value === '视频' && w.content_type !== 'video') return false
    if (fType.value === '图文' && w.content_type !== 'image') return false
    if (fStatus.value !== 'all' && Number(w.status) !== Number(fStatus.value)) return false
    if (fTag.value === 'hq' && !w.high_quality) return false
    if (fTag.value === 'elite' && !w.elite) return false
    if (fRange.value && fRange.value.length === 2) {
      const d = (w.publish_time || '').slice(0, 10)
      if (!d || d < fRange.value[0] || d > fRange.value[1]) return false
    }
    const kw = fKeyword.value.trim().toLowerCase()
    if (kw && !(String(w.work_id).includes(kw) || (w.title || '').toLowerCase().includes(kw))) return false
    return true
  })
})

function statusText(s) {
  return { 0: '公域审核中', 1: '公域审核通过', '-1': '公域审核不通过', '-2': '作品违规' }[String(s)] || `状态${s}`
}
function statusTagType(s) {
  return { 0: 'warning', 1: 'success', '-1': 'danger', '-2': 'danger' }[String(s)] || 'info'
}

// ---- 分页（每页 20，仿官方；在筛选结果上切片） ----
const currentPage = ref(1)
const pageSize = 20
const jumpPage = ref('')
const pageCount = computed(() => Math.ceil(filteredWorks.value.length / pageSize) || 1)
const pagedWorks = computed(() =>
  filteredWorks.value.slice((currentPage.value - 1) * pageSize, currentPage.value * pageSize))
watch([fType, fStatus, fTag, fRange, fKeyword], () => { currentPage.value = 1 })
function doJump() {
  const p = Math.min(Math.max(1, parseInt(jumpPage.value) || 1), pageCount.value)
  currentPage.value = p
}
function fmt(n) { return n >= 10000 ? (n / 10000).toFixed(1) + 'w' : (n || 0) }
function fmtDuration(sec) {
  const m = Math.floor(sec / 60), s = sec % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

async function loadAccounts() {
  accounts.value = await api.listAccounts()
  if (accounts.value.length && !accountId.value) accountId.value = accounts.value[0].id
}
function onAccountChange() { load() }

async function load() {
  if (!accountId.value) return
  loading.value = true
  try {
    const r = await api.listWorks(accountId.value)
    works.value = r.items || []
    totalCount.value = r.total || r.items.length || 0
    currentPage.value = 1
  } catch (e) {} finally { loading.value = false }
}

async function sync() {
  syncing.value = true
  try {
    await api.syncWorks(accountId.value)
    ElMessage.success('同步完成')
    load()
  } catch (e) {} finally { syncing.value = false }
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除作品「${row.title || row.work_id}」？此操作不可恢复`, '警告', { type: 'warning' })
  await api.deleteWork(accountId.value, row.work_id)
  ElMessage.success('已删除')
  load()
}

async function toggleTop(row) {
  await api.topWork(accountId.value, row.work_id, !row.homepage_top)
  ElMessage.success(row.homepage_top ? '已取消置顶' : '已置顶')
  load()
}

// ---- 编辑：跳转到独立编辑页 ----
function editWork(row) {
  router.push({ path: `/edit/${row.work_id}`, query: { account_id: accountId.value } })
}

async function togglePrivacy(row) {
  const toPrivate = row.private_level === 1
  if (toPrivate) {
    await ElMessageBox.confirm(`确认将「${row.title || row.work_id}」设为私密？设为私密后仅自己可见`, '提示', { type: 'warning' })
  }
  await api.setPrivacy(accountId.value, row.work_id, toPrivate)
  ElMessage.success(toPrivate ? '已设为私密' : '已设为公开')
  load()
}

onMounted(async () => {
  await loadAccounts()
  // 从发布页跳转过来：定位账号并自动同步最新作品
  if (route.query.account_id) accountId.value = Number(route.query.account_id)
  await load()
  if (route.query.sync == '1' && accountId.value) {
    sync().catch(() => {})
  }
})
</script>

<style scoped>
.page-title { font-size: 18px; font-weight: 600; color: #303133; padding-bottom: 12px; border-bottom: 2px solid #ff5000; display: inline-block; margin-bottom: 4px; }
.toolbar { display: flex; align-items: center; gap: 10px; margin: 14px 0; }
.spacer { flex: 1; }
.hint { color: #909399; font-size: 13px; }

.filter-sec { border-top: 1px solid #f0f0f0; padding: 12px 4px 4px; }
.filter-brand { color: #ff5000; font-size: 14px; font-weight: 600; margin-bottom: 10px; }
.filter-line { display: flex; align-items: center; gap: 18px; margin-bottom: 10px; flex-wrap: wrap; }
.f-label { color: #909399; font-size: 13px; width: 60px; flex-shrink: 0; }
.f-item { color: #606266; font-size: 13px; cursor: pointer; user-select: none; }
.f-item:hover { color: #ff5000; }
.f-item.on { color: #ff5000; font-weight: 600; }

.works-list { border-top: 1px solid #f0f0f0; padding-top: 6px; }
.work-row { display: flex; align-items: center; gap: 14px; padding: 14px 4px; border-bottom: 1px solid #f5f5f5; }
.work-row:hover { background: #fafafa; }
.thumb-box { position: relative; flex-shrink: 0; }
.thumb { width: 88px; height: 118px; border-radius: 6px; display: block; }
.thumb-empty { background: #f5f7fa; }
.duration { position: absolute; left: 4px; bottom: 4px; background: rgba(0,0,0,.6); color: #fff; font-size: 11px; border-radius: 3px; padding: 0 5px; }
.work-info { flex: 1; min-width: 0; }
.w-title { font-size: 15px; color: #303133; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.w-meta { color: #909399; font-size: 12px; margin: 6px 0; }
.w-stats { display: flex; align-items: center; gap: 16px; color: #606266; font-size: 13px; }
.w-stats span { display: inline-flex; align-items: center; gap: 4px; }
.work-ops { display: flex; flex-direction: column; align-items: flex-end; gap: 8px; flex-shrink: 0; }
.op-btns { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }

/* 分页器（仿官方橙色） */
.pager-wrap { display: flex; align-items: center; justify-content: center; gap: 16px; padding: 22px 0 8px; flex-wrap: wrap; }
.pg-total { color: #606266; font-size: 13px; }
.pg-cur { color: #ff5000; font-weight: 600; }
.pg-sep { margin: 0 2px; color: #909399; }
.pg-meta { display: inline-flex; align-items: center; gap: 6px; color: #606266; font-size: 13px; }
.pg-jump-label { color: #606266; }
.pg-input { width: 52px; }
.pager :deep(.el-pager li.is-active) { background: #ff5000 !important; color: #fff !important; }
.pager :deep(.el-pager li:hover) { color: #ff5000; }
.pager :deep(.btn-prev:hover), .pager :deep(.btn-next:hover) { color: #ff5000; }
</style>
