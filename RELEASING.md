# 发行维护

核心源码和构建脚本只保存在 Flora 私有仓库。公开仓库不需要访问私有仓库的 token，
也不配置自动拉取私有源码的构建任务。

1. 在私有仓库构建并运行 `tools/release/build_runtime_wheel.py`。脚本调用 Release 构建，
   从显式文件清单生成 wheel，检查 x64 / CPython ABI / DLL 依赖，并附带许可文本。
2. 在本地 `dist/<版本>/` 准备四个文件：wheel、`release.json`、`requirements.txt`、`SHA256SUMS.txt`。
   这个目录被 Git 忽略，二进制不进入 Git 历史。
3. 执行 `python tools/verify_release.py dist/<版本>`，在新虚拟环境安装，运行
   `python -I examples/smoke.py`；再运行匹配 GeoPhys 的无窗口集成资格验证。
4. 将经过验证的 `release.json` 复制为 `releases/<版本>.json`，将生成的 `requirements.txt`
   复制到仓库根目录，更新默认版本和说明。两处 SHA-256 必须与准备上传的 wheel 一致。
5. 经仓库所有者确认后，提交并推送本仓库的文档、脚本和版本清单；创建 `v<版本>` 的
   GitHub Release，上传上述四个文件。Flora 和 GeoPhys 的源码改动在各自仓库处理。
6. Release 实际发布后移除 README 中对应的“尚未上传”说明，并从公开下载地址复验安装。

不要把 Flora 仓库整体复制进来，不要上传源码压缩包、构建目录或符号文件。
wheel 内的 Python 是允许分发的运行时部分；增加 Python 文件、原生依赖或平台时，
先更新私有导出清单并重新验证。不要在同一个版本 tag 下替换不同内容的 wheel。

从 0.1.1 起，构建器从 Visual Studio 的 release x64 redist 目录提取三个未修改的 VC++ DLL，
并审计这些 DLL 的间接依赖。不要从 System32 或非官方 DLL 网站取文件，不打包 debug runtime。
用户不需要运行 `vc_redist.x64.exe`；DLL 随 wheel 安装在 native 模块和 VLM 工具旁。
应用本地运行库的更新由维护者通过新 wheel 分发，构建时应使用受支持且已更新的工具链。

普通用户通过 `pip install -r <公开 requirements.txt URL>` 或直接 wheel URL 安装，
不要求克隆仓库或运行 `install.py`。若以后需要 `pip install flora-render` 的短包名入口，
经所有者授权后把同一 wheel 上传到所控制的 PyPI 项目；不上传核心源码或 sdist。

## 本地校验命令

```powershell
python -m unittest discover -s tests -v
python tools\verify_release.py dist\0.1.1
python -m pip install dist\0.1.1\flora_render-0.1.1-cp313-cp313-win_amd64.whl
python -I examples\smoke.py
```

首版验证仅覆盖 Windows x64／CPython 3.13／本机 NVIDIA Vulkan 的无窗口路径。
新的 GPU、系统和 Python ABI 应分别构建、验证并登记，不能仅重命名 wheel 标签。
