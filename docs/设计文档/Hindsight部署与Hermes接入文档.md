# Hindsight 部署与 Hermes 接入文档

> 目标：在已经装好并使用了一段时间 Hermes 的机器上，部署 Hindsight 记忆系统，
> 并把它作为 Hermes 的外部 memory provider 接入。**全程不影响 Hermes
> 现有配置和已积累的会话记忆。**

---

## 0. 读者前提

文档假设你已经满足：

- ✅ 已安装 Hermes Agent（任意版本），`hermes chat` 正常工作
- ✅ 已配置至少一个 LLM provider（Anthropic / OpenAI / DeepSeek / MiniMax / OpenRouter 等）
- ✅ 已积累了一定量 `~/.hermes/memories/`、`USER.md`、`MEMORY.md` 等内置记忆
- ✅ 知道怎么编辑 YAML 文件

**Hermes 自身的安装、provider 配置、session 管理等都不在本文档范围。**

---

## 1. 我们要做什么

Hindsight 是一个**外部 memory 服务**（独立于 Hermes 跑），提供 retain / recall / reflect 三个操作。Hermes 通过 `hindsight` 插件把它当 memory provider 接入。

```
┌─────────────────────────────────────────────────────────────┐
│  hermes chat                                               │
│      │                                                      │
│      │ 走 hindsight plugin（写入/读取）                       │
│      ▼                                                      │
│  ┌────────────────────────────────────┐                     │
│  │  Hindsight API  (localhost:8888)   │  ← 本文部署         │
│  │  ├─ retain  (LLM 抽 fact)         │                     │
│  │  ├─ recall  (4 路并行检索)        │                     │
│  │  └─ reflect(LLM 形成 mental model)│                     │
│  └──────────────┬─────────────────────┘                     │
│                 │                                           │
│                 ▼                                           │
│       pg0 (embedded PostgreSQL)                             │
│       + bge-small embeddings (本地)                          │
│       + cross-encoder rerank (本地)                          │
└─────────────────────────────────────────────────────────────┘
```

**关键不变性**：
- Hermes 的 `MEMORY.md` / `USER.md` / `~/.hermes/memories/` 完全不动
- Hindsight 的数据存在 `~/.pg0/instances/hindsight/`，跟 Hermes 隔离
- 装在独立的 Python venv（`~/hindsight-env/`），不污染 Hermes 的 Python 环境

---

## 2. 前置检查

```bash
# 1. Python 3.11+（hindsight-all 要求）
python3.11 --version || python3.12 --version || python3.13 --version

# 如果没有，需要装（macOS）
brew install python@3.11

# Linux
sudo apt install python3.11

# 2. uv（hindsight 官方推荐用 uv 管 venv）
which uv || curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. 端口 8888 空闲
lsof -i :8888 || echo "8888 空闲"

# 4. Hermes 的 memory 子命令正常
hermes memory status

# 5. 至少有一个 LLM provider 的 API key
#    可选：DeepSeek（推荐，便宜）、OpenAI、Anthropic、OpenRouter、Ollama（本地免费）
#    ⚠ 注意：见 §3.2 关于 MiniMax 的域名问题
```

预计占用：
- 磁盘：~500MB（hindsight-all + bge-small 模型 + cross-encoder）
- 内存：~700MB（pg0 + embedding 模型常驻）
- 端口：8888（API）、可选 9999（Web UI，README 提到但当前 embedded 模式不开放）

---

## 3. 部署 Hindsight

### 3.1 建 venv 并装包

```bash
# 在 $HOME 下建独立 venv（不污染任何项目环境）
cd ~
uv venv hindsight-env --python 3.11
source ~/hindsight-env/bin/activate

# 装 embedded 版本（自带 pg0，不用起 Postgres）
uv pip install hindsight-all

# 验证装好
python -c "from hindsight import HindsightServer; print('OK')"
```

**为什么用 venv 隔离**：Hindsight 依赖很多（transformers、sentence-transformers、pg0…），版本要求高。**不跟 Hermes 自己的 Python 环境混**。

### 3.2 选 LLM provider（关键决策点）

Hindsight 调 LLM 做两件事：
- **retain**：把对话内容抽取成结构化 fact
- **reflect**：基于历史记忆生成 mental model

**provider 通过环境变量配置**。Hindsight 源码（`openai_compatible_llm.py`）内置了几个 provider 的 base URL：

| Provider | Hindsight 默认 base URL | 备注 |
| --- | --- | --- |
| `openai` | `https://api.openai.com/v1` | 官方 OpenAI |
| `deepseek` | `https://api.deepseek.com` | ✅ **推荐，便宜** |
| `minimax` | `https://api.minimax.io/v1` | ⚠ 见下方坑 |
| `anthropic` | (通过 litellm) | 走 Anthropic 官方 |
| `groq` | `https://api.groq.com/openai/v1` | 速度极快，免费额度 |
| `openrouter` | `https://openrouter.ai/api/v1` | 聚合 |
| `ollama` | `http://localhost:11434/v1` | 本地，**零成本** |

**⚠ MiniMax 域名坑**（实测发现）：

Hindsight 硬编码的 `minimax` provider 走 `https://api.minimax.io/v1`（**新域名**）。如果你用的是 **minimaxi.com**（旧域名）签发的 key，Hindsight 直接 401，**不是配置问题，是 Hindsight 跟厂商域名不一致**。

两种绕过方案：
- **A. 换 provider**：用 deepseek / ollama / 其他
- **B. 覆盖 base URL**：在 HindsightServer 启动时传 `llm_base_url` 参数（后面 §3.3 会用到）

**推荐**：如果 Hermes 本来就在用 DeepSeek 或 OpenAI，那就直接复用。**没特别理由别用 MiniMax**，省心。

### 3.3 写环境变量

```bash
mkdir -p ~/.hindsight

cat > ~/.hindsight.env <<EOF
# === 选一个 provider，注释掉其他 ===

# 选项 1：DeepSeek（推荐）
HINDSIGHT_API_LLM_PROVIDER=deepseek
HINDSIGHT_API_LLM_API_KEY=sk-your-deepseek-key
HINDSIGHT_API_LLM_MODEL=deepseek-chat

# 选项 2：OpenAI
# HINDSIGHT_API_LLM_PROVIDER=openai
# HINDSIGHT_API_LLM_API_KEY=sk-your-openai-key
# HINDSIGHT_API_LLM_MODEL=gpt-5-mini

# 选项 3：Ollama 本地（零成本）
# HINDSIGHT_API_LLM_PROVIDER=ollama
# HINDSIGHT_API_LLM_MODEL=qwen2.5:7b
# （ollama 不需要 key，url 默认 http://localhost:11434/v1）

# 选项 4：MiniMax（如果你用的是 minimaxi.com 旧 key，加 base_url 覆盖）
# HINDSIGHT_API_LLM_PROVIDER=minimax
# HINDSIGHT_API_LLM_API_KEY=sk-your-minimaxi-key
# HINDSIGHT_API_LLM_MODEL=MiniMax-M3
# HINDSIGHT_API_LLM_BASE_URL=https://api.minimaxi.com/v1
EOF

chmod 600 ~/.hindsight.env
```

### 3.4 写启动脚本

```bash
cat > ~/hindsight-env/start_hindsight.sh <<'EOF'
#!/bin/bash
set -e

# 加载 LLM provider 配置
set -a
source ~/.hindsight.env
set +a

# 激活 venv
source ~/hindsight-env/bin/activate

# 启动服务（带 MCP，方便日后接其他 agent）
exec python -c "
import os
from hindsight import HindsightServer

print('[hindsight] provider:', os.environ.get('HINDSIGHT_API_LLM_PROVIDER'))
print('[hindsight] model:', os.environ.get('HINDSIGHT_API_LLM_MODEL'))
print('[hindsight] key set:', bool(os.environ.get('HINDSIGHT_API_LLM_API_KEY')))

server = HindsightServer(
    llm_provider=os.environ['HINDSIGHT_API_LLM_PROVIDER'],
    llm_model=os.environ.get('HINDSIGHT_API_LLM_MODEL', 'gpt-5-mini'),
    llm_api_key=os.environ.get('HINDSIGHT_API_LLM_API_KEY', ''),
    llm_base_url=os.environ.get('HINDSIGHT_API_LLM_BASE_URL'),  # 可选
    host='127.0.0.1',
    port=8888,
    mcp_enabled=True,
    log_level='info',
)
server.start(timeout=60)
print('[hindsight] serving on', server.url)
import threading
threading.Event().wait()
"
EOF

chmod +x ~/hindsight-env/start_hindsight.sh
```

### 3.5 首次启动 + 烟测

```bash
# 前台跑一次看是否正常
source ~/hindsight-env/bin/activate
python -c "
import os
os.environ.update({
    'HINDSIGHT_API_LLM_PROVIDER': 'deepseek',  # 改你的
    'HINDSIGHT_API_LLM_API_KEY': 'sk-test',
    'HINDSIGHT_API_LLM_MODEL': 'deepseek-chat',
})
from hindsight import HindsightServer
server = HindsightServer(llm_provider='deepseek', llm_model='deepseek-chat',
                        llm_api_key='sk-test', host='127.0.0.1', port=8888,
                        mcp_enabled=True, log_level='info')
server.start(timeout=60)
print('URL:', server.url)
import urllib.request, time
time.sleep(2)
print('health:', urllib.request.urlopen(server.url + '/health', timeout=5).read())
" 2>&1 | tail -30
```

期望看到：
- `[hindsight] serving on http://127.0.0.1:8888`
- `health: {"status":"healthy","database":"connected"}`

### 3.6 后台常驻

```bash
# 停掉前台测试
pkill -f HindsightServer

# 后台跑
nohup ~/hindsight-env/start_hindsight.sh > /tmp/hindsight.log 2>&1 &
disown
sleep 10

# 验证
curl -fsS http://127.0.0.1:8888/health
# 期望：{"status":"healthy","database":"connected"}

lsof -i :8888 | head -3
# 期望：python ... TCP 127.0.0.1:8888 (LISTEN)
```

### 3.7 端到端测

```bash
source ~/hindsight-env/bin/activate
python -c "
from hindsight_client import Hindsight
c = Hindsight(base_url='http://127.0.0.1:8888')

# 写
r = c.retain(bank_id='test', content='Alice works at Google as a senior engineer')
print('retain:', r.success, r.usage)

# 查
r = c.recall(bank_id='test', query='What does Alice do?')
print('recall:', [m.text for m in r.results])

# 反思
r = c.reflect(bank_id='test', query='What should I know about Alice?')
print('reflect:', r.text[:200])
"
```

### 3.8 retain 的 token 成本与优化

**⚠ retain 比普通 LLM 调用贵得多**，是 Hindsight 整个系统里**最贵的一环**。原因：每次 retain 实际做 4 件事（LLM 抽 fact → 归一化 → 存 4 路索引 → 生成 embedding），其中 LLM 抽取是成本大头。

#### 单次成本估算

| 场景 | 输入 | 输出 | Embedding | 单次成本（DeepSeek-V3 价） |
| --- | --- | --- | --- | --- |
| 短对话 1 轮 | ~2K | ~300 | ~1K | $0.001 |
| 长对话 1 轮 | ~10K | ~800 | ~8K | $0.005 |
| 一次 session 全文 | ~50K | ~2K | ~40K | $0.025 |
| 一周累积 | ~300K | ~12K | ~250K | ~$0.15 |

按"每天 retain 1 个 session"算：每月 **$5-10**（DeepSeek 价）。换 OpenAI / Anthropic 直接 ×10-30。

#### 为什么这么设计（不是 bug）

Hindsight 卖的就是"高质量 recall"，质量来自：
- 抽取 fact 比直接 embed raw text 检索准 30-50%
- 4 路并行检索需要**结构化**的 entity/relation/temporal 数据
- reflect 操作依赖 mental models 抽象（**这一步也必须 LLM**）

**省掉 LLM 抽取 = 回到裸向量模式，质量下降**。取舍明确：花 token 换质量。

#### 4 个优化方案（按性价比排序）

**方案 1：换便宜模型（最关键）**

LLM provider 在 §3.2 选就决定。同一段抽取任务：

| Provider | 单次 retain 成本 | 质量 |
| --- | --- | --- |
| Ollama 本地 qwen2.5:7b | **$0** | 中（够用） |
| DeepSeek-V3 | $0.001-0.005 | 高 |
| OpenAI gpt-5-mini | $0.003-0.015 | 高 |
| Anthropic Haiku 4.5 | $0.005-0.020 | 高 |
| Anthropic Opus 4.8 | $0.05-0.20 | 最高（**浪费**） |

**推荐**：抽取任务用 deepseek / gpt-5-mini / 本地 ollama 即可。**不要给 Hindsight 用 Opus**。

**方案 2：批量 retain（最常用，单次成本降低 50-100 倍）**

Hermes 的 hindsight plugin 默认**每轮都 retain**。高频场景下要改成批量：

```python
# ❌ 每个 turn 调一次（hermes 默认行为）
def on_user_message(text):
    client.retain(bank_id, text)  # 100 次/会话 = 100 次 LLM

# ✅ 会话结束一次性
def on_session_end(full_transcript):
    client.retain(bank_id, full_transcript)  # 1 次/会话 = 1 次 LLM
```

**注意**：这不是改 Hindsight 配置，是改 hermes plugin 行为。如果 hermes 当前没提供 batch 开关，就只能接受默认（参考 §6 排查"成本过高"问题）。

**方案 3：内容截断后再 retain**

如果某次内容特别长（比如导入了整个文件），可以截断：

```python
def smart_retain(text, max_chars=2000):
    if len(text) > max_chars:
        # 截断 / 摘要 / 只取关键句
        text = extract_key_sentences(text, max_chars=max_chars)
    client.retain(bank_id, text)
```

**方案 4：关掉 reflect（如果不需要"学习"能力）**

reflect 是 Hindsight 跟 mem0/claude-mem 的本质区别 —— 它能**跨记忆形成 mental model**。但很多场景用不上：

```bash
# 关 reflect
# Hindsight 当前没有配置文件开关，需要通过 plugin 配置
# 详见 hermes 文档，或在 .env 加 HINDSIGHT_DISABLE_REFLECT=true（如果有）
```

**关掉 reflect → 成本降 30-40%**，且不影响日常 recall。

#### 月度成本估算公式

```
月成本 = (日均 retain 次数) × (单次 token) × (token 单价) × 30
       = N × 3000 × $X/1K × 30
```

举例：
- 每天 20 次短 retain + DeepSeek：`20 × 3000 × $0.0000014 × 30 ≈ $2.5/月`
- 每天 5 次长 retain + OpenAI：`5 × 12000 × $0.00015 × 30 ≈ $27/月`
- 每天 1 次 batch + Ollama 本地：`$0/月`

**最便宜的方案**：Ollama 本地 + batch retain。每月接近 $0，质量够用。

#### 决策树

```
需要每月花 $50+ 吗？
├─ 是 → 考虑换便宜模型（方案 1）或 batch（方案 2）
├─ 否
│   └─ 需要 reflect 这个独有能力吗？
│       ├─ 是 → 保留 reflect
│       └─ 否 → 关 reflect（方案 4）
└─ 不在乎钱 → 啥都不动
```

---

## 4. 接入 Hermes（**不影响现有 Hermes**）

### 4.1 装 hindsight-client

Hermes 自己的 venv 里需要 `hindsight-client` 才能调 Hindsight：

```bash
# 找到 hermes 用的 python
which hermes
# 假设是 ~/.hermes/hermes-agent/venv/bin/hermes
HERMES_PY=$(dirname $(which hermes))/python

# 在 hermes 的 venv 里装 hindsight-client
$HERMES_PY -m pip install 'hindsight-client>=0.4.22'

# 验证
$HERMES_PY -c "import hindsight_client; print('OK')"
```

如果 `hermes memory setup hindsight` 走通，它会自动装。但**走交互式的话需要 TUI**，用上面的手动方式更可控。

### 4.2 写 Hindsight 自己的配置

**关键**：Hindsight plugin 读的是 `~/.hindsight/config.json`，**不是** `~/.hermes/config.yaml`。

```bash
mkdir -p ~/.hindsight
cat > ~/.hindsight/config.json <<'EOF'
{
  "mode": "local_external",
  "api_url": "http://127.0.0.1:8888",
  "timeout": 120,
  "banks": {
    "hermes": {
      "bankId": "hermes",
      "budget": "mid",
      "enabled": true
    }
  }
}
EOF
chmod 600 ~/.hindsight/config.json
```

字段说明：
- `mode: local_external` — 连接到现有 Hindsight 进程（vs `cloud` 走 Hindsight 官方云 / `local_embedded` 自起一个 daemon）
- `api_url` — 你的 Hindsight 进程地址
- `bank_id: hermes` — 记忆存在哪个 bank（`hermes` 是默认值，也可以换）
- `budget: mid` — 召回时返回多少条，可选 `low/mid/high`

### 4.3 改 Hermes 顶层 provider（**这是唯一会动 Hermes 的一步**）

```bash
# 备份原 config（防止意外）
cp ~/.hermes/config.yaml ~/.hermes/config.yaml.bak.hindsight-$(date +%Y%m%d)

# 用 python 安全改 yaml
~/.hermes/hermes-agent/venv/bin/python <<'PYEOF'
import yaml
from pathlib import Path

p = Path.home() / ".hermes" / "config.yaml"
cfg = yaml.safe_load(p.read_text())

# 改一个字段，其他什么都不动
cfg.setdefault("memory", {})
cfg["memory"]["provider"] = "hindsight"

p.write_text(yaml.safe_dump(cfg, default_flow_style=False, sort_keys=False, allow_unicode=True))
print("memory.provider =", cfg["memory"]["provider"])
PYEOF
```

**只改了 `memory.provider` 一个字段**。其他所有配置（provider、hooks、skills、sessions、model 等）原样保留。

回滚：
```bash
cp ~/.hermes/config.yaml.bak.hindsight-$(date +%Y%m%d) ~/.hermes/config.yaml
```

### 4.4 验证

```bash
hermes memory status
```

期望看到：

```
Memory status
────────────────────────────────────────
  Built-in:  always active
  Provider:  hindsight

  Plugin:    installed ✓
  Status:    available ✓

  Installed plugins:
    • hindsight  (API key / local) ← active
```

如果 `Status: not available`，回 §6 排查。

### 4.5 端到端测试

```bash
# 1. 让 hermes 记一些信息（用任何你当前能用的 provider）
hermes chat -q "My favorite programming language is Rust. Please remember this." \
  --accept-hooks --yolo --provider deepseek -m deepseek-chat

# 2. 等几秒让 Hindsight 后台 consolidate
sleep 8

# 3. 验证 Hindsight 里有了
source ~/hindsight-env/bin/activate
python -c "
from hindsight_client import Hindsight
c = Hindsight(base_url='http://127.0.0.1:8888')
r = c.recall(bank_id='hermes', query='favorite programming language')
print([m.text for m in r.results])
"

# 4. 新会话让 hermes 召回
hermes chat -q "What is my favorite programming language?" \
  --accept-hooks --yolo --provider deepseek -m deepseek-chat
```

期望：新会话能准确回答 "Rust"。

---

## 5. 日常运维

### 5.1 起停

```bash
# 起
nohup ~/hindsight-env/start_hindsight.sh > /tmp/hindsight.log 2>&1 &
disown

# 停
pkill -f HindsightServer

# 看日志
tail -f /tmp/hindsight.log

# health check
curl http://127.0.0.1:8888/health
```

### 5.2 开机自启（macOS launchd）

```bash
cat > ~/Library/LaunchAgents/com.user.hindsight.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.hindsight</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/$(whoami)/hindsight-env/start_hindsight.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/hindsight.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/hindsight.log</string>
</dict>
</plist>
EOF

launchctl load ~/Library/LaunchAgents/com.user.hindsight.plist
```

### 5.3 数据备份

Hindsight 的所有数据在 `~/.pg0/instances/hindsight/`：

```bash
# 备份
tar czf ~/hindsight-data-$(date +%Y%m%d).tgz ~/.pg0/instances/hindsight/

# 恢复
tar xzf ~/hindsight-data-YYYYMMDD.tgz -C ~/
```

### 5.4 升级 / 重装

```bash
# 停服务
pkill -f HindsightServer

# 升级包（保留 venv）
source ~/hindsight-env/bin/activate
uv pip install --upgrade hindsight-all

# 重启
nohup ~/hindsight-env/start_hindsight.sh > /tmp/hindsight.log 2>&1 &
```

数据不会丢（pg0 文件在 venv 之外）。

### 5.5 彻底回滚（**完全恢复 Hermes 原状**）

如果 Hindsight 跟 Hermes 配合得不好，想恢复成原来：

```bash
# 1. 停 Hindsight
pkill -f HindsightServer

# 2. 把 hermes config 改回去
cp ~/.hermes/config.yaml.bak.hindsight-$(date +%Y%m%d) ~/.hermes/config.yaml
# 或者手动：把 memory.provider 改回空字符串
# ~/.hermes/hermes-agent/venv/bin/python -c "
# import yaml
# from pathlib import Path
# p = Path.home() / '.hermes' / 'config.yaml'
# cfg = yaml.safe_load(p.read_text())
# cfg['memory']['provider'] = ''
# p.write_text(yaml.safe_dump(cfg, default_flow_style=False, sort_keys=False, allow_unicode=True))
# "

# 3. 验证 hermes 内置记忆仍然工作
hermes memory status
# 应该看到 Provider: (none — built-in only)

hermes chat -q "你好" --provider deepseek -m deepseek-chat
# 应该正常工作
```

Hindsight 本身不删也没事，**只是 Hermes 不再调它了**。想删干净：
```bash
# 删 venv
rm -rf ~/hindsight-env

# 删 pg0 数据
rm -rf ~/.pg0/instances/hindsight

# 删 hermes 里的 client
$(dirname $(which hermes))/../../venv/bin/pip uninstall -y hindsight-client
# 实际路径看你 hermes 装在哪
```

---

## 6. 故障排查

### 6.1 `hindsight memory status` 显示 `Status: not available`

按顺序检查：

```bash
# 1. Hindsight 进程在跑吗？
lsof -i :8888 | head -3
# 期望：python ... TCP 127.0.0.1:8888 (LISTEN)
# 不在 → 重启：nohup ~/hindsight-env/start_hindsight.sh > /tmp/hindsight.log 2>&1 &

# 2. health 端点响应吗？
curl -fsS http://127.0.0.1:8888/health
# 期望：{"status":"healthy","database":"connected"}
# 不是 → 看 /tmp/hindsight.log 末尾

# 3. LLM provider 配对吗？
source ~/hindsight-env/bin/activate
python -c "
import os
print('provider:', os.environ.get('HINDSIGHT_API_LLM_PROVIDER'))
print('model:', os.environ.get('HINDSIGHT_API_LLM_MODEL'))
print('key set:', bool(os.environ.get('HINDSIGHT_API_LLM_API_KEY')))
"
# 或直接看 .env：cat ~/.hindsight.env

# 4. config.json 路径对吗？
cat ~/.hindsight/config.json
# mode 必须是 local_external，api_url 必须是 127.0.0.1:8888
```

### 6.2 Hindsight 启动报 401 / 鉴权错

最常见：provider 域名跟你 key 不匹配。

```bash
# 看日志里的具体错误
grep -i "401\|auth\|api key" /tmp/hindsight.log | tail -5
```

如果用的是 MiniMax 且 key 是 minimaxi.com 签发的：
- 切到 deepseek / openai / ollama
- 或者在 `~/.hindsight.env` 加 `HINDSIGHT_API_LLM_BASE_URL=https://api.minimaxi.com/v1`

### 6.3 hermes chat 不写记忆

```bash
# 1. 确认 provider 已切到 hindsight
hermes memory status
# Provider: hindsight ← 必须看到这个

# 2. 看 hermes 日志
tail -50 ~/.hermes/logs/*.log 2>/dev/null
grep -i "hindsight\|memory" ~/.hermes/logs/*.log 2>/dev/null | tail -10

# 3. 手动 retain 试试，确认连接
source ~/hindsight-env/bin/activate
python -c "
from hindsight_client import Hindsight
c = Hindsight(base_url='http://127.0.0.1:8888')
r = c.retain(bank_id='hermes', content='test from terminal')
print(r)
"
```

### 6.4 启动卡在 `Loading weights` 不动

Hindsight 第一次启动会下载两个本地模型：
- `BAAI/bge-small-en-v1.5`（embedding，~30MB）
- `cross-encoder/ms-marco-MiniLM-L-6-v2`（rerank，~80MB）

如果网络不好会卡：

```bash
# 设 Hugging Face 镜像
export HF_ENDPOINT=https://hf-mirror.com

# 重启
pkill -f HindsightServer
nohup ~/hindsight-env/start_hindsight.sh > /tmp/hindsight.log 2>&1 &
```

或者预先手动下：
```bash
source ~/hindsight-env/bin/activate
python -c "
from sentence_transformers import SentenceTransformer, CrossEncoder
SentenceTransformer('BAAI/bge-small-en-v1.5')
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
print('downloaded')
"
```

### 6.5 port 8888 冲突

```bash
# 看谁在占
lsof -i :8888

# 在 §3.4 启动脚本里改 port
sed -i '' 's/port=8888/port=8889/' ~/hindsight-env/start_hindsight.sh

# 同步改 ~/.hindsight/config.json
# "api_url": "http://127.0.0.1:8889"
```

### 6.6 装到一半 hermes 坏了

**最坏情况**：误改了 `~/.hermes/config.yaml` 的其他字段。

```bash
# 还原
cp ~/.hermes/config.yaml.bak.hindsight-* ~/.hermes/config.yaml
# 或从 hermes 自己备份
ls -la ~/.hermes/config.yaml.bak.*
```

**下次预防**：任何改 `~/.hermes/config.yaml` 的操作前**先备份**：
```bash
cp ~/.hermes/config.yaml ~/.hermes/config.yaml.bak.$(date +%Y%m%d_%H%M%S)
```

---

## 7. 用了之后有什么变化

成功接入后，hermes 的记忆行为会从：

```
之前（仅内置）：
  user 说 "我喜欢 Rust"
    ↓
  内置 MEMORY.md 累积（每 6 轮 flush）
    ↓
  满了就压缩，丢信息
```

变成：

```
之后（hindsight 加持）：
  user 说 "我喜欢 Rust"
    ↓
  hermes hindsight plugin 自动 retain
    ↓
  Hindsight 调 LLM 抽 fact：实体=Rust, 类型=preference
    ↓
  存进 ~/.pg0/instances/hindsight（4 路索引）
    ↓
  未来任意时刻 recall 都能 100% 找到
    ↓
  reflect 还能跨记忆形成 mental model：
  "用户喜欢系统级、静态类型、高性能语言"
```

**Hermes 的内置 MEMORY.md / USER.md 仍然在工作**（hindsight 是 additive）。两套并存，hindsight 装得越久，记得越准。

---

## 8. 关键文件位置速查

| 文件 | 谁读 | 内容 | 删了会怎样 |
| --- | --- | --- | --- |
| `~/hindsight-env/` | Hindsight | venv + 启动脚本 | 服务跑不起来 |
| `~/.hindsight.env` | 启动脚本 | LLM provider + key | 服务跑不起来（401） |
| `~/.hindsight/config.json` | Hermes hindsight plugin | mode + api_url + bank | plugin unavailable |
| `~/.pg0/instances/hindsight/` | Hindsight | 所有 memory 数据 | 历史记忆全丢 |
| `~/.hermes/config.yaml` | Hermes | `memory.provider: hindsight`（**仅这一行**） | hermes 退回到内置记忆 |

**回滚优先级**：从下往上。改 `~/.hermes/config.yaml` 改坏了→还原这文件。Hindsight 服务挂了→起回来或停用 plugin。

---

## 9. 一句话总结

```
装：uv venv + hindsight-all
配：~/.hindsight.env (LLM) + ~/.hindsight/config.json (mode)
跑：~/hindsight-env/start_hindsight.sh 后台
接：hermes 的 memory.provider: hindsight
验：hermes memory status → available ✓
```

30 分钟搞定，可独立回滚，不影响 Hermes 现有所有数据。
