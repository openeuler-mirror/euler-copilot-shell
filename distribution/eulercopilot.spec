Name: eulercopilot-cli
Version: 1.2
Release: 1%{?_tag}%{?dist}
Group: Applications/Utilities
Summary: EulerCopilot Command Line Assistant
Source: %{name}-%{version}.tar.gz
License: MulanPSL-2.0
URL: https://www.openeuler.org/zh/

BuildRequires: python3-devel python3-setuptools
BuildRequires: python3-pip
BuildRequires: python3-Cython gcc

Requires: python3 jq hostname

%description
EulerCopilot Command Line Assistant

%prep
%setup -q
python3 -m venv .venv
.venv/bin/python3 -m pip install -U pip setuptools
.venv/bin/python3 -m pip install -U Cython pyinstaller
.venv/bin/python3 -m pip install -U websockets requests
.venv/bin/python3 -m pip install -U rich typer questionary

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
install -c -m 0755 %{_builddir}/%{name}-%{version}/eulercopilot.sh %{buildroot}/etc/profile.d

%files
%defattr(-,root,root,-)
/usr/bin/copilot
/etc/profile.d/eulercopilot.sh

%pre
sed -i '/# >>> eulercopilot >>>/,/# <<< eulercopilot <<</{d}' /etc/bashrc
cat << 'EOF' >> /etc/bashrc
# >>> eulercopilot >>>
if type revert_copilot_prompt &> /dev/null && type set_copilot_prompt &> /dev/null; then
    run_after_return() {
        if [[ "$PS1" == *"\[\033[1;33m"* ]]; then
            revert_copilot_prompt
            set_copilot_prompt
        fi
    }
    PROMPT_COMMAND="${PROMPT_COMMAND:+${PROMPT_COMMAND}; }run_after_return"
    set_copilot_prompt
fi
# <<< eulercopilot <<<
EOF

%postun
if [ ! -f /usr/bin/copilot ]; then
    sed -i '/# >>> eulercopilot >>>/,/# <<< eulercopilot <<</{d}' /etc/bashrc
fi
