%global go_version  1.26.4
%global import_path atomgit.com/openeuler/euler-copilot-shell
%global debug_package %{nil}

# Resolve commit and date from build-info file (if present), then --define, finally fallback
%{lua:
  local info = rpm.expand("%{_sourcedir}/build-info")
  local f = io.open(info)
  if f then
    local content = f:read("*a")
    f:close()
    rpm.expand(content)
  end
}
%{?!commit:  %global commit unknown}
%{?!date:    %global date   unknown}

Name:           euler-copilot-shell
Version:        3.0.0
Release:        2
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
Requires:       witty-release = %{version}-%{release}
Recommends:     witty-log-detection
Recommends:     witty-lite-rag

%description -n witty
Witty is the terminal-side intelligent interaction entry point for openEuler.

%package -n witty-release
Summary:        EPOL update repository configuration for witty
BuildArch:      noarch

%description -n witty-release
This package adds the openEuler EPOL update repository configuration
required by witty and its dependencies. The repository is enabled by
default upon installation.

%prep
%setup -q -n %{name}-%{version}

%ifarch x86_64
tar -xzf %{SOURCE1} -C %{_builddir}
%define __goroot %{_builddir}/go
%endif
%ifarch aarch64
tar -xzf %{SOURCE2} -C %{_builddir}
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
install -Dpm 0644 packaging/witty-epol-update.repo %{buildroot}%{_sysconfdir}/yum.repos.d/witty-epol-update.repo

%check
%{buildroot}%{_bindir}/witty version
%{buildroot}%{_bindir}/witty --help

%files

%files -n witty
%license LICENSE
%doc README.md
%{_bindir}/witty
%dir %{_sysconfdir}/witty
%config(noreplace) %{_sysconfdir}/witty/config.toml
%{_datadir}/bash-completion/completions/witty
%{_sysconfdir}/profile.d/witty.sh

%files -n witty-release
%config(noreplace) %{_sysconfdir}/yum.repos.d/witty-epol-update.repo

%changelog
* Tue Jun 30 2026 Witty Team <contact@openeuler.org> - 3.0.0-2
- Add witty-release subpackage to enable EPOL update repository
- witty now Requires witty-release for automatic repo configuration

* Tue Jun 23 2026 Witty Team <contact@openeuler.org> - 3.0.0-1
- Rename source package to euler-copilot-shell; binary subpackage is witty
- Provides/Obsoletes euler-copilot-shell and witty-assistant for upgrade from 1.x/2.x
- Vendor + Go toolchain bundling; static build with CGO_ENABLED=0, GOAMD64=v1
