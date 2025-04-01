%global pypi_name eulercopilot-shell

Name:           euler-copilot-shell
Version:        0.1.0
Release:        1%{?dist}
Summary:        智能 Shell 终端工具
License:        MulanPSL-2.0
URL:            https://www.eulercopilot.com
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools

Requires:       python3
Requires:       python3-openai >= 1.61.0
Requires:       python3-rich >= 14.0.0
Requires:       python3-textual >= 3.0.0

%description
EulerCopilot Smart Shell 是一个智能命令行程序。
它允许用户输入命令，通过集成大语言模型提供命令建议，帮助用户更高效地使用命令行。

%prep
%autosetup -n %{name}-%{version}

%build
%py3_build

%install
%py3_install

# 安装启动脚本
mkdir -p %{buildroot}%{_bindir}
install -m 0755 %{pypi_name} %{buildroot}%{_bindir}/%{pypi_name}

%files
%license LICENSE
%doc README.md
%{_bindir}/%{pypi_name}
%{python3_sitelib}/*

%changelog
* %{_builddate} openEuler <contact@openeuler.org> - 0.1.0-1
- 首次构建RPM包