<template>
  <el-container style="height:100vh">
    <el-aside width="200px" class="aside">
      <div class="logo">淘宝·光合<span class="logo-sub">运营</span></div>
      <div class="pub-btn-wrap">
        <el-button type="primary" class="pub-btn" @click="$router.push('/publish')">
          <el-icon style="margin-right:4px"><Plus /></el-icon> 发布作品
        </el-button>
      </div>
      <el-menu :default-active="activePath" router class="side-menu"
               background-color="#ffffff" text-color="#303133" active-text-color="#ff5000"
               :default-openeds="['manage','asset']">
        <el-menu-item index="/dashboard" class="menu-item">
          <el-icon><HomeFilled /></el-icon><span>首页</span>
        </el-menu-item>
        <el-sub-menu index="manage" class="menu-group">
          <template #title><el-icon><Files /></el-icon><span>内容管理</span></template>
          <el-menu-item index="/works">作品管理</el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="asset" class="menu-group">
          <template #title><el-icon><Wallet /></el-icon><span>账号资产</span></template>
          <el-menu-item index="/accounts">账号矩阵</el-menu-item>
          <el-menu-item index="/commission">带货推广</el-menu-item>
        </el-sub-menu>
      </el-menu>
      <div class="aside-footer">
        <span class="user">{{ username }}</span>
        <el-button link size="small" @click="logout">退出</el-button>
      </div>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="page-title">{{ $route.meta.title }}</span>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Plus, HomeFilled, Files, Wallet } from '@element-plus/icons-vue'
import api from '../api'

const router = useRouter()
const route = useRoute()
const username = ref('')

const activePath = computed(() => route.path)

onMounted(async () => {
  try {
    const r = await api.me()
    username.value = r.username
  } catch (e) {}
})

function logout() {
  localStorage.removeItem('gh_token')
  router.push('/login')
}
</script>

<style scoped>
.aside { background: #fff; border-right: 1px solid #f0f0f0; display: flex; flex-direction: column; }
.logo { font-weight: 800; font-size: 17px; color: #111; padding: 20px 16px 14px; letter-spacing: .5px; }
.logo-sub { color: #ff5000; }
.pub-btn-wrap { padding: 4px 16px 16px; }
.pub-btn { width: 100%; background: #ff5000; border-color: #ff5000; border-radius: 22px; font-weight: 600; height: 40px; font-size: 15px; }
.pub-btn:hover { background: #ff6a1f; border-color: #ff6a1f; }
.side-menu { border-right: none; flex: 1; }
.side-menu :deep(.el-menu-item.is-active) { background: #fff3ee; border-radius: 8px; margin: 2px 8px; width: auto; }
.side-menu :deep(.el-menu-item:hover) { background: #f7f8fa; border-radius: 8px; margin: 2px 8px; width: auto; }
.side-menu :deep(.el-sub-menu__title:hover) { background: #f7f8fa; }
.side-menu :deep(.el-sub-menu .el-menu-item) { padding-left: 48px !important; font-size: 13px; color: #606266; }
.menu-item { height: 46px; line-height: 46px; }
.aside-footer { padding: 12px 16px; border-top: 1px solid #f0f0f0; display: flex; align-items: center; justify-content: space-between; }
.user { color: #606266; font-size: 13px; }
.header { display: flex; align-items: center; border-bottom: 1px solid #ebeef5; background: #fff; }
.page-title { font-size: 15px; font-weight: 600; color: #303133; }
.main { background: #f5f7fa; }
</style>
