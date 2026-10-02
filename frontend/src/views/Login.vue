<template>
  <div class="login-page">
    <div class="logo-bar">
      <span class="logo-tb">淘宝</span>
      <span class="logo-sub">·光合运营平台</span>
    </div>
    <div class="login-card">
      <!-- 左栏：品牌区 -->
      <div class="left-pane">
        <div class="brand-title">淘宝光合运营</div>
        <div class="brand-desc">
          <div class="bd-item">采集 · 选品 · 发布 · 数据</div>
          <div class="bd-item">账号矩阵 · 一站式光合运营</div>
        </div>
        <div class="brand-foot">淘宝光合创作平台 · 运营工具</div>
      </div>
      <!-- 右栏：登录表单 -->
      <div class="right-pane">
        <div class="tabs">
          <span class="tab" :class="{ on: mode === 'login' }" @click="mode = 'login'">密码登录</span>
          <span class="tab-div"></span>
          <span class="tab" :class="{ on: mode === 'register' }" @click="mode = 'register'">注册账号</span>
        </div>
        <el-form :model="form" @submit.prevent>
          <el-input v-model="form.username" placeholder="账号名称" size="large" class="ipt" />
          <el-input v-model="form.password" type="password" placeholder="请输入登录密码" size="large" class="ipt"
                    show-password @keyup.enter="mode === 'login' ? doLogin() : doRegister()" />
          <el-button type="primary" size="large" class="login-btn" :loading="loading" @click="mode === 'login' ? doLogin() : doRegister()">
            {{ mode === 'login' ? '登录' : '注册并登录' }}
          </el-button>
          <div class="tips">
            <template v-if="mode === 'login'">登录即代表同意本平台仅用于管理自有光合账号</template>
            <template v-else>注册后即可使用账号矩阵 · 视频发布 · 带货推广等全部功能</template>
          </div>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'

const router = useRouter()
const mode = ref('login')
const loading = ref(false)
const form = reactive({ username: '', password: '' })

async function submit(action) {
  if (!form.username || !form.password) return ElMessage.warning('请输入账号名称和密码')
  loading.value = true
  try {
    const r = await api[action](form)
    localStorage.setItem('gh_token', r.access_token)
    ElMessage.success(action === 'register' ? '注册成功' : '登录成功')
    router.push('/')
  } catch (e) {} finally { loading.value = false }
}
const doLogin = () => submit('login')
const doRegister = () => submit('register')
</script>

<style scoped>
.login-page { min-height: 100vh; background: #f4f4f4; }
.logo-bar { padding: 22px 40px; display: flex; align-items: baseline; gap: 6px; }
.logo-tb { color: #ff5000; font-size: 26px; font-weight: 800; letter-spacing: 2px; }
.logo-sub { color: #303133; font-size: 15px; font-weight: 600; }
.login-card {
  width: 760px; margin: 60px auto 0; background: #fff; border-radius: 16px;
  display: flex; padding: 50px 0; min-height: 420px; box-shadow: 0 2px 12px rgba(0,0,0,.04);
}
.left-pane {
  width: 340px; display: flex; flex-direction: column; align-items: center; justify-content: center;
  border-right: 1px solid #f0f0f0; gap: 22px; padding: 20px;
}
.brand-title { font-size: 22px; font-weight: 700; color: #303133; letter-spacing: 1px; }
.brand-desc { display: grid; gap: 10px; text-align: center; }
.bd-item { color: #909399; font-size: 14px; }
.brand-foot { color: #c0c4cc; font-size: 12px; margin-top: 30px; }
.right-pane { flex: 1; padding: 10px 56px 0; }
.tabs { display: flex; align-items: center; justify-content: center; gap: 14px; margin-bottom: 30px; }
.tab { font-size: 18px; font-weight: 600; color: #606266; cursor: pointer; user-select: none; }
.tab.on { color: #ff5000; }
.tab-div { width: 1px; height: 16px; background: #e0e0e0; }
.ipt { margin-bottom: 18px; }
.ipt :deep(.el-input__wrapper) { background: #f5f7fa; box-shadow: none; border-radius: 6px; }
.login-btn { width: 100%; background: #ff5000; border-color: #ff5000; font-size: 16px; height: 44px; border-radius: 6px; }
.login-btn:hover { background: #ff6a1f; border-color: #ff6a1f; }
.tips { margin-top: 18px; text-align: center; color: #c0c4cc; font-size: 12px; line-height: 1.8; }
</style>
