import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Layout from '../views/Layout.vue'
import Accounts from '../views/Accounts.vue'
import Works from '../views/Works.vue'
import Publish from '../views/Publish.vue'
import EditWork from '../views/EditWork.vue'
import Commission from '../views/Commission.vue'
import Dashboard from '../views/Dashboard.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login },
    {
      path: '/',
      component: Layout,
      redirect: '/accounts',
      children: [
        { path: 'accounts', component: Accounts, meta: { title: '账号矩阵' } },
        { path: 'works', component: Works, meta: { title: '作品管理' } },
        { path: 'publish', component: Publish, meta: { title: '视频发布' } },
        { path: 'edit/:workId', component: EditWork, meta: { title: '编辑作品' } },
        { path: 'commission', component: Commission, meta: { title: '带货推广' } },
        { path: 'dashboard', component: Dashboard, meta: { title: '数据看板' } },
      ]
    }
  ]
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('gh_token')
  if (to.path !== '/login' && !token) {
    next('/login')
  } else {
    next()
  }
})

export default router
