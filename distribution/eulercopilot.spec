Name: eulercopilot
Version: 1.1
Release: 1%{?dist}%{?_timestamp}
Group: Applications/Utilities
Summary: EulerCopilot CLI Tool
Source: %{name}-%{version}.tar.gz
License: MulanPSL-2.0
URL: https://www.openeuler.org/zh/

BuildRequires: python3-devel python3-setuptools python3-Cython gcc

Requires: python3 python3-pip

%description
EulerCopilot CLI Tool

%prep
%setup -q

%build
python3 setup.py build_ext

%install
%define _unpackaged_files_terminate_build 0
python3 setup.py install --root=%{buildroot} --single-version-externally-managed --record=INSTALLED_FILES
install -d %{buildroot}/etc/profile.d
install -c -m 0755 %{_builddir}/%{name}-%{version}/eulercopilot_shortcut.sh %{buildroot}/etc/profile.d

%files -f INSTALLED_FILES
%defattr(-,root,root,-)
/etc/profile.d/eulercopilot_shortcut.sh

%post
/usr/bin/python3 -m pip install --upgrade websockets >/dev/null
/usr/bin/python3 -m pip install --upgrade requests >/dev/null
/usr/bin/python3 -m pip install --upgrade rich >/dev/null
