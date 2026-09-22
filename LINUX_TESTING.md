# Linux 0.1.2rc1 测试指南

[下载预发布版本 v0.1.2rc1](https://github.com/xio-md/Flora-runtime/releases/tag/v0.1.2rc1)。
本次提供已在 Ubuntu 云端构建的原始候选 wheel，不包含 Flora 核心源码。

## 环境要求

- Ubuntu **24.04 x64**，glibc 2.39 或更新；当前运行时会检查 Ubuntu 版本。
- 常规 **CPython 3.13**，不支持 free-threaded Python、ARM64 或其他 Python ABI。
- 进行 GPU 测试时，需要支持 Vulkan ray query 的显卡及已安装的显卡驱动。
- 系统运行库：`libstdc++6`、`libvulkan1` 和 X11 库，通常随系统/驱动安装。

不需要 Vulkan SDK、CMake、C++ 编译器或 Flora 私有仓库权限。NumPy 由 pip 自动安装。
本包是针对 Ubuntu 24.04 构建的 `linux_x86_64` wheel，不是 manylinux 通用发行包。
如果缺少系统运行库，可在目标 Ubuntu 机器上安装：

```bash
sudo apt-get update
sudo apt-get install libstdc++6 libvulkan1 libx11-6 libxext6 libxrandr2 libxinerama1 libxcursor1 libxi6
```

这条命令不会安装显卡厂商驱动；显卡驱动需要由目标机器正常提供。

## 安装

使用已有的 Python 3.13 创建虚拟环境。若 `python3.13` 不存在，需要先准备对应的 Python 环境，
不能直接用其他 Python 版本替代。无需克隆仓库：

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r https://raw.githubusercontent.com/xio-md/Flora-runtime/v0.1.2rc1/requirements-linux.txt
.venv/bin/python -m pip check
.venv/bin/python -I -m flora_runtime
```

清单固定 wheel 版本、下载地址和 SHA-256。离线时直接安装已下载的 wheel，
同时自行准备匹配的 NumPy wheel。

## 测试

下载随版本提供的独立测试脚本：

```bash
curl -fL https://github.com/xio-md/Flora-runtime/releases/download/v0.1.2rc1/smoke_installed.py -o flora_smoke.py
.venv/bin/python -I flora_smoke.py
```

上面的检查只验证包完整性、原生模块导入和三个 VLM 工具的启动，不会使用 GPU。
在配好驱动的机器上，继续运行真实 GPU 测试：

```bash
.venv/bin/python -I flora_smoke.py --gpu
```

脚本不打开窗口，自动生成小场景并检查：红色表面 RGB、约 3 米的深度、VLM 烘焙和探针有效性。
成功会输出 `PASS` 和 JSON 结果。缓存默认写入 `~/.cache/Flora/cache`，
设置了 `XDG_CACHE_HOME` 时使用对应目录，也可通过 `FLORA_CACHE_DIR` 指定。
不用手动复制 `.so`、调整工具执行权限或配置开发目录。

如需核对所有 Release 附件，将附件下载到同一目录后运行 `sha256sum -c SHA256SUMS.txt`。

## 已验证与已知限制

- 已通过 Ubuntu 24.04 / CPython 3.13.15 的原生编译、25 项打包测试、依赖审计、
  独立虚拟环境安装、原生导入和 VLM 工具 `--help` 检查。
- **发布前未在 Linux GPU 上验证 RGB、深度或实际 VLM 烘焙**，本版本用于收集这部分测试结果。
- **Linux 的 CUDA/Vulkan 共享变换和共享画面尚未实现**。不要使用 `gpu_direct` 模式。
- GeoPhys 自身及其适配代码不包含在此 wheel 中。本轮建议先运行上述 Flora 独立测试；
  GeoPhys 的 Linux 集成尚未验收，不能把独立测试通过视为集成通过。

包内包括 `flora`、`flora_backend`、`flora_runtime`、`FloraRenderPyNative.so` 和三个 VLM 可执行工具，
着色器已经编译并内嵌。Linux 包不包含 Windows DLL。

若测试失败，请保留完整终端报错，并附上 `cat /etc/os-release`、Python 版本、GPU 型号和驱动版本。
