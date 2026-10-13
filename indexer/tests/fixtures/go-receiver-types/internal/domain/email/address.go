package email

type Address struct{ Raw string }

func (a Address) Validate() error { return nil }
