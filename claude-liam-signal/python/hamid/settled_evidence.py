"""Select one consistent observed outcome per identifiable paper lifecycle. Never rewrite history."""
from hamid.position_state import key, geometry


class Outcomes:
    def __init__(self):
        self.first = {}
        self.conflict = set()

    def observe(self, row, index):
        ident = key(row)
        if ident is None:
            return None
        outcome = (row.get("outcome"), row.get("filled"), row.get("R"), row.get("R_net"))
        when = row.get("closed") or 0
        prev = self.first.get(ident)
        if prev and prev[0] != outcome:
            self.conflict.add(ident)
        if not prev or (when,index) < (prev[1],prev[2]):
            self.first[ident] = outcome,when,index
        return ident

    def status(self, ident, index):
        if ident is None:
            return "unidentified"
        if ident in self.conflict:
            return "conflicting"
        if self.first[ident][2] != index:
            return "repeat"
        if not geometry(ident[1],ident[4],ident[5],ident[6],ident[7]):
            return "invalid_levels"
        return "unique"


def consistent(rows):
    evidence = Outcomes()
    tagged = [(evidence.observe(r,i),r) for i,r in enumerate(rows)]
    # Older unidentifiable data is not a proven repeat. Leave it in the archival
    # reader; callers using this analysis view may only learn from unique evidence.
    return [r for i,(k,r) in enumerate(tagged) if evidence.status(k,i)=="unique"]
