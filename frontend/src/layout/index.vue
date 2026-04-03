<template>
  <div class="layout-container">
    <el-container>
      <!-- 侧边栏 -->
      <el-aside width="200px">
        <div class="logo">
          <h2>🏛️ Argus</h2>
        </div>
        <el-menu
          :default-active="activeMenu"
          class="el-menu-vertical"
          :router="true"
          :default-openeds="['/portfolio', '/trades']"
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
        </el-menu>
      </el-aside>

      <!-- 主内容区 -->
      <el-container>
        <el-header>
          <div class="header-title">{{ pageTitle }}</div>
          <div class="header-right">
            <el-tag :type="systemReady ? 'success' : 'danger'" size="small">
              {{ systemReady ? '● 系统正常' : '● 服务未连接' }}
            </el-tag>
          </div>
        </el-header>

        <el-main>
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Briefcase } from '@element-plus/icons-vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { storeToRefs } from 'pinia'

const route = useRoute()
const appStore = useAppStore()
const { systemReady } = storeToRefs(appStore)

const activeMenu = computed(() => route.path)

const pageTitleMap: Record<string, string> = {
  '/': '首页概览',
  '/portfolio': '持仓管理',
  '/trades': '调仓记录',
  '/thinking': '盘中思考',
  '/weakness': '弱点画像',
  '/rules': '规则库',
}

const pageTitle = computed(() => pageTitleMap[route.path] || 'Argus-Invest')
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
</style>
