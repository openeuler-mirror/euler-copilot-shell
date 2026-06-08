# 安全红线

## 禁止

- 提交 secrets、API keys、tokens 到代码仓库
- 硬编码凭证或密码
- 在日志中输出敏感信息（session tokens 等）
- 使用不安全的随机数生成器（仅允许 `crypto/rand`）
- 提交 `.agents/config.yaml`

## 构建安全

- `CGO_ENABLED=0` 确保静态链接
- ldflags 注入版本信息，不注入敏感数据
- RPM 签名验证（发布时）

## 代码安全

- 不在代码中留下调试后门或临时测试代码
- 不引入已知有 CVE 的依赖版本
- 所有外部输入（用户输入、HTTP 响应、文件内容）必须做边界校验
