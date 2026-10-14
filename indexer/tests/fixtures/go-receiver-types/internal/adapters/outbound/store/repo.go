package store

type MemRepo struct{ rows []string }

func (m *MemRepo) Save(s string) error {
	m.rows = append(m.rows, s)
	return nil
}
