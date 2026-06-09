---
name: witty-release
description: 执行版本发布流程。包括版本号管理、GoReleaser 构建、RPM 打包和发布验证。用于准备新版本发布时。
---

# 版本发布与打包

## 读取远程环境配置（重要）

发布前若要做 openEuler 远程验证，直接读取 `shell/.agents/config.yaml`；不要先用 `find_path` 或目录扫描判断其是否存在。该文件可能被 `.gitignore` 隐藏，但实际可读。若直接读取失败，再回退参考 `shell/.agents/config.template.yaml`。

## 发布流程

1. **确认所有测试通过**（含 openEuler 环境验证）
2. **更新版本号**: 遵循 semver，更新代码中的 version 常量
3. **更新 CHANGELOG**: 记录本版本的变更摘要
4. **创建 tag**:

   ```bash
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   ```

5. **本地验证构建**:

   ```bash
   goreleaser release --snapshot --clean --skip=publish
   ```

6. **检查 RPM 产物**:

   ```bash
   ls dist/*.rpm
   ```

7. **推送 tag 触发 CI/CD**:

   ```bash
   git push origin vX.Y.Z
   ```

## 构建配置要点 (`.goreleaser.yaml`)

```yaml
builds:
  - main: ./cmd/witty
    goos: [linux] # 仅构建 Linux
    goarch: [amd64, arm64]
    goamd64: [v1] # 确保旧型 openEuler 服务器兼容
    env: [CGO_ENABLED=0]
    ldflags:
      - "-s -w"
      - "-X main.version={{.Version}}"
      - "-X main.commit={{.Commit}}"
      - "-X main.date={{.Date}}"
```

## RPM 打包验证（在 openEuler 环境中执行）

```bash
# 安装测试
rpm -ivh witty-*.rpm
# 升级测试
rpm -Uvh witty-*.rpm
# 文件清单验证
rpm -ql witty
# 卸载
rpm -e witty
```

## 发布检查清单

- [ ] 所有 openEuler 环境测试通过（`go test -count=1 ./...`）
- [ ] PTY 测试在 openEuler 上通过
- [ ] `witty doctor` 诊断通过
- [ ] RPM 安装/升级/卸载正常
- [ ] `witty init bash` 输出有效且通过 shellcheck
- [ ] `golangci-lint run ./...` 无错误
- [ ] goamd64=v1 兼容性确认（二进制可在旧型服务器上运行）
