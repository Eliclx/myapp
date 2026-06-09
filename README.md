# 🏷️ LabelTool - 目标检测标注工具

在大图上画标注框，自动裁剪为小图 + 生成 VOC XML 格式标注文件。支持随机抖动（防过拟合）、类别管理、拖拽打开图片。

## 功能

- 🖼️ 打开大图，鼠标画框标注目标
- 🏷️ 类别管理：添加/选择/双击修改类别
- ✂️ 自动裁剪：每个标注框为中心生成小图 + VOC XML
- 🎲 随机抖动：裁剪中心可偏移，数据增强防过拟合（底部栏可直接调）
- 🖱️ 拖拽打开图片、滚轮缩放、右键/中键拖动画布
- 🔍 鼠标悬停显示坐标 + 像素值（RGB）
- ⚙️ 可配置裁剪尺寸、抖动范围、输出目录（带浏览按钮）
- 📦 PyInstaller 一键打包，GitHub Actions 双平台构建

## 开发

```bash
conda activate py_env
python src/main.py
```

## 测试

```bash
conda activate py_env
cd src && python -m pytest test_all.py -v
```

## 本机打包（Linux）

```bash
conda activate py_env
pyinstaller myapp.spec
# 产物在 dist/myapp/ 目录
```

## 跨平台打包（Windows + Linux）

推 tag 触发 GitHub Actions 自动构建：

```bash
git tag v1.0.0
git push origin v1.0.0
```

到 GitHub Releases 页面下载对应平台压缩包。

## 项目结构

```
myapp/
├── src/
│   ├── main.py              # 应用入口
│   ├── main_window.py       # 主窗口：组装所有组件
│   ├── annotation.py        # 数据模型：BBox + AnnotationData
│   ├── image_view.py        # 大图交互视图：缩放、拖动、画框
│   ├── label_panel.py       # 左侧类别管理面板
│   ├── export_engine.py     # 导出引擎：裁剪小图 + VOC XML
│   ├── settings_dialog.py   # 导出设置对话框 + 快捷参数栏
│   └── test_all.py          # 测试套件（纯逻辑 + GUI 冒烟）
├── myapp.spec                # PyInstaller 配置
├── .github/workflows/
│   └── build.yml             # CI: 双平台自动打包
├── requirements.txt          # 依赖
└── README.md
```

## 依赖

- Python 3.11
- PyQt5 >= 5.15
- OpenCV (opencv-python-headless) >= 4.5
- lxml >= 4.9

## 操作说明

| 操作 | 快捷键 |
|---|---|
| 画标注框 | 左键拖拽 |
| 开始标注（十字光标） | W |
| 拖动画布 | 右键 / 中键 |
| 缩放 | 滚轮 |
| 适配视口 | F |
| 取消画框 | Esc |
| 上一张图片 | A |
| 下一张图片 | D |
| 删除选中框 | Delete / Backspace |
| 修改类别 | 双击标注框 |
| 打开图片 | Ctrl+O |
| 打开文件夹 | Ctrl+Shift+O |
| 导出标注 | Ctrl+S |
| 打开设置 | Ctrl+, |
| 打开图片（拖拽） | 拖拽文件到窗口 |
