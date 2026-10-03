package usecases

import (
	"example.com/svc/internal/domain/email"
	pw "example.com/svc/internal/domain/password"
)

type Repo interface{ Save(string) error }

type Complete struct {
	policy pw.Policy
	repo   Repo
}

func NewComplete(policy pw.Policy, repo Repo) *Complete { return &Complete{policy: policy, repo: repo} }

// field receiver: uc.policy -> pw.Policy
func (uc *Complete) Execute(secret string) error {
	if err := uc.policy.Validate(secret); err != nil {
		return err
	}
	return uc.repo.Save(secret)
}

// parameter receiver: p -> pw.Policy
func Check(p pw.Policy, s string) error { return p.Validate(s) }

// composite literal receiver: a -> email.Address
func CheckEmail(raw string) error {
	a := email.Address{Raw: raw}
	return a.Validate()
}

// constructor receiver: p := pw.NewPolicy(8) -> pw.Policy (return type of NewPolicy)
func CheckDefault(s string) error {
	p := pw.NewPolicy(8)
	return p.Validate(s)
}
