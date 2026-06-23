package main

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/signal"

	"atomgit.com/openeuler/euler-copilot-shell/internal/cli"
	versionpkg "atomgit.com/openeuler/euler-copilot-shell/internal/version"
)

var (
	version = "dev"
	commit  = "none"
	date    = "unknown"
)

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()

	info := versionpkg.New(version, commit, date)
	if err := cli.Execute(ctx, os.Args[1:], os.Stdout, os.Stderr, info); err != nil {
		if errors.Is(err, context.Canceled) {
			fmt.Fprintln(os.Stderr, "interrupted")
			os.Exit(130)
		}
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
