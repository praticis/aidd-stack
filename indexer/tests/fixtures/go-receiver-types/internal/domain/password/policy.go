package password

import "errors"

type Policy struct {
	MinLength int
}

func NewPolicy(min int) Policy { return Policy{MinLength: min} }

func (p Policy) Validate(s string) error {
	if len(s) < p.MinLength {
		return errors.New("too short")
	}
	return nil
}
