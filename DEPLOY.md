# 部署指南

本文档说明如何将项目上传到 GitHub 并在新服务器上部署。

## 一、上传到 GitHub

### 1. 初始化 Git 仓库

在 `generator` 文件夹中打开终端：

```bash
# 进入项目目录
cd generator

# 初始化 Git 仓库
git init

# 添加所有文件
git add .

# 提交
git commit -m "初始版本: ARINC429 接口代码生成平台"
```

### 2. 关联远程仓库

```bash
# 添加远程仓库
git remote add origin https://github.com/wzwvivi/IO_protocol.git

# 推送到 GitHub
git branch -M main
git push -u origin main
```

### 3. 验证上传

访问 https://github.com/wzwvivi/IO_protocol 确认文件已上传。

---

## 二、在新服务器上部署

### 方式一：Docker 部署（推荐）

**前提条件**：服务器已安装 Docker 和 Docker Compose

```bash
# 1. 克隆仓库
git clone https://github.com/wzwvivi/IO_protocol.git
cd IO_protocol

# 2. 启动服务
docker-compose up -d

# 3. 查看日志
docker-compose logs -f

# 4. 访问平台
# http://服务器IP:5001
```

**管理命令**：

```bash
# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 查看状态
docker-compose ps

# 更新代码后重新部署
git pull
docker-compose up -d --build
```

### 方式二：直接运行

**前提条件**：服务器已安装 Python 3.8+

```bash
# 1. 克隆仓库
git clone https://github.com/wzwvivi/IO_protocol.git
cd IO_protocol

# 2. 运行安装脚本
# Linux/Mac:
chmod +x setup.sh
./setup.sh

# Windows:
setup.bat

# 3. 启动服务
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

python app.py
```

---

## 三、数据备份与恢复

### 备份数据

数据库文件位于 `data/arinc429.db`，备份此文件即可：

```bash
cp data/arinc429.db data/arinc429.db.backup
```

### 恢复数据

将备份文件复制回来：

```bash
cp data/arinc429.db.backup data/arinc429.db
```

### Docker 环境备份

```bash
# 备份
docker cp arinc429-generator:/app/data/arinc429.db ./backup/

# 恢复
docker cp ./backup/arinc429.db arinc429-generator:/app/data/
docker-compose restart
```

---

## 四、常见问题

### Q: 端口被占用？

修改 `docker-compose.yml` 中的端口映射：

```yaml
ports:
  - "8080:5000"  # 将 5001 改为其他端口
```

### Q: 如何修改管理员密码？

```bash
python init_users.py reset 新密码
```

### Q: 如何查看所有用户？

```bash
python init_users.py list
```

### Q: 数据库损坏怎么办？

1. 删除 `data/arinc429.db`
2. 重新运行 `python seed_data/init_db.py`
3. 这会创建新的空数据库和默认管理员账户

---

## 五、生产环境建议

### 1. 使用 Nginx 反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 2. 配置 HTTPS

使用 Let's Encrypt 免费 SSL 证书：

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 3. 设置防火墙

```bash
# 只开放必要端口
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

### 4. 定期备份

创建定时任务自动备份数据库：

```bash
# 编辑 crontab
crontab -e

# 添加每日备份任务（每天凌晨 2 点）
0 2 * * * cp /path/to/IO_protocol/data/arinc429.db /path/to/backup/arinc429_$(date +\%Y\%m\%d).db
```

---

## 六、联系方式

- GitHub: https://github.com/wzwvivi/IO_protocol
- Issues: https://github.com/wzwvivi/IO_protocol/issues
