"""The dashboard's browser model must give the numbers the build gives.

The page runs `model()` from pipeline/template.html when a reader moves a
slider. This test cuts that function out of the template, runs it under Node
for the bear, base and bull assumptions in config.SCENARIOS, and compares the
result with metrics.scenarios() and metrics.priced_in() in
data/derived/metrics.json. Skipped when Node is not installed.
"""

import json
import os
import shutil
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def browser_model():
    with open(os.path.join(ROOT, "pipeline", "template.html")) as fh:
        src = fh.read()
    start = src.index("/* model:start")
    end = src.index("/* model:end */")
    return src[src.index("*/", start) + 2:end]


@unittest.skipIf(shutil.which("node") is None, "needs Node")
class BrowserModelParity(unittest.TestCase):
    def test_same_numbers_as_python(self):
        with open(os.path.join(ROOT, "data", "derived", "metrics.json")) as fh:
            m = json.load(fh)
        sc, pi = m["scenarios"], m["priced_in"]
        k = {"market_year": sc["market_volume_year_now"], "buyback_part": sc["buyback_part_of_captured"],
             "new_near": sc["new_near_per_year"], "supply": pi["supply_near"],
             "discount": pi["mid"]["discount"], "growth": pi["mid"]["growth"]}
        cases = [dict(r["assumptions"], price=sc["price_usd"]) for r in sc["rows"]]
        for c in cases:
            c.pop("story", None)
        js = browser_model() + "\nconsole.log(JSON.stringify(%s.map(function (p) { return model(p, %s); })));" % (
            json.dumps(cases), json.dumps(k))
        got = json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)
        priced = {r["name"]: r for r in pi["rows"]}
        for row, js_row in zip(sc["rows"], got):
            for key in ("intents_volume", "fees", "captured_usd", "bought_back_near", "coverage", "capture_for_half"):
                self.assertAlmostEqual(js_row[key], row[key], delta=abs(row[key]) * 1e-9, msg=(row["name"], key))
            for key in ("captured_per_near", "part_of_price"):
                want = priced[row["name"]][key]
                self.assertAlmostEqual(js_row[key], want, delta=abs(want) * 1e-9, msg=(row["name"], key))


if __name__ == "__main__":
    unittest.main()
