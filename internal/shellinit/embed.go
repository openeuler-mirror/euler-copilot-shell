package shellinit

import "embed"

// TemplateFS contains the Bash integration templates.
//
//go:embed templates
var TemplateFS embed.FS
