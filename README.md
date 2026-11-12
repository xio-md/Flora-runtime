# Flora runtime

Flora 的二进制交付入口，供独立 Python 程序和 GeoPhys 使用。渲染核心在私有仓库构建；
本仓库保存安装脚本、版本清单和示例，wheel 通过 [Releases](https://github.com/xio-md/Flora-runtime/releases) 分发。

有 Flora 源码访问权限的开发者，建议 [拉取主线并自行编译](https://github.com/SCAILab-USTC/Flora#构建)，以便及时获得渲染和烘焙修复。下方的 wheel 适合固定版本复现和无源码访问权限的用户。

Windows 正式版 [**0.1.1**](https://github.com/xio-md/Flora-runtime/releases/tag/v0.1.1)
已将所需 VC++ DLL 随 wheel 打包，无需另外安装运行库。

Windows 预发布版 [**0.1.3rc1**](https://github.com/xio-md/Flora-runtime/releases/tag/v0.1.3rc1)
支持 GeoPhys 的自动光照、反射探针和 DLSS RR 预览。安装命令见 [Windows DLSS RR 预发布](#windows-dlss-rr-预发布)。

Linux 测试版 [**0.1.2rc1**](https://github.com/xio-md/Flora-runtime/releases/tag/v0.1.2rc1)
面向 **Ubuntu 24.04 x64 / CPython 3.13**。已通过编译、安装和原生导入检查，
GPU 渲染/深度/VLM 尚待实机验收，Linux GPU 共享功能暂不支持。
安装和测试步骤见 [Linux 测试指南](LINUX_TESTING.md)。

| Windows 正式版支持范围 | 要求 |
| --- | --- |
| 系统 / Python | Windows 10/11 x64，CPython 3.13 常规 GIL 版本 |
| GPU | 支持 Vulkan ray query 的 GPU 和已安装的驱动；本机验证为 NVIDIA |
| VC++ 运行库 | 已包含在 wheel 内，无需用户另行下载安装 |
| Python 依赖 | NumPy，安装时由 pip 解析 |
| GeoPhys 合同 | `geophys.flora_adapter.v4`，需包含安装包自动发现功能的 GeoPhys 版本 |

无需 Flora 源码、Visual Studio、CMake、Vulkan SDK 或 VC++ Redistributable，
无需手动复制 DLL 或配置 PATH。显卡驱动和 Windows 自带系统组件由用户环境提供。
当前不提供 macOS、其他 Python ABI 或 free-threaded Python 的二进制。
Linux 测试包仅面向上述 Ubuntu 版本，不是通用 manylinux 包。

## Windows 安装

在要使用 Flora 的 Python 环境中执行一条标准 pip 命令，无需克隆本仓库：

```powershell
python -m pip install -r https://raw.githubusercontent.com/xio-md/Flora-runtime/main/requirements.txt
```

清单固定版本、wheel URL 和 SHA-256；pip 自动下载、校验和安装整个包，并解析 NumPy 依赖。
也可以直接安装指定版本：

```powershell
python -m pip install https://github.com/xio-md/Flora-runtime/releases/download/v0.1.1/flora_render-0.1.1-cp313-cp313-win_amd64.whl
```

已下载 wheel 时，也可以本地安装：

```powershell
python -m pip install .\dist\0.1.1\flora_render-0.1.1-cp313-cp313-win_amd64.whl
```

完全离线时，把 Flora wheel 和所需 NumPy wheel 放在同一目录，增加
`--no-index --find-links .\dist\0.1.1`。回退版本只需安装对应旧 wheel，不覆盖已有 Release 附件。

最短形式 `pip install flora-render` 需要另行把同一 wheel 发布到所控制的 PyPI 项目。
目前仅通过 GitHub Releases 发布；请使用上面的明确 URL，不依赖 PyPI 上的同名项目。
`install.py` 保留为 Windows 辅助工具，普通使用无需运行。

### Windows DLSS RR 预发布

在运行 GeoPhys 的 Windows x64 / CPython 3.13 环境中安装并检查版本。

```powershell
python -m pip install -r https://github.com/xio-md/Flora-runtime/releases/download/v0.1.3rc1/requirements.txt
python -I -m flora_runtime
```

输出应显示 `version` 为 `0.1.3rc1` 和 `capabilities.dlss_rr` 为 `true`。
DLSS RR 需要支持该功能的 NVIDIA RTX 显卡、兼容驱动和 Forge CUDA。
窗口预览和无头出图见 [GeoPhys 使用指南](https://github.com/SCAILab-USTC/GeoPhys/blob/main/docs/guides/flora-usd-preview.md#快速开始)。

## Linux 测试版安装

在 Ubuntu 24.04 x64 的常规 Python 3.13 环境中执行：

```bash
python3.13 -m pip install -r https://raw.githubusercontent.com/xio-md/Flora-runtime/v0.1.2rc1/requirements-linux.txt
```

建议先建立虚拟环境，完整命令和 GPU 检查见 [Linux 测试指南](LINUX_TESTING.md)。
无需 Vulkan SDK、编译器或私有源码；系统仍需兼容显卡驱动及 Vulkan 运行库。
根目录 `requirements.txt` 继续固定 Windows 正式版；Linux 使用单独的 `requirements-linux.txt`。

## 与 GeoPhys 使用

把 wheel 安装到 **GeoPhys 使用的同一个 Python 环境**。需要自动光照、反射探针或 DLSS RR 时，
使用 [Windows 预发布安装命令](#windows-dlss-rr-预发布)。使用正式版时，按实际位置替换以下 GeoPhys 路径。

```powershell
D:\work\GeoPhys\.venv\Scripts\python.exe -m pip install -r https://raw.githubusercontent.com/xio-md/Flora-runtime/main/requirements.txt
```

然后在 GeoPhys 中：

```python
from visualization.flora import probe_flora_runtime

print(probe_flora_runtime().require().describe())
visualizer = source.build_visualizer(backend="flora")  # source 为已有 GeoPhys 场景
```

无需设置 `GEOPHYS_FLORA_ROOT`。若此前设置过它或 `GEOPHYS_FLORA_MODULE_DIR` /
`GEOPHYS_FLORA_PYTHON_DIR`，它们仍会优先选择开发安装；使用 wheel 前应清除这些旧覆盖值。
同一 Python 进程中切换已加载的原生安装会被拒绝，需要重启该 Python 进程。

## Windows 包含哪些文件

- `flora`、`flora_backend`：可读的 Python 接口和运行时实现。
- `flora_runtime`：安装位置发现、完整性诊断和用户缓存路径。
- `FloraRenderPyNative.pyd`：原生渲染核心，内嵌编译后的着色器。
- `flora-vlm-bake.exe`、`flora-vlm-inspect.exe`、`flora-vlm-delta.exe`：VLM 工具。
- `msvcp140.dll`、`vcruntime140.dll`、`vcruntime140_1.dll`：随包 VC++ 运行库，位于原生模块和工具旁。
- `flora_runtime/licenses/`：Flora、第三方组件及 Microsoft runtime 的对应许可文本。

不包含核心 C++、HLSL、构建树、PDB、内部测试、开发资产、Git 历史或编译器工具。
公开的 Python 实现也位于 wheel 中，无需从私有仓库取得。公开仓库和 Release 可供所有人下载；
GeoPhys 与 Flora 核心仓库的访问权限仍各自独立。

Flora 生成的 cluster 缓存默认写入 `%LOCALAPPDATA%\Flora\cache`，可通过 `FLORA_CACHE_DIR` 覆盖，
不会要求安装目录可写。其他场景和 VLM 输出仍由调用方指定。

可选诊断：`python -I -m flora_runtime` 检查已安装文件；下载示例后运行
`python -I examples/smoke.py`，执行无窗口 RGB、米制深度和 VLM 烘焙检查。

本仓库沿用 Flora 现有 MIT 许可；随包第三方组件及 Microsoft DLL 保留各自许可。
发布维护流程见 [RELEASING.md](RELEASING.md)。
