package main

import (
	"context"
	"fmt"
	"os"

	"atomgit.com/openeuler/witty-cli/internal/cli"
	versionpkg "atomgit.com/openeuler/witty-cli/internal/version"
)

var (
	version = "dev"
	commit  = "none"
	date    = "unknown"
)

func main() {
	info := versionpkg.New(version, commit, date)
	if err := cli.Execute(context.Background(), os.Args[1:], os.Stdout, os.Stderr, info); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
