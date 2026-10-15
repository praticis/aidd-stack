package clock

type System struct{}

func (System) Now() int64 { return 1 }

type Fixed struct{ At int64 }

func (f Fixed) Now() int64 { return f.At }
