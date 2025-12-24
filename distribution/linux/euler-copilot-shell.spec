%global pypi_name witty-assistant
%global shortcut_name witty
%global debug_package %{nil}

Name:           euler-copilot-shell
Version:        2.0.0
Release:        3%{?dev_timestamp:.dev%{dev_timestamp}}%{?dist}
Summary:        Witty Assistant 智能命令行工具集
License:        MulanPSL-2.0
URL:            https://gitee.com/openeuler/euler-copilot-shell
Source0:        %{name}-%{version}.tar.gz

ExclusiveArch:  x86_64 aarch64 riscv64 loongarch64

BuildRequires:  python3-devel python3-virtualenv python3-pip
BuildRequires:  gettext

%description
Witty Assistant 智能命令行工具集，包含 Witty Assistant 命令行程序和部署安装工具。

# 智能命令行助手子包
%package -n witty-assistant
Summary:        Witty Assistant 命令行助手
Requires:       glibc

# 替换原来的 euler-copilot-shell 包
Obsoletes:      euler-copilot-shell < %{version}-%{release}
Provides:       euler-copilot-shell = %{version}-%{release}
# 替换原来的 openeuler-intelligence-cli 包
Obsoletes:      openeuler-intelligence-cli < %{version}-%{release}
Provides:       openeuler-intelligence-cli = %{version}-%{release}

%description -n witty-assistant
Witty Assistant 是一个智能命令行程序。
它允许用户输入命令，通过集成大语言模型提供命令建议，帮助用户更高效地使用命令行。

# 部署安装工具子包
%package -n witty-assistant-installer
Summary:        Witty Assistant 部署安装脚本
Requires:       wget
Requires:       python3-aiohttp
Requires:       python3-requests
BuildArch:      noarch

# 替换原来的 openeuler-intelligence-installer 包
Obsoletes:      openeuler-intelligence-installer < %{version}-%{release}
Provides:       openeuler-intelligence-installer = %{version}-%{release}

%description -n witty-assistant-installer
Witty Assistant 部署安装工具包，包含部署脚本和相关资源文件。

%prep
%autosetup -n %{name}-%{version}

%build
# 创建虚拟环境
python3 -m venv %{_builddir}/venv
source %{_builddir}/venv/bin/activate

# 升级 pip 并安装 uv
pip install --upgrade pip
pip install uv

# 使用 uv 安装项目依赖
uv pip install .

# 安装 PyInstaller（通过 uv 保证环境一致）
uv pip install pyinstaller

# 编译国际化翻译文件
./scripts/tools/i18n-manager.sh compile

# 使用虚拟环境中的 PyInstaller 创建单一可执行文件
pyinstaller --noconfirm \
            --distpath dist \
            witty-assistant.spec

# 退出虚拟环境
deactivate

%install
# 安装智能命令行工具
mkdir -p %{buildroot}%{_bindir}
install -m 0755 dist/%{pypi_name} %{buildroot}%{_bindir}/%{pypi_name}

# 创建快捷链接
ln -sf %{pypi_name} %{buildroot}%{_bindir}/%{shortcut_name}

# 安装部署脚本和资源
mkdir -p %{buildroot}/usr/lib/witty-assistant/{scripts,resources}
mkdir -p %{buildroot}%{_bindir}

# 复制部署脚本和资源
install -m 755 scripts/deploy/deploy.sh %{buildroot}/usr/lib/witty-assistant/scripts/deploy
cp -r scripts/deploy/0-one-click-deploy scripts/deploy/1-check-env scripts/deploy/2-install-dependency scripts/deploy/3-install-server scripts/deploy/4-other-script scripts/deploy/5-resource %{buildroot}/usr/lib/witty-assistant/scripts/
chmod -R +x %{buildroot}/usr/lib/witty-assistant/scripts/

# 创建可执行文件的符号链接
ln -sf /usr/lib/witty-assistant/scripts/deploy %{buildroot}%{_bindir}/witty-manager

%files -n witty-assistant
%license LICENSE
%doc README.md
%{_bindir}/%{pypi_name}
%{_bindir}/%{shortcut_name}

%files -n witty-assistant-installer
%license LICENSE
%doc scripts/deploy/安装部署手册.md
/usr/lib/witty-assistant
%{_bindir}/witty-manager

%postun -n witty-assistant
if [ $1 -eq 0 ]; then
# 卸载时清理用户缓存和配置文件
for home in /root /home/*; do
    cache_dir="$home/.cache/witty/logs"
    if [ -d "$cache_dir" ]; then
        rm -rf "$cache_dir"
    fi
    config_dir="$home/.config/witty"
    if [ -d "$config_dir" ]; then
        rm -rf "$config_dir"
    fi
done
rm -f /etc/witty-assistant/config-template.json
elif [ $1 -ge 1 ]; then
# 升级时清理日志
for home in /root /home/*; do
    cache_dir="$home/.cache/witty/logs"
    if [ -d "$cache_dir" ]; then
        rm -rf "$cache_dir"
    fi
done
fi

%postun -n witty-assistant-installer
if [ $1 -eq 0 ]; then
# 卸载时清理安装器相关文件
rm -f /etc/euler_Intelligence_install*
rm -f /usr/lib/witty-assistant/scripts
fi

%changelog
* Tue Dec 23 2025 openEuler <contact@openeuler.org> - 2.0.0-3
- feat: Add Witty Assistant welcome screen & LOGO
- refactor: Improve Markdown rendering performance in TUI

* Fri Dec 12 2025 openEuler <contact@openeuler.org> - 2.0.0-2
- chore: Update project name to "Witty Assistant"
- chore: Update program short name to "witty"

* Mon Dec 08 2025 openEuler <contact@openeuler.org> - 2.0.0-1
- Major update to version 2.0.0

* Wed Dec 03 2025 openEuler <contact@openeuler.org> - 0.10.2-7
- cli: Add support for select text in LLM response TUI

* Thu Nov 13 2025 openEuler <contact@openeuler.org> - 0.10.2-6
- installer: Add support for package name and alternative package name formats
- cli: Fix TUI keyboard interaction issue in some environments

* Tue Nov 11 2025 openEuler <contact@openeuler.org> - 0.10.2-5
- Fix detecting el version issue in deployment script

* Tue Nov 04 2025 openEuler <contact@openeuler.org> - 0.10.2-4
- Fix timeout when executing complex MCP tasks
- Feature: Add login through browser (requires proper desktop environment)

* Wed Oct 29 2025 openEuler <contact@openeuler.org> - 0.10.2-3
- Fix issue where failing to fetch mcp when creating agent with oi-manager

* Sat Oct 25 2025 openEuler <contact@openeuler.org> - 0.10.2-2
- Add internationalization support (currently supports English and Simplified Chinese)
- Fix issue where settings page may reopen multiple times

* Mon Oct 20 2025 openEuler <contact@openeuler.org> - 0.10.2-1
- 修复后端可用性校验，优化令牌格式验证

* Tue Sep 30 2025 openEuler <contact@openeuler.org> - 0.10.1-5
- 支持通过环境变量 OI_SKIP_SSL_VERIFY / OI_SSL_VERIFY 控制 OpenAI 客户端 SSL 验证

* Wed Sep 17 2025 openEuler <contact@openeuler.org> - 0.10.1-4
- 修复 Token 计算器中类型注解的兼容性问题
- 优化部署脚本中下载资源文件的逻辑

* Tue Sep 16 2025 openEuler <contact@openeuler.org> - 0.10.1-3
- 优化 LLM 和 Embedding 配置验证逻辑
- 添加部署后修改 LLM 和 Embedding 配置功能

* Thu Sep 11 2025 openEuler <contact@openeuler.org> - 0.10.1-2
- 卸载时清理用户缓存和配置文件

* Wed Sep 10 2025 openEuler <contact@openeuler.org> - 0.10.1-1
- 支持切换 MCP 自动执行模式
- 简化安装器命令为 oi-manager

* Tue Sep 09 2025 openEuler <contact@openeuler.org> - 0.10.0-4
- 优化安装脚本：添加内核版本检查和架构支持，优化 MongoDB 和 MinIO 安装逻辑
- 优化 MCP 交互相关 TUI 样式

* Thu Sep 04 2025 openEuler <contact@openeuler.org> - 0.10.0-3
- 部署功能新增支持全量部署（含 RAG、Web）
- 允许构建 riscv64 loongarch64 版本

* Thu Aug 28 2025 openEuler <contact@openeuler.org> - 0.10.0-2
- 新增 openEuler Intelligence 部署功能 TUI
- 新增选择默认 Agent 功能

* Wed Aug 13 2025 openEuler <contact@openeuler.org> - 0.10.0-1
- 重构为子包形式：openeuler-intelligence-cli 和 openeuler-intelligence-installer
- openeuler-intelligence-cli 替换原 euler-copilot-shell 包
- 新增 openeuler-intelligence-installer 子包，包含部署安装脚本

* Thu Jun 26 2025 Wenlong Zhang <zhangwenlong@loongson.cn> - 0.9.2-12
- enable loongarch64 build

* Fri Jun 20 2025 misaka00251 <liuxin@iscas.ac.cn> - 0.9.2-11
- Enable riscv64 build

* Tue May 20 2025 Hongyu Shi <shywzt@iCloud.com> - 0.9.2-10
- Fix OpenAI backend issue

* Mon Apr 07 2025 Hongyu Shi <shywzt@iCloud.com> - 0.9.2-9
- Fix OpenAI backend issue

* Wed Mar 12 2025 Hongyu Shi <shywzt@iCloud.com> - 0.9.2-8
- Set default backend to openai

* Mon Mar 10 2025 Hongyu Shi <shywzt@iCloud.com> - 0.9.2-7
- Update build 7

* Fri Feb 28 2025 Hongyu Shi <shywzt@iCloud.com> - 0.9.2-6
- Update build 6

* Mon Feb 24 2025 Hongyu Shi <shywzt@iCloud.com> - 0.9.2-5
- Add euler-copilot-shell
