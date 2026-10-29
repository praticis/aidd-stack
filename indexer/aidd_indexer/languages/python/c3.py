"""C3's linearization, the order CPython gives a class's bases in its MRO."""


def merge(sequences: list[list]) -> list | None:
    """C3's merge: None when the sequences admit no order."""
    pending = [list(s) for s in sequences if s]
    out = []
    while pending:
        head = next((s[0] for s in pending if not any(s[0] in t[1:] for t in pending)), None)
        if head is None:
            return None
        out.append(head)
        pending = [r for r in ([x for x in s if x != head] for s in pending) if r]
    return out
