<template>
  <div class="persona-page">
    <!-- 左栏：人格选择 -->
    <div class="persona-sidebar">
      <div class="sidebar-header">
        <span>🧠 思维顾问</span>
        <el-button size="small" text @click="loadPersonas" :loading="loading">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>

      <div v-if="loading" class="sidebar-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>加载中...</span>
      </div>

      <div v-else-if="personas.length === 0" class="sidebar-empty">
        <p>暂无可用人格</p>
        <p class="sidebar-empty__hint">在 <code>~/.hermes/skills/</code> 安装 Skill 后刷新</p>
      </div>

      <div v-else class="persona-list">
        <div
          v-for="p in personas"
          :key="p.id"
          class="persona-item"
          :class="{ 'is-active': selectedId === p.id }"
          @click="selectPersona(p)"
        >
          <div class="persona-item__avatar">{{ avatarChar(p.name) }}</div>
          <div class="persona-item__info">
            <div class="persona-item__name">{{ p.name }}</div>
            <div class="persona-item__desc">{{ shortDesc(p.description) }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 右栏：聊天区域 -->
    <div class="chat-area">
      <!-- 无人格选中时 -->
      <div v-if="!selectedId" class="chat-empty">
        <div class="chat-empty__icon">💬</div>
        <p class="chat-empty__title">选择一个思维顾问开始对话</p>
        <p class="chat-empty__sub">左侧列出所有已安装的人格Skill，点击即可切换并开始对话</p>
      </div>

      <!-- 已选中人格 -->
      <template v-else>
        <!-- 聊天头 -->
        <div class="chat-header">
          <div class="chat-header__info">
            <span class="chat-header__avatar">{{ avatarChar(selectedPersona?.name || '') }}</span>
            <div>
              <div class="chat-header__name">{{ selectedPersona?.name }}</div>
              <div class="chat-header__desc">{{ shortDesc(selectedPersona?.description || '') }}</div>
            </div>
          </div>
          <el-button size="small" text type="danger" @click="clearHistory">
            <el-icon><Delete /></el-icon> 清空对话
          </el-button>
        </div>

        <!-- 消息列表 -->
        <div ref="messagesEl" class="messages-container">
          <!-- 欢迎消息 -->
          <div v-if="messages.length === 0" class="welcome-msg">
            <p>👋 你正在与 <strong>{{ selectedPersona?.name }}</strong> 对话</p>
            <p>{{ selectedPersona?.description }}</p>
            <div class="welcome-hints">
              <span v-for="h in welcomeHints" :key="h" class="welcome-hint" @click="sendHint(h)">
                {{ h }}
              </span>
            </div>
          </div>

          <!-- 消息气泡 -->
          <div
            v-for="(msg, idx) in messages"
            :key="idx"
            class="message"
            :class="msg.role === 'user' ? 'message--user' : 'message--persona'"
          >
            <div class="message__avatar">
              {{ msg.role === 'user' ? '👤' : avatarChar(selectedPersona?.name || '') }}
            </div>
            <div class="message__content">
              <div class="message__text" v-html="renderMarkdown(msg.content)" />
            </div>
          </div>

          <!-- 加载中 -->
          <div v-if="thinking" class="message message--persona">
            <div class="message__avatar">{{ avatarChar(selectedPersona?.name || '') }}</div>
            <div class="message__content">
              <div class="message__thinking">
                <el-icon class="is-loading"><Loading /></el-icon>
                {{ selectedPersona?.name }} 正在思考...
              </div>
            </div>
          </div>
        </div>

        <!-- 输入区 -->
        <div class="input-area">
          <div class="input-area__box">
            <el-input
              v-model="inputText"
              type="textarea"
              :rows="3"
              resize="none"
              :placeholder="`向 ${selectedPersona?.name} 提问...（Enter 发送，Shift+Enter 换行）`"
              :disabled="thinking"
              @keydown.enter.exact.prevent="sendMessage"
              @keydown.enter.shift="handleShiftEnter"
            />
            <div class="input-area__actions">
              <span class="input-area__tip">Enter 发送 · Shift+Enter 换行</span>
              <el-button
                type="primary"
                size="small"
                :loading="thinking"
                :disabled="!inputText.trim() || thinking"
                @click="sendMessage"
              >
                发送
              </el-button>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Loading, Delete } from '@element-plus/icons-vue'

// ── 类型定义 ──────────────────────────────────────────────────────────────────

interface Persona {
  id: string
  name: string
  description: string
}

interface Message {
  role: 'user' | 'assistant'
  content: string
}

// ── 状态 ─────────────────────────────────────────────────────────────────────

const personas = ref<Persona[]>([])
const selectedId = ref<string | null>(null)
const messages = ref<Message[]>([])
const inputText = ref('')
const thinking = ref(false)
const loading = ref(false)
const messagesEl = ref<HTMLElement | null>(null)

// ── 计算属性 ─────────────────────────────────────────────────────────────────

const selectedPersona = computed(() =>
  personas.value.find(p => p.id === selectedId.value) || null
)

const welcomeHints = computed(() => {
  if (!selectedPersona.value) return []
  const id = selectedPersona.value.id
  if (id === 'munger-perspective') {
    return [
      '怎么看现在的A股市场？',
      '这个决策有什么认知偏误？',
      '用逆向思考分析一下当前形势',
    ]
  }
  if (id === 'huashu-nuwa') {
    return [
      '帮我蒸馏一个人的思维框架',
      '我想提升决策质量，有什么推荐？',
    ]
  }
  return ['你好，请介绍一下你自己']
})

// ── 方法 ─────────────────────────────────────────────────────────────────────

async function loadPersonas() {
  loading.value = true
  try {
    const res = await import('@/api').then(m => m.personaApi.list())
    personas.value = res.data
    // 自动选中第一个
    if (personas.value.length > 0 && !selectedId.value) {
      selectPersona(personas.value[0])
    }
  } catch {
    ElMessage.error('加载人格列表失败，请检查后端服务')
  } finally {
    loading.value = false
  }
}

function selectPersona(p: Persona) {
  selectedId.value = p.id
  messages.value = []
}

function avatarChar(name: string): string {
  return name ? name.charAt(0).toUpperCase() : '?'
}

function shortDesc(desc: string): string {
  if (!desc) return ''
  // 取description第一行，不超过50字
  const firstLine = desc.split('\n')[0].trim()
  return firstLine.length > 50 ? firstLine.slice(0, 50) + '…' : firstLine
}

function renderMarkdown(text: string): string {
  // 简单的markdown渲染：粗体、斜体、换行
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
}

function handleShiftEnter() {
  // 仅换行，阻止默认发送
}

async function sendHint(hint: string) {
  inputText.value = hint
  await sendMessage()
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || thinking.value || !selectedId.value) return

  // 添加用户消息
  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  thinking.value = true
  scrollToBottom()

  try {
    const history = messages.value.map(m => ({
      role: m.role,
      content: m.content,
    }))

    const res = await import('@/api').then(m =>
      m.personaApi.chat({ skill_id: selectedId.value!, messages: history })
    )

    if (res.data.error) {
      ElMessage.error(res.data.error)
      messages.value.push({ role: 'assistant', content: `⚠️ ${res.data.error}` })
    } else {
      messages.value.push({ role: 'assistant', content: res.data.reply })
    }
  } catch (err: unknown) {
    const e = err as Error
    ElMessage.error(e?.message || '请求失败，请重试')
    messages.value.push({ role: 'assistant', content: `❌ 请求失败：${e?.message || '未知错误'}` })
  } finally {
    thinking.value = false
    await nextTick()
    scrollToBottom()
  }
}

function clearHistory() {
  messages.value = []
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesEl.value) {
      messagesEl.value.scrollTop = messagesEl.value.scrollHeight
    }
  })
}

// ── 初始化 ───────────────────────────────────────────────────────────────────

loadPersonas()
</script>

<style scoped lang="scss">
.persona-page {
  display: flex;
  height: calc(100vh - 50px);
  background: #f0f2f5;
  overflow: hidden;
}

// ── 左栏 ─────────────────────────────────────────────────────────────────────

.persona-sidebar {
  width: 260px;
  flex-shrink: 0;
  background: #fff;
  border-right: 1px solid #e8eaf0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #f0f2f5;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.sidebar-loading,
.sidebar-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex: 1;
  color: #909399;
  font-size: 13px;
  padding: 20px;
  text-align: center;
}

.sidebar-empty__hint {
  font-size: 11px;
  color: #c0c4cc;
  code {
    background: #f5f7fa;
    padding: 2px 4px;
    border-radius: 4px;
    font-size: 11px;
  }
}

.persona-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.persona-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
  margin-bottom: 2px;

  &:hover {
    background: #f5f7fa;
  }

  &.is-active {
    background: #ecf5ff;
    border: 1px solid #d9ecff;
  }

  &__avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: #fff;
    font-size: 15px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  &__info {
    flex: 1;
    min-width: 0;
  }

  &__name {
    font-size: 13px;
    font-weight: 600;
    color: #303133;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  &__desc {
    font-size: 11px;
    color: #909399;
    margin-top: 3px;
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
}

// ── 右栏 ─────────────────────────────────────────────────────────────────────

.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;

  &__icon {
    font-size: 48px;
    opacity: 0.5;
  }

  &__title {
    font-size: 16px;
    font-weight: 600;
    color: #303133;
    margin: 0;
  }

  &__sub {
    font-size: 13px;
    color: #909399;
    margin: 0;
    max-width: 320px;
    text-align: center;
    line-height: 1.6;
  }
}

// ── 聊天头 ───────────────────────────────────────────────────────────────────

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid #e8eaf0;
  flex-shrink: 0;

  &__info {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  &__avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: #fff;
    font-size: 15px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  &__name {
    font-size: 14px;
    font-weight: 600;
    color: #303133;
  }

  &__desc {
    font-size: 12px;
    color: #909399;
    margin-top: 2px;
    max-width: 300px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

// ── 消息列表 ─────────────────────────────────────────────────────────────────

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.welcome-msg {
  background: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  border: 1px solid #e8eaf0;
  text-align: center;

  p {
    margin: 0 0 8px;
    font-size: 14px;
    color: #606266;
    line-height: 1.6;
  }

  strong {
    color: #303133;
  }

  .welcome-hints {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: center;
    margin-top: 14px;
  }

  .welcome-hint {
    background: #ecf5ff;
    color: #409eff;
    font-size: 12px;
    padding: 5px 12px;
    border-radius: 16px;
    cursor: pointer;
    transition: background 0.15s;
    border: 1px solid #d9ecff;

    &:hover {
      background: #d9ecff;
    }
  }
}

// ── 消息气泡 ─────────────────────────────────────────────────────────────────

.message {
  display: flex;
  gap: 10px;
  align-items: flex-start;

  &__avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: #fff;
    font-size: 13px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  &--user {
    flex-direction: row-reverse;

    .message__avatar {
      background: linear-gradient(135deg, #409eff, #66b1ff);
    }

    .message__content {
      background: #409eff;
      color: #fff;
      border-radius: 12px 12px 2px 12px;
    }
  }

  &--persona {
    .message__content {
      background: #fff;
      color: #303133;
      border-radius: 12px 12px 12px 2px;
      border: 1px solid #e8eaf0;
    }
  }

  &__content {
    max-width: 68%;
    padding: 10px 14px;
    font-size: 14px;
    line-height: 1.7;
    word-break: break-word;
  }

  &__text {
    white-space: pre-wrap;
    word-break: break-word;

    :deep(strong) {
      font-weight: 700;
    }
    :deep(em) {
      font-style: italic;
    }
    :deep(code) {
      background: #f5f7fa;
      padding: 1px 5px;
      border-radius: 4px;
      font-size: 12px;
    }
  }

  &__thinking {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: #909399;
  }
}

// ── 输入区 ───────────────────────────────────────────────────────────────────

.input-area {
  padding: 12px 20px 16px;
  background: #fff;
  border-top: 1px solid #e8eaf0;
  flex-shrink: 0;

  &__box {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  &__actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  &__tip {
    font-size: 11px;
    color: #c0c4cc;
  }
}
</style>
