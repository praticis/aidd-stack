package usecases

type Clock interface{ Now() int64 }

type Store interface {
	Repo
}

type Report struct {
	clock Clock
	store Store
}

func (r *Report) Stamp() int64 { return r.clock.Now() }

func (r *Report) Keep(s string) error { return r.store.Save(s) }
