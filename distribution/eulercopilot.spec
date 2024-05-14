Name: eulercopilot
Version: 1.1
Release: 1%{?dist}.%{?_timestamp}
Group: Applications/Utilities
Summary: EulerCopilot CLI Tool
Source: %{name}-%{version}.tar.gz
License: MulanPSL-2.0
URL: https://www.openeuler.org/zh/

BuildRequires: python3-devel python3-setuptools
BuildRequires: python3-pip
BuildRequires: python3-Cython gcc

Requires: python3

%description
EulerCopilot Command Line Tool

%prep
%setup -q
python3 -m venv .venv
.venv/bin/python3 -m pip install -U pip setuptools
.venv/bin/python3 -m pip install -U Cython pyinstaller
.venv/bin/python3 -m pip install -U websockets requests rich

%build
.venv/bin/python3 setup.py build_ext
.venv/bin/pyinstaller --onefile --clean \
    --distpath=%{_builddir}/%{name}-%{version}/dist \
    --workpath=%{_builddir}/%{name}-%{version}/build \
    copilot.py

%install
%define _unpackaged_files_terminate_build 0
install -d %{buildroot}/%{_bindir}
install -c -m 0755 %{_builddir}/%{name}-%{version}/dist/copilot %{buildroot}/%{_bindir}
install -d %{buildroot}/etc/profile.d
install -c -m 0755 %{_builddir}/%{name}-%{version}/eulercopilot_shortcut.sh %{buildroot}/etc/profile.d

%files
%defattr(-,root,root,-)
/usr/bin/copilot
/etc/profile.d/eulercopilot_shortcut.sh
