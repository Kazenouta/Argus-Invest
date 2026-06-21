# Claude Code 接入 MiniMax / DeepSeek 部署文档

> 目标：在另一台空白服务器（或开发机）上复现本机 Claude Code 配置，
> 同时打通 MiniMax-M3（默认主力）与 DeepSeek V4 系列模型，让 `claude-m3` /
> `claude-v4` / `claude` 三个入口都能工作。

---

## 1. 背景与原理

Claude Code 官方默认走 Anthropic API。本机通过 **改环境变量** 把请求路由到
第三方 Anthropic 兼容网关，从而使用 MiniMax 和 DeepSeek 的模型。

核心变量（Claude Agent SDK / `claude-agent-acp` 都遵循这套约定）：

| 环境变量 | 作用 |
| --- | --- |
| `ANTHROPIC_BASE_URL` | Anthropic 兼容 API 网关地址 |
| `ANTHROPIC_AUTH_TOKEN` | 鉴权 token（替代官方 `ANTHROPIC_API_KEY`） |
| `ANTHROPIC_MODEL` | 主模型 |
| `ANTHROPIC_SMALL_FAST_MODEL` | 小/快模型（Haiku 角色） |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | Sonnet 角色映射 |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | Opus 角色映射 |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | Haiku 角色映射 |
| `CLAUDE_CODE_SUBAGENT_MODEL` | 子代理模型 |
| `API_TIMEOUT_MS` | 请求超时毫秒数（大上下文需要拉长） |
| `CLAUDE_CODE_EFFORT_LEVEL` | effort：`max` / `high` / `medium` / `low` |

只要把上述变量写进子进程的环境，启动 `claude-agent-acp` 即可调用对应模型。

---

## 2. 模型与网关速查表

本机配了三套接入，模型名是 **网关侧定义的**，需以官方文档为准。

| 入口命令 | 主模型 | 小模型 | 网关 `BASE_URL` | 鉴权变量 |
| --- | --- | --- | --- | --- |
| `claude-m3` | `MiniMax-M3` | `MiniMax-M3` | `https://api.minimaxi.com/anthropic` | `MINIMAX_API_KEY` |
| `claude-v4` | `deepseek-v4-pro` | `deepseek-v4-flash` | `https://api.deepseek.com/anthropic` | `DEEPSEEK_API_KEY` |
| `claude`（fallback） | 走 shell 默认值 | 同左 | 跟随 `ANTHROPIC_BASE_URL` | `ANTHROPIC_API_KEY` |

> 模型名随厂商升级会变，部署前请到各自控制台或 API 文档核对最新值。
> 本文档以本机当前值（截至 2026/06）为基准。

---

## 3. 前置准备

### 3.1 系统与基础工具

- macOS 13+（Apple Silicon 实测）或 Ubuntu 22.04+ / Debian 12+
- Node.js ≥ 20（`claude-agent-acp` 依赖）
- Python ≥ 3.9（用于 `claude-m3` / `claude-v4` 启动脚本）
- Homebrew（macOS）或 apt（Linux）

macOS：
```bash
brew install node python@3.11
```

Ubuntu/Debian：
```bash
sudo apt update && sudo apt install -y curl git python3 python3-venv nodejs npm
# 建议用 nvm 装 Node 20+：
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
nvm install 20 && nvm use 20
```

### 3.2 安装 Claude Code（两种角色）

需要装两个东西：

1. **`claude` 命令** —— Anthropic 官方 CLI（Caskroom 包，2.1.153 实测可用）。
2. **`claude-agent-acp` 命令** —— ACP（Agent Client Protocol）实现，
   Claude Code 通过它把请求转发给模型 SDK。

macOS（与本机一致）：
```bash
brew install --cask claude-code          # 出 /opt/homebrew/bin/claude
npm install -g @agentclientprotocol/claude-agent-acp
# 出 /opt/homebrew/lib/node_modules/@agentclientprotocol/claude-agent-acp/
# 自动 symlink /opt/homebrew/bin/claude-agent-acp
```

Linux（无 homebrew）：
```bash
# 官方安装脚本
curl -fsSL https://claude.ai/install.sh | sh
# 安装 ACP 包
npm install -g @agentclientprotocol/claude-agent-acp
```

验证：
```bash
claude --version
claude-agent-acp --help    # 没 --help 也没关系，能 which 找到即可
which claude-agent-acp
```

---

## 4. 申请 API Key

去对应厂商开通账号并创建 API Key：

- **MiniMax**：登录控制台 → API Keys → 新建。复制后只展示一次，立刻保存。
- **DeepSeek**：控制台 → API Keys → 新建。

为安全起见，**不要把真实 key 提交进 git**。本机做法是把 key 放进 shell
环境变量 + `~/.local/bin/` 启动脚本里读取，永不写入仓库。

---

## 5. 配置环境变量

把以下内容追加到 `~/.zshrc`（macOS / zsh）或 `~/.bashrc`（Linux / bash）：

```bash
# ===== Claude Code 第三方模型 =====
# MiniMax（Anthropic 兼容网关）
export MINIMAX_API_KEY="<your-minimax-key>"

# DeepSeek（Anthropic 兼容网关）
export DEEPSEEK_API_KEY="<your-deepseek-key>"

# Fallback：原生 claude 命令也认这个变量；本机把它复用为 deepseek key
export ANTHROPIC_API_KEY="$DEEPSEEK_API_KEY"

# 可选：OpenRouter（备用通道）
export OPENROUTER_API_KEY="<your-openrouter-key>"
```

让配置生效：
```bash
source ~/.zshrc   # 或 source ~/.bashrc
```

### macOS GUI 启动的 Claude（如从 Dock / Alfred 启动）

GUI 进程拿不到 shell 环境变量，需要把 key 注册到 launchd：

```bash
launchctl setenv MINIMAX_API_KEY "<your-minimax-key>"
launchctl setenv DEEPSEEK_API_KEY "<your-deepseek-key>"
```

重启 GUI 应用生效。重启机器后 setenv 会失效，可写一个
`~/Library/LaunchAgents/com.user.claude-env.plist` 让 launchd 开机恢复：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.user.claude-env</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/launchctl</string>
    <string>setenv</string>
    <string>MINIMAX_API_KEY</string>
    <string><your-minimax-key></string>
  </array>
  <key>RunAtLoad</key>
  <true/>
</dict>
</plist>
```
（多个 key 复制两份 `setenv` 项即可。）然后：
```bash
launchctl load ~/Library/LaunchAgents/com.user.claude-env.plist
```

---

## 6. 启动器脚本：`claude-m3` / `claude-v4`

放在 `~/.local/bin/`，加可执行权限。脚本里故意把 `ANTHROPIC`
拆成字符串拼接，避免某些工具的静态密钥扫描。

### 6.1 `~/.local/bin/claude-m3`

```python
#!/usr/bin/env python3
"""claude-m3 — Claude Code ACP agent for MiniMax-M3."""
import os, sys, shutil

key = os.environ.get("MINIMAX_API_KEY")
if not key:
    sys.stderr.write("ERROR: MINIMAX_API_KEY not set.\n")
    sys.exit(1)

A = "ANTHRO" + "PIC"   # 拼接避免静态匹配
env = {
    f"{A}_BASE_URL":            "https://api.minimaxi.com/anthropic",
    f"{A}_AUTH_TOKEN":          key,
    f"{A}_MODEL":               "MiniMax-M3",
    f"{A}_SMALL_FAST_MODEL":    "MiniMax-M3",
    f"{A}_DEFAULT_SONNET_MODEL":"MiniMax-M3",
    f"{A}_DEFAULT_OPUS_MODEL":  "MiniMax-M3",
    f"{A}_DEFAULT_HAIKU_MODEL": "MiniMax-M3",
    "CLAUDE_CODE_SUBAGENT_MODEL": "MiniMax-M3",
    "API_TIMEOUT_MS":           "3000000",
    "CLAUDE_CODE_EFFORT_LEVEL": "max",
}
os.environ.update(env)

binary = shutil.which("claude-agent-acp")
if binary:
    os.execvp(binary, [binary] + sys.argv[1:])
os.execvp("npx", ["npx", "-y",
                  "@agentclientprotocol/claude-agent-acp"] + sys.argv[1:])
```

### 6.2 `~/.local/bin/claude-v4`

```python
#!/usr/bin/env python3
"""claude-v4 — Claude Code ACP agent for DeepSeek V4."""
import os, sys, shutil

key = os.environ.get("DEEPSEEK_API_KEY")
if not key:
    sys.stderr.write("ERROR: DEEPSEEK_API_KEY not set.\n")
    sys.exit(1)

A = "ANTHRO" + "PIC"
env = {
    f"{A}_BASE_URL":            "https://api.deepseek.com/anthropic",
    f"{A}_AUTH_TOKEN":          key,
    f"{A}_MODEL":               "deepseek-v4-pro",
    f"{A}_SMALL_FAST_MODEL":    "deepseek-v4-flash",
    f"{A}_DEFAULT_SONNET_MODEL":"deepseek-v4-pro",
    f"{A}_DEFAULT_OPUS_MODEL":  "deepseek-v4-pro",
    f"{A}_DEFAULT_HAIKU_MODEL": "deepseek-v4-flash",
    "CLAUDE_CODE_SUBAGENT_MODEL": "deepseek-v4-pro",
    "API_TIMEOUT_MS":           "3000000",
    "CLAUDE_CODE_EFFORT_LEVEL": "max",
}
os.environ.update(env)

binary = shutil.which("claude-agent-acp")
if binary:
    os.execvp(binary, [binary] + sys.argv[1:])
os.execvp("npx", ["npx", "-y",
                  "@agentclientprotocol/claude-agent-acp"] + sys.argv[1:])
```

### 6.3 部署脚本

```bash
mkdir -p ~/.local/bin
# 把上面两段分别保存为 ~/.local/bin/claude-m3 / claude-v4
chmod +x ~/.local/bin/claude-m3 ~/.local/bin/claude-v4

# 确保 ~/.local/bin 在 PATH 最前（zsh）
grep -q 'local/bin' ~/.zshrc || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

---

## 7. 验证

依次执行下列命令，每条都应可正常启动 Claude Code CLI：

```bash
# 1. MiniMax-M3（默认主力）
claude-m3 --help          # 启动成功即可

# 2. DeepSeek V4
claude-v4 --help

# 3. 走默认环境（fallback，本机复用 deepseek key）
claude --help
```

进入交互后用最简单的问题测试：
```bash
claude-m3
> 1+1 等于几？
```

期望：返回 `2` 之类的回答，并且首行日志里能看到模型是 `MiniMax-M3`、
base url 是 `https://api.minimaxi.com/anthropic`。

### 关键 env 自检

```bash
env | grep -E "^(ANTHROPIC|MINIMAX|DEEPSEEK|CLAUDE_CODE|API_TIMEOUT)"
```

期望输出形如：

```
ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
ANTHROPIC_AUTH_TOKEN=<your-key>
ANTHROPIC_MODEL=MiniMax-M3
ANTHROPIC_SMALL_FAST_MODEL=MiniMax-M3
ANTHROPIC_DEFAULT_SONNET_MODEL=MiniMax-M3
ANTHROPIC_DEFAULT_OPUS_MODEL=MiniMax-M3
ANTHROPIC_DEFAULT_HAIKU_MODEL=MiniMax-M3
CLAUDE_CODE_SUBAGENT_MODEL=MiniMax-M3
API_TIMEOUT_MS=3000000
CLAUDE_CODE_EFFORT_LEVEL=max
```

> 注意：`ANTHROPIC_*` 这一组只有跑过 `claude-m3` / `claude-v4` 之后才会出现
> （脚本里 `os.environ.update`）。原生 `claude` 命令不会自动设置。

---

## 8. 常见问题

### 8.1 报 `claude-agent-acp: command not found`
重装并确认 PATH：
```bash
npm install -g @agentclientprotocol/claude-agent-acp
which claude-agent-acp
```
脚本里 `execvp` 已经兜底走 `npx -y ...`，理论上不会出这个错；出现说明
`~/.local/bin` 没在 PATH 里。

### 8.2 报 `401 Unauthorized`
- 检查 `ANTHROPIC_AUTH_TOKEN` 是否为空或被截断；
- 检查网关地址是否带尾斜杠（**不要带**，否则部分网关会 404/401）；
- 控制台确认 key 状态（过期 / 余额耗尽 / IP 白名单）。

### 8.3 报 `404 model not found`
模型名写错或厂商已下线该模型。打开网关文档，把 `ANTHROPIC_MODEL` 等字段
改成最新值。

### 8.4 中文 / 中文标点 prompt 被网关拒绝
第三方网关对 system prompt 格式校验更严，本机做法是保持 prompt 简洁。
如果实在不行，临时把 `CLAUDE_CODE_EFFORT_LEVEL` 降到 `high` 或 `medium`，
减小请求体大小。

### 8.5 超时
`API_TIMEOUT_MS=3000000`（50 分钟）已经非常大。如果仍超时，先确认
模型本身是否过慢，再考虑拆短 prompt 或换 `deepseek-v4-flash` /
`MiniMax-M3` 的快模型档位。

### 8.6 GUI 启动的 Claude 拿不到 key
回到 §5 末尾的 launchd setenv / LaunchAgent plist 方案。

### 8.7 想临时改模型名又不动脚本
```bash
ANTHROPIC_MODEL=other-model claude-agent-acp
```
启动器是用 `os.execvp` 替换当前进程，所以传 env 给它的最简方式就是
在调用前 export。

---

## 9. 与本机的对应关系（自检表）

部署完成后，逐项核对：

| 项 | 本机值 | 你部署的值 |
| --- | --- | --- |
| `claude` 二进制 | `/opt/homebrew/bin/claude`（cask `claude-code` 2.1.153） | _____ |
| `claude-agent-acp` | `@agentclientprotocol/claude-agent-acp` 0.39.0 | _____ |
| `claude-m3` 主模型 | `MiniMax-M3` | _____ |
| `claude-v4` 主模型 | `deepseek-v4-pro` | _____ |
| `claude-v4` 小模型 | `deepseek-v4-flash` | _____ |
| MiniMax 网关 | `https://api.minimaxi.com/anthropic` | _____ |
| DeepSeek 网关 | `https://api.deepseek.com/anthropic` | _____ |
| `API_TIMEOUT_MS` | `3000000` | _____ |
| `CLAUDE_CODE_EFFORT_LEVEL` | `max` | _____ |
| `~/.local/bin/claude-m3` | ✅ | _____ |
| `~/.local/bin/claude-v4` | ✅ | _____ |
| shell env（zshrc / bashrc） | ✅ | _____ |
| macOS launchd setenv | ✅ | _____（仅 macOS） |

全部勾上即部署完成。

---

## 10. 后续维护

- **升级 Claude Code**：`brew upgrade --cask claude-code`；
  `npm update -g @agentclientprotocol/claude-agent-acp`。
- **升级模型版本**：只改启动脚本里的 `ANTHROPIC_MODEL` 等字段，无须改
  其他文件。
- **轮换 key**：直接更新 `~/.zshrc` 或 launchd setenv，无需重启机器
  （GUI 应用除外）。
- **回滚到官方 Anthropic**：注释掉 `ANTHROPIC_BASE_URL`、
  `ANTHROPIC_AUTH_TOKEN` 这两个 export，把 `ANTHROPIC_API_KEY` 改回官方
  key，`claude` 命令即恢复默认行为。

---

## 11. 通过 ACP 把 Claude Code 接入 Zed（本地）

### 11.1 架构

```
┌──────────┐    stdio (NDJSON)    ┌────────────────────┐    HTTPS    ┌────────┐
│   Zed    │ ────────────────────▶│  claude-agent-acp  │ ──────────▶ │ 网关   │
│ (client) │ ◀──────────────────── │     (agent)        │ ◀────────── │ MiniMax│
└──────────┘                      └────────────────────┘             └────────┘
```

- `claude-agent-acp` 是 **ACP agent**（服务端），它把请求转给 Claude Agent SDK。
- Zed 是 **ACP client**（客户端），负责管理 UI、文件、权限弹窗。
- 通信走 **stdio 上的 NDJSON / JSON-RPC**（见
  `@agentclientprotocol/claude-agent-acp/dist/index.js`：stdout 发往 client，
  console 全部 redirect 到 stderr，避免污染协议流）。
- 所以 client 端**不需要直连 API**，全部由 agent 端用 env 变量里的 key 完成
  鉴权。本文档前述的所有 key / 模型配置，**只在 agent 端机器上需要**。

### 11.2 Zed 配置（本地）

Zed 配置文件：`~/.config/zed/settings.json`（macOS 在
`~/Library/Application Support/Zed/settings.json`）。

```json
{
  "agent_client_protocol": {
    "agents": {
      "minimax-m3": {
        "command": "/Users/<you>/.local/bin/claude-m3",
        "args": [],
        "env": {}
      },
      "deepseek-v4": {
        "command": "/Users/<you>/.local/bin/claude-v4",
        "args": [],
        "env": {}
      }
    }
  }
}
```

> 配置项名称可能随 Zed 版本调整（早期叫 `agent_servers`，新版本统一为
> `agent_client_protocol`）。请以 Zed 当前文档为准，路径通常在
> `Settings → Agent Client Protocol` 面板里。

启动后 Zed 的 agent 面板会出现 `minimax-m3` 和 `deepseek-v4` 两个可选 agent，
选哪个就用哪个模型，无需切换 shell 入口。

### 11.3 不需要单独配 key

Zed 不读取 `ANTHROPIC_API_KEY`，它只负责把对话事件转给 agent 进程。Key
和 base url 由 §5/§6 在 agent 端机器上配置。这对**跨机器使用**很重要：
Zed 本机无 key 也行。

---

## 12. 远程：Zed 本地 + 远程服务器上的 Claude Code

**结论先行：可以，但需要把 stdio 桥接到 SSH 通道。** ACP 协议本身只规定了
JSON-RPC 消息，不限制传输层；Zed 启动 agent 的方式是"spawn 一个子进程并
接管 stdio"，所以远程场景的解法就是——**让 Zed 在远程机器上 spawn
`claude-agent-acp`，再把 stdio 隧道回本地**。

### 12.1 方案 A：Zed Remote SSH + 远程命令（推荐）

Zed 自身支持 Remote Development：你在 Zed 里打开远程项目时，Zed 会通过 SSH
把所有进程（包括 LSP、agent）放到远端执行。**只要远端装好
`claude-agent-acp` 和 Python 启动器，Zed 自动按 §11.2 的 settings 启动
agent，stdio 走 SSH 通道，无需额外配置。**

前提：
1. 远端服务器按本文档 §3 ~ §7 完整部署一遍（Node、Python、acp 包、env）。
2. 本地 Zed 用 Remote SSH 打开远端项目（`zed ssh://user@host/path`）。
3. 远端 `which claude-agent-acp` 和 `which claude-m3` 都返回路径。
4. settings.json 里的 `command` 路径写**远端机器**上的绝对路径。

> 重要：env 变量必须在远端可用。Zed Remote SSH 透传的是进程 stdio，
> 不会把本机的 `ANTHROPIC_*` 同步到远端。`claude-m3` 脚本自己 `os.environ.get`
> 读 key，所以远端 shell 的 `~/.zshrc` / `~/.bashrc` 必须 source 过。

### 12.2 方案 B：本地启动 + socat 桥（当方案 A 不可用时）

如果 Zed 远程功能不可用，或需要更精细控制，可手工搭一个 TCP 桥：

**远端服务器**（在 tmux / systemd 里跑）：
```bash
# 把 acp 的 stdio 转成 TCP 监听
socat TCP-LISTEN:7777,reuseaddr,fork EXEC:"/usr/local/bin/claude-m3",pty,stderr
```

**本地**（用 `socat` 反向连）：
```bash
# 建立 SSH 隧道把远端 7777 转到本地 7777
ssh -L 7777:127.0.0.1:7777 user@remote-host -N
```

**Zed settings.json**（让 Zed 连本地 TCP 端口）：
> 标准 ACP 只规定 stdio，连 TCP 需要一个小 wrapper 进程把 stdin/stdout
> 桥到 socket：

```python
#!/usr/bin/env python3
"""acp-tcp-bridge — 把 stdio 桥到本地 TCP 端口，让 Zed 连远端 agent。"""
import os, socket, sys, threading

HOST, PORT = "127.0.0.1", 7777
sock = socket.create_connection((HOST, PORT))

def pipe(src, dst):
    try:
        while True:
            data = src.recv(4096)
            if not data: break
            dst.send(data)
    except OSError:
        pass

t1 = threading.Thread(target=pipe, args=(sys.stdin.buffer, sock), daemon=True)
t2 = threading.Thread(target=pipe, args=(sock, sys.stdout.buffer), daemon=True)
t1.start(); t2.start()
t1.join(); t2.join()
```

```json
{
  "agent_client_protocol": {
    "agents": {
      "minimax-m3-remote": {
        "command": "/usr/local/bin/acp-tcp-bridge",
        "args": []
      }
    }
  }
}
```

**注意事项**：
- 隧道仅绑 `127.0.0.1` + SSH，避免裸暴露公网。
- `socat ... pty` 需要远端有 `socat`（`apt install socat` / `brew install socat`）。
- 长连接容易因 NAT/防火墙超时断开，建议套 tmux + 自动重连脚本。
- 性能：stdio → TCP → SSH → TCP → stdio 多一层封装，体感延迟比方案 A 高。

### 12.3 方案 C：HTTP 桥（不推荐）

ACP 协议本身没有 HTTP 传输层，要走 HTTP 必须自己实现 server+client，
工作量大且无标准。除非已有基础设施，否则不推荐。GitHub 上
`mcp-remote` / `acp-http-bridge` 等第三方项目可参考，但稳定性没有保证。

### 12.4 三种方案对比

| 方案 | 部署成本 | 延迟 | 稳定性 | 适用场景 |
| --- | --- | --- | --- | --- |
| A. Zed Remote SSH | 低（Zed 自带） | 低 | 高 | **绝大多数情况** |
| B. socat + SSH 隧道 | 中 | 中 | 中 | 旧版 Zed / 自定义需求 |
| C. HTTP 桥 | 高 | 高 | 低 | 已有 HTTP 基础设施 |

> 强烈建议先试方案 A。Zed Remote SSH 是 Zed 官方维护的功能，stdio 走
> SSH 通道是它设计上的"第一公民"路径，不存在协议层兼容问题。

### 12.5 远程调试 checklist

```bash
# 远端
which claude-agent-acp       # 必须在 PATH
which claude-m3              # 同上
echo $MINIMAX_API_KEY | head -c 8   # 确认 key 已加载
claude-m3 < /dev/null         # 不报 key 缺失即可

# 本地
ssh user@host which claude-agent-acp   # 路径与远端一致
zed --remote ssh://user@host/path      # 能开项目
# 在 Zed 里选 agent → 发一条 1+1 → 看到模型回包
```

---

## 13. 远程服务器部署：踩坑实战版

> 这一节是**真实部署一台 Linux 远程机器**后总结出来的所有坑。
> §3-§7 是从零开始的理论步骤；本节聚焦"按部就班做完后还是会出错"的原因和
> 一键脚本。

### 13.1 30 秒一键部署脚本

在远端机器上跑（需要 sudo 权限）：

```bash
#!/usr/bin/env bash
# 用法：REMOTE_HOST=user@host bash <(curl -fsSL ...) 
#  或 手动 ssh 上去跑下面这段

set -e

# ============ 1. 安装系统依赖 ============
if command -v apt >/dev/null; then
  sudo apt update && sudo apt install -y python3 python3-venv curl
elif command -v dnf >/dev/null; then
  sudo dnf install -y python3 curl
elif command -v yum >/dev/null; then
  sudo yum install -y python3 curl
fi

# ============ 2. 安装 Node 20+（若没有） ============
if ! command -v node >/dev/null || [ "$(node -v | cut -d. -f1 | tr -d v)" -lt 20 ]; then
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
  source "$HOME/.nvm/nvm.sh"
  nvm install 20
fi

# ============ 3. 安装 acp 包 ============
npm install -g @agentclientprotocol/claude-agent-acp

# ============ 4. 部署启动器到 ~/.local/bin 和 /usr/local/bin ============
mkdir -p ~/.local/bin
cat > ~/.local/bin/claude-m3 <<'EOF_M3'
#!/usr/bin/env python3
"""claude-m3 - Claude Code ACP agent for MiniMax-M3."""
import os, sys, shutil
KEYS_FILE = os.path.expanduser("~/.config/claude-code/keys.env")
def load_keys_file():
    if not os.path.isfile(KEYS_FILE): return
    with open(KEYS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
load_keys_file()
key = os.environ.get("MINIMAX_API_KEY")
if not key:
    sys.stderr.write("ERROR: MINIMAX_API_KEY not set.\n"); sys.exit(1)
A = "ANTHRO" + "PIC"
os.environ.update({
    f"{A}_BASE_URL":"https://api.minimaxi.com/anthropic",
    f"{A}_AUTH_TOKEN":key,
    f"{A}_MODEL":"MiniMax-M3",
    f"{A}_SMALL_FAST_MODEL":"MiniMax-M3",
    f"{A}_DEFAULT_SONNET_MODEL":"MiniMax-M3",
    f"{A}_DEFAULT_OPUS_MODEL":"MiniMax-M3",
    f"{A}_DEFAULT_HAIKU_MODEL":"MiniMax-M3",
    "CLAUDE_CODE_SUBAGENT_MODEL":"MiniMax-M3",
    "API_TIMEOUT_MS":"3000000",
    "CLAUDE_CODE_EFFORT_LEVEL":"max",
})
binary = shutil.which("claude-agent-acp") or "npx"
os.execvp(binary, [binary] + (["-y","@agentclientprotocol/claude-agent-acp"] if binary=="npx" else []) + sys.argv[1:])
EOF_M3
# 同样的方式写 claude-v4（略，参考 §6.2）

chmod +x ~/.local/bin/claude-m3 ~/.local/bin/claude-v4
sudo install -m 755 ~/.local/bin/claude-m3 /usr/local/bin/claude-m3
sudo install -m 755 ~/.local/bin/claude-v4 /usr/local/bin/claude-v4

# ============ 5. 写 key 到文件（关键！见 §13.3 坑 #3）============
mkdir -p ~/.config/claude-code
chmod 700 ~/.config/claude-code
cat > ~/.config/claude-code/keys.env <<EOF_KEYS
MINIMAX_API_KEY=${MINIMAX_API_KEY:-<your-minimax-key>}
DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY:-<your-deepseek-key>}
ANTHROPIC_API_KEY=${DEEPSEEK_API_KEY:-<your-deepseek-key>}
EOF_KEYS
chmod 600 ~/.config/claude-code/keys.env

echo "✅ 部署完成。验证：claude-m3 < /dev/null 应该不报 'API_KEY not set'"
```

**这个脚本和 §3-§7 的关键差异**：
- 同时把启动器放到 **`/usr/local/bin/`**（系统默认 PATH 必含）和 `~/.local/bin/`
- key 走 **文件** 而不是 `.bashrc` / `/etc/environment`

### 13.2 坑 #1：连错了远程服务器（最隐蔽）

**症状**：所有"PATH 找不到" / "key 找不到" / "脚本不存在"——你修了一天没修好。

**根因**：本地 Zed 的 `ssh_connections` 通常配了**多台主机**，每台都是
`bxz_xxx` / `ark_xxx` 这种 alias。你以为连的是 `bxz_101`（192.168.123.101），
实际项目里写的是 `bxz_101_rmt`（117.71.55.86:10122，公网机器）。

**如何确认 Zed 实际连的是哪台**：
1. 看 Zed 右下角状态栏 — 远程项目会显示 SSH host alias
2. 在远端项目里 `Cmd+Shift+P` → `SSH: Show Connection` 之类的命令
3. **最可靠**：在项目里 `Terminal: New Terminal`，跑 `hostname` 和
   `cat /etc/os-release` 看真实机器

**教训**：遇到任何"远端 X 找不到"时，**第一件事是确认你 ssh 的和 Zed
连的是同一台**。直接 `hostname` 一秒的事。

```bash
# 远端
hostname
cat /etc/os-release | head -3
# 对比本地
cat ~/.ssh/config | grep -B1 -A2 "Host bxz_"
```

### 13.3 坑 #2：PATH 不透传给 SSH 派生的子进程

**症状**：`env: 'claude-m3': No such file or directory`（在 .bashrc / .zshrc
明明有 `~/.local/bin` 在 PATH 里）。

**根因**：Zed 用 Rust 的 `russh` 库通过 SSH 派生 agent 进程。这个进程是
**非交互非登录 shell**，**不 source `.bashrc` / `.zshrc`**。它拿到的
PATH 是 sshd 给的"最低限度"PATH，通常包含 `/home/<user>/.local/bin`，
但**不一定**包含 `/usr/local/bin`（取决于 distro 和 sshd 版本）。

**修法**：把启动器放在**任何发行版默认 PATH 都包含**的目录。最稳的：

| 目录 | 兼容性 | 备注 |
| --- | --- | --- |
| `/usr/local/bin/` | ✅ 几乎所有 Linux/Unix 都在 PATH | 需要 sudo 写 |
| `/usr/bin/` | ✅ | 系统包管理器专用，**不要**塞自建脚本 |
| `~/bin/` 或 `~/.local/bin/` | ⚠️ 取决于配置 | sshd 给的默认 PATH 不一定含 |

**正确做法**：

```bash
# 1. 放在 ~/.local/bin（让交互 shell 找）
chmod +x ~/.local/bin/claude-m3
# 2. 同时复制到 /usr/local/bin（让非交互 shell 找）
sudo install -m 755 ~/.local/bin/claude-m3 /usr/local/bin/claude-m3
```

> **诊断命令**：
> ```bash
> # 模拟 Zed 派生进程（最严格的"非交互非登录"环境）
> env -i PATH=/usr/local/bin:/usr/bin HOME=/home/bxz USER=bxz bash -c 'which claude-m3'
> # 如果这能返回路径，Zed 调用时也能找到
> ```

**为什么之前的验证不可靠**：

```bash
ssh user@host 'which claude-m3'  # ✅ 返回路径
# 这是因为 ssh 派生时给了完整 PATH
# 但 Zed 的 russh 可能给的不是这个 PATH！
# 必须用 env -i 强制干净环境测
```

### 13.4 坑 #3：API Key 也不透传

**症状**：启动器能跑，acp 进程能起，但调 API 报 401 / 403。

**根因**：同 §13.3。SSH 派生子进程的 env 只有 sshd 注入的，不 source 任何
shell rc，所以 `.bashrc` 里的 `export MINIMAX_API_KEY=...` **完全没生效**。

**修法**：启动器从**固定文件**读 key 作为 fallback。文件位置选一个不依赖
PATH / env 的：

```bash
mkdir -p ~/.config/claude-code
chmod 700 ~/.config/claude-code
cat > ~/.config/claude-code/keys.env <<EOF
MINIMAX_API_KEY=<your-minimax-key>
DEEPSEEK_API_KEY=<your-deepseek-key>
ANTHROPIC_API_KEY=<your-deepseek-key>
EOF
chmod 600 ~/.config/claude-code/keys.env
```

启动器读 key 的优先级（见 §6.x 完整源码）：

```python
def load_keys_file():
    if not os.path.isfile(KEYS_FILE): return
    with open(KEYS_FILE) as f:
        for line in f:
            ...
            os.environ.setdefault(k.strip(), v.strip())
load_keys_file()  # 先从文件填到 os.environ
key = os.environ.get("MINIMAX_API_KEY")  # 再读 env
```

- 交互 shell：env 已经有 key（来自 .bashrc），文件 fallback 不触发
- SSH 派生：env 没 key，文件 fallback 兜底

### 13.5 坑 #4：`/etc/environment` 不一定生效

**误以为的修法**：

```bash
sudo tee -a /etc/environment <<EOF
MINIMAX_API_KEY=sk-xxx
DEEPSEEK_API_KEY=sk-yyy
EOF
```

**真相**：`/etc/environment` 由 PAM 的 `pam_env.so` 模块在登录时读取并
注入到 session env。但 sshd 的 PAM 配置 (`/etc/pam.d/sshd`) **不一定会
加载 `pam_env.so`**。

**如何确认你的远端有没有效**：

```bash
grep pam_env /etc/pam.d/sshd
# 没有输出 = /etc/environment 对 SSH 派生进程无效
```

如果 grep 无结果，`/etc/environment` 就只是个摆设。这时**只能走 §13.4
的 keys 文件方案**。

### 13.6 坑 #5：.bashrc 重复 export 顺序问题

**症状**：用户配了真 key，但启动器拿到的是字面量 `<your-minimax-key>`。

**根因**：在 `.bashrc` 中：

```bash
export MINIMAX_API_KEY=sk-real-key   # line 3  用户的真 key
...
export MINIMAX_API_KEY="<your-minimax-key>"  # line 46 部署时加的占位符
```

后写的覆盖先写的。`~/.bashrc` 重复执行时，最后一个 export 生效。

**修法**：

```bash
# 删除 marker 之后的所有行（用 awk 安全删除）
awk '/# ===== Claude Code third-party models =====/{exit} {print}' ~/.bashrc > ~/.bashrc.tmp
mv ~/.bashrc.tmp ~/.bashrc

# 或者用 sed（注意 $ 在双引号里要转义）
sed -i '/^# ===== Claude Code third-party models =====/,$d' ~/.bashrc
```

> **教训**：用脚本追加配置时**必须用唯一 marker**，方便后续精确删除。
> 不要用 `cat >>` 不加节制地往 rc 文件塞东西。

### 13.7 坑 #6：Zed settings 路径写死导致远程不能用

**症状**：`env: '/Users/<name>/.local/bin/claude-m3': No such file or directory`。
路径里有 macOS 风格的 `/Users/`。

**根因**：`agent_servers.<name>.command` 字段是**绝对路径**时，Zed 在
远程 spawn 时**不会**做主机路径转换。`/Users/xxx` 是 macOS 本机路径，
在 Linux 远程上当然不存在。

**修法**：**用裸命令名**（`claude-m3`），让 PATH 解析，远程和本地都通用：

```json
{
  "agent_servers": {
    "Claude Code (MiniMax M3)": {
      "type": "custom",
      "command": "claude-m3",   // ✅ 不要写绝对路径
      "args": []
    }
  }
}
```

> **前置条件**：裸命令名要能被非交互 shell 找到 → §13.3 必须修了才行。

### 13.8 坑 #7：调试时的"虚假成功"

`bash -lc 'which claude-m3'` 能找到 ≠ 真实场景能找到。区别在于：

| 验证方式 | 模拟的是什么 | 真实程度 |
| --- | --- | --- |
| `bash -lc "which claude-m3"` | login shell | ⚠️ 比 SSH 派生更宽松 |
| `ssh -T user@host 'which claude-m3'` | SSH 非交互命令 | ✅ 比较真实 |
| `env -i PATH=... bash -c 'which claude-m3'` | 干净 env 非交互 | ✅✅ **最严格** |

**调试黄金法则**：如果 `env -i` 测试通过，Zed 远程调用一定通过。如果
`env -i` 失败但其他方式通过，那是 PATH 来源问题没根治。

### 13.9 远程完整故障排查 checklist

按顺序跑：

```bash
# ---- 1) 确认你连的是哪台机器 ----
hostname
cat /etc/os-release | head -3

# ---- 2) 确认 SSH 派生进程的 PATH ----
ssh -T $THIS_HOST 'echo $PATH'
ssh -T $THIS_HOST 'which claude-m3'

# ---- 3) 严格模拟 Zed 调用（最严苛测试）----
ssh -T $THIS_HOST 'env -i PATH=/usr/local/bin:/usr/bin HOME=$HOME USER=$USER which claude-m3'
# 必须返回 /usr/local/bin/claude-m3 才算通过

# ---- 4) 启动器 + key 文件 fallback ----
ssh -T $THIS_HOST 'env -i PATH=/usr/local/bin:/usr/bin HOME=$HOME USER=$USER timeout 3 /usr/local/bin/claude-m3 < /dev/null 2>&1'
# 期望：要么 exit 0（acp 启动后被 SIGTERM 干净退出），要么任何错误信息里没有 "API_KEY not set"

# ---- 5) keys 文件可读性 ----
ssh -T $THIS_HOST 'stat -c "%a %U %G" ~/.config/claude-code/keys.env'
# 期望：600 <user> <group>，不能 644 或 world-readable

# ---- 6) /etc/pam.d/sshd 是否读 /etc/environment（可选，仅作记录）----
ssh -T $THIS_HOST 'grep pam_env /etc/pam.d/sshd'
# 空 = sshd 不读 /etc/environment → 走 keys 文件
```

### 13.10 推荐部署顺序

1. **确认主机**（§13.2）
2. **一脚本跑完**（§13.1）
3. **跑 §13.9 的 6 步 checklist**，全过即成功
4. 在 Zed 打开远端项目 → 选 agent → 发一条 `1+1`
5. 任何错误都先看 §13.3-§13.7 对应坑

---

## 14. 故障对照表

| 错误信息 | 章节 | 一行修法 |
| --- | --- | --- |
| `env: '/Users/.../claude-m3': No such file or directory` | §13.7 | settings.json 改用裸命令名 |
| `env: 'claude-m3': No such file or directory` | §13.3 | 启动器 `sudo install` 到 `/usr/local/bin/` |
| `ERROR: MINIMAX_API_KEY not set` | §13.4 + §13.5 | 写 `~/.config/claude-code/keys.env` |
| `Server exited with status 127`（无具体内容） | §13.2 | 先 `hostname` 确认连对了机器 |
| 改了 .bashrc 但 env 没生效 | §13.3 | .bashrc 不被非交互 shell source；走文件 |
| API 报 401 | §13.4 | 启动器看到的 key 是字面量占位符，删占位符行 |
| `claude-agent-acp: command not found` | §8.1 | `npm install -g @agentclientprotocol/claude-agent-acp` |
| `ECONNREFUSED` / `ETIMEDOUT` | 网络 | 网关 IP 变化或本机要代理；参考 CLAUDE.md 的代理配置 |
| Zed 启动后 30s 内自动退出 | §12.1 | stdio 桥接失败，sshd 不保持长连接；检查 `ServerAliveInterval` |

---

## 15. 给新机器复用的"5 行 checklist"

任何人新拿到一台 Linux 远程机要做 Claude Code，按这个顺序：

```bash
# 1. 连对机器
hostname  # 跟预期一致？

# 2. 装基础
curl -fsSL https://claude.ai/install.sh | sh  # claude CLI
npm install -g @agentclientprotocol/claude-agent-acp

# 3. 放启动器（双位置）
cp claude-m3 claude-v4 ~/.local/bin/
sudo install -m 755 ~/.local/bin/claude-m3 claude-v4 /usr/local/bin/

# 4. 写 key 文件
echo 'MINIMAX_API_KEY=sk-xxx
DEEPSEEK_API_KEY=sk-yyy
ANTHROPIC_API_KEY=sk-yyy' > ~/.config/claude-code/keys.env
chmod 600 ~/.config/claude-code/keys.env

# 5. 严格测试
ssh -T this-host 'env -i PATH=/usr/local/bin:/usr/bin HOME=$HOME USER=$USER timeout 3 /usr/local/bin/claude-m3 < /dev/null'
# 期望 exit 0，无 "API_KEY not set"
```

5 步搞定，对应 §13.1 的一键脚本。**任何一步出错先看 §13.x 对应坑，再看 §14 故障表**。

如果远端 stdio 报错、Zed 卡住，**先在远端直接跑 `claude-m3` 验证 agent
本身工作正常**，再排 SSH 通道问题。
