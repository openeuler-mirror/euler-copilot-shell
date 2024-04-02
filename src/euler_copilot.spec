Name: euler_copilot
Version: 1.0
Release: 1
BuildArch: x86_64
Summary: euler_copilot
SOURCE: copilot.tar.gz
SOURCE1: setup.py
License: GPL
URL: https://www.openeuler.org/zh/

BuildRequires: python3-devel python3-Cython gcc

%description
test examples for xats, create xats rpm package


%prep
rm -rf %{name}-%{version}
tar -xf %{SOURCE0}
mv copilot %{name}-%{version}
cp %{SOURCE1} %{name}-%{version}

%post
cat << EOF >> /root/.bashrc
# eulercopilot
function commandline {
    stty sane && python3 /eulercopilot/eulercopilot.py \$READLINE_LINE
    READLINE_LINE=
    stty erase ^H
}
bind -x '"\C-l":commandline'
EOF
source /root/.bashrc

%postun
sed -i '/^# eulercopilot/,+6d' /root/.bashrc
source /root/.bashrc

%build
pushd %{name}-%{version}
python3 setup.py build_ext

%install
%define _unpackaged_files_terminate_build 0
mkdir -p -m 700 %{buildroot}/%{python3_sitelib}
mkdir -p -m 700 %{buildroot}/eulercopilot

install -c -m 0700 %{_builddir}/%{name}-%{version}/build/lib.linux-x86_64-3.9/cmd_generate.cpython-39-x86_64-linux-gnu.so %{buildroot}/%{python3_sitelib}
install -c -m 0700 %{_builddir}/%{name}-%{version}/build/lib.linux-x86_64-3.9/interact.cpython-39-x86_64-linux-gnu.so %{buildroot}/%{python3_sitelib}
install -c -m 0700 %{_builddir}/%{name}-%{version}/eulercopilot.py %{buildroot}/eulercopilot

%files
%{python3_sitelib}/cmd_generate.cpython-39-x86_64-linux-gnu.so
%{python3_sitelib}/interact.cpython-39-x86_64-linux-gnu.so
/eulercopilot/eulercopilot.py