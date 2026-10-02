<template>
  <div>
    <el-card>
      <div class="toolbar">
        <span>已绑定 {{ accounts.length }} 个光合账号</span>
        <span class="spacer"></span>
        <el-button type="primary" @click="openLogin">扫码 / 验证码登录</el-button>
        <el-button @click="dialog = true">Cookie 导入</el-button>
      </div>
      <el-table :data="accounts" style="margin-top:12px">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="名称" width="180">
          <template #default="{ row }">
            <span>{{ row.name }}</span>
            <el-tag size="small" :type="row.source === 'profile' ? 'primary' : 'info'" style="margin-left:6px">{{ row.source === 'profile' ? '本机' : '手动' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="淘宝账号" width="180">
          <template #default="{ row }">
            <span>{{ row.taobao_id }}</span>
            <el-tag v-if="duplicateIds.has(row.taobao_id)" type="warning" size="small" style="margin-left:6px">重复</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ok' ? 'success' : 'danger'">{{ row.status === 'ok' ? '健康' : '失效' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" />
        <el-table-column label="代理" width="170">
          <template #default="{ row }">
            <el-tag v-if="row.proxy" type="warning" size="small" effect="plain" style="max-width:150px;overflow:hidden;text-overflow:ellipsis">{{ row.proxy }}</el-tag>
            <span v-else style="color:#c0c4cc">直连</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="380">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" @click="check(row)">体检</el-button>
            <el-button size="small" type="primary" @click="refresh(row)">刷新登录态</el-button>
            <el-button v-if="row.proxy" size="small" type="warning" plain :loading="testingId === row.id" @click="testProxy(row)">测代理</el-button>
            <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="loginDialog" title="添加光合账号" width="440px" :close-on-click-modal="false" @closed="stopPolling">
      <el-tabs v-model="loginMode" @tab-change="switchLoginMode">
        <!-- 扫码登录 -->
        <el-tab-pane label="扫码登录" name="scan">
          <div class="login-scan" v-loading="loginState === 'starting'">
            <template v-if="loginState === 'success'">
              <div class="login-success">
                <div class="ls-icon">✓</div>
                <div>登录成功</div>
                <div class="ls-id">淘宝账号：{{ loginTaobaoId || '—' }}</div>
                <el-input v-model="importName" placeholder="账号名称（可选）" style="margin:12px 0" />
                <el-button type="primary" :loading="importing" @click="doImport">导入账号</el-button>
              </div>
            </template>
            <template v-else-if="loginSid">
              <div class="login-qr">
                <img v-if="loginScreenshot" :src="'data:image/png;base64,' + loginScreenshot" class="qr-img" />
                <div v-else class="qr-img qr-empty">二维码加载中…</div>
              </div>
              <div class="login-tip">打开淘宝 App，点击左上角「扫一扫」扫码登录</div>
              <div v-if="loginError" class="login-error">{{ loginError }}</div>
              <el-button link type="primary" @click="refreshLogin">刷新二维码</el-button>
            </template>
            <template v-else>
              <div class="qr-gen">
                <div class="qr-gen-tip">点击下方按钮，生成登录二维码</div>
                <el-button type="primary" :loading="loginState === 'starting'" @click="startLogin('scan')">生成二维码</el-button>
              </div>
            </template>
          </div>
        </el-tab-pane>

        <!-- 短信登录 -->
        <el-tab-pane label="短信登录" name="sms">
          <template v-if="loginState === 'success'">
            <div class="login-success">
              <div class="ls-icon">✓</div>
              <div>登录成功</div>
              <div class="ls-id">淘宝账号：{{ loginTaobaoId || '—' }}</div>
              <el-input v-model="importName" placeholder="账号名称（可选）" style="margin:12px 0" />
              <el-button type="primary" :loading="importing" @click="doImport">导入账号</el-button>
            </div>
          </template>
          <el-form v-else label-width="90px" style="margin-top:8px">
            <el-form-item label="手机号">
              <el-input v-model="sms.phone" placeholder="请输入手机号" />
            </el-form-item>
            <el-form-item label="短信验证码">
              <div class="checkcode-row">
                <el-input v-model="sms.sms_code" placeholder="短信验证码" />
                <el-button :disabled="smsCountdown > 0" @click="doSmsSend">
                  {{ smsCountdown > 0 ? smsCountdown + 's 后重发' : '获取验证码' }}
                </el-button>
              </div>
            </el-form-item>
            <el-form-item v-if="loginShotType === 'checkcode' && loginScreenshot" label="图片验证码">
              <div class="checkcode-row">
                <img :src="'data:image/png;base64,' + loginScreenshot" class="cc-img" title="看不清？点击换一张" @click="refreshCheckcode" />
                <el-input v-model="sms.checkcode" placeholder="图片验证码" />
              </div>
            </el-form-item>
            <div v-if="loginShotType === 'page' && loginScreenshot" class="page-shot">
              <img :src="'data:image/png;base64,' + loginScreenshot" />
              <div class="page-shot-tip">当前登录页状态（如出现滑块/异常，建议改用扫码登录）</div>
            </div>
            <div v-if="loginError" class="login-error" style="margin:0 0 8px 90px">{{ loginError }}</div>
            <el-form-item>
              <el-button type="primary" @click="doSmsLogin">登录</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>

    <el-dialog v-model="dialog" title="Cookie 导入" width="560px">
      <el-form label-width="90px">
        <el-form-item label="账号名称"><el-input v-model="form.name" placeholder="如：主号 / 小号A" /></el-form-item>
        <el-form-item label="Cookie">
          <el-input v-model="form.cookie" type="textarea" :rows="6" placeholder="粘贴浏览器里光合平台的完整 Cookie（需含 _m_h5_tk）" />
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="save">保存并体检</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editDialog" title="编辑账号" width="480px">
      <el-form label-width="90px">
        <el-form-item label="账号名称"><el-input v-model="editForm.name" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="editForm.remark" /></el-form-item>
        <el-form-item label="代理 IP">
          <el-input v-model="editForm.proxy" placeholder="如 http://ip:port 或 socks5://ip:port，留空直连" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialog = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

const accounts = ref([])
const testingId = ref(null)
const dialog = ref(false)
const form = reactive({ name: '', cookie: '', remark: '' })
const editDialog = ref(false)
const editForm = reactive({ id: null, name: '', remark: '', proxy: '' })

// ---- 扫码/密码/短信登录 ----
const loginDialog = ref(false)
const loginMode = ref('scan')
const loginSid = ref('')
const loginState = ref('starting')
const loginScreenshot = ref('')
const loginShotType = ref('')   // qrcode / checkcode / page
const loginError = ref('')
const loginTaobaoId = ref('')
const importName = ref('')
const importing = ref(false)
const smsCountdown = ref(0)
let smsTimer = null
const sms = reactive({ phone: '', sms_code: '', checkcode: '' })
let pollTimer = null

// 出现超过一次的 taobao_id（提示重复账号）
const duplicateIds = computed(() => {
  const cnt = {}
  accounts.value.forEach(a => { cnt[a.taobao_id] = (cnt[a.taobao_id] || 0) + 1 })
  return new Set(Object.keys(cnt).filter(k => cnt[k] > 1))
})

async function load() { accounts.value = await api.listAccounts() }

async function save() {
  if (!form.name || !form.cookie) return ElMessage.warning('请填写名称和 Cookie')
  await api.createAccount(form)
  ElMessage.success('添加成功')
  dialog.value = false
  Object.assign(form, { name: '', cookie: '', remark: '' })
  load()
}

async function check(row) {
  const r = await api.checkAccount(row.id)
  ElMessage.info(r.message)
  load()
}

async function refresh(row) {
  const r = await api.refreshAccount(row.id)
  ElMessage.success(r.message)
  load()
}

async function testProxy(row) {
  testingId.value = row.id
  try {
    const r = await api.testProxy(row.id)
    const ip = r.exit_ip ? `出口IP: ${r.exit_ip}` : ''
    const tb = r.taobao_ok ? '光合访问正常' : `光合访问: ${r.taobao_msg || '失败'}`
    if (r.ok) {
      ElMessage.success(`${r.msg}｜${ip}｜${tb}`)
    } else {
      ElMessage.warning(`${r.msg}｜${ip || r.ip_test || ''}`)
    }
  } catch (e) {
    // 错误已由拦截器提示
  } finally {
    testingId.value = null
  }
}

function openEdit(row) {
  editForm.id = row.id
  editForm.name = row.name
  editForm.remark = row.remark || ''
  editForm.proxy = row.proxy || ''
  editDialog.value = true
}

async function saveEdit() {
  if (!editForm.name) return ElMessage.warning('请填写名称')
  await api.updateAccount(editForm.id, { name: editForm.name, remark: editForm.remark, proxy: editForm.proxy })
  ElMessage.success('已保存')
  editDialog.value = false
  load()
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除账号「${row.name}」？`, '提示', { type: 'warning' })
  await api.deleteAccount(row.id)
  ElMessage.success('已删除')
  load()
}

// ---- 登录 ----
function resetLogin() {
  stopPolling()
  loginSid.value = ''
  loginState.value = ''
  loginScreenshot.value = ''
  loginShotType.value = ''
  loginError.value = ''
  loginTaobaoId.value = ''
}
function openLogin() {
  loginDialog.value = true
  loginMode.value = 'scan'
  resetLogin()   // 不自动生成二维码，等用户点「生成二维码」
}
async function startLogin(mode) {
  stopPolling()
  loginState.value = 'starting'
  loginScreenshot.value = ''
  loginShotType.value = ''
  loginError.value = ''
  loginTaobaoId.value = ''
  try {
    const r = await api.loginStart(mode)
    loginSid.value = r.sid
    loginState.value = r.state
    loginScreenshot.value = r.screenshot || ''
    loginShotType.value = r.shot_type || ''
    if (r.state !== 'success') pollLogin()
  } catch (e) { loginError.value = '启动登录失败' }
}
function switchLoginMode(mode) {
  // 注意：el-tabs 触发 tab-change 时 v-model 已更新为新 tab，不能再用 loginMode 比较（恒等会跳过）。
  // 扫码 tab 不自动生成二维码（等用户点按钮）；短信 tab 自动开会话（表单需要页面就绪）。
  if (mode === 'scan') {
    resetLogin()
  } else {
    startLogin(mode)
  }
}
function pollLogin(holdNeedCheckcode = false) {
  stopPolling()
  let cnt = 0
  let hold = holdNeedCheckcode   // 提交类动作后：见到旧 need_checkcode 不停轮，等真正结果
  pollTimer = setInterval(async () => {
    if (!loginSid.value) { stopPolling(); return }
    if (++cnt > 100) { stopPolling(); return }   // 最多轮询 5 分钟
    try {
      const r = await api.loginStatus(loginSid.value)
      loginState.value = r.state
      if (r.screenshot) {
        loginScreenshot.value = r.screenshot
        loginShotType.value = r.shot_type || ''
      }
      loginError.value = r.error || ''
      loginTaobaoId.value = r.taobao_id || ''
      if (r.state === 'success' && !importName.value) importName.value = r.taobao_id || ''
      if (hold && r.state !== 'need_checkcode') hold = false
      const done = r.state === 'success' || r.state === 'error' ||
                   (!hold && r.state === 'need_checkcode' && loginMode.value !== 'scan')
      if (done) stopPolling()
    } catch (e) {}
  }, 3000)
}
function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}
async function refreshLogin() {
  // 扫码：让后端重载登录页重新截二维码
  if (!loginSid.value) return
  try { await api.loginRefresh(loginSid.value) } catch (e) {}
}
async function refreshCheckcode() {
  // 密码/短信：点击验证码图 = 换一张
  if (!loginSid.value) return
  try {
    const r = await api.loginRefreshCode(loginSid.value)
    if (r.screenshot) {
      loginScreenshot.value = r.screenshot
      loginShotType.value = r.shot_type || ''
    }
  } catch (e) {}
}
function startSmsCountdown() {
  smsCountdown.value = 60
  if (smsTimer) clearInterval(smsTimer)
  smsTimer = setInterval(() => {
    smsCountdown.value--
    if (smsCountdown.value <= 0) { clearInterval(smsTimer); smsTimer = null }
  }, 1000)
}

async function doSmsSend() {
  if (!sms.phone) return ElMessage.warning('请填写手机号')
  loginError.value = ''
  startSmsCountdown()
  await api.loginSubmit(loginSid.value, { action: 'send_code', phone: sms.phone, checkcode: sms.checkcode })
  pollLogin()
}
async function doSmsLogin() {
  if (!sms.phone || !sms.sms_code) return ElMessage.warning('请填写手机号和短信验证码')
  loginError.value = ''
  loginState.value = 'starting'
  await api.loginSubmit(loginSid.value, { action: 'login', phone: sms.phone, sms_code: sms.sms_code, checkcode: sms.checkcode })
  pollLogin(true)   // 跳过旧 need_checkcode 态，等登录真正结果
}
async function doImport() {
  importing.value = true
  try {
    await api.loginImport(loginSid.value, { name: importName.value || loginTaobaoId.value || '扫码账号' })
    ElMessage.success('账号已导入')
    loginDialog.value = false
    stopPolling()
    load()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '导入失败') } finally { importing.value = false }
}

onMounted(load)
</script>

<style scoped>
.toolbar { display: flex; align-items: center; }
.spacer { flex: 1; }

.login-scan { text-align: center; }
.qr-gen { padding: 30px 0 14px; }
.qr-gen-tip { color: #606266; font-size: 13px; margin-bottom: 16px; }
.login-qr { display: flex; justify-content: center; margin: 8px 0; }
.qr-img { width: 220px; height: 220px; border: 1px solid #ebeef5; border-radius: 8px; display: block; }
.qr-empty { display: flex; align-items: center; justify-content: center; color: #c0c4cc; font-size: 13px; }
.login-tip { color: #606266; font-size: 13px; margin: 10px 0; }
.login-error { color: #f56c6c; font-size: 12px; margin-top: 8px; }
.login-success { padding: 20px 0; }
.ls-icon { width: 48px; height: 48px; line-height: 48px; border-radius: 50%; background: #67c23a; color: #fff; font-size: 26px; margin: 0 auto 10px; }
.ls-id { color: #909399; font-size: 13px; margin: 6px 0; }
.checkcode-row { display: flex; gap: 8px; align-items: center; }
.cc-img { width: 90px; height: 36px; border: 1px solid #ebeef5; border-radius: 4px; cursor: pointer; flex-shrink: 0; }
.page-shot { margin: 0 0 8px 90px; }
.page-shot img { width: 100%; border: 1px solid #ebeef5; border-radius: 6px; display: block; }
.page-shot-tip { color: #909399; font-size: 12px; margin-top: 4px; }
</style>
