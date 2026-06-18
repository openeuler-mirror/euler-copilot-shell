package session

import (
	"context"
	"errors"
	"fmt"
	"os"

	"atomgit.com/openeuler/witty-cli/internal/transport"
)

const defaultListLimit = 1.0

type Transport interface {
	CreateSession(ctx context.Context, req transport.CreateSessionRequest) (transport.Session, error)
	GetSession(ctx context.Context, sessionID string) (transport.Session, error)
	ListSessions(ctx context.Context, filter transport.SessionFilter) ([]transport.Session, error)
}

type Resolver interface {
	Resolve(ctx context.Context, cwd string, forceNew bool) (Context, error)
	Continue(ctx context.Context, id string) (Context, error)
	List(ctx context.Context, scope Scope) ([]Summary, error)
}

type Options struct {
	Transport   Transport
	StatePath   string
	LookupEnv   func(string) (string, bool)
	UserHomeDir func() (string, error)
}

type Context struct {
	ID        string
	Directory string
	Title     string
	Session   transport.Session
}

type Scope struct {
	Directory string
	Workspace string
	Search    string
	Limit     *float64
}

type Summary struct {
	ID        string
	Title     string
	Directory string
	Agent     string
	Updated   int // Unix timestamp
}

type service struct {
	transport Transport
	state     *stateStore
}

func NewService(opts Options) (Resolver, error) {
	if opts.Transport == nil {
		return nil, fmt.Errorf("session transport is required")
	}
	statePath := opts.StatePath
	if statePath == "" {
		path, err := DefaultStatePath(opts.LookupEnv, opts.UserHomeDir)
		if err != nil {
			return nil, err
		}
		statePath = path
	}
	return &service{transport: opts.Transport, state: newStateStore(statePath)}, nil
}

func (s *service) Resolve(ctx context.Context, cwd string, forceNew bool) (Context, error) {
	if err := ctx.Err(); err != nil {
		return Context{}, err
	}
	if cwd == "" {
		workingDir, err := os.Getwd()
		if err != nil {
			return Context{}, fmt.Errorf("resolve cwd: %w", err)
		}
		cwd = workingDir
	}
	if forceNew {
		return s.create(ctx, cwd)
	}

	state, err := s.state.load()
	if err != nil {
		return Context{}, err
	}
	if pinned := state.CurrentByDirectory[cwd]; pinned != "" {
		session, err := s.transport.GetSession(ctx, pinned)
		if err != nil {
			var httpErr *transport.HTTPError
			if errors.As(err, &httpErr) && httpErr.StatusCode == 404 {
				// Pinned session was deleted on the server; clear the
				// pin and fall through to list or create a new one.
				s.unpin(cwd)
			} else {
				return Context{}, fmt.Errorf("resolve pinned session %q: %w", pinned, err)
			}
		} else {
			return contextFromSession(session), nil
		}
	}

	limit := defaultListLimit
	sessions, err := s.transport.ListSessions(ctx, transport.SessionFilter{Directory: cwd, Limit: &limit})
	if err != nil {
		return Context{}, fmt.Errorf("list sessions for %q: %w", cwd, err)
	}
	if len(sessions) > 0 {
		if err := s.pin(cwd, sessions[0].ID); err != nil {
			return Context{}, err
		}
		return contextFromSession(sessions[0]), nil
	}
	return s.create(ctx, cwd)
}

func (s *service) Continue(ctx context.Context, id string) (Context, error) {
	if err := ctx.Err(); err != nil {
		return Context{}, err
	}
	if id == "" {
		return Context{}, fmt.Errorf("session id is required")
	}
	session, err := s.transport.GetSession(ctx, id)
	if err != nil {
		return Context{}, fmt.Errorf("continue session %q: %w", id, err)
	}
	if session.Directory != "" {
		if err := s.pin(session.Directory, session.ID); err != nil {
			return Context{}, err
		}
	}
	return contextFromSession(session), nil
}

func (s *service) List(ctx context.Context, scope Scope) ([]Summary, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	sessions, err := s.transport.ListSessions(ctx, transport.SessionFilter{
		Directory: scope.Directory,
		Workspace: scope.Workspace,
		Search:    scope.Search,
		Limit:     scope.Limit,
	})
	if err != nil {
		return nil, fmt.Errorf("list sessions: %w", err)
	}
	summaries := make([]Summary, 0, len(sessions))
	for _, session := range sessions {
		summaries = append(summaries, summaryFromSession(session))
	}
	return summaries, nil
}

func (s *service) create(ctx context.Context, cwd string) (Context, error) {
	session, err := s.transport.CreateSession(ctx, transport.CreateSessionRequest{Directory: cwd})
	if err != nil {
		return Context{}, fmt.Errorf("create session for %q: %w", cwd, err)
	}
	if err := s.pin(cwd, session.ID); err != nil {
		return Context{}, err
	}
	return contextFromSession(session), nil
}

func (s *service) pin(cwd, sessionID string) error {
	if cwd == "" || sessionID == "" {
		return nil
	}
	state, err := s.state.load()
	if err != nil {
		return err
	}
	state.CurrentByDirectory[cwd] = sessionID
	if err := s.state.save(state); err != nil {
		return err
	}
	return nil
}

func (s *service) unpin(cwd string) {
	if cwd == "" {
		return
	}
	state, err := s.state.load()
	if err != nil {
		return
	}
	delete(state.CurrentByDirectory, cwd)
	_ = s.state.save(state)
}

func contextFromSession(session transport.Session) Context {
	return Context{
		ID:        session.ID,
		Directory: session.Directory,
		Title:     session.Title,
		Session:   session,
	}
}

func summaryFromSession(session transport.Session) Summary {
	agent := ""
	if session.Agent != nil {
		agent = *session.Agent
	}
	return Summary{
		ID:        session.ID,
		Title:     session.Title,
		Directory: session.Directory,
		Agent:     agent,
		Updated:   session.Time.Updated,
	}
}
