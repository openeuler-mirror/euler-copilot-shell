# Go 编码规则

## 包组织

- internal 模块按职责划分，一个模块一个包
- 导出接口而非具体类型（构造函数返回接口）
- 接口定义在消费方包中
- 所有 internal 模块通过 `app/wiring.go` 组装

## 命名

- 变量/函数: camelCase
- 导出符号: PascalCase
- 测试函数: TestPascalCase
- 包名: 小写单词（如 `shellbridge`，不是 `shell_bridge`）
- 构造函数: `New<Type>`

## 错误处理

- 使用 `fmt.Errorf("context: %w", err)` 包装
- 禁止 panic 处理业务错误（仅用于不可恢复的初始化失败）
- 自定义错误类型实现 `Error()` 方法

## 并发

- 优先使用 `context.Context` 传递取消信号
- goroutine 生命周期必须可追踪
- channel 关闭由发送方负责

## 禁止事项

- 禁止编辑 `transport/generated/` 目录（自动生成代码）
- 禁止在 `internal/` 包之间产生循环依赖
- 禁止 `CGO_ENABLED=1`
- 禁止引用不存在的依赖或虚构的 API
