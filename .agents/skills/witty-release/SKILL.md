---
name: witty-release
description: 执行版本发布流程。包括版本号管理、vendor tarball 生成、RPM 打包和发布验证。用于准备新版本发布时。
---

# 版本发布与打包

## 读取远程环境配置（重要）

发布前若要做 openEuler 远程验证，直接读取 `.agents/config.yaml`；不要先用 `find_path` 或目录扫描判断其是否存在。该文件可能被 `.gitignore` 隐藏，但实际可读。若直接读取失败，再回退参考 `.agents/config.template.yaml`。

## 发布流程

1. **确认所有测试通过**（含 openEuler 环境验证）

2. **更新版本号**: spec 中的 `Version` 和 `%global go_version`（默认 1.26.5，与 `prepare-release.sh` 的 `go_version` 参数保持一致），以及文档示例；若上游 Skill 升级，同步更新 `packaging/builtin-agents/skill-versions.sh` 中的版本号（唯一事实来源）

3. **生成发布产物**:

   ```bash
   bash packaging/scripts/prepare-release.sh <version> [<go_version>]
   ```

   产物:
   - `euler-copilot-shell-<version>.tar.gz` → Source0
   - `go<go_version>.linux-amd64.tar.gz` → Source1
   - `go<go_version>.linux-arm64.tar.gz` → Source2
   - `witty-cli-vendor-<version>.tar.xz` → Source3
   - `witty-agent-loader-<version>.tar.gz` → Source4
   - `manpage-skill-<ver>.zip` → Source5（SkillHub）
   - `log-anomaly-detector-<ver>.zip` → Source6（SkillHub）
   - `html-report-generator-<ver>.zip` → Source7（SkillHub）
   - `brainstorm-beagle-<ver>.zip` → Source8（SkillHub）
   - `plantuml-skill-<ver>.zip` → Source9（SkillHub）
   - `build-info` →（含 commit / date，由 spec 的 `%{lua}` 段读取）

   > Skill zip 的版本号与下载 URL 统一从 `packaging/builtin-agents/skill-versions.sh` 读取（单一事实来源）；下载需要网络访问 SkillHub。Skill 版本硬编码在 spec 的 Source 文件名中，升级 Skill 时需同步更新 spec 和 `skill-versions.sh`。

4. **本地可选的冒烟构建**（宿主机，不依赖 vendor）:

   ```bash
   bash scripts/build.sh
   build/<host-goos>-<host-goarch>/witty version
   ```

5. **openEuler 远程 RPM 构建与验证**:

   ```bash
   # Source 文件已在 build/release/ 下，直接构建
   mkdir -p ~/rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
   cp packaging/euler-copilot-shell.spec ~/rpmbuild/SPECS/
   rpmbuild -ba ~/rpmbuild/SPECS/euler-copilot-shell.spec \
     --define "_sourcedir $(pwd)/build/release"
   ```

6. **上传至 openEuler 构建系统**: 将 Source0~Source9、`build-info` 和 spec 文件上传，由 CI 完成离线构建

7. **创建 tag**:

   ```bash
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin vX.Y.Z
   ```

## RPM 打包验证（在 openEuler 环境中执行）

```bash
# 安装测试
dnf install -y ~/rpmbuild/RPMS/$(uname -m)/witty-*.rpm
# 升级测试（同版本用 reinstall，跨版本用 install 即自动升级）
dnf reinstall -y ~/rpmbuild/RPMS/$(uname -m)/witty-*.rpm
# 文件清单验证
rpm -ql witty
# 版本信息
witty version
# 卸载
dnf remove -y witty
```

## 发布检查清单

- [ ] 所有 openEuler 环境测试通过（`go test -count=1 ./...`）
- [ ] PTY 测试在 openEuler 上通过
- [ ] `witty doctor` 诊断通过
- [ ] RPM 安装/升级/卸载正常
- [ ] `witty init bash` 输出有效且通过 shellcheck
- [ ] shellcheck + shfmt 全部通过
- [ ] `GOAMD64=v1` 兼容性确认（amd64 二进制可在旧型服务器上运行）
- [ ] `witty version` 输出正确的 version / commit / date
- [ ] amd64 / arm64 双架构 RPM 均构建成功
