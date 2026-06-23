# euler-copilot-shell.spec — Witty CLI RPM for openEuler
#
# Source package: euler-copilot-shell
# Binary package:  witty (with upgrade path from euler-copilot-shell 1.x/2.x and witty-assistant)

%global go_version  1.26.4
%global import_path atomgit.com/openeuler/euler-copilot-shell
%global debug_package %{nil}

Name:           euler-copilot-shell
Version:        3.0.0
Release:        1%{?dist}
Summary:        openEuler terminal AI assistant

License:        MulanPSL2
URL:            https://atomgit.com/openeuler/euler-copilot-shell

Source0:        %{name}-%{version}.tar.gz
Source1:        go%{go_version}.linux-amd64.tar.gz
Source2:        go%{go_version}.linux-arm64.tar.gz
Source3:        %{name}-vendor-%{version}.tar.xz

BuildRequires:  xz
Requires:       bash
Requires:       glibc

%description
Witty is the terminal-side intelligent interaction entry point for openEuler.

%package -n witty
Summary:        openEuler terminal AI assistant

Provides:       euler-copilot-shell = %{version}-%{release}
Obsoletes:      euler-copilot-shell < 3.0.0
Provides:       witty-assistant = %{version}-%{release}
Obsoletes:      witty-assistant < 3.0.0

%description -n witty
Witty is the terminal-side intelligent interaction entry point for openEuler.

%prep
%setup -q -n %{name}-%{version}

%ifarch x86_64
tar -xzf %{SOURCE1}
%define __goroot %{_builddir}/go
%endif
%ifarch aarch64
tar -xzf %{SOURCE2}
%define __goroot %{_builddir}/go
%endif

tar -xJf %{SOURCE3}

%build
export GOROOT=%{__goroot}
export PATH=%{__goroot}/bin:${PATH}
export GOCACHE=%{_builddir}/.gocache
export CGO_ENABLED=0
export GOAMD64=v1

%{__goroot}/bin/go version

%{__goroot}/bin/go build \
    -mod=vendor \
    -trimpath \
    -ldflags="-s -w
        -X main.version=%{version}
        -X main.commit=%{commit}
        -X main.date=%{date}" \
    -o witty \
    %{import_path}/cmd/witty

%install
install -Dpm 0755 witty %{buildroot}%{_bindir}/witty
install -Dpm 0644 packaging/config.toml %{buildroot}%{_sysconfdir}/witty/config.toml
install -Dpm 0644 packaging/witty.bash-completion %{buildroot}%{_datadir}/bash-completion/completions/witty
install -Dpm 0644 packaging/profile.d/witty.sh %{buildroot}%{_sysconfdir}/profile.d/witty.sh

%check
%{buildroot}%{_bindir}/witty version
%{buildroot}%{_bindir}/witty --help

%files
# Main euler-copilot-shell package is intentionally empty;
# all content lives in the witty subpackage.

%files -n witty
%license LICENSE
%doc README.md
%{_bindir}/witty
%dir %{_sysconfdir}/witty
%config(noreplace) %{_sysconfdir}/witty/config.toml
%{_datadir}/bash-completion/completions/witty
%{_sysconfdir}/profile.d/witty.sh

%changelog
* Mon Jun 23 2026 Witty Team <witty@openeuler.org> - 3.0.0-1
- Rename source package to euler-copilot-shell; binary subpackage is witty
- Provides/Obsoletes euler-copilot-shell and witty-assistant for upgrade from 1.x/2.x
- Vendor + Go toolchain bundling; static build with CGO_ENABLED=0, GOAMD64=v1
