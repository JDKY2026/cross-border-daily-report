# 跨境电商日报 Agent

每天早上 8 点自动搜索 Amazon 政策变动与跨境电商行业新闻，筛选整理后生成一份专业网页日报，推送到你的邮箱。

## 它解决了什么问题

跨境电商卖家每天需要手动搜索零散的政策和新闻信息，费时、易遗漏。这个 Agent 把「搜 → 筛 → 整 → 推」四步自动化，你每天早上打开邮箱就能看到当天的日报。

## 核心流程

```
定时触发(08:00) → 联网搜索 → LLM 筛选去重 → 生成 HTML 网页 → 上传对象存储 → 邮件推送
```

1. **搜索**：自动搜索 Amazon 平台政策变动（费用调整、合规新规、FBA 变化等）和跨境电商行业新闻（关税政策、大卖动态、平台重大事件）
2. **筛选**：大模型对原始搜索结果去重、分类、生成摘要、按重要性排序
3. **生成**：输出为一份专业风格的静态 HTML 网页，分「📋 政策变动」和「📰 行业动态」两大板块
4. **推送**：上传网页到对象存储，通过邮件发送日报链接

## 使用方式

- **手动触发**：对 Agent 说「生成今日日报」
- **自动触发**：每天早上 8:00 定时执行，邮件自动推送到配置的收件邮箱

## 项目结构

```
src/
├── agents/
│   └── agent.py              # Agent 主逻辑，编排工具调用 + 启动调度器
├── tools/
│   ├── web_search_tool.py    # 联网搜索工具（Amazon 政策 + 跨境新闻）
│   ├── daily_report_tool.py  # 日报生成与上传工具（HTML 生成 + S3 上传）
│   ├── email_tool.py         # 邮件推送工具（SMTP 发送纯文本日报通知）
│   └── scheduler.py          # 定时调度器（APScheduler，每天 08:00 触发）
├── storage/
│   └── memory/               # 短期记忆（滑动窗口 40 条消息）
└── utils/                    # 内置工具函数
config/
└── agent_llm_config.json     # LLM 模型配置 + 系统提示词 + 工具列表
docs/
└── SKILL.md                  # 日报 Skill 定义文档
```

## 技术栈

- **Agent 框架**：LangChain + LangGraph 1.0
- **大模型**：doubao-seed-2-0-pro（豆包旗舰模型）
- **联网搜索**：coze-coding-dev-sdk Web Search
- **对象存储**：S3 兼容存储（coze-coding-dev-sdk Storage）
- **邮件推送**：IMAP/SMTP（QQ 邮箱）
- **定时调度**：APScheduler
- **依赖管理**：uv

## 日报网页效果

- 深色渐变 Hero Banner + 日期 + 统计卡片
- 政策变动（紫色系）与行业动态（蓝色系）视觉区分
- 每条信息包含：标题、摘要、来源链接、发布时间
- 响应式布局，移动端适配

## 当前能力边界

| ✅ 已支持 | ❌ 暂不支持 |
|-----------|-------------|
| Amazon 公开政策变动搜索 | Amazon Seller Central 私有数据 |
| 跨境电商行业新闻搜索 | 竞品监控 / 价格追踪 |
| HTML 网页日报生成 | 实时交互仪表盘 |
| 邮件推送 + 每日定时触发 | 多平台数据（Shopify / TikTok Shop）|

## 本地运行

```bash
# 运行流程
bash scripts/local_run.sh -m flow

# 运行节点
bash scripts/local_run.sh -m node -n node_name

# 启动 HTTP 服务
bash scripts/http_run.sh -m http -p 5000
```

