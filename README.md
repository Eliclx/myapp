# myapp

一个用 PyInstaller 打包的跨平台 Python 项目。

## 开发

```bash
conda activate py_env
python src/main.py
```

## 本机打包（Linux）

```bash
conda activate py_env
pyinstaller myapp.spec
# 产物在 dist/ 目录
```

## 跨平台打包（Windows + Linux）

推送到 GitHub 后，GitHub Actions 自动构建双平台产物：

```bash
git push origin main
```

到 GitHub Releases 页面下载对应平台的压缩包。

## 项目结构

```
myapp/
├── src/
│   └── main.py          # 应用入口
├── myapp.spec            # PyInstaller 配置
├── .github/
│   └── workflows/
│       └── build.yml     # CI: 双平台自动打包
├── requirements.txt      # 依赖
└── README.md
```
