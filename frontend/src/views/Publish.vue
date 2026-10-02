<template>
  <div>
    <el-card class="publish-card">
      <div class="page-title">发布视频</div>

      <!-- 账号（进入发布页前已选定，只读展示；刷新按钮可重新选择） -->
      <div class="account-row">
        <span class="label">发布账号</span>
        <template v-if="currentAccount">
          <span class="account-name">{{ currentAccount.name }}（{{ currentAccount.taobao_id }}）</span>
          <el-tag :type="currentAccount.status === 'ok' ? 'success' : 'danger'" size="small">
            {{ currentAccount.status === 'ok' ? '健康' : '失效' }}
          </el-tag>
        </template>
        <span v-else class="account-empty">未选择</span>
        <el-button :icon="Refresh" circle :loading="refreshing" title="刷新并重新选择账号" @click="doRefresh" />
      </div>

      <div class="main-grid">
        <!-- 左栏：上传 / 预览 -->
        <div class="left-col">
          <!-- 上传前 -->
          <div v-if="!videoId" class="upload-box" :class="{ dragging }"
               @click="$refs.videoInput.click()"
               @dragover.prevent="dragging = true" @dragleave="dragging = false"
               @drop.prevent="onDrop">
            <el-icon :size="46" color="#c0c4cc"><UploadFilled /></el-icon>
            <div class="upload-text">点击上传视频，或将视频拖拽到此处</div>
            <el-button type="primary" class="upload-btn" :loading="uploading" @click.stop="$refs.videoInput.click()">上传视频</el-button>
            <div class="fmt-list">
              <div><el-icon><Document /></el-icon> 视频格式推荐使用mp4</div>
              <div><el-icon><Iphone /></el-icon> 视频比例推荐9:16竖版画面</div>
              <div><el-icon><Film /></el-icon> 清晰度建议1080P及以上</div>
              <div><el-icon><Clock /></el-icon> 时长30分钟以下，文件量最大1.5GB</div>
            </div>
          </div>
          <!-- 远程拉取 -->
          <div v-if="!videoId" class="remote-row">
            <el-input v-model="remoteUrl" size="small" placeholder="或粘贴视频链接拉取" @keyup.enter="doRemote" />
            <el-button size="small" type="primary" plain :loading="remoteLoading" @click="doRemote">拉取</el-button>
          </div>
          <!-- 小红书一键导入 -->
          <div v-if="!videoId" class="remote-row xhs-row">
            <el-input v-model="xhsUrl" size="small" placeholder="粘贴小红书链接，一键导入视频/封面/标题/#标签" @keyup.enter="doXhsImport" />
            <el-button size="small" type="danger" plain :loading="xhsLoading" @click="doXhsImport">导入</el-button>
          </div>

          <!-- 上传后预览 -->
          <div v-else class="preview-box">
            <video v-if="videoObjectUrl" :src="videoObjectUrl" controls preload="metadata" class="preview-video"></video>
            <div v-else class="preview-loading">视频加载中…</div>
            <el-button size="small" class="reupload" @click="resetVideo">重新上传</el-button>
          </div>
        </div>

        <!-- 右栏：表单 -->
        <div class="right-col">
          <!-- 封面 -->
          <div class="sec">
            <div class="sec-title"><span class="req">*</span> 视频封面</div>
            <div v-if="!videoId" class="cover-placeholder">等待视频上传...</div>
            <template v-else>
              <div class="cover-row">
                <div class="cover-card" :class="{ active: !selectedCover }" @click="selectedCover = ''">
                  <video v-if="videoObjectUrl" :src="videoObjectUrl" muted preload="metadata" class="cover-default"></video>
                  <div class="cover-tag">默认封面</div>
                </div>
                <div v-for="(c, i) in draftCovers" :key="i" class="cover-card" :class="{ active: selectedCover === c.url }" @click="selectedCover = c.url">
                  <el-image :src="c.url" fit="cover" class="cover-smart" />
                  <div class="cover-tag">智能封面</div>
                </div>
                <div class="cover-card add" @click="$refs.coverInput.click()">
                  <el-icon :size="22"><Plus /></el-icon>
                  <div class="cover-tag">本地上传</div>
                </div>
                <div class="cover-card add" @click="coverRemoteVisible = true">
                  <el-icon :size="22"><Link /></el-icon>
                  <div class="cover-tag">远程图片</div>
                </div>
              </div>
              <div class="hint">智能封面图：根据视频内容智能生成，点击即可应用；不选择则使用平台默认封面</div>
              <input ref="coverInput" type="file" accept="image/jpeg,image/png,image/webp" style="display:none" @change="onCoverPicked" />
            </template>
          </div>

          <!-- 描述 -->
          <div class="sec">
            <div class="sec-title">视频描述</div>
            <el-input v-model="pubForm.title" maxlength="30" show-word-limit placeholder="加个标题让内容更吸引人" />
            <el-input v-model="pubForm.desc" type="textarea" :rows="4" maxlength="1000" show-word-limit
                      class="desc-input" placeholder="展开说说，你写的文字我们都喜欢（点击下方推荐标签可填入 #话题）" />
            <div class="reco-tags" v-if="draftTags.length">
              <span class="reco-label">推荐内容标签</span>
              <span class="reco-tags-list">
                <span v-for="t in draftTags" :key="t.id || t.name" class="reco-tag" :class="{ on: isTagSelected(t) }" @click="toggleTag(t)"># {{ t.name }}</span>
                <span class="reco-tag add" @click="addCustomTag">+ 自定义</span>
              </span>
            </div>
            <div class="hint">点击推荐标签填入上方描述框，描述中以 # 开头的内容即为发布的话题标签（最多 5 个）</div>
          </div>

          <!-- 参与话题活动 -->
          <div class="sec">
            <div class="sec-title">参与话题活动</div>
            <div v-if="selectedTopics.length" class="picked-topics">
              <div v-for="(t, i) in selectedTopics" :key="'pt' + i" class="picked-topic">
                <span class="pt-name"># {{ t.title }}</span>
                <span v-if="t.activity_title" class="pt-activity">{{ t.activity_title }} {{ t.activity_delivery }}</span>
                <el-icon class="pt-del" @click="selectedTopics.splice(i, 1)"><Close /></el-icon>
              </div>
            </div>
            <div class="add-item-btn" :class="{ disabled: !draftId }" @click="openTopicDialog">
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

          <!-- 发布设置 -->
          <div class="sec">
            <div class="sec-title">发布设置</div>
            <div class="schedule-row">
              <el-switch v-model="scheduleOn" />
              <span class="schedule-label">定时发布</span>
              <el-date-picker v-model="scheduleTime" type="datetime" format="YYYY-MM-DD HH:mm"
                              :disabled="!scheduleOn" placeholder="选择发布时间" style="width:220px" />
            </div>
          </div>

          <!-- 创作者声明 -->
          <div class="sec">
            <div class="sec-title"><span class="req">*</span> 创作者声明 <el-tooltip content="按内容实际情况选择，平台会据此进行合规标注"><el-icon><QuestionFilled /></el-icon></el-tooltip></div>
            <el-radio-group v-model="pubForm.declaration">
              <el-radio v-for="d in declarations" :key="d" :value="d">{{ d }}</el-radio>
            </el-radio-group>
          </div>

          <el-button type="primary" size="large" class="publish-btn" :loading="submitting"
                     :disabled="preparing || (submitResult && submitResult.ok)" @click="doSubmit">{{ preparing ? '视频解析中…' : '立即发布' }}</el-button>
          <div v-if="submitResult" class="submit-result" :class="submitResult.ok ? 'ok' : 'fail'">
            {{ submitResult.ok ? '✅ 发布成功，正在跳转到作品管理…' : '❌ 发布失败：' + submitResult.msg }}
          </div>
        </div>
      </div>

      <input ref="videoInput" type="file" accept=".mp4,.mov,.m4v" style="display:none" @change="onVideoPicked" />
    </el-card>

    <!-- 账号选择弹窗（进入发布页的前置步骤：先选账号再发布，刷新页面重新选择） -->
    <el-dialog v-model="accountDialog" title="选择发布账号" width="520px"
               :close-on-click-modal="false" :close-on-press-escape="false" :show-close="false">
      <div class="pick-tip">发布前请先选择光合账号，页面内将锁定该账号</div>
      <div class="pick-list" v-loading="accountsLoading">
        <div v-for="a in accounts" :key="a.id" class="pick-item" :class="{ on: pubForm.account_id === a.id }" @click="pickAccount(a)">
          <div class="pi2-main">
            <div class="pi2-name">{{ a.name }}
              <el-tag size="small" :type="a.status === 'ok' ? 'success' : 'danger'" style="margin-left:6px">
                {{ a.status === 'ok' ? '健康' : '失效' }}
              </el-tag>
            </div>
            <div class="pi2-id">淘宝账号：{{ a.taobao_id || '—' }}</div>
          </div>
          <el-button type="primary" size="small" @click.stop="pickAccount(a)">选择</el-button>
        </div>
        <el-empty v-if="!accountsLoading && !accounts.length" description="暂无可用账号，请先到「账号矩阵」添加账号" :image-size="60" />
      </div>
      <template #footer>
        <el-button @click="goAccounts">去添加账号</el-button>
      </template>
    </el-dialog>

    <!-- 话题选择弹窗（仿官方） -->
    <el-dialog v-model="topicDialog" title="话题选择" width="760px">
      <div class="td-search">
        <el-input v-model="topicKeyword" placeholder="输入关键词搜索" @keyup.enter="doTopicSearch" clearable />
        <el-button type="primary" @click="doTopicSearch">搜索</el-button>
        <el-button @click="resetTopicSearch">重置</el-button>
      </div>
      <div class="td-body">
        <div class="td-tabs">
          <div v-for="t in topicTabs" :key="t.tabId" class="td-tab" :class="{ on: topicTabId === t.tabId }"
               @click="switchTopicTab(t)">{{ t.tabName }}</div>
        </div>
        <div class="td-list" v-loading="topicsLoading">
          <div class="td-banner">参与官方话题投稿，有机会获得额外流量奖励~</div>
          <div v-for="t in topicList" :key="t.topic_id" class="td-topic" :class="{ on: isTopicPicked(t) }"
               @click="toggleTopic(t)">
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
            <div class="tdt-desc" v-if="t.desc">{{ t.desc }}</div>
            <el-icon v-if="isTopicPicked(t)" class="tdt-check"><CircleCheckFilled /></el-icon>
          </div>
          <div v-if="topicHasNext" class="td-more">
            <el-button size="small" :loading="topicsLoading" @click="loadMoreTopics">加载更多</el-button>
          </div>
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
          <template #default="{ row }">
            <el-image :src="row.pic_url" fit="cover" style="width:40px;height:40px;border-radius:3px">
              <template #error><div style="width:40px;height:40px;background:#f5f7fa"></div></template>
            </el-image>
          </template>
        </el-table-column>
        <el-table-column label="商品" show-overflow-tooltip>
          <template #default="{ row }">{{ row.title }}</template>
        </el-table-column>
        <el-table-column prop="price" label="价格" width="90" />
        <el-table-column label="佣金" width="80">
          <template #default="{ row }"><el-tag type="danger" size="small">{{ row.commission_rate }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button size="small" :type="isItemPicked(row) ? 'success' : 'default'" @click.stop="toggleItem(row)">
              {{ isItemPicked(row) ? '已选' : '选择' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="hint" style="margin-top:8px">已选 {{ selectedItems.length }}/6 · 数据来源：视频内容推荐 + 高佣选品库</div>
      <template #footer>
        <el-button @click="itemDialog = false">完成</el-button>
      </template>
    </el-dialog>

    <!-- 远程封面 -->
    <el-dialog v-model="coverRemoteVisible" title="远程图片封面" width="460px">
      <el-input v-model="remoteCoverUrl" placeholder="https://.../*.jpg" />
      <template #footer>
        <el-button @click="coverRemoteVisible = false">取消</el-button>
        <el-button type="primary" :loading="coverUploading" @click="uploadRemoteCover">上传应用</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Document, Iphone, Film, Clock, Plus, Link, Close, QuestionFilled, Refresh, CircleCheckFilled } from '@element-plus/icons-vue'
import api from '../api'

const router = useRouter()
const declarations = ['内容无需标注', '含AI生成内容', '含虚构演绎内容', '内容为转载', '个人观点，仅供参考', '内容含营销信息']

const accounts = ref([])
const videoInput = ref(null)
const coverInput = ref(null)
const remoteUrl = ref('')
const remoteLoading = ref(false)
const videoFile = ref(null)
const videoId = ref(null)
const videoObjectUrl = ref('')
const uploading = ref(false)
const dragging = ref(false)

const pubForm = reactive({ account_id: null, title: '', desc: '', declaration: '内容无需标注' })

const preparing = ref(false)
const submitting = ref(false)
const draftId = ref(null)
const submitResult = ref(null)

const draftCovers = ref([])
const selectedCover = ref('')
const coverUploading = ref(false)
const remoteCoverUrl = ref('')
const coverRemoteVisible = ref(false)
const draftTags = ref([])
const itemKeyword = ref('')
const itemList = ref([])
const selectedItems = ref([])
const itemsLoading = ref(false)
const itemDialog = ref(false)

const scheduleOn = ref(false)
const scheduleTime = ref(null)

// 内容标签通过描述框内 #xxx 文本提交（光合从文本识别），不走 topics 数组（topics 为官方活动话题，上限极低）

function fmtSize(n) { return n >= 1 << 20 ? (n / (1 << 20)).toFixed(1) + ' MB' : (n / 1024).toFixed(0) + ' KB' }
function baseName(p) { return (p || '').split('/').pop().split('?')[0].replace(/\.(mp4|mov|m4v)$/i, '') }

// ---- 发布账号（进入发布页先选账号，页面内锁定；刷新页面重新选择） ----
const accountDialog = ref(false)
const accountsLoading = ref(false)

const currentAccount = computed(() => accounts.value.find(a => a.id === pubForm.account_id) || null)

async function loadAccounts() {
  accountsLoading.value = true
  try {
    accounts.value = await api.listAccounts()
  } catch (e) {} finally {
    accountsLoading.value = false
  }
}

function pickAccount(a) {
  pubForm.account_id = a.id
  accountDialog.value = false
}

function goAccounts() {
  router.push('/accounts')
}

const refreshing = ref(false)
async function doRefresh() {
  refreshing.value = true
  try {
    await loadAccounts()
    // 刷新后重新弹出账号选择（等效于刷新页面重新选择账号）
    accountDialog.value = true
  } finally {
    refreshing.value = false
  }
}

// ---- 视频上传（本地 / 拖拽 / 远程） ----
async function onVideoPicked(e) {
  const file = e.target.files[0]
  if (!file) return
  e.target.value = ''
  await uploadAndPrepare({ name: file.name, size: file.size }, () => api.uploadVideoFile(file, ''))
}
function onDrop(e) {
  dragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (!file) return
  if (!/\.(mp4|mov|m4v)$/i.test(file.name)) return ElMessage.warning('仅支持 mp4/mov/m4v')
  uploadAndPrepare({ name: file.name, size: file.size }, () => api.uploadVideoFile(file, ''))
}
async function doRemote() {
  if (!remoteUrl.value) return ElMessage.warning('请输入视频链接')
  remoteLoading.value = true
  try {
    const r = await api.addRemoteVideo(remoteUrl.value, '')
    await afterVideoReady({ name: r.filename, size: r.size }, r.id)
  } catch (err) {} finally { remoteLoading.value = false }
}

// ---- 小红书一键导入：视频下载解析 + 封面 + 标题 + 前4个#标签 ----
const xhsUrl = ref('')
const xhsLoading = ref(false)

async function doXhsImport() {
  if (!xhsUrl.value.trim()) return ElMessage.warning('请粘贴小红书笔记链接')
  if (preparing.value) return ElMessage.warning('正在解析上一个视频，请稍候再导入')
  if (!pubForm.account_id) {
    accountDialog.value = true
    return ElMessage.warning('请先选择发布账号')
  }
  xhsLoading.value = true
  try {
    const r = await api.importXhs(xhsUrl.value.trim())
    // 标题：去掉 #标签 后的干净标题（30 字内）
    const clean = (r.title || '').replace(/#[^#\s]+/g, '').trim()
    pubForm.title = clean.slice(0, 30)
    // 前 4 个 #标签 填入描述框
    if (r.tags && r.tags.length) {
      pubForm.desc = r.tags.slice(0, 4).map(t => '#' + t).join(' ')
    }
    ElMessage.success('小红书视频已导入，开始解析…')
    // 上传视频 + 自动 prepare（跳过智能封面，改用小红书封面）
    await afterVideoReady({ name: r.filename, size: r.size }, r.id, true)
    // prepare 完成后上传小红书封面
    if (r.cover_url) {
      try {
        const c = await api.uploadCoverUrl(pubForm.account_id, r.cover_url)
        selectedCover.value = c.url
        ElMessage.success('小红书封面已上传应用')
      } catch (e) { ElMessage.warning('封面获取失败，将使用平台默认封面') }
    }
    ElMessage.success('小红书一键导入完成')
  } catch (err) {
    // 错误已由 api 拦截器统一提示
  } finally { xhsLoading.value = false }
}
async function uploadAndPrepare(fileInfo, uploadFn) {
  uploading.value = true
  try {
    const r = await uploadFn()
    await afterVideoReady(fileInfo, r.id)
  } catch (err) {} finally { uploading.value = false }
}
async function afterVideoReady(fileInfo, vid, skipCovers = false) {
  videoFile.value = fileInfo
  videoId.value = vid
  if (!pubForm.title) pubForm.title = baseName(fileInfo.name).slice(0, 30)
  ElMessage.success('视频已上传，开始解析…')
  // 加载视频本地流（预览用）
  try {
    const resp = await fetch(`/api/videos/${vid}/file`, { headers: { Authorization: `Bearer ${localStorage.getItem('gh_token')}` } })
    if (resp.ok) videoObjectUrl.value = URL.createObjectURL(await resp.blob())
  } catch (err) {}
  await autoPrepare(vid, skipCovers)
}

async function autoPrepare(vid, skipCovers = false) {
  if (!pubForm.account_id) return ElMessage.warning('请选择发布账号')
  preparing.value = true
  try {
    const r = await api.preparePublish({
      account_id: pubForm.account_id, video_id: vid,
      title: pubForm.title, desc: pubForm.desc, declaration: pubForm.declaration,
      skip_covers: skipCovers,
    })
    draftId.value = r.id
    const start = Date.now()
    while (Date.now() - start < 240000) {
      await new Promise(res => setTimeout(res, 2500))
      const d = await api.getDraft(draftId.value)
      if (d.status === 'prepared') {
        draftCovers.value = d.covers || []
        draftTags.value = d.tags || []
        // 官方行为：默认勾选第一张智能封面
        if (draftCovers.value.length) selectedCover.value = draftCovers.value[0].url
        loadItems()
        ElMessage.success('解析完成')
        return
      }
      if (d.status === 'failed') { ElMessage.error(`解析失败: ${d.error_msg}`); return }
    }
    ElMessage.error('解析超时')
  } catch (err) {} finally { preparing.value = false }
}

function resetVideo() {
  videoId.value = null
  videoObjectUrl.value = ''
  videoFile.value = null
  remoteUrl.value = ''
  xhsUrl.value = ''
  draftId.value = null
  draftCovers.value = []
  draftTags.value = []
  selectedCover.value = ''
  itemList.value = []
  selectedItems.value = []
  itemKeyword.value = ''
  selectedTopics.value = []
  topicList.value = []
  topicKeyword.value = ''
  submitResult.value = null
}

// ---- 封面 ----
async function onCoverPicked(e) {
  const file = e.target.files[0]
  if (!file) return
  coverUploading.value = true
  try {
    const r = await api.uploadCoverFile(pubForm.account_id, file)
    selectedCover.value = r.url
    ElMessage.success('自定义封面上传成功')
  } catch (err) {} finally { coverUploading.value = false; e.target.value = '' }
}
async function uploadRemoteCover() {
  if (!remoteCoverUrl.value) return ElMessage.warning('请输入图片 URL')
  coverUploading.value = true
  try {
    const r = await api.uploadCoverUrl(pubForm.account_id, remoteCoverUrl.value)
    selectedCover.value = r.url
    coverRemoteVisible.value = false
    ElMessage.success('远程封面上传成功')
  } catch (err) {} finally { coverUploading.value = false }
}

// ---- 标签（官方交互：点击推荐标签 → 填入描述框，框内 #xxx 即提交的话题） ----
function escapeReg(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') }
function isTagSelected(t) { return pubForm.desc.includes(`#${t.name}`) }
function toggleTag(t) {
  const tag = `#${t.name}`
  if (pubForm.desc.includes(tag)) {
    // 从描述框移除该标签
    pubForm.desc = pubForm.desc.replace(new RegExp(`\\s*${escapeReg(tag)}`, 'g'), '').replace(/\s{2,}/g, ' ').trim()
  } else {
    pubForm.desc = (pubForm.desc.trim() ? pubForm.desc.trimEnd() + ' ' : '') + tag
  }
}
function addCustomTag(t) {
  if (t && t.name) { toggleTag(t); return }
  ElMessageBox.prompt('输入自定义话题名（不含#）', '自定义标签', { inputValue: '' })
    .then(({ value }) => {
      const name = (value || '').trim().replace(/^#/, '')
      if (name) toggleTag({ name })
    }).catch(() => {})
}

// ---- 商品（官方同款：推荐列表 + 平台优选服务端搜索 source=coreitem） ----
function isItemPicked(row) { return selectedItems.value.some(x => x.item_id === row.item_id) }
function toggleItem(row) {
  if (isItemPicked(row)) selectedItems.value = selectedItems.value.filter(x => x.item_id !== row.item_id)
  else {
    if (selectedItems.value.length >= 6) return ElMessage.warning('最多关联 6 个商品')
    selectedItems.value.push(row)
  }
}
async function loadItems() {
  if (!draftId.value) return
  itemsLoading.value = true
  try {
    const r = await api.draftItems(draftId.value, '', '', 50)
    itemList.value = r.items
    if (itemKeyword.value.trim()) await searchItems()
  } catch (err) {} finally { itemsLoading.value = false }
}
function openItemDialog() {
  itemDialog.value = true
  if (!itemList.value.length) loadItems()
}
async function searchItems() {
  const kw = itemKeyword.value.trim()
  if (!kw) { await loadItems(); return }
  // 官方「平台优选」服务端搜索（支持 itemId 精确搜与标题关键词）
  itemsLoading.value = true
  try {
    const r = await api.searchDraftItems(draftId.value, kw)
    itemList.value = r.items
    if (r.items.length) {
      ElMessage.success(`平台优选搜到 ${r.items.length} 个商品`)
    } else {
      // 平台优选未命中 → 回退搜高佣选品库
      let pool = []
      let cursor = '1'
      for (let i = 0; i < 3; i++) {
        const c = await api.commission(pubForm.account_id, cursor, 50)
        pool = pool.concat(c.items || [])
        if (!c.cursor || c.cursor === cursor) break
        cursor = c.cursor
      }
      const kwl = kw.toLowerCase()
      const hc = pool
        .filter(it => String(it.item_id) === kw || (it.title || '').toLowerCase().includes(kwl))
        .map(it => ({ item_id: String(it.item_id), title: it.title, price: it.price,
                      commission_rate: it.commission_rate, pic_url: it.pic_url || '',
                      source: 'coreitem' }))
      itemList.value = hc
      if (hc.length) ElMessage.success(`在选品库中找到 ${hc.length} 个商品`)
      else ElMessage.warning('平台优选与选品库中均未找到该商品')
    }
  } catch (err) {} finally { itemsLoading.value = false }
}

// ---- 参与话题活动（官方征稿话题） ----
const topicDialog = ref(false)
const topicTabs = ref([])
const topicTabId = ref('1')
const topicList = ref([])
const topicCursor = ref('1')
const topicHasNext = ref(false)
const topicsLoading = ref(false)
const topicKeyword = ref('')
const topicSearching = ref(false)
const selectedTopics = ref([])

function openTopicDialog() {
  if (!draftId.value) return ElMessage.warning('请先上传解析视频')
  topicDialog.value = true
  if (!topicTabs.value.length) loadTopicList('1', true)
}
async function loadTopicList(tabId, reset) {
  topicsLoading.value = true
  try {
    const r = await api.draftTopics(draftId.value, tabId, reset ? '1' : topicCursor.value)
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
    const r = await api.draftTopicsSearch(draftId.value, kw, '1')
    topicList.value = r.topics || []
    topicCursor.value = r.cursor || ''
    topicHasNext.value = !!r.has_next
  } catch (e) {} finally { topicsLoading.value = false }
}
function resetTopicSearch() {
  topicKeyword.value = ''
  topicSearching.value = false
  loadTopicList(topicTabId.value, true)
}
async function loadMoreTopics() {
  if (topicSearching.value) {
    topicsLoading.value = true
    try {
      const r = await api.draftTopicsSearch(draftId.value, topicKeyword.value.trim(), topicCursor.value)
      topicList.value = topicList.value.concat(r.topics || [])
      topicCursor.value = r.cursor || ''
      topicHasNext.value = !!r.has_next
    } catch (e) {} finally { topicsLoading.value = false }
  } else {
    loadTopicList(topicTabId.value, false)
  }
}
function isTopicPicked(t) { return selectedTopics.value.some(x => x.topic_id === t.topic_id) }
function toggleTopic(t) {
  if (isTopicPicked(t)) {
    selectedTopics.value = selectedTopics.value.filter(x => x.topic_id !== t.topic_id)
    return
  }
  if (selectedTopics.value.length >= 5) return ElMessage.warning('最多参与 5 个话题')
  const act = (t.activities && t.activities[0]) || {}
  selectedTopics.value.push({ ...t, activity_title: act.title || '', activity_level: act.level || '', activity_delivery: act.delivery || '' })
}

// ---- 提交（立即 / 定时），成功后跳转作品管理 ----
async function doSubmit() {
  if (!pubForm.account_id) return ElMessage.warning('请选择发布账号')
  if (!videoId.value) return ElMessage.warning('请先上传视频')
  if (preparing.value) return ElMessage.warning('视频解析中，请稍候再发布')
  if (!draftId.value) return ElMessage.warning('视频尚未解析完成，请稍候再发布')
  if (!pubForm.title.trim()) return ElMessage.warning('请填写视频标题')
  let schedule_at = null
  if (scheduleOn.value) {
    if (!scheduleTime.value) return ElMessage.warning('请选择定时发布时间')
    const d = scheduleTime.value
    const pad = n => String(n).padStart(2, '0')
    schedule_at = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
  }
  submitting.value = true
  try {
    const r = await api.submitPublish({
      draft_id: draftId.value,
      title: pubForm.title, desc: pubForm.desc, declaration: pubForm.declaration,
      cover_url: selectedCover.value || null,
      topics: selectedTopics.value.map(t => ({ topicId: t.topic_id, topicTitle: t.title, type: t.type })),
      items: selectedItems.value.map(it => {
        const { item_id, pic_url, commission_rate, ...rest } = it
        return { ...rest, itemId: item_id, source: it.source || 'coreitem' }
      }),
      schedule_at,
    })
    if (r.status === 'success') {
      submitResult.value = { ok: true, msg: '作品已发布' }
      ElMessage.success('发布成功，即将跳转到作品管理')
    } else if (r.status === 'scheduled') {
      submitResult.value = { ok: true, msg: r.result_msg }
      ElMessage.success(r.result_msg)
    } else {
      submitResult.value = { ok: false, msg: r.result_msg }
      return
    }
    // 成功后保持按钮禁用，防重复提交；短延时后跳转
    setTimeout(() => router.push({ path: '/works', query: { sync: '1', account_id: pubForm.account_id } }), 600)
  } catch (err) {
    const msg = err.response?.data?.detail || err.message || '提交失败'
    submitResult.value = { ok: false, msg: typeof msg === 'string' ? msg : JSON.stringify(msg) }
  } finally { submitting.value = false }
}

onMounted(async () => {
  await loadAccounts()
  // 进入发布页必须先选择账号（刷新页面后重新弹窗选择）
  if (!pubForm.account_id) accountDialog.value = true
})
</script>

<style scoped>
.publish-card { max-width: 1060px; margin: 0 auto; }
.page-title { font-size: 18px; font-weight: 600; color: #303133; margin-bottom: 16px; }
.account-row { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.label { color: #606266; font-size: 14px; }
.account-name { color: #303133; font-weight: 600; font-size: 14px; }
.account-empty { color: #c0c4cc; font-size: 13px; }

/* 账号选择弹窗 */
.pick-tip { color: #909399; font-size: 13px; margin-bottom: 12px; }
.pick-list { display: flex; flex-direction: column; gap: 8px; max-height: 380px; overflow-y: auto; }
.pick-item {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  border: 1px solid #ebeef5; border-radius: 8px; padding: 10px 14px; cursor: pointer;
  transition: border-color .2s, background .2s;
}
.pick-item:hover { border-color: #ff5000; background: #fff8f5; }
.pick-item.on { border-color: #ff5000; background: #fff8f5; }
.pi2-main { min-width: 0; flex: 1; }
.pi2-name { color: #303133; font-size: 14px; font-weight: 600; }
.pi2-id { color: #909399; font-size: 12px; margin-top: 4px; }
.main-grid { display: flex; gap: 22px; align-items: flex-start; }
.left-col { width: 280px; flex-shrink: 0; }
.right-col { flex: 1; min-width: 0; }

.upload-box { border: 1.5px dashed #dcdfe6; border-radius: 10px; padding: 34px 18px 22px; text-align: center; cursor: pointer; transition: border-color .2s; background: #fafafa; }
.upload-box:hover, .upload-box.dragging { border-color: #ff5000; }
.upload-text { color: #909399; font-size: 13px; margin: 10px 0 14px; }
.upload-btn { background: #ff5000; border-color: #ff5000; }
.fmt-list { margin-top: 22px; text-align: left; color: #909399; font-size: 12px; display: grid; gap: 8px; }
.fmt-list div { display: flex; align-items: center; gap: 6px; }
.remote-row { display: flex; gap: 8px; margin-top: 12px; }
.xhs-row :deep(.el-input__wrapper) { box-shadow: 0 0 0 1px rgba(255, 46, 77, .4) inset; }
.xhs-row :deep(.el-input__wrapper.is-focus) { box-shadow: 0 0 0 1px #ff2e4d inset; }

.preview-box { position: relative; text-align: center; }
.preview-video { width: 250px; max-height: 460px; border-radius: 14px; background: #000; }
.preview-loading { width: 250px; height: 440px; border-radius: 14px; background: #f5f7fa; line-height: 440px; color: #909399; margin: 0 auto; }
.reupload { margin-top: 12px; }

.sec { margin-bottom: 20px; }
.sec-title { font-size: 14px; font-weight: 600; color: #303133; margin-bottom: 10px; display: flex; align-items: center; gap: 4px; }
.req { color: #f56c6c; }
.cover-placeholder { height: 120px; background: #f5f7fa; border-radius: 6px; line-height: 120px; text-align: center; color: #c0c4cc; font-size: 13px; width: 320px; }
.cover-row { display: flex; gap: 10px; flex-wrap: wrap; }
.cover-card { position: relative; width: 88px; height: 118px; border-radius: 6px; overflow: hidden; cursor: pointer; border: 2px solid transparent; background: #f5f7fa; }
.cover-card.active { border-color: #ff5000; }
.cover-card.add { display: flex; flex-direction: column; align-items: center; justify-content: center; color: #909399; gap: 4px; }
.cover-default { width: 100%; height: 100%; object-fit: cover; }
.cover-smart { width: 100%; height: 100%; }
.cover-tag { position: absolute; bottom: 0; left: 0; right: 0; background: rgba(0,0,0,.45); color: #fff; font-size: 11px; text-align: center; padding: 2px 0; }
.desc-input { margin-top: 4px; }
.tagline { margin-top: 8px; }

.reco-tags { margin-top: 10px; background: #f7f8fa; border-radius: 8px; padding: 8px 12px; display: flex; gap: 12px; align-items: flex-start; }
.reco-tags .reco-label { flex-shrink: 0; color: #909399; font-size: 12px; line-height: 1.9; }
.reco-tags-list { line-height: 1.9; }
.reco-tag { color: #606266; cursor: pointer; margin-right: 12px; user-select: none; font-size: 13px; }
.reco-tag:hover { color: #ff5000; }
.reco-tag.on { color: #409eff; font-weight: 600; }
.reco-tag.add { color: #909399; border: 1px dashed #dcdfe6; border-radius: 4px; padding: 1px 8px; }

.picked-items { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 10px; }
.picked-item { display: flex; align-items: center; gap: 8px; border: 1px solid #ebeef5; border-radius: 6px; padding: 6px 8px; position: relative; }
.pi-img { width: 40px; height: 40px; border-radius: 4px; flex-shrink: 0; }
.pi-empty { background: #f5f7fa; }
.pi-info { min-width: 0; flex: 1; }
.pi-title { font-size: 12px; color: #303133; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pi-meta { font-size: 11px; color: #909399; margin-top: 2px; }
.pi-del { position: absolute; top: 4px; right: 4px; color: #c0c4cc; cursor: pointer; }
.pi-del:hover { color: #f56c6c; }
.add-item-btn { width: 96px; height: 72px; border: 1.5px dashed #dcdfe6; border-radius: 8px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; color: #909399; font-size: 12px; cursor: pointer; background: #fafafa; }
.add-item-btn:hover { border-color: #ff5000; color: #ff5000; }

.schedule-row { display: flex; align-items: center; gap: 10px; }
.schedule-label { color: #606266; font-size: 14px; }
.publish-btn { background: #ff5000; border-color: #ff5000; margin-top: 6px; padding: 0 42px; }
.publish-btn:hover { background: #ff6a1f; border-color: #ff6a1f; }
.submit-result { margin-top: 12px; padding: 12px 16px; border-radius: 6px; font-size: 14px; }
.submit-result.ok { background: #f0f9eb; color: #67c23a; }
.submit-result.fail { background: #fef0f0; color: #f56c6c; }
.hint { color: #909399; font-size: 12px; margin-top: 6px; }

:deep(.picked-row) { background: #f0f9eb; }

/* 参与话题活动 */
.picked-topics { display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }
.picked-topic { display: flex; align-items: center; gap: 8px; background: #fff7f2; border: 1px solid #ffd6c0; border-radius: 6px; padding: 6px 10px; font-size: 13px; }
.pt-name { color: #ff5000; font-weight: 500; }
.pt-activity { color: #909399; font-size: 12px; }
.pt-del { margin-left: auto; cursor: pointer; color: #909399; }
.pt-del:hover { color: #ff5000; }

/* 话题选择弹窗 */
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
.tdt-desc { color: #909399; font-size: 12px; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tdt-check { position: absolute; top: 8px; right: 10px; color: #ff5000; font-size: 18px; }
.td-more { text-align: center; padding: 6px 0 2px; }
</style>
