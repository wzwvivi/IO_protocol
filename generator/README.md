# 接口代码生成平台

基于 Web 的 ARINC429 接口代码生成平台，支持**设备树管理**、**多用户协作**、**Git 版本控制**，可视化编辑协议定义并自动生成 Python 和 C 解析代码。

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Flask](https://img.shields.io/badge/Flask-3.0-green)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)

## 功能特性

### 核心功能
- 🌲 **设备树管理**：支持层级设备结构（系统 → 子系统 → 设备），从目录自动导入设备树
- 🎯 **可视化协议编辑**：通过 Web 界面直观地定义 ARINC429 Label
- 📊 **位图显示**：32位数据字的可视化位定义表
- 🔧 **多种字段类型**：支持 BNR 数值、离散位、多位枚举字段
- 🐍 **Python 代码生成**：生成完整的 Python 解析脚本，支持 Excel 导出
- 📝 **C 代码生成**：生成标准 C 语言解析器
- 📄 **协议文件自动解析**：上传 Excel/Word 协议文档，AI 自动识别 Label 定义

### 版本管理（Git 存储）
- 📦 **Git 原生存储**：协议数据以 JSON 文件形式存储在 Git 仓库中
- 🏷️ **按 ATA 系统分仓库**：每个 ATA 系统独立仓库，便于管理和追踪
- 📜 **完整版本历史**：每次保存自动创建新版本，支持查看、对比、恢复历史版本
- 🔒 **设备级锁定**：防止多人同时编辑同一设备
- ⚡ **乐观锁机制**：检测并发冲突，避免数据覆盖

### 协作功能
- 👥 **用户系统**：支持用户注册、登录、个人资料管理
- 🔐 **权限管理**：管理员(admin)、操作员(operator)、查看者(viewer) 三级权限
- 💾 **配置持久化**：每个用户独立配置，自动保存，重启不丢失
- 🐳 **Docker 部署**：一键部署，无需复杂配置

---

## 快速开始

### 方式一：Docker 部署（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/wzwvivi/IO_protocol.git
cd IO_protocol/generator

# 2. 启动服务
docker-compose up -d

# 3. 访问平台
# 打开浏览器访问 http://localhost:5001
# 默认管理员账户: admin / admin123
```

### 方式二：本地运行

**Windows:**
```cmd
cd generator
setup.bat
```

**Linux/Mac:**
```bash
cd generator
chmod +x setup.sh
./setup.sh
```

或手动运行：
```bash
cd generator
pip install -r requirements.txt
python app.py
# 访问 http://localhost:5001
```

---

## 项目结构

```
IO_protocol/generator/
├── app.py                    # Flask 应用入口
├── device_manager.py         # 设备树管理模块
├── models.py                 # 用户认证模块
├── database.py               # SQLite 数据库操作（用户管理、设备索引）
├── generator_core.py         # 代码生成核心模块
├── arinc429_runtime.py       # ARINC429 运行时库
├── document_extractors.py    # 文档解析器
├── llm_parser.py             # LLM 智能解析模块
├── protocol_importer.py      # 协议导入模块
├── git_storage/              # Git 存储模块
│   ├── __init__.py           # 模块入口
│   ├── config.py             # 配置和数据结构定义
│   ├── repo_manager.py       # Git 仓库管理
│   ├── device_storage.py     # 设备数据存储
│   ├── version_manager.py    # 版本管理核心
│   ├── lock_manager.py       # 设备锁管理
│   ├── read_adapter.py       # 读取适配器
│   ├── save_adapter.py       # 保存适配器
│   └── db_exporter.py        # 数据库导出工具
├── git_repos/                # Git 存储仓库（协议版本数据）
│   ├── protocol-ata21/       # ATA21 系统仓库
│   ├── protocol-ata32/       # ATA32 系统仓库
│   ├── protocol-default/     # 默认仓库（未分类设备）
│   └── ...
├── templates/                # HTML 模板
│   ├── index.html            # 主界面
│   ├── login.html            # 登录页面
│   ├── register.html         # 注册页面
│   ├── profile.html          # 个人资料页面
│   └── admin_users.html      # 用户管理页面
├── data/                     # 数据目录
│   └── arinc429.db           # SQLite 数据库（用户、设备索引）
├── output/                   # 生成代码输出目录
├── Dockerfile                # Docker 镜像配置
├── docker-compose.yml        # Docker Compose 配置
├── entrypoint.py             # Docker 启动脚本
└── requirements.txt          # Python 依赖
```

---

## 数据存储架构

### Git 存储（协议数据）

协议数据使用 Git 仓库存储，按 ATA 系统分仓库：

```
git_repos/
├── protocol-ata32/           # ATA32 起落架系统
│   ├── repo_meta.json        # 仓库元数据
│   └── devices/
│       ├── ata32_32_1/       # 设备: 32-1-刹车控制单元
│       │   ├── device_meta.json
│       │   ├── current/      # 当前版本
│       │   │   ├── protocol.json
│       │   │   └── labels/
│       │   │       ├── 121.json
│       │   │       └── ...
│       │   ├── versions/     # 版本快照
│       │   │   ├── V1.0.json
│       │   │   ├── V2.0.json
│       │   │   └── ...
│       │   └── history/      # 历史记录
│       │       ├── releases.json
│       │       └── saves.json
│       └── ata32_32_3/       # 设备: 32-3-转弯控制单元
│           └── ...
└── protocol-default/         # 默认仓库
```

### SQLite 数据库（索引和用户）

`data/arinc429.db` 用于：
- 用户账户管理
- 设备树索引（快速查询）
- 用户配置存储

---

## 版本管理功能

### 版本历史
- 每次保存自动创建新版本（V1.0 → V2.0 → V3.0）
- 记录变更统计（新增/修改/删除的 Label 数量）
- 保存变更说明和操作人信息

### 版本操作
- **查看历史**：点击版本下拉框查看所有历史版本
- **版本对比**：对比任意两个版本的差异
- **恢复版本**：将历史版本恢复为当前版本
- **删除版本**：删除不需要的历史版本

### 并发控制
- **设备锁**：编辑设备时自动获取锁，防止他人同时编辑
- **乐观锁**：保存时检测是否有他人更新，避免覆盖

---

## 默认账户

| 用户名 | 密码 | 角色 | 权限 |
|--------|------|------|------|
| admin | admin123 | 管理员 | 全部权限 |

### 角色权限说明

| 权限 | 管理员 | 操作员 | 查看者 |
|------|--------|--------|--------|
| 查看设备和协议 | ✓ | ✓ | ✓ |
| 编辑和保存协议 | ✓ | ✓ | ✗ |
| 生成代码 | ✓ | ✓ | ✓ |
| 用户管理 | ✓ | ✗ | ✗ |
| 设备树管理 | ✓ | ✗ | ✗ |

⚠️ **首次部署后请及时修改管理员密码！**

---

## 部署指南

### Docker 部署（推荐）

```bash
cd generator

# 构建并启动
docker-compose up -d --build

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 数据持久化

| 数据类型 | 存储位置 | Docker 挂载 |
|----------|----------|-------------|
| 协议数据 | `git_repos/` | `./git_repos:/app/git_repos` |
| 用户数据 | `data/arinc429.db` | `./data:/app/data` |
| 生成代码 | `output/` | `./output:/app/output` |

### 迁移到新服务器

1. 克隆仓库（包含完整的 `git_repos/` 目录）
2. 启动 Docker：`docker-compose up -d`
3. 所有协议数据和版本历史自动可用

---

## 协议文件自动解析

### 功能说明

平台支持上传 Excel/Word 格式的协议文档，自动识别并提取 ARINC429 Label 定义：

1. 点击设备树旁边的 **"📄解析"** 按钮
2. 上传协议文件（支持 .xlsx, .xls, .docx）
3. 系统自动识别 Label、位定义、数据类型等信息
4. 审核并修正解析结果
5. 确认后入库，自动创建设备和版本

### LLM 配置（可选）

协议解析功能可以使用 AI (LLM) 来提高准确率。如需启用，请在 `docker-compose.yml` 中配置：

```yaml
environment:
  - LLM_API_BASE_URL=https://api.openai.com/v1
  - LLM_API_KEY=your-api-key-here
  - LLM_MODEL=gpt-4o
  - LLM_TIMEOUT=120
```

---

## 常见问题

### Q: 数据存储在哪里？
A: 协议数据存储在 `git_repos/` 目录，用户数据存储在 `data/arinc429.db`。

### Q: 如何备份数据？
A: 复制整个 `git_repos/` 目录和 `data/arinc429.db` 文件即可完整备份。

### Q: Docker 部署后数据会丢失吗？
A: 不会。`git_repos/` 和 `data/` 目录已挂载到宿主机，数据持久化保存。

### Q: 如何查看版本历史？
A: 选择设备后，点击版本下拉框可查看所有历史版本，点击"📜 保存历史"可查看详细变更记录。

### Q: 多人同时编辑会冲突吗？
A: 不会。系统使用设备级锁定，同一时间只有一人可以编辑某个设备。

### Q: 如何恢复到历史版本？
A: 在版本历史中点击"恢复此版本"，系统会将该版本的 Labels 恢复为当前版本，并创建新的版本记录。

---

## 技术栈

- **后端**：Python 3.11, Flask 3.0
- **数据存储**：Git（协议数据）+ SQLite（用户索引）
- **前端**：HTML5, CSS3, JavaScript (原生)
- **代码生成**：Jinja2 模板引擎
- **容器化**：Docker, Docker Compose
- **AI 解析**：支持 OpenAI API 兼容的 LLM

---

## 更新日志

### v2.0.0 (2026-03-25)
- **重大更新**：协议数据存储从 SQLite 迁移到 Git
- 新增：按 ATA 系统分仓库存储
- 新增：完整的版本历史和快照功能
- 新增：版本恢复和对比功能
- 新增：设备级锁定和乐观锁机制
- 新增：详细的变更记录（diff_details）
- 改进：版本下拉列表实时更新
- 改进：XSS 防护（用户输入转义）
- 修复：版本删除的强一致性
- 修复：乐观锁 commit hash 返回问题

### v1.1.0 (2026-03-20)
- 修复：数据库文件现在包含在 Git 仓库中
- 改进：更新 .gitignore 配置
- 新增：添加部署问题的常见问题解答

### v1.0.0
- 初始版本发布
- 完整的设备树管理功能
- 多用户协作支持
- Python/C 代码生成
- 协议文件自动解析

---

## 许可证

MIT License

## 联系方式

- GitHub: https://github.com/wzwvivi/IO_protocol
