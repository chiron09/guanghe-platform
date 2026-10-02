<template>
  <div class="dashboard">
    <!-- 顶部工具栏 -->
    <el-card class="toolbar-card" shadow="never">
      <div class="toolbar">
        <el-select v-model="accountId" placeholder="选择账号" style="width:260px" @change="load">
          <el-option v-for="a in accounts" :key="a.id" :label="`${a.name}（${a.taobao_id}）`" :value="a.id" />
        </el-select>
        <el-radio-group v-model="days" @change="load">
          <el-radio-button :value="7">近7天</el-radio-button>
          <el-radio-button :value="30">近30天</el-radio-button>
        </el-radio-group>
        <span class="spacer"></span>
        <span v-if="dataDate" class="data-date"><i class="dot"></i>数据截至 {{ dataDate }}</span>
        <el-button :icon="Refresh" circle :loading="loading" title="刷新" @click="load" />
      </div>
    </el-card>

    <!-- 主体 -->
    <div v-loading="loading" class="body">
      <!-- 空状态 -->
      <el-empty v-if="!loading && !hasData" description="暂无数据，请选择账号后重试" />

      <template v-if="hasData">
        <!-- 分组指标区 -->
        <el-card v-for="g in groups" :key="g.key" class="group-card" shadow="never">
          <template #header>
            <div class="group-head">
              <span class="group-ic" :style="{ background: g.bg, color: g.color }">
                <el-icon :size="16"><component :is="g.icon" /></el-icon>
              </span>
              <span class="group-title">{{ g.title }}</span>
              <span class="group-sub">{{ g.sub }}</span>
            </div>
          </template>
          <div class="metric-grid">
            <div v-for="m in g.items" :key="m.key" class="metric-card" :class="{ big: m.big }">
              <div class="mc-head">
                <span class="mc-icon" :style="m.big ? { background: 'rgba(255,255,255,.22)', color: '#fff' } : { background: m.bg, color: m.color }">
                  <el-icon :size="16"><component :is="m.icon" /></el-icon>
                </span>
                <span class="mc-label">{{ m.label }}</span>
              </div>
              <div class="mc-value" :style="m.big ? { color: '#fff' } : { color: m.color }">{{ m.value }}</div>
              <div v-if="m.diff !== null" class="mc-diff" :class="[m.diffUp ? 'up' : 'down', { onhero: m.big }]">
                <span class="arrow">{{ m.diffUp ? '↑' : '↓' }}</span>较上期 {{ m.diff }}
              </div>
              <div v-else class="mc-diff flat" :class="{ onhero: m.big }">较上期持平</div>
            </div>
          </div>
        </el-card>

        <!-- 图表区 -->
        <div class="charts">
          <el-card v-if="trendPoints.length > 1" class="panel panel-trend" shadow="never">
            <template #header><span class="panel-title">播放量趋势</span></template>
            <div class="line-chart">
              <div class="lc-plot">
                <svg viewBox="0 0 100 100" preserveAspectRatio="none" class="lc-svg">
                  <defs>
                    <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stop-color="#ff5000" stop-opacity="0.22" />
                      <stop offset="100%" stop-color="#ff5000" stop-opacity="0" />
                    </linearGradient>
                  </defs>
                  <polygon v-if="areaPoints" :points="areaPoints" fill="url(#areaGrad)" />
                  <polyline v-if="linePoints" :points="linePoints" fill="none" stroke="#ff5000"
                            stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" />
                  <circle v-for="(p, i) in trendPoints" :key="i" :cx="p.px" :cy="p.py" r="2.2"
                          fill="#fff" stroke="#ff5000" stroke-width="1.5" />
                </svg>
                <div v-for="(p, i) in trendPoints" :key="'v' + i" class="lc-val"
                     :style="{ left: p.px + '%', bottom: (100 - p.py) + '%' }">{{ p.text }}</div>
              </div>
              <div class="lc-x">
                <span v-for="(p, i) in trendPoints" :key="'x' + i" class="lc-x-item">{{ p.label }}</span>
              </div>
            </div>
          </el-card>

          <el-card v-if="interactItems.length" class="panel panel-interact" shadow="never">
            <template #header><span class="panel-title">互动构成</span></template>
            <div class="interact-list">
              <div v-for="it in interactItems" :key="it.key" class="interact-row">
                <span class="ir-label">{{ it.label }}</span>
                <div class="ir-track">
                  <div class="ir-bar" :style="{ width: it.pct + '%', background: it.color }"></div>
                </div>
                <span class="ir-value">{{ it.text }}</span>
                <span class="ir-pct" :style="{ color: it.color }">{{ it.pct }}%</span>
              </div>
            </div>
            <div class="interact-foot">点赞 · 评论 · 收藏 · 分享（PV）</div>
          </el-card>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  View, User, DataLine, Timer, Pointer, ChatDotRound, Star, Share,
  Money, Coin, ShoppingCart, VideoPlay, Refresh,
} from '@element-plus/icons-vue'
import api from '../api'

const accounts = ref([])
const accountId = ref(null)
const days = ref(7)
const raw = ref(null)
const loading = ref(false)

// ---- 分组指标配置（按业务域组织）----
const GROUPS = [
  {
    key: 'traffic', title: '流量表现', sub: '播放 · 完播 · 时长',
    icon: VideoPlay, color: '#ff5000', bg: '#fff1ec',
    metrics: [
      { key: 'consumePv', label: '播放量', icon: View, color: '#ff5000', bg: '#fff1ec', type: 'count', big: true },
      { key: 'consumeUv', label: '播放人数', icon: User, color: '#ff7a45', bg: '#fff1ec', type: 'count' },
      { key: 'playRateComplete', label: '完播率', icon: DataLine, color: '#00bcd4', bg: '#e0f7fa', type: 'percent' },
      { key: 'consumeTimeAvg', label: '平均播放时长', icon: Timer, color: '#3f51b5', bg: '#e8eaf6', type: 'duration' },
    ],
  },
  {
    key: 'interaction', title: '互动表现', sub: '点赞 · 评论 · 收藏 · 分享',
    icon: ChatDotRound, color: '#409eff', bg: '#ecf5ff',
    metrics: [
      { key: 'favorPv', label: '点赞', icon: Pointer, color: '#f56c6c', bg: '#fef0f0', type: 'count' },
      { key: 'commentPv', label: '评论', icon: ChatDotRound, color: '#409eff', bg: '#ecf5ff', type: 'count' },
      { key: 'collectPv', label: '收藏', icon: Star, color: '#e6a23c', bg: '#fdf6ec', type: 'count' },
      { key: 'sharePv', label: '分享', icon: Share, color: '#67c23a', bg: '#f0f9eb', type: 'count' },
    ],
  },
  {
    key: 'fans', title: '粉丝资产', sub: '粉丝 · 关注',
    icon: User, color: '#722ed1', bg: '#f4eafb',
    metrics: [
      { key: 'fansCount', label: '粉丝数', icon: User, color: '#722ed1', bg: '#f4eafb', type: 'count', fallback: 'attentionFansCount' },
      { key: 'attentionFansCount', label: '新增关注', icon: User, color: '#9c27b0', bg: '#f4eafb', type: 'count' },
    ],
  },
  {
    key: 'commerce', title: '带货数据', sub: '收入 · 订单 · 买家',
    icon: ShoppingCart, color: '#e6a23c', bg: '#fdf6ec',
    metrics: [
      { key: 'incomeAmt', label: '预估收入', icon: Money, color: '#ff5000', bg: '#fff1ec', type: 'money' },
      { key: 'payAmtZcLast', label: '成交金额', icon: Coin, color: '#f56c6c', bg: '#fef0f0', type: 'money' },
      { key: 'orderCnt', label: '成交订单', icon: ShoppingCart, color: '#409eff', bg: '#ecf5ff', type: 'count' },
      { key: 'buyerCnt', label: '成交买家', icon: User, color: '#67c23a', bg: '#f0f9eb', type: 'count' },
    ],
  },
]

const INTERACT = [
  { key: 'favorPv', label: '点赞', color: '#f56c6c' },
  { key: 'commentPv', label: '评论', color: '#409eff' },
  { key: 'collectPv', label: '收藏', color: '#e6a23c' },
  { key: 'sharePv', label: '分享', color: '#67c23a' },
]

// ---- 解析光合 dashboard 返回结构 ----
const parsed = computed(() => {
  const result = raw.value?.model?.result
  if (!Array.isArray(result) || !result.length) return { latest: null, trend: [] }
  const sorted = [...result].sort((a, b) => String(a.ds || '').localeCompare(String(b.ds || '')))
  const latest = sorted[sorted.length - 1]
  const trend = sorted.map(r => ({
    label: fmtShortDate(r.ds || r.date?.absolute),
    value: metricValue(r, 'consumePv'),
  }))
  return { latest, trend }
})

const hasData = computed(() => !!parsed.value.latest)

const dataDate = computed(() => {
  const l = parsed.value.latest
  if (!l) return ''
  return fmtFullDate(l.ds || l.date?.absolute)
})

// ---- 指标取值 ----
function metricValue(obj, key, fallback) {
  const m = obj?.[key]
  if (m && typeof m.absolute === 'number') return m.absolute
  if (fallback) {
    const f = obj?.[fallback]
    if (f && typeof f.absolute === 'number') return f.absolute
  }
  return null
}

function metricDiff(obj, key) {
  const m = obj?.[key]
  if (!m || m.Diff === undefined || m.Diff === null || m.Diff === '') return null
  const v = parseFloat(m.Diff)
  if (isNaN(v) || v === 0) return null
  return v
}

function hasAnyData(keys) {
  const latest = parsed.value.latest
  if (!latest) return false
  return keys.some(k => (metricValue(latest, k) || 0) > 0)
}

const groups = computed(() => {
  const latest = parsed.value.latest
  if (!latest) return []
  return GROUPS
    .filter(g => {
      if (g.key === 'commerce') return hasAnyData(['incomeAmt', 'payAmtZcLast', 'orderCnt', 'buyerCnt'])
      return true
    })
    .map(g => ({
      ...g,
      items: g.metrics.map(m => {
        const v = metricValue(latest, m.key, m.fallback)
        const d = metricDiff(latest, m.key)
        return {
          ...m,
          value: formatValue(m.type, v),
          diff: d === null ? null : fmtDiff(d),
          diffUp: d > 0,
        }
      }),
    }))
})

// ---- 趋势折线图（归一化坐标 0-100）----
const trendPoints = computed(() => {
  const t = parsed.value.trend
  if (!t.length) return []
  const values = t.map(x => x.value || 0)
  const max = Math.max(...values, 1)
  const n = t.length
  const top = 22
  const bottom = 86
  return t.map((x, i) => {
    const px = n === 1 ? 50 : (i * 100) / (n - 1)
    const py = top + (1 - (x.value || 0) / max) * (bottom - top)
    return { ...x, px, py, text: fmtCount(x.value) }
  })
})

const linePoints = computed(() => trendPoints.value.map(p => `${p.px},${p.py}`).join(' '))

const areaPoints = computed(() => {
  const pts = trendPoints.value
  if (!pts.length) return ''
  const first = pts[0]
  const last = pts[pts.length - 1]
  return `${first.px},100 ${pts.map(p => `${p.px},${p.py}`).join(' ')} ${last.px},100`
})

// ---- 互动构成 ----
const interactItems = computed(() => {
  const latest = parsed.value.latest
  if (!latest) return []
  const items = INTERACT.map(m => ({ ...m, value: metricValue(latest, m.key) || 0 }))
  const max = Math.max(...items.map(x => x.value), 1)
  return items.map(x => ({
    ...x,
    text: fmtCount(x.value),
    pct: Math.round((x.value / max) * 100),
  }))
})

// ---- 格式化 ----
function fmtCount(n) {
  if (n === null || n === undefined) return '—'
  return Number(n).toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}

function fmtMoney(n) {
  if (n === null || n === undefined) return '—'
  return '¥' + Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtPercent(v) {
  if (v === null || v === undefined) return '—'
  return (v * 100).toFixed(1) + '%'
}

function fmtDuration(sec) {
  if (sec === null || sec === undefined) return '—'
  sec = Math.round(sec)
  if (sec < 60) return sec + '秒'
  const m = Math.floor(sec / 60)
  const s = sec % 60
  if (m < 60) return `${m}分${s}秒`
  const h = Math.floor(m / 60)
  const mm = m % 60
  return `${h}时${mm}分`
}

function fmtDiff(v) {
  const a = Math.abs(v)
  if (a >= 1) return fmtCount(a)
  return (a * 100).toFixed(1) + '%'
}

function formatValue(type, v) {
  switch (type) {
    case 'percent': return fmtPercent(v)
    case 'duration': return fmtDuration(v)
    case 'money': return fmtMoney(v)
    default: return fmtCount(v)
  }
}

function fmtShortDate(ds) {
  const s = String(ds || '')
  return s.length === 8 ? s.slice(4, 6) + '-' + s.slice(6, 8) : s
}

function fmtFullDate(ds) {
  const s = String(ds || '')
  return s.length === 8 ? `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}` : s
}

// ---- 数据加载 ----
async function loadAccounts() {
  accounts.value = await api.listAccounts()
  if (accounts.value.length && !accountId.value) accountId.value = accounts.value[0].id
}

async function load() {
  if (!accountId.value) return
  loading.value = true
  try {
    raw.value = await api.dashboard(accountId.value, days.value)
  } catch (e) {
    raw.value = null
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadAccounts()
  await load()
})
</script>

<style scoped>
.dashboard { display: flex; flex-direction: column; gap: 16px; }

/* 工具栏 */
.toolbar-card :deep(.el-card__body) { padding: 14px 18px; }
.toolbar { display: flex; align-items: center; gap: 14px; }
.spacer { flex: 1; }
.data-date { display: inline-flex; align-items: center; gap: 6px; color: #909399; font-size: 13px; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: #67c23a; display: inline-block; }

/* 主体 */
.body { min-height: 240px; }

/* 分组卡片 */
.group-card { background: #fff; }
.group-card :deep(.el-card__header) { padding: 13px 18px; border-bottom: 1px solid #f5f5f5; }
.group-head { display: flex; align-items: center; gap: 9px; }
.group-ic {
  width: 28px; height: 28px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.group-title { font-size: 15px; font-weight: 600; color: #303133; }
.group-sub { color: #c0c4cc; font-size: 12px; margin-left: auto; }

/* 组内指标网格 */
.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(168px, 1fr));
  gap: 12px;
  padding: 16px 18px;
}
.metric-card {
  background: #fff; border-radius: 10px; padding: 14px;
  border: 1px solid #f0f0f0; box-shadow: 0 1px 4px rgba(0, 0, 0, .04);
  transition: transform .2s, box-shadow .2s;
}
.metric-card:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(0, 0, 0, .06); }
.metric-card.big {
  grid-column: span 2;
  background: linear-gradient(135deg, #ff7a45, #ff5000);
  border: none; box-shadow: 0 6px 18px rgba(255, 80, 0, .28);
}
.mc-head { display: flex; align-items: center; gap: 7px; }
.mc-icon {
  width: 28px; height: 28px; border-radius: 7px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.mc-label { color: #606266; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.metric-card.big .mc-label { color: rgba(255, 255, 255, .92); }
.mc-value { font-size: 22px; font-weight: 700; margin: 8px 0 6px; line-height: 1; }
.metric-card.big .mc-value { font-size: 32px; }
.mc-diff { font-size: 11px; display: flex; align-items: center; gap: 1px; }
.mc-diff .arrow { font-weight: 700; }
.mc-diff.up { color: #67c23a; }
.mc-diff.down { color: #f56c6c; }
.mc-diff.flat { color: #c0c4cc; }
.mc-diff.onhero { color: rgba(255, 255, 255, .92); }
.mc-diff.onhero .arrow { color: #fff; }

/* 图表区 */
.charts { display: flex; gap: 14px; }
.panel { background: #fff; }
.panel :deep(.el-card__header) { padding: 14px 18px; border-bottom: 1px solid #f5f5f5; }
.panel-title { font-size: 15px; font-weight: 600; color: #303133; }
.panel-trend { flex: 1.6; min-width: 0; }
.panel-interact { flex: 1; min-width: 0; }

/* 折线图 */
.line-chart { padding: 4px 6px 0; }
.lc-plot { position: relative; height: 200px; overflow: visible; }
.lc-svg { position: absolute; inset: 0; width: 100%; height: 100%; }
.lc-val {
  position: absolute; transform: translate(-50%, -100%);
  font-size: 11px; color: #606266; padding-bottom: 3px; white-space: nowrap; pointer-events: none;
}
.lc-x { display: flex; justify-content: space-between; padding: 8px 0 2px; }
.lc-x-item { font-size: 12px; color: #909399; }

/* 互动构成 */
.interact-list { display: flex; flex-direction: column; gap: 18px; padding: 8px 4px; }
.interact-row { display: flex; align-items: center; gap: 10px; }
.ir-label { width: 34px; flex-shrink: 0; color: #606266; font-size: 13px; }
.ir-track { flex: 1; height: 10px; background: #f5f7fa; border-radius: 5px; overflow: hidden; }
.ir-bar { height: 100%; border-radius: 5px; transition: width .4s; }
.ir-value { width: 70px; flex-shrink: 0; text-align: right; color: #303133; font-size: 13px; font-weight: 600; }
.ir-pct { width: 40px; flex-shrink: 0; text-align: right; font-size: 12px; }
.interact-foot { color: #c0c4cc; font-size: 12px; padding: 4px 4px 0; }

/* 响应式 */
@media (max-width: 960px) {
  .charts { flex-direction: column; }
  .metric-card.big { grid-column: span 1; }
}
</style>
