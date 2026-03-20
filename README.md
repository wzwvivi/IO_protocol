# 接口代码生成平台

基于 Web 的 ARINC429 接口代码生成平台，支持**设备树管理**、**多用户协作**、**版本控制**，可视化编辑协议定义并自动生成 Python 和 C 解析代码。

## 功能特性

### 核心功能
- 🌲 **设备树管理**：支持层级设备结构（系统 → 子系统 → 设备），从目录自动导入设备树
- 🎯 **可视化协议编辑**：通过 Web 界面直观地定义 ARINC429 Label
- 📊 **位图显示**：32位数据字的可视化位定义表
- 🔧 **多种字段类型**：支持 BNR 数值、离散位、多位枚举字段
- 🐍 **Python 代码生成**：生成完整的 Python 解析脚本，支持 Excel 导出
- 📝 **C 代码生成**：生成标准 C 语言解析器

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
IO_protocol/
└── generator/
    ├── app.py                    # Flask 应用入口
    ├── device_manager.py         # 设备树管理模块
    ├── models.py                 # 用户认证模块
    ├── database.py               # SQLite 数据库操作
    ├── generator_core.py         # 代码生成核心模块
    ├── arinc429_runtime.py       # ARINC429 运行时库
    ├── templates/                # HTML 模板
    │   ├── index.html            # 主界面
    │   ├── login.html            # 登录页面
    │   └── ...
    ├── data/                     # 数据目录
    │   └── arinc429.db           # SQLite 数据库（包含完整设备树）
    ├── output/                   # 生成代码输出目录
    ├── Dockerfile                # Docker 镜像配置
    ├── docker-compose.yml        # Docker Compose 配置
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

## 常见问题

### Q: 数据库在哪里？
A: 数据库文件位于 `data/arinc429.db`，已包含完整的设备树和示例数据。

### Q: 如何备份数据？
A: 复制 `data/arinc429.db` 文件即可完整备份所有数据。

### Q: Docker 部署后数据会丢失吗？
A: 不会。`data/` 目录已挂载到宿主机，数据持久化保存。

### Q: 如何重置到初始状态？
A: 删除 `data/arinc429.db` 后重新运行 `python build_full_db.py`。

---

## 技术栈

- **后端**：Python 3.11, Flask
- **数据库**：SQLite（内置，无需安装）
- **前端**：HTML5, CSS3, JavaScript (原生)
- **代码生成**：Jinja2 模板引擎
- **容器化**：Docker, Docker Compose

---

## 许可证

MIT License

## 联系方式

- GitHub: https://github.com/wzwvivi/IO_protocol
