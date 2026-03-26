# 接口代码生成平台

基于 Web 的 ARINC429 接口代码生成平台，支持**设备树管理**、**多用户协作**、**版本控制**，可视化编辑协议定义并自动生成 Python 和 C 解析代码。

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

### 协作功能
- 👥 **用户系统**：支持用户注册、登录、个人资料管理
- 🔐 **权限管理**：管理员可管理用户、重置密码
- 📦 **版本管理**：设备配置支持版本历史、变更追踪、快照回滚
- 💾 **配置持久化**：每个用户独立配置，自动保存，重启不丢失
- 🐳 **Docker 部署**：一键部署，无需复杂配置

---

## 快速开始

### 方式一：Docker 部署（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/wzwvivi/IO_protocol.git
cd IO_protocol

# 2. 启动服务
docker-compose up -d

# 3. 访问平台
# 打开浏览器访问 http://localhost:5001
# 默认管理员账户: admin / admin123
```

### 方式二：本地运行

**Windows:**
```cmd
setup.bat
```

**Linux/Mac:**
```bash
chmod +x setup.sh
./setup.sh
```

或手动运行：
```bash
pip install -r requirements.txt
python app.py
# 访问 http://localhost:5001
```

---

## 项目结构

```
IO_protocol/
├── app.py                    # Flask 应用入口
├── device_manager.py         # 设备树管理模块
├── models.py                 # 用户认证模块
├── database.py               # SQLite 数据库操作
├── generator_core.py         # 代码生成核心模块
├── arinc429_runtime.py       # ARINC429 运行时库
├── document_extractors.py    # 文档解析器
├── llm_parser.py             # LLM 智能解析模块
├── protocol_importer.py      # 协议导入模块
├── templates/                # HTML 模板
│   ├── index.html            # 主界面
│   ├── login.html            # 登录页面
│   ├── register.html         # 注册页面
│   ├── profile.html          # 个人资料页面
│   └── admin.html            # 管理员页面
├── data/                     # 数据目录
│   └── arinc429.db           # SQLite 数据库（包含完整设备树）
├── output/                   # 生成代码输出目录
├── Dockerfile                # Docker 镜像配置
├── docker-compose.yml        # Docker Compose 配置
├── entrypoint.py             # Docker 启动脚本
├── build_full_db.py          # 数据库构建脚本
└── requirements.txt          # Python 依赖
```

---

## 数据说明

### 预置数据

克隆后数据库 `data/arinc429.db` 已包含：

- ✅ **完整设备树**：13个顶级系统（ATA21-92），33个叶子设备
- ✅ **多版本支持**：部分设备包含多个协议版本（如 32-3-转弯控制单元的 V5.0）
- ✅ **示例 Labels**：32-3-转弯控制单元已包含 21 个完整的 Label 定义
- ✅ **默认管理员**：admin / admin123

### 数据持久化

| 场景 | 数据是否保留 |
|------|-------------|
| 刷新网页 | ✓ 保留 |
| 重启 Docker | ✓ 保留 |
| 重新构建镜像 | ✓ 保留 |
| 删除并重新克隆仓库 | ✓ 恢复到初始状态 |

---

## 使用说明

### 1. 设备树管理

平台支持层级设备树结构：

```
ATA32-起落架系统/
├── 32-1-刹车控制单元/
├── 32-2-收放控制单元/
└── 32-3-转弯控制单元/
    └── 转弯系统ARINC429通讯协议-V5.0 (21个Labels)
```

### 2. 版本管理

- 每次保存会创建新版本（V5.0 → V6.0 → V7.0）
- 旧版本自动保存到历史记录
- 可随时查看和对比历史版本

### 3. 生成代码

1. 选择目标设备
2. 点击 "生成 Python 脚本" 或 "生成 C 代码"
3. 下载生成的代码包

---

## 默认账户

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | 管理员 |

⚠️ **首次部署后请及时修改管理员密码！**

---

## ARINC429 协议说明

### 32位数据字格式

| 位号 | 名称 | 说明 |
|------|------|------|
| 1-8 | Label | 标签（八进制，位反序） |
| 9-10 | SDI | 源/目标标识符 |
| 11-29 | Data | 数据域 |
| 30-31 | SSM | 状态矩阵 |
| 32 | P | 奇校验位 |

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

支持的 LLM 提供商：
- OpenAI（GPT-4o, GPT-4, GPT-3.5-turbo）
- Azure OpenAI
- 任何兼容 OpenAI API 的服务

如不配置 LLM，系统将使用纯规则解析，需要更多人工校正。

---

## 部署指南

### Docker 部署（推荐）

```bash
# 构建并启动
docker-compose up -d --build

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 手动部署

1. 确保 Python 3.11+ 已安装
2. 安装依赖：`pip install -r requirements.txt`
3. 运行应用：`python app.py`

### 重要提示

- 数据库文件 `data/arinc429.db` 已包含在仓库中，克隆后即可使用
- Docker 部署时，数据目录会自动挂载，数据持久化保存
- 如需重置数据库，运行 `python build_full_db.py --reset`

---

## 常见问题

### Q: 数据库在哪里？
A: 数据库文件位于 `data/arinc429.db`，已包含完整的设备树和示例数据。

### Q: 如何备份数据？
A: 复制 `data/arinc429.db` 文件即可完整备份所有数据。

### Q: Docker 部署后数据会丢失吗？
A: 不会。`data/` 目录已挂载到宿主机，数据持久化保存。

### Q: 如何重置到初始状态？
A: 删除 `data/arinc429.db` 后重新运行 `python build_full_db.py`。

### Q: 协议文件自动解析准确吗？
A: 解析结果需要人工审核。配置 LLM 后准确率会显著提高。复杂的位定义可能需要手动调整。

### Q: 部署到新服务器后点击设备报 404 错误？
A: 这通常是因为数据库文件未正确部署。请确保：
1. `data/arinc429.db` 文件存在
2. 如果使用 Docker，确保数据卷正确挂载
3. 可以运行 `python build_full_db.py` 重新初始化数据库

---

## 技术栈

- **后端**：Python 3.11, Flask 3.0
- **数据库**：SQLite（内置，无需安装）
- **前端**：HTML5, CSS3, JavaScript (原生)
- **代码生成**：Jinja2 模板引擎
- **容器化**：Docker, Docker Compose
- **AI 解析**：支持 OpenAI API 兼容的 LLM

---

## 更新日志

### v1.1.0 (2026-03-25)
- 修复：数据库文件现在包含在 Git 仓库中，解决部署后设备树为空的问题
- 改进：更新 .gitignore 配置，确保数据库文件被正确追踪
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
