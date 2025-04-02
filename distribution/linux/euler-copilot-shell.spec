%global pypi_name eulercopilot

Name:           euler-copilot-shell
Version:        0.9.6
Release:        1%{?dist}
Summary:        智能 Shell 命令行工具
License:        MulanPSL-2.0
URL:            https://gitee.com/openeuler/euler-copilot-shell
Source0:        %{name}-%{version}.tar.gz

# 支持x86_64和aarch64双架构
ExclusiveArch:  x86_64 aarch64

BuildRequires:  python3-devel
BuildRequires:  python3-virtualenv
BuildRequires:  python3-pip

# 运行时不再需要Python依赖，因为已经被打包到可执行文件中
Requires:       glibc

%description
EulerCopilot 智能 Shell 是一个智能命令行程序。
它允许用户输入命令，通过集成大语言模型提供命令建议，帮助用户更高效地使用命令行。

%prep
%autosetup -n %{name}-%{version}

%build
# 创建虚拟环境
python3 -m venv %{_builddir}/venv
source %{_builddir}/venv/bin/activate

# 升级pip和setuptools
pip install --upgrade pip setuptools wheel

# 安装项目依赖
pip install -r requirements.txt

# 安装PyInstaller
pip install pyinstaller

# 使用虚拟环境中的PyInstaller创建单一可执行文件
pyinstaller --noconfirm --onefile \
            --name %{pypi_name} \
            --add-data "src/app/css:app/css" \
            --target-architecture %{_target_cpu} \
            src/main.py

# 退出虚拟环境
deactivate

%install
# 创建目标目录
mkdir -p %{buildroot}%{_bindir}

# 复制PyInstaller生成的可执行文件
install -m 0755 dist/%{pypi_name} %{buildroot}%{_bindir}/%{pypi_name}

%files
%license LICENSE
%doc README.md
%{_bindir}/%{pypi_name}

%changelog
* %{_builddate} openEuler <contact@openeuler.org> - 0.1.0-1
- 首次构建RPM包，支持x86_64和aarch64架构