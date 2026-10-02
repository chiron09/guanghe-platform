<template>
  <div>
    <el-card>
      <div class="toolbar">
        <el-select v-model="accountId" placeholder="选择账号" style="width:220px" @change="load">
          <el-option v-for="a in accounts" :key="a.id" :label="`${a.name}（${a.taobao_id}）`" :value="a.id" />
        </el-select>
        <el-input v-model="keyword" placeholder="搜索商品关键词 / 商品ID" clearable style="width:280px"
                  @keyup.enter="doSearch" @clear="load" />
        <el-button type="primary" @click="doSearch" :loading="loading">搜索</el-button>
        <span class="spacer"></span>
        <span class="hint">{{ searched ? `搜索结果 ${items.length} 条` : '高佣商品（佣金由账号权限决定）' }}</span>
      </div>

      <div v-loading="loading" class="goods-grid">
        <div v-for="row in items" :key="row.item_id" class="goods-card">
          <div class="goods-pic" @click="openDetail(row)">
            <img v-if="row.pic_url" :src="row.pic_url" loading="lazy" @error="onImgError" />
            <div v-else class="pic-empty">无图</div>
          </div>
          <div class="goods-body">
            <div class="goods-title" :title="row.title">{{ row.title }}</div>
            <div class="goods-shop">{{ row.shop_name || '—' }}</div>
            <div class="goods-meta">
              <span class="goods-price">¥{{ row.price }}</span>
              <el-tag v-if="row.commission_rate" type="danger" size="small">{{ row.commission_rate }}</el-tag>
            </div>
            <div class="goods-income">约赚 ¥{{ row.predict_income }} / 件</div>
            <div class="goods-actions">
              <el-button size="small" @click="copyId(row)">复制ID</el-button>
              <el-button size="small" type="primary" plain @click="openDetail(row)">查看</el-button>
            </div>
          </div>
        </div>

        <el-empty v-if="!loading && !items.length" description="暂无商品" style="grid-column:1/-1; padding:40px 0" />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const accounts = ref([])
const accountId = ref(null)
const items = ref([])
const keyword = ref('')
const searched = ref(false)
const loading = ref(false)

async function loadAccounts() {
  accounts.value = await api.listAccounts()
  if (accounts.value.length && !accountId.value) accountId.value = accounts.value[0].id
}

async function load() {
  if (!accountId.value) return
  loading.value = true
  try {
    const r = await api.commission(accountId.value)
    items.value = r.items
    searched.value = false
  } catch (e) {} finally { loading.value = false }
}

async function doSearch() {
  const kw = keyword.value.trim()
  if (!kw) return load()
  loading.value = true
  try {
    const r = await api.commissionSearch(accountId.value, kw)
    items.value = r.items
    searched.value = true
    if (!r.items.length) ElMessage.info('未找到匹配商品')
  } catch (e) {} finally { loading.value = false }
}

async function copyId(row) {
  try {
    await navigator.clipboard.writeText(row.item_id)
    ElMessage.success('商品ID已复制')
  } catch (e) {
    ElMessage.warning('复制失败，请手动复制')
  }
}

// 查看：新窗口打开 item.taobao.com 详情页
function detailUrl(row) {
  return `https://item.taobao.com/item.htm?id=${row.item_id}`
}
function openDetail(row) {
  window.open(detailUrl(row), '_blank')
}

function onImgError(e) {
  e.target.style.visibility = 'hidden'
}

onMounted(async () => { await loadAccounts(); await load() })
</script>

<style scoped>
.toolbar { display: flex; align-items: center; gap: 8px; }
.spacer { flex: 1; }
.hint { color: #909399; font-size: 13px; }

.goods-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 16px;
  margin-top: 16px;
  min-height: 120px;
}
.goods-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
  transition: box-shadow .2s, transform .2s;
  display: flex;
  flex-direction: column;
}
.goods-card:hover { box-shadow: 0 6px 18px rgba(0,0,0,.08); transform: translateY(-2px); }
.goods-pic {
  width: 100%;
  aspect-ratio: 1;
  background: #f5f7fa;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.goods-pic img { width: 100%; height: 100%; object-fit: cover; display: block; }
.pic-empty { color: #c0c4cc; font-size: 13px; }
.goods-body { padding: 10px 12px 12px; display: flex; flex-direction: column; flex: 1; }
.goods-title {
  font-size: 13px; line-height: 1.45; color: #303133;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
  min-height: 38px;
}
.goods-shop { color: #909399; font-size: 12px; margin-top: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.goods-meta { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
.goods-price { color: #f56c6c; font-size: 16px; font-weight: 600; }
.goods-income { color: #e6a23c; font-size: 12px; margin-top: 6px; }
.goods-actions { display: flex; gap: 8px; margin-top: 10px; }
.goods-actions .el-button { flex: 1; margin-left: 0; }
</style>
