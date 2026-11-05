"""Read-only, exact lifecycle comparison against all canonical settled ledger parts."""
import collections
import json
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root/"claude-liam-signal/python"))
from hamid import paper, position_state


def run():
    opened = paper._read(paper.OPEN)
    counts = collections.Counter()
    shapes = collections.Counter()
    keys = {position_state.key(p) for p in opened} - {None}
    for line in paper.jsonl_store.lines(paper.CLOSED):
        row = json.loads(line)
        k = position_state.key(row)
        if k is not None and row.get("outcome") and row.get("closed") and k in keys:
            counts[k] += 1
            shapes[row["outcome"]] += 1
    print(json.dumps({"open_rows":len(opened),"exact_settled_open_rows":sum(position_state.key(p) in counts for p in opened),
                      "distinct_exact_matches":len(counts),"matched_closed_rows":sum(counts.values()),
                      "outcomes":shapes,"unknown_identity":sum(position_state.key(p) is None for p in opened)},indent=2))


if __name__ == "__main__":
    run()
