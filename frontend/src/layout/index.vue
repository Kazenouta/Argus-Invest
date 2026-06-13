<template>
  <div class="layout-container">
    <el-container>
      <!-- 侧边栏 -->
      <el-aside :width="sidebarWidth">
        <div class="logo">
          <h2 v-if="!isCollapsed">🏛️ Argus</h2>
          <span v-else class="logo-icon">🏛️</span>
        </div>
        <el-menu
          :default-active="activeMenu"
          class="el-menu-vertical"
          :router="true"
          :default-openeds="['/portfolio', '/trades']"
          :collapse="isCollapsed"
          :collapse-transition="false"
          background-color="#304156"
          text-color="#bfcbd9"
          active-text-color="#409EFF"
        >
          <el-menu-item index="/">
            <el-icon><HomeFilled /></el-icon>
            <span>首页概览</span>
          </el-menu-item>

          <el-sub-menu index="/portfolio">
            <template #title>
              <el-icon><Briefcase /></el-icon>
              <span>持仓管理</span>
            </template>
            <el-menu-item index="/portfolio">持仓看板</el-menu-item>
            <el-menu-item index="/portfolio/watchlist">观察池</el-menu-item>
            <el-menu-item index="/trades">调仓记录</el-menu-item>
          </el-sub-menu>

          <el-menu-item index="/thinking">
            <el-icon><ChatDotRound /></el-icon>
            <span>盘中思考</span>
          </el-menu-item>

          <el-menu-item index="/weakness">
            <el-icon><Warning /></el-icon>
            <span>弱点画像</span>
          </el-menu-item>

          <el-menu-item index="/rules">
            <el-icon><SetUp /></el-icon>
            <span>规则库</span>
          </el-menu-item>

          <el-sub-menu index="/kv">
            <template #title>
              <el-icon><Reading /></el-icon>
              <span>大V观点</span>
            </template>
            <el-menu-item index="/kv/guolei">郭磊宏观</el-menu-item>
          </el-sub-menu>

        </el-menu>
      </el-aside>

      <!-- 主内容区 -->
      <el-container>
        <el-header>
          <div class="header-title">
            <el-icon class="collapse-btn" @click="toggleSidebar"><component :is="isCollapsed ? 'DArrowRight' : 'DArrowLeft'" /></el-icon>
            {{ pageTitle }}
          </div>
          <div class="header-right">
            <el-badge :value="unreadCount" :hidden="unreadCount === 0" :max="99" type="danger">
              <el-button size="small" @click="showMessages = true">
                <el-icon><Bell /></el-icon>
                消息
              </el-button>
            </el-badge>
            <el-tag :type="systemReady ? 'success' : 'danger'" size="small">
              {{ systemReady ? '● 系统正常' : '● 服务未连接' }}
            </el-tag>
          </div>
        </el-header>

        <!-- 消息抽屉 -->
        <el-drawer v-model="showMessages" title="消息中心" direction="rtl" size="400px" @open="loadMessages">
          <div class="msg-toolbar">
            <el-button size="small" type="primary" plain :disabled="unreadCount === 0" @click="markAllRead">
              全部标为已读
            </el-button>
          </div>
          <el-scrollbar height="calc(100vh - 120px)">
            <div v-if="messages.length === 0" class="msg-empty">
              <el-empty description="暂无消息" :image-size="60" />
            </div>
            <div
              v-for="msg in messages"
              :key="msg.id"
              class="msg-item"
              :class="{ unread: !msg.is_read }"
              @click="handleMsgClick(msg)"
            >
              <div class="msg-header">
                <el-tag size="small" :type="msg.msg_type === 'buy_signal' ? 'danger' : 'warning'">
                  {{ msg.msg_type === 'buy_signal' ? '买入信号' : '规则触发' }}
                </el-tag>
                <span class="msg-time">{{ formatTime(msg.created_at) }}</span>
              </div>
              <div class="msg-content">{{ msg.content }}</div>
              <div v-if="msg.stock_code" class="msg-stock">{{ msg.stock_code }}</div>
            </div>
          </el-scrollbar>
        </el-drawer>

        <el-main>
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { Briefcase, DArrowLeft, DArrowRight, Bell, Reading } from '@element-plus/icons-vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { storeToRefs } from 'pinia'
import { messageApi } from '@/api'
import { ElMessage } from 'element-plus'

const route = useRoute()
const appStore = useAppStore()
const { systemReady } = storeToRefs(appStore)

const isCollapsed = ref(false)

const sidebarWidth = computed(() => isCollapsed.value ? '64px' : '200px')

const toggleSidebar = () => {
  isCollapsed.value = !isCollapsed.value
}

const activeMenu = computed(() => route.path)

const pageTitleMap: Record<string, string> = {
  '/': '首页概览',
  '/portfolio': '持仓管理',
  '/portfolio/watchlist': '观察池',
  '/trades': '调仓记录',
  '/thinking': '盘中思考',
  '/weakness': '弱点画像',
  '/rules': '规则库',
  '/kv': '大V观点',
  '/kv/guolei': '郭磊宏观',
}

const pageTitle = computed(() => pageTitleMap[route.path] || 'Argus-Invest')

// ── Messages ───────────────────────────────────────────────────────────────────

const showMessages = ref(false)
const unreadCount = ref(0)
const messages = ref<any[]>([])

async function loadUnreadCount() {
  try {
    const res = await messageApi.unreadCount()
    unreadCount.value = res.data?.unread ?? 0
  } catch { /* silent */ }
}

async function loadMessages() {
  try {
    const res = await messageApi.list(100)
    messages.value = res.data?.messages ?? []
    unreadCount.value = res.data?.unread ?? 0
  } catch { /* silent */ }
}

async function markAllRead() {
  try {
    await messageApi.markAllRead()
    unreadCount.value = 0
    messages.value = messages.value.map(m => ({ ...m, is_read: true }))
    ElMessage.success('已全部标为已读')
  } catch {
    ElMessage.error('操作失败')
  }
}

async function handleMsgClick(msg: any) {
  if (msg.is_read) return
  try {
    await messageApi.markRead(msg.id)
    msg.is_read = true
    unreadCount.value = Math.max(0, unreadCount.value - 1)
  } catch { /* silent */ }
}

function formatTime(ts: string | null): string {
  if (!ts) return ''
  try {
    return new Date(ts).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return ts
  }
}

// Polling unread count every 60s
let pollTimer: ReturnType<typeof setInterval> | null = null
onMounted(() => {
  loadUnreadCount()
  pollTimer = setInterval(loadUnreadCount, 60000)
})
</script>

<style scoped lang="scss">
.layout-container {
  height: 100vh;

  .el-container {
    height: 100%;
  }
}

.el-aside {
  background-color: #304156;
  color: #fff;
  transition: width 0.3s;

  .logo {
    height: 50px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-bottom: 1px solid #1f2d3d;

    h2 {
      color: #fff;
      margin: 0;
      font-size: 16px;
      font-weight: 600;
    }

    .logo-icon {
      font-size: 20px;
    }
  }

  :deep(.el-sub-menu .el-menu) {
    padding-left: 0 !important;
  }

  :deep(.el-sub-menu .el-menu-item) {
    background-color: #1f2d3d !important;
    padding-left: 68px !important;
    min-height: 0 !important;
    &:hover {
      background-color: #263445 !important;
    }
    &.is-active {
      background-color: #263445 !important;
      color: #409EFF !important;
    }
  }

  :deep(.el-sub-menu__title) {
    padding-left: 20px !important;
  }
}

.el-menu--collapse {
  width: 64px;

  :deep(.el-menu-item),
  :deep(.el-sub-menu__title) {
    padding-left: 20px !important;
    justify-content: center;
    span {
      display: none;
    }
  }
}

.el-header {
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 50px;

  .header-title {
    font-size: 16px;
    font-weight: 600;
    color: #303133;
    display: flex;
    align-items: center;
    gap: 8px;

    .collapse-btn {
      cursor: pointer;
      font-size: 18px;
      color: #606266;
      transition: color 0.2s;
      &:hover {
        color: #409EFF;
      }
    }
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 12px;
  }
}

.el-main {
  background-color: #f0f2f5;
  padding: 20px;
  overflow-y: auto;
}

// Message drawer
.msg-toolbar {
  margin-bottom: 12px;
}
.msg-empty {
  padding: 20px 0;
  text-align: center;
}
.msg-item {
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  transition: background 0.15s;
  &:hover {
    background: #fafafa;
  }
  &.unread {
    background: #f0f7ff;
    border-left: 3px solid #409EFF;
    padding-left: 13px;
    &:hover {
      background: #e8f2ff;
    }
  }
}
.msg-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.msg-time {
  font-size: 11px;
  color: #999;
}
.msg-content {
  font-size: 13px;
  color: #303133;
  line-height: 1.6;
}
.msg-stock {
  margin-top: 4px;
  font-size: 11px;
  color: #409EFF;
}
</style>
