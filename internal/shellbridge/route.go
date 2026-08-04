package shellbridge

// Route identifies how a shell line should be dispatched.
type Route string

const (
	RouteEmpty   Route = "empty"
	RouteShell   Route = "shell"
	RouteAgent   Route = "agent"
	RouteControl Route = "control"
)
