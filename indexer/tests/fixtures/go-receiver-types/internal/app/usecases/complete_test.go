package usecases

import "testing"

type fakePolicy struct{}

func (fakePolicy) Validate(string) error { return nil }

func setup(t *testing.T) (*Complete, Repo) {
	t.Helper()
	return &Complete{}, nil
}

func TestExecute(t *testing.T) {
	f := fakePolicy{}
	if err := f.Validate("x"); err != nil {
		t.Fatal(err)
	}
	uc, _ := setup(t)
	_ = uc.Execute("secret") // multi-value helper: uc is *Complete
}
