# signal

Hamid Signal Agent — SMC panel (v4.8).

## Regression test

```bash
python3 -m http.server 8901 --directory . &
npm i playwright  # once
node tests/regression.mjs
```
All 15 checks must print true (Binance is mocked; no network needed).
