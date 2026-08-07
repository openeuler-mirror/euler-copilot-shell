%global go_version  1.26.5
%global import_path atomgit.com/openeuler/euler-copilot-shell

%global skill_manpage_slug        manpage-skill
%global skill_log_anomaly_slug    log-anomaly-detector
%global skill_html_report_slug    html-report-generator
%global skill_brainstorm_slug     brainstorm-beagle
%global skill_plantuml_slug       plantuml-skill
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

%global witty_managed_root %{_datadir}/witty/opencode
%global witty_managed_config_dropins %{witty_managed_root}/config.d
%global witty_managed_agents %{witty_managed_root}/agents
%global witty_managed_skills %{witty_managed_root}/skills
%global witty_managed_plugins %{witty_managed_root}/plugins
%global witty_managed_libexec %{_libexecdir}/witty-opencode
%global witty_loader_source_dir %{_builddir}/witty-agent-loader-%{version}

Name:           euler-copilot-shell
Version:        3.1.3
Release:        1
Summary:        openEuler terminal AI assistant

License:        MulanPSL2
URL:            https://atomgit.com/openeuler/euler-copilot-shell

Source0:        %{name}-%{version}.tar.gz
Source1:        https://go.dev/dl/go%{go_version}.linux-amd64.tar.gz#/go%{go_version}.linux-amd64.tar.gz
Source2:        https://go.dev/dl/go%{go_version}.linux-arm64.tar.gz#/go%{go_version}.linux-arm64.tar.gz
Source3:        witty-cli-vendor-%{version}.tar.xz
Source4:        witty-agent-loader-%{version}.tar.gz
Source5:        https://api.skillhub.cn/api/v1/download?slug=manpage-skill#/manpage-skill-1.0.0.zip
Source6:        https://api.skillhub.cn/api/v1/download?slug=log-anomaly-detector#/log-anomaly-detector-1.0.0.zip
Source7:        https://api.skillhub.cn/api/v1/download?slug=html-report-generator#/html-report-generator-1.0.0.zip
Source8:        https://api.skillhub.cn/api/v1/download?slug=brainstorm-beagle#/brainstorm-beagle-1.0.5.zip
Source9:        https://api.skillhub.cn/api/v1/download?slug=plantuml-skill#/plantuml-skill-1.4.1.zip

BuildRequires:  xz
BuildRequires:  unzip
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
Requires:       witty-builtin-agent = %{version}-%{release}

%description -n witty
Witty is the terminal-side intelligent interaction entry point for openEuler.

%package -n witty-agent-loader
Summary:        Managed configuration and RPM integration assets for witty-opencode
License:        MulanPSL-2.0
BuildArch:      noarch
Provides:       witty-opencode-base = %{version}-%{release}
Obsoletes:      witty-opencode-base < 3.0.0
Recommends:     opencode
Recommends:     nodejs >= 20

%description -n witty-agent-loader
This package ships the managed-config assets for witty-opencode on openEuler.
It owns the managed resource directories, the config generator, and
the RPM transaction hooks that rebuild /etc/opencode/opencode.json
from installed config fragments and resource bundles.

%package -n witty-builtin-agent
Summary:        Built-in agent, skills, and MCP config for Witty Assistant
BuildArch:      noarch
Requires:       witty-agent-loader >= %{version}-%{release}
Requires:       nodejs >= 20
Recommends:     witty-experience-skill
Recommends:     opencode

%description -n witty-builtin-agent
This package ships the built-in Witty Assistant agent (Role Prompt),
five core skills sourced from SkillHub (manpage-skill, log-anomaly-detector,
html-report-generator, brainstorm-beagle, plantuml-skill), and the openEuler
Portal MCP configuration. Together with the separately-packaged
witty-experience-skill, they form the complete openEuler intelligent
assistant agent system.

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

rm -rf %{witty_loader_source_dir}
mkdir -p %{witty_loader_source_dir}
tar -xzf %{SOURCE4} --strip-components=1 -C %{witty_loader_source_dir}

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

%{__goroot}/bin/go build \
    -mod=vendor \
    -trimpath \
    -ldflags="-s -w
        -X main.version=%{version}
        -X main.commit=%{commit}
        -X main.date=%{date}" \
    -o wittyd \
    %{import_path}/cmd/wittyd

%install
install -Dpm 0755 witty %{buildroot}%{_bindir}/witty
install -Dpm 0755 wittyd %{buildroot}%{_bindir}/wittyd
install -Dpm 0644 packaging/config.toml %{buildroot}%{_sysconfdir}/witty/config.toml
install -Dpm 0644 packaging/daemon.toml %{buildroot}%{_sysconfdir}/witty/daemon.toml
install -Dpm 0644 packaging/witty.bash-completion %{buildroot}%{_datadir}/bash-completion/completions/witty
install -Dpm 0644 packaging/profile.d/witty.sh %{buildroot}%{_sysconfdir}/profile.d/witty.sh
install -Dpm 0644 packaging/wittyd.service %{buildroot}%{_unitdir}/wittyd.service

# Install witty-agent-loader assets
cd %{witty_loader_source_dir}

install -d "%{buildroot}%{_licensedir}/witty-agent-loader"
install -Dm644 LICENSE "%{buildroot}%{_licensedir}/witty-agent-loader/LICENSE"
install -d "%{buildroot}%{_docdir}/witty-agent-loader"
install -Dm644 "docs/witty-opencode-base.md" "%{buildroot}%{_docdir}/witty-agent-loader/witty-opencode-base.md"
install -Dm644 "README.md" "%{buildroot}%{_docdir}/witty-agent-loader/base-source-layout.md"

install -d "%{buildroot}%{witty_managed_libexec}"
install -Dm755 "bin/rebuild-managed-config.mjs" "%{buildroot}%{witty_managed_libexec}/rebuild-managed-config.mjs"
install -Dm755 "bin/run-managed-config-hook.sh" "%{buildroot}%{witty_managed_libexec}/run-managed-config-hook.sh"

install -d "%{buildroot}%{_sysconfdir}/opencode"
install -d "%{buildroot}%{witty_managed_config_dropins}"
install -d "%{buildroot}%{witty_managed_agents}"
install -d "%{buildroot}%{witty_managed_skills}"
install -d "%{buildroot}%{witty_managed_plugins}"

cd -

# witty-builtin-agent: config.d fragment
install -Dpm 0644 packaging/builtin-agents/config.d/witty-builtin-agent.json \
  %{buildroot}%{witty_managed_config_dropins}/witty-builtin-agent.json

# witty-builtin-agent: agent prompt
install -d %{buildroot}%{witty_managed_agents}/witty-builtin-agent
install -Dpm 0644 packaging/builtin-agents/agents/witty-builtin-agent/witty-builtin-agent.md \
  %{buildroot}%{witty_managed_agents}/witty-builtin-agent/witty-builtin-agent.md

# witty-builtin-agent: 5 skills from SkillHub (HTTP API, no auth)
install -d %{buildroot}%{witty_managed_skills}/witty-builtin-agent

mkdir -p %{buildroot}%{witty_managed_skills}/witty-builtin-agent/%{skill_manpage_slug}
unzip -qo %{SOURCE5} -d %{buildroot}%{witty_managed_skills}/witty-builtin-agent/%{skill_manpage_slug}/
mkdir -p %{buildroot}%{witty_managed_skills}/witty-builtin-agent/%{skill_log_anomaly_slug}
unzip -qo %{SOURCE6} -d %{buildroot}%{witty_managed_skills}/witty-builtin-agent/%{skill_log_anomaly_slug}/
mkdir -p %{buildroot}%{witty_managed_skills}/witty-builtin-agent/%{skill_html_report_slug}
unzip -qo %{SOURCE7} -d %{buildroot}%{witty_managed_skills}/witty-builtin-agent/%{skill_html_report_slug}/
mkdir -p %{buildroot}%{witty_managed_skills}/witty-builtin-agent/%{skill_brainstorm_slug}
unzip -qo %{SOURCE8} -d %{buildroot}%{witty_managed_skills}/witty-builtin-agent/%{skill_brainstorm_slug}/
mkdir -p %{buildroot}%{witty_managed_skills}/witty-builtin-agent/%{skill_plantuml_slug}
unzip -qo %{SOURCE9} -d %{buildroot}%{witty_managed_skills}/witty-builtin-agent/%{skill_plantuml_slug}/

find %{buildroot}%{witty_managed_skills}/witty-builtin-agent/ \
  -name '__MACOSX' -prune -exec rm -rf {} + 2>/dev/null || true
find %{buildroot}%{witty_managed_skills}/witty-builtin-agent/ \
  -name '.DS_Store' -delete 2>/dev/null || true

%check
%{buildroot}%{_bindir}/witty version
%{buildroot}%{_bindir}/witty --help

%files -n witty
%license LICENSE
%doc README.md
%{_bindir}/witty
%{_bindir}/wittyd
%{_unitdir}/wittyd.service
%dir %{_sysconfdir}/witty
%config(noreplace) %{_sysconfdir}/witty/config.toml
%config(noreplace) %{_sysconfdir}/witty/daemon.toml
%{_datadir}/bash-completion/completions/witty
%{_sysconfdir}/profile.d/witty.sh

%files -n witty-agent-loader
%license %{_licensedir}/witty-agent-loader/LICENSE
%doc %{_docdir}/witty-agent-loader/witty-opencode-base.md
%doc %{_docdir}/witty-agent-loader/base-source-layout.md
%dir %{_sysconfdir}/opencode
%ghost %config(noreplace) %{_sysconfdir}/opencode/opencode.json
%{witty_managed_libexec}/rebuild-managed-config.mjs
%{witty_managed_libexec}/run-managed-config-hook.sh
%dir %{witty_managed_root}
%dir %{witty_managed_config_dropins}
%dir %{witty_managed_agents}
%dir %{witty_managed_skills}
%dir %{witty_managed_plugins}

%files -n witty-builtin-agent
%{witty_managed_config_dropins}/witty-builtin-agent.json
%{witty_managed_agents}/witty-builtin-agent
%{witty_managed_skills}/witty-builtin-agent

%posttrans -n witty-agent-loader
%{witty_managed_libexec}/run-managed-config-hook.sh posttrans

%transfiletriggerin -n witty-agent-loader -- %{witty_managed_config_dropins} %{witty_managed_agents} %{witty_managed_skills} %{witty_managed_plugins}
%{witty_managed_libexec}/run-managed-config-hook.sh transfiletriggerin

# NOTE: use %filetriggerpostun (per-package) instead of %transfiletriggerpostun.
# %transfiletriggerpostun does not fire on package removal in rpm 4.17-4.19
# (rpm-software-management/rpm#2324, #3048), so the managed config would go
# stale when an addon subpackage is uninstalled. %filetriggerpostun fires
# reliably per removed package; the rebuild hook is idempotent.
%filetriggerpostun -n witty-agent-loader -- %{witty_managed_config_dropins} %{witty_managed_agents} %{witty_managed_skills} %{witty_managed_plugins}
%{witty_managed_libexec}/run-managed-config-hook.sh filetriggerpostun

%post -n witty
%systemd_post wittyd.service

%preun -n witty
%systemd_preun wittyd.service

%postun -n witty
%systemd_postun_with_restart wittyd.service

%changelog
* Fri Aug 07 2026 Witty Team <intelligence@openeuler.org> - 3.1.3-1
- feat: Handle session.error events from opencode
- fix: add bare /session command help in REPL
- feat(shellbridge): route bare /session to session usage help
- docs: clarify shell routing, session list, and server status behavior
- docs: Add comprehensive usage documentation for Witty CLI
- feat: Stream reasoning echo in EchoRenderer

* Thu Jul 30 2026 Witty Team <intelligence@openeuler.org> - 3.1.2-1
- fix: Refactor doctor to treat not-running server as OK, remove agent-packages check
- fix: Move /new force-next detection into dispatch
- chore: Allow context, websearch, and grep MCPs in builtin agent
- chore: Extract dev setup dependencies into a shared script
- chore: Add Go PATH to profile for all setup scripts
- chore: Clean old release artifacts before building

* Tue Jul 28 2026 Witty Team <intelligence@openeuler.org> - 3.1.1-1
- feat: Prompt for provider API key interactively on TTY
- fix: Make permission handling synchronous to prevent terminal desync
- refactor: permission display with multi-line title support
- fix: Change QuestionInfo.Custom from bool to *bool with helper method
- fix: Refine shell command routing with precise NL detection and Bash generation
- chore: Adjust builtin agent permissions for read, external directory, and bash
- chore: Widen witty-builtin-agent permissions and refine prompt
- chore: Allow witty dirs and experience-skill by default

* Tue Jul 14 2026 Witty Team <intelligence@openeuler.org> - 3.1.0-1
- Add witty-builtin-agent subpackage with built-in agent, skills, and MCP config
- Ship Role Prompt and config.d fragment for Witty Assistant as default agent (mode=primary)
- Download 5 SkillHub skills (manpage-skill, log-anomaly-detector, html-report-generator,
  brainstorm-beagle, plantuml-skill) at build time via prepare-release.sh
- witty now Requires witty-builtin-agent for out-of-the-box agent experience
- Skill versions centralized in skill-versions.sh, spec Sources use real URLs for CI

* Tue Jun 23 2026 Witty Team <intelligence@openeuler.org> - 3.0.0-1
- Rename source package to euler-copilot-shell; binary subpackage is witty
- Provides/Obsoletes euler-copilot-shell and witty-assistant for upgrade from 1.x/2.x
- Vendor + Go toolchain bundling; static build with CGO_ENABLED=0, GOAMD64=v1

* Thu Jun 04 2026 SIG-Intelligence <intelligence@openeuler.org> - 2.0.3-4
- Add witty-agent-loader subpackage (migrated from witty-opencode-base)

* Fri May 08 2026 openEuler <contact@openeuler.org> - 2.0.3-3
- chore: remove redundant logs
- chore: exclude dev scripts from release package

* Tue Apr 28 2026 openEuler <contact@openeuler.org> - 2.0.3-2
- chore: Remove tests from SRPM

* Fri Mar 13 2026 openEuler <contact@openeuler.org> - 2.0.3-1
- installer: Add support for witty-mcp-manager installation
- fix: Tool call rendering issue

* Fri Jan 30 2026 openEuler <contact@openeuler.org> - 2.0.2-1
- feat: Add option to launch OpenCode through Witty Assistant
- installer: Install OpenCode-AI during deployment

* Tue Jan 06 2026 openEuler <contact@openeuler.org> - 2.0.1-1
- feat: Set defautl chat model during installation
- feat: Add shell completion installation command
- fix: Markdown rendering issue in TUI
- chore: Remove deprecated scripts in installer

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
