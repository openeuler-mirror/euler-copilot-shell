package presenter

import "fmt"

// UserError marks an error as a user-facing/request validation failure.
type UserError struct {
	Op  string
	Err error
}

func (e *UserError) Error() string {
	if e == nil {
		return ""
	}
	if e.Op == "" {
		return e.Err.Error()
	}
	return fmt.Sprintf("%s: %v", e.Op, e.Err)
}

func (e *UserError) Unwrap() error {
	if e == nil {
		return nil
	}
	return e.Err
}

// SchemaError marks an error as an event/schema decoding or payload-shape failure.
type SchemaError struct {
	Op  string
	Err error
}

func (e *SchemaError) Error() string {
	if e == nil {
		return ""
	}
	if e.Op == "" {
		return e.Err.Error()
	}
	return fmt.Sprintf("%s: %v", e.Op, e.Err)
}

func (e *SchemaError) Unwrap() error {
	if e == nil {
		return nil
	}
	return e.Err
}
