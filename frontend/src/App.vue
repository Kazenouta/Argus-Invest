<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <header class="app-header">
    <div class="logo">🏛️ Argus-Invest</div>
    <nav>
      <RouterLink to="/">首页</RouterLink>
      <RouterLink to="/portfolio">持仓</RouterLink>
      <RouterLink to="/trades">调仓</RouterLink>
      <RouterLink to="/thinking">思考</RouterLink>
      <RouterLink to="/weakness">弱点</RouterLink>
      <RouterLink to="/rules">规则</RouterLink>
    </nav>
  </header>
  <main>
    <RouterView />
  </main>
</template>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #fafafa; color: #333; }

.app-header {
  background: #1a1a2e;
  color: white;
  padding: 0 2rem;
  height: 56px;
  display: flex;
  align-items: center;
  gap: 2rem;
  position: sticky;
  top: 0;
  z-index: 100;
}
.logo { font-size: 1.2rem; font-weight: 700; }
nav { display: flex; gap: 1.5rem; }
nav a { color: #ccc; text-decoration: none; font-size: 0.9rem; transition: color 0.2s; }
nav a:hover, nav a.router-link-active { color: white; }
main { min-height: calc(100vh - 56px); }
</style>
