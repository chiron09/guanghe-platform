<template>
  <el-card class="edit-card">
    <div class="page-title">编辑作品</div>

    <div class="account-row">
      <span class="label">发布账号</span>
      <span class="account-name">{{ accountName || '—' }}</span>
      <span class="spacer"></span>
      <el-button size="small" @click="back">返回作品管理</el-button>
    </div>

    <div v-loading="loading" class="main-grid">
      <!-- 左栏：原封面预览 -->
      <div class="left-col">
        <div class="cover-preview">
          <el-image :src="(selectedCover && selectedCover.url) || coverUrl" fit="cover" class="cover-img">
            <template #error><div class="cover-img cover-empty"></div></template>
          </el-image>
          <span v-if="duration" class="duration">{{ fmtDuration(duration) }}</span>
        </div>
        <div class="hint" style="text-align:center">编辑不更换视频，仅修改内容信息</div>
      </div>

      <!-- 右栏：表单 -->
      <div class="right-col">
        <!-- 标题 -->
        <div class="sec">
          <div class="sec-title"><span class="req">*</span> 视频标题</div>
          <el-input v-model="form.title" maxlength="30" show-word-limit placeholder="加个标题让内容更吸引人" />
        </div>

        <!-- 描述 -->
        <div class="sec">
          <div class="sec-title">视频描述</div>
          <el-input v-model="form.desc" type="textarea" :rows="4" maxlength="1000" show-word-limit
                    class="desc-input" placeholder="展开说说，你写的文字我们都喜欢" />
          <div class="reco-tags" v-if="draftTags.length">
            <span class="reco-label">推荐内容标签</span>
            <span class="reco-tags-list">
              <span v-for="t in draftTags" :key="t.id || t.name" class="reco-tag" :class="{ on: isTagSelected(t) }" @click="toggleTag(t)"># {{ t.name }}</span>
            </span>
          </div>
          <div class="hint">点击推荐标签填入描述框，描述中以 # 开头的内容即为发布的话题标签</div>
        </div>

        <!-- 封面 -->
        <div class="sec">
          <div class="sec-title">视频封面</div>
          <div class="cover-opts">
            <div class="cover-opt" :class="{ on: !selectedCover }" @click="selectedCover = null">
              <el-image :src="coverUrl" fit="cover" class="co-img"><template #error><div class="co-img co-empty">原封面</div></template></el-image>
              <span class="co-label">原封面</span>
            </div>
            <div v-for="(c, i) in draftCovers" :key="'cv' + i" class="cover-opt"
                 :class="{ on: selectedCover && selectedCover.url === c.url }" @click="selectedCover = c">
              <el-image :src="c.url" fit="cover" class="co-img"><template #error><div class="co-img co-empty"></div></template></el-image>
              <span class="co-label">智能封面{{ i + 1 }}</span>
            </div>
            <div class="cover-opt cover-add">
              <el-upload :show-file-list="false" :before-upload="(f) => { pickCoverFile(f); return false }" accept="image/*">
                <div class="co-add">本地上传</div>
              </el-upload>
              <el-input v-model="remoteCoverUrl" size="small" placeholder="远程图片URL" style="margin-top:6px" @keyup.enter="applyCoverUrl" />
              <el-button size="small" style="margin-top:6px" @click="applyCoverUrl">应用远程</el-button>
            </div>
          </div>
        </div>

        <!-- 参与话题活动 -->
        <div class="sec">
          <div class="sec-title">参与话题活动</div>
          <div v-if="selectedTopics.length" class="picked-topics">
            <div v-for="(t, i) in selectedTopics" :key="'pt' + i" class="picked-topic">
              <span class="pt-name"># {{ t.title }}</span>
              <el-icon class="pt-del" @click="selectedTopics.splice(i, 1)"><Close /></el-icon>
            </div>
          </div>
          <div class="add-item-btn" @click="openTopicDialog">
            <el-icon><Plus /></el-icon>
            <span>点击添加话题</span>
          </div>
          <div class="hint">由官方发起的征稿话题，奖励多多（最多 5 个）</div>
        </div>

        <!-- 关联商品 -->
        <div class="sec">
          <div class="sec-title">关联商品</div>
          <div v-if="selectedItems.length" class="picked-items">
            <div v-for="(it, i) in selectedItems" :key="'pk' + i" class="picked-item">
              <el-image :src="it.pic_url" fit="cover" class="pi-img"><template #error><div class="pi-img pi-empty"></div></template></el-image>
              <div class="pi-info">
                <div class="pi-title">{{ it.title }}</div>
                <div class="pi-meta">¥{{ it.price }} · 佣金 {{ it.commission_rate }}</div>
              </div>
              <el-icon class="pi-del" @click="selectedItems.splice(i, 1)"><Close /></el-icon>
            </div>
          </div>
          <div class="add-item-btn" @click="openItemDialog">
            <el-icon><Plus /></el-icon>
            <span>添加商品</span>
          </div>
          <div class="hint">商品挂载需账号已开通商品推广权限；最多关联 6 个</div>
        </div>

        <!-- 声明 -->
        <div class="sec">
          <div class="sec-title"><span class="req">*</span> 创作者声明</div>
          <el-radio-group v-model="form.declaration">
            <el-radio v-for="d in declarations" :key="d" :value="d">{{ d }}</el-radio>
          </el-radio-group>
        </div>

        <el-button type="primary" size="large" class="save-btn" :loading="saving" @click="doSave">保存修改</el-button>
        <div class="hint" style="margin-top:10px">提示：光合限制每条作品最多编辑 1 次，保存后作品将重新进入公域审核。</div>
      </div>
    </div>

    <!-- 话题选择弹窗 -->
    <el-dialog v-model="topicDialog" title="话题选择" width="760px">
      <div class="td-search">
        <el-input v-model="topicKeyword" placeholder="输入关键词搜索" @keyup.enter="doTopicSearch" clearable />
        <el-button type="primary" @click="doTopicSearch">搜索</el-button>
        <el-button @click="resetTopicSearch">重置</el-button>
      </div>
      <div class="td-body">
        <div class="td-tabs">
          <div v-for="t in topicTabs" :key="t.tabId" class="td-tab" :class="{ on: topicTabId === t.tabId }" @click="switchTopicTab(t)">{{ t.tabName }}</div>
        </div>
        <div class="td-list" v-loading="topicsLoading">
          <div class="td-banner">参与官方话题投稿，有机会获得额外流量奖励~</div>
          <div v-for="t in topicList" :key="t.topic_id" class="td-topic" :class="{ on: isTopicPicked(t) }" @click="toggleTopic(t)">
            <div class="tdt-head">
              <span class="tdt-title"># {{ t.title }}</span>
              <span v-if="t.icon_type === '1'" class="tdt-badge">小二推荐</span>
              <span v-if="t.category" class="tdt-badge cat">{{ t.category }}</span>
            </div>
            <div class="tdt-meta">作品 {{ t.content_count }} · 参与 {{ t.user_count }} · 浏览 {{ t.browse_count }}</div>
            <div v-if="t.activity_title" class="tdt-activity">
              <span v-if="t.activity_level" class="tdt-act-level">{{ t.activity_level }}</span>
              平台活动：{{ t.activity_title }} {{ t.activity_delivery }}
            </div>
            <el-icon v-if="isTopicPicked(t)" class="tdt-check"><CircleCheckFilled /></el-icon>
          </div>
          <div v-if="topicHasNext" class="td-more"><el-button size="small" :loading="topicsLoading" @click="loadMoreTopics">加载更多</el-button></div>
          <el-empty v-if="!topicList.length && !topicsLoading" description="暂无话题" :image-size="60" />
        </div>
      </div>
      <template #footer>
        <el-button type="primary" @click="topicDialog = false">确认提交</el-button>
        <el-button @click="topicDialog = false">取消</el-button>
      </template>
    </el-dialog>

    <!-- 商品选择弹窗 -->
    <el-dialog v-model="itemDialog" title="添加关联商品" width="680px">
      <div style="display:flex;gap:8px;margin-bottom:12px">
        <el-input v-model="itemKeyword" placeholder="搜索商品ID/标题/关键词（平台优选）" @keyup.enter="searchItems" clearable />
        <el-button :loading="itemsLoading" @click="searchItems">搜索</el-button>
      </div>
      <el-table :data="itemList" size="small" v-loading="itemsLoading" max-height="380"
                @row-click="toggleItem" :row-class-name="r => isItemPicked(r.row) ? 'picked-row' : ''">
        <el-table-column label="图" width="60">
          <template #default="{ row }"><el-image :src="row.pic_url" fit="cover" style="width:40px;height:40px;border-radius:3px"><template #error><div style="width:40px;height:40px;background:#f5f7fa"></div></template></el-image></template>
        </el-table-column>
        <el-table-column label="商品" show-overflow-tooltip><template #default="{ row }">{{ row.title }}</template></el-table-column>
        <el-table-column prop="price" label="价格" width="90" />
        <el-table-column label="佣金" width="80"><template #default="{ row }"><el-tag type="danger" size="small">{{ row.commission_rate }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }"><el-button size="small" :type="isItemPicked(row) ? 'success' : 'default'" @click.stop="toggleItem(row)">{{ isItemPicked(row) ? '已选' : '选择' }}</el-button></template>
        </el-table-column>
      </el-table>
      <div class="hint" style="margin-top:8px">已选 {{ selectedItems.length }}/6</div>
      <template #footer><el-button @click="itemDialog = false">完成</el-button></template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Close, CircleCheckFilled } from '@element-plus/icons-vue'
import api from '../api'

const route = useRoute()
const router = useRouter()
const declarations = ['内容无需标注', '含AI生成内容', '含虚构演绎内容', '内容为转载', '个人观点，仅供参考', '内容含营销信息']

const accountId = ref(Number(route.query.account_id) || 0)
const workId = ref(route.params.workId)
const accountName = ref('')
const loading = ref(false)
const saving = ref(false)

const form = reactive({ title: '', desc: '', declaration: '内容无需标注' })
const coverUrl = ref('')
const coverWidth = ref('')
const coverHeight = ref('')
const duration = ref(0)
const selectedCover = ref(null)   // null=原封面，否则 {url,width,height}
const draftCovers = ref([])
const draftTags = ref([])
const remoteCoverUrl = ref('')
const coverUploading = ref(false)

const selectedItems = ref([])
const selectedTopics = ref([])
const itemTaskId = ref('')
const publishSession = ref('')
const fileId = ref('')

// 商品
const itemDialog = ref(false)
const itemList = ref([])
const itemsLoading = ref(false)
const itemKeyword = ref('')

// 话题
const topicDialog = ref(false)
const topicTabs = ref([])
const topicTabId = ref('1')
const topicList = ref([])
const topicCursor = ref('1')
const topicHasNext = ref(false)
const topicsLoading = ref(false)
const topicKeyword = ref('')
const topicSearching = ref(false)

function fmtDuration(sec) {
  const m = Math.floor(sec / 60), s = sec % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}
function back() { router.push({ path: '/works', query: { account_id: accountId.value } }) }

// ---- 回填 ----
async function loadEditContent() {
  loading.value = true
  try {
    const c = await api.editWorkContent(accountId.value, workId.value)
    form.title = c.title || ''
    form.desc = c.desc || ''
    form.declaration = c.declaration || '内容无需标注'
    coverUrl.value = c.cover_url || ''
    coverWidth.value = c.cover_width
    coverHeight.value = c.cover_height
    draftCovers.value = c.covers || []
    draftTags.value = c.tags || []
    selectedItems.value = c.items || []
    selectedTopics.value = c.topics || []
    itemTaskId.value = c.item_task_id || ''
    publishSession.value = c.publish_session || ''
    fileId.value = c.file_id || ''
    // 时长：从 item 里拿不到，跳过（用封面预览）
  } catch (e) { ElMessage.error('加载编辑内容失败'); back() } finally { loading.value = false }
}

// ---- 标签 ----
function isTagSelected(t) {
  return form.desc.includes('#' + t.name)
}
function toggleTag(t) {
  if (isTagSelected(t)) form.desc = form.desc.replace(new RegExp('#' + t.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), '').replace(/\s+/g, ' ').trim()
  else form.desc = (form.desc ? form.desc + ' ' : '') + '#' + t.name
}

// ---- 封面 ----
async function pickCoverFile(f) {
  coverUploading.value = true
  try {
    const r = await api.uploadCoverFile(accountId.value, f.raw)
    selectedCover.value = { url: r.url, width: 720, height: 1280 }
  } catch (e) {} finally { coverUploading.value = false }
}
async function applyCoverUrl() {
  const u = remoteCoverUrl.value.trim()
  if (!u) return
  coverUploading.value = true
  try {
    const r = await api.uploadCoverUrl(accountId.value, u)
    selectedCover.value = { url: r.url, width: 720, height: 1280 }
    ElMessage.success('封面已更新')
  } catch (e) {} finally { coverUploading.value = false }
}

// ---- 话题 ----
function openTopicDialog() {
  topicDialog.value = true
  if (!topicTabs.value.length) loadTopicList('1', true)
}
async function loadTopicList(tabId, reset) {
  topicsLoading.value = true
  try {
    const r = await api.editTopics(accountId.value, workId.value, publishSession.value, tabId, reset ? '1' : topicCursor.value)
    if (reset) topicTabs.value = r.tabs || []
    topicList.value = reset ? (r.topics || []) : topicList.value.concat(r.topics || [])
    topicCursor.value = r.cursor || ''
    topicHasNext.value = !!r.has_next
  } catch (e) {} finally { topicsLoading.value = false }
}
function switchTopicTab(t) {
  topicTabId.value = t.tabId
  topicKeyword.value = ''
  topicSearching.value = false
  loadTopicList(t.tabId, true)
}
async function doTopicSearch() {
  const kw = topicKeyword.value.trim()
  if (!kw) { topicSearching.value = false; loadTopicList(topicTabId.value, true); return }
  topicSearching.value = true
  topicsLoading.value = true
  try {
    const r = await api.editTopicsSearch(accountId.value, workId.value, publishSession.value, kw, '1')
    topicList.value = r.topics || []
    topicCursor.value = r.cursor || ''
    topicHasNext.value = !!r.has_next
  } catch (e) {} finally { topicsLoading.value = false }
}
function resetTopicSearch() { topicKeyword.value = ''; topicSearching.value = false; loadTopicList(topicTabId.value, true) }
async function loadMoreTopics() {
  if (topicSearching.value) {
    topicsLoading.value = true
    try {
      const r = await api.editTopicsSearch(accountId.value, workId.value, publishSession.value, topicKeyword.value.trim(), topicCursor.value)
      topicList.value = topicList.value.concat(r.topics || [])
      topicCursor.value = r.cursor || ''
      topicHasNext.value = !!r.has_next
    } catch (e) {} finally { topicsLoading.value = false }
  } else loadTopicList(topicTabId.value, false)
}
function isTopicPicked(t) { return selectedTopics.value.some(x => x.topic_id === t.topic_id) }
function toggleTopic(t) {
  if (isTopicPicked(t)) { selectedTopics.value = selectedTopics.value.filter(x => x.topic_id !== t.topic_id); return }
  if (selectedTopics.value.length >= 5) return ElMessage.warning('最多参与 5 个话题')
  const act = (t.activities && t.activities[0]) || {}
  selectedTopics.value.push({ ...t, activity_title: act.title || '', activity_level: act.level || '', activity_delivery: act.delivery || '' })
}

// ---- 商品 ----
function openItemDialog() { itemDialog.value = true; if (!itemList.value.length) loadItems() }
async function loadItems() {
  itemsLoading.value = true
  try {
    const r = await api.editItems(accountId.value, workId.value, publishSession.value, itemTaskId.value, '', 50)
    itemList.value = r.items || []
  } catch (e) {} finally { itemsLoading.value = false }
}
async function searchItems() {
  const kw = itemKeyword.value.trim()
  if (!kw) { loadItems(); return }
  itemsLoading.value = true
  try {
    const r = await api.editSearchItems(accountId.value, workId.value, publishSession.value, kw)
    itemList.value = r.items || []
  } catch (e) {} finally { itemsLoading.value = false }
}
function isItemPicked(row) { return selectedItems.value.some(x => x.item_id === row.item_id) }
function toggleItem(row) {
  if (isItemPicked(row)) { selectedItems.value = selectedItems.value.filter(x => x.item_id !== row.item_id); return }
  if (selectedItems.value.length >= 6) return ElMessage.warning('最多关联 6 个商品')
  selectedItems.value.push(row)
}

// ---- 提交 ----
async function doSave() {
  if (!form.title.trim()) return ElMessage.warning('请填写视频标题')
  saving.value = true
  try {
    const cov = selectedCover.value
    const r = await api.editWork(accountId.value, workId.value, {
      title: form.title, desc: form.desc, declaration: form.declaration,
      cover_url: cov ? cov.url : null,
      cover_width: cov ? cov.width : coverWidth.value,
      cover_height: cov ? cov.height : coverHeight.value,
      topics: selectedTopics.value.map(t => ({ topicId: t.topic_id, topicTitle: t.title, type: t.type })),
      items: selectedItems.value.map(it => {
        const { item_id, pic_url, commission_rate, ...rest } = it
        return { ...rest, itemId: item_id, source: it.source || 'coreitem' }
      }),
    })
    if (r.status === 'success') {
      ElMessage.success('编辑已提交，作品重新进入审核')
      setTimeout(() => back(), 800)
    } else {
      ElMessage.error(r.result_msg || '编辑失败')
    }
  } catch (err) {
    const msg = err.response?.data?.detail || err.message || '编辑失败'
    ElMessage.error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  } finally { saving.value = false }
}

onMounted(() => {
  if (!accountId.value) {
    api.listAccounts().then(accs => { if (accs.length) accountId.value = accs[0].id; accountName.value = accs[0]?.name || '' }).finally(loadEditContent)
  } else {
    api.listAccounts().then(accs => { const a = accs.find(x => x.id === accountId.value); accountName.value = a?.name || '' })
    loadEditContent()
  }
})
</script>

<style scoped>
.edit-card { max-width: 1060px; margin: 0 auto; }
.page-title { font-size: 18px; font-weight: 600; color: #303133; margin-bottom: 16px; }
.account-row { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.label { color: #606266; font-size: 14px; }
.account-name { color: #303133; font-weight: 500; }
.spacer { flex: 1; }
.main-grid { display: flex; gap: 22px; align-items: flex-start; }
.left-col { width: 280px; flex-shrink: 0; }
.right-col { flex: 1; min-width: 0; }
.cover-preview { position: relative; }
.cover-img { width: 100%; height: 373px; border-radius: 10px; display: block; }
.cover-empty { background: #f5f7fa; display: flex; align-items: center; justify-content: center; color: #c0c4cc; }
.duration { position: absolute; left: 8px; bottom: 8px; background: rgba(0,0,0,.6); color: #fff; font-size: 12px; border-radius: 3px; padding: 1px 6px; }
.sec { margin-bottom: 20px; }
.sec-title { font-size: 14px; font-weight: 600; color: #303133; margin-bottom: 10px; display: flex; align-items: center; gap: 4px; }
.req { color: #ff5000; }
.desc-input { margin-top: 4px; }
.hint { color: #909399; font-size: 12px; margin-top: 6px; }
.reco-tags { margin-top: 10px; background: #f7f8fa; border-radius: 8px; padding: 8px 12px; display: flex; gap: 12px; align-items: flex-start; }
.reco-tags .reco-label { flex-shrink: 0; color: #909399; font-size: 12px; line-height: 1.9; }
.reco-tags-list { line-height: 1.9; }
.reco-tag { color: #ff5000; cursor: pointer; margin-right: 12px; user-select: none; }
.reco-tag.on { color: #409eff; font-weight: 600; }

.cover-opts { display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-start; }
.cover-opt { cursor: pointer; text-align: center; }
.co-img { width: 76px; height: 102px; border-radius: 6px; display: block; border: 2px solid transparent; }
.cover-opt.on .co-img { border-color: #ff5000; }
.co-empty { background: #f5f7fa; display: flex; align-items: center; justify-content: center; color: #909399; font-size: 12px; }
.co-label { font-size: 12px; color: #606266; display: block; margin-top: 4px; }
.cover-add { display: flex; flex-direction: column; width: 180px; }
.co-add { border: 1px dashed #dcdfe6; border-radius: 6px; padding: 12px; color: #909399; font-size: 13px; cursor: pointer; }
.co-add:hover { border-color: #ff5000; color: #ff5000; }

.picked-topics { display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }
.picked-topic { display: flex; align-items: center; gap: 8px; background: #fff7f2; border: 1px solid #ffd6c0; border-radius: 6px; padding: 6px 10px; font-size: 13px; }
.pt-name { color: #ff5000; font-weight: 500; }
.pt-del { margin-left: auto; cursor: pointer; color: #909399; }
.pt-del:hover { color: #ff5000; }
.add-item-btn { display: inline-flex; align-items: center; gap: 6px; border: 1px dashed #dcdfe6; border-radius: 6px; padding: 8px 16px; color: #ff5000; cursor: pointer; font-size: 13px; }
.add-item-btn:hover { border-color: #ff5000; background: #fff8f5; }
.picked-items { display: flex; flex-direction: column; gap: 8px; margin-bottom: 10px; }
.picked-item { display: flex; align-items: center; gap: 10px; border: 1px solid #ebeef5; border-radius: 6px; padding: 8px 10px; }
.pi-img { width: 44px; height: 44px; border-radius: 4px; flex-shrink: 0; }
.pi-empty { background: #f5f7fa; }
.pi-info { flex: 1; min-width: 0; }
.pi-title { font-size: 13px; color: #303133; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pi-meta { font-size: 12px; color: #909399; margin-top: 2px; }
.pi-del { cursor: pointer; color: #909399; }
.pi-del:hover { color: #ff5000; }
.save-btn { background: #ff5000; border-color: #ff5000; width: 200px; }
.save-btn:hover { background: #ff6a1f; border-color: #ff6a1f; }
:deep(.picked-row) { background: #f0f9eb; }

/* 话题弹窗 */
.td-search { display: flex; gap: 8px; margin-bottom: 12px; }
.td-body { display: flex; gap: 12px; height: 430px; }
.td-tabs { width: 92px; overflow-y: auto; border-right: 1px solid #f0f0f0; flex-shrink: 0; }
.td-tab { padding: 8px 12px; font-size: 13px; color: #606266; cursor: pointer; border-radius: 6px; user-select: none; }
.td-tab:hover { background: #f5f7fa; }
.td-tab.on { color: #ff5000; background: #fff3ec; font-weight: 600; }
.td-list { flex: 1; overflow-y: auto; min-width: 0; }
.td-banner { background: #fff7f2; color: #ff5000; border-radius: 6px; padding: 8px 12px; font-size: 12px; margin-bottom: 10px; }
.td-topic { position: relative; border: 1px solid #ebeef5; border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; cursor: pointer; transition: border-color .2s; background: #fff; }
.td-topic:hover { border-color: #ff5000; }
.td-topic.on { border-color: #ff5000; background: #fff8f5; }
.tdt-head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.tdt-title { color: #ff5000; font-weight: 600; font-size: 14px; }
.tdt-badge { font-size: 10px; color: #e6a23c; border: 1px solid #f3d19e; border-radius: 3px; padding: 0 4px; background: #fdf6ec; }
.tdt-badge.cat { color: #909399; border-color: #dcdfe6; background: #f5f7fa; }
.tdt-meta { color: #909399; font-size: 12px; margin-top: 4px; }
.tdt-activity { color: #606266; font-size: 12px; margin-top: 4px; }
.tdt-act-level { display: inline-block; background: #ff5000; color: #fff; font-size: 10px; border-radius: 3px; padding: 0 4px; margin-right: 4px; }
.tdt-check { position: absolute; top: 8px; right: 10px; color: #ff5000; font-size: 18px; }
.td-more { text-align: center; padding: 6px 0 2px; }
</style>
