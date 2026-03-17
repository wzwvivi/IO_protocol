# ARINC429 协议解析代码生成器

基于 Web 的 ARINC429 协议解析代码生成平台，支持可视化编辑协议定义并自动生成 Python 和 C 解析代码。

## 功能特性

- 🎯 **可视化协议编辑**：通过 Web 界面直观地定义 ARINC429 Label
- 📊 **位图显示**：32位数据字的可视化位定义表
- 🔧 **多种字段类型**：支持 BNR 数值、离散位、多位枚举字段
- 🐍 **Python 代码生成**：生成完整的 Python 解析脚本，支持 Excel 导出
- 📝 **C 代码生成**：生成标准 C 语言解析器
- 💾 **配置持久化**：自动保存协议配置，重启不丢失
- 🐳 **Docker 部署**：一键部署，无需复杂配置

## 快速开始

### 方式一：Docker 部署（推荐）

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/arinc429-generator.git
cd arinc429-generator

# 启动服务
docker-compose up -d

# 访问 http://localhost:5001
```

### 方式二：本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python app.py

# 访问 http://localhost:5000
```

## 项目结构

```
generator/
├── app.py                    # Flask 应用入口
├── generator_core.py         # 代码生成核心模块
├── arinc429_runtime.py       # ARINC429 运行时库
├── templates/
│   └── index.html            # Web 界面
├── example_protocol_config.json  # 示例协议配置
├── Dockerfile                # Docker 镜像配置
├── docker-compose.yml        # Docker Compose 配置
└── requirements.txt          # Python 依赖
```

## 使用说明

### 1. 创建 Label

1. 点击左侧 "➕ 新建" 按钮
2. 填写 Label 八进制编号（000-377）和信号名称
3. 选择数据方向

### 2. 定义字段

在位定义表中点击对应位号进行编辑：

- **单 bit 离散**：单个位的开关量，如 `1=有效, 0=无效`
- **多位枚举**：多个位组合表示状态，如 `00=故障, 01=正常`
- **BNR 数值**：多位表示数值，需指定分辨率和单位

### 3. 生成代码

1. 在左侧列表中勾选需要的 Label
2. 点击 "生成 Python 脚本" 或 "生成 C 代码"
3. 下载生成的代码包

### 4. 使用生成的代码

**Python 版本**：

```bash
# 解压下载的 zip 包
unzip arinc429_python_package.zip
cd arinc429_python_package

# 交互式解析
python protocol_parser.py

# 批量解析文件
python protocol_parser.py --raw data.txt
```

**C 版本**：

```bash
# 编译
gcc -o parser protocol_parser.c

# 运行
./parser 67FF00B2
./parser B2 00 FF 67
```

## ARINC429 协议说明

### 32位数据字格式

| 位号 | 名称 | 说明 |
|------|------|------|
| 1-8 | Label | 标签（八进制，位反序） |
| 9-10 | SDI | 源/目标标识符 |
| 11-29 | Data | 数据域 |
| 30-31 | SSM | 状态矩阵 |
| 32 | P | 奇校验位 |

### SSM 状态定义

| 值 | 含义 |
|----|------|
| 00 | 故障 |
| 01 | 无效 |
| 10 | 测试 |
| 11 | 正常 |

## 配置文件格式

```json
{
  "protocol_meta": {
    "name": "协议名称",
    "version": "V1.0",
    "description": "协议描述"
  },
  "labels": [
    {
      "label_oct": "115",
      "name": "信号名称",
      "direction": "RDIU -> SCU",
      "discrete_bits": {"12": "字段名: 1=有效, 0=无效"},
      "special_fields": [],
      "bnr_fields": [
        {
          "name": "数值字段",
          "data_bits": [17, 28],
          "sign_bit": 29,
          "resolution": 0.01,
          "unit": "°"
        }
      ]
    }
  ]
}
```

## 技术栈

- **后端**：Python 3.11, Flask
- **前端**：HTML5, CSS3, JavaScript (原生)
- **代码生成**：Jinja2 模板引擎
- **Excel 导出**：openpyxl
- **容器化**：Docker, Docker Compose

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
