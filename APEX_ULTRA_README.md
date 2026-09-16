# APEX ULTRA v1 — Unified 12-Engine Confluence Strategy (sina)

**File:** `APEX_ULTRA.pine` · **Pine Script:** `v6` · **Type:** `strategy` (backtestable) · **Repaint:** none (closed-bar only)

This is the single-script synthesis of everything in `PINE_SCRIPT.zip` (UICE, OMEGA, AICE PRO, the multi-strategy containers, the MTF ADX/DMI/MFI/CCI + Supertrend/ZLSMA/MDFS family, the Luxalgo ICT/SMC suite, the DGT collection) and the APEX GEN5 specification — fused into **one decision pipeline** instead of 14+ overlapping sub-strategies.

---

## 1. Why one pipeline instead of many containers

Your previous containers fire 14 independent strategies on the same chart — which means 14 independent opinions that conflict, and no single measure of "is this setup good?". APEX ULTRA replaces that with the APEX GEN5 five-station design:

```
Station 1  Data quality & warm-up      epsilon floor, ATR floor, history gate
Station 2  Twelve analyst engines      E01–E12 each emit a directional evidence score
Station 3  Context & confluence        weighted aggregation + conflict penalty (0.40)
                                         + thin-evidence penalty (0.25) + regime multiplier
Station 4  Setup gates                 min score, min independent families, hard vetoes
Station 5  Risk kernel & execution     structural stops, TP1 partial, breakeven,
                                         chandelier trail, daily-loss breaker, streak cooldown
```

A signal exists **only** when enough *independent* engine families agree, after conflicting families have discounted the score. That is the core of the "accuracy" claim: fewer signals, each with a measurable confluence basis shown on the dashboard.

## 2. The twelve engines

| Engine | What it scores | Max points |
|---|---|---|
| **E01 Structure** | BOS / CHoCH on confirmed fractal swings (event + 0.85 decay), displacement-aware | 35 |
| **E02 Liquidity** | Sweep + reclaim (SSL/BSL raid), equal-highs/lows pools, Wyckoff spring/upthrust (sweep + reclaim + volume) | 60 |
| **E03 Volume** | VWAP bias (intraday), OBV trend, VFI (log-return weighted flow, wash-trading cap), CMF, volume spike, POC trend continuation | 42 |
| **E04 Volatility** | BB/Keltner squeeze release in breakout direction; ATR-ratio health band | 25 |
| **E05 FVG** | Tracked fair value gaps (min-width × ATR), tap-without-fill scoring, expiry | (in E02) |
| **E06 Order Blocks** | Origin-candle OB before displacement, retest-and-hold scoring, 48-bar expiry | (in E02) |
| **E07 RTM/ICT** | Premium/discount equilibrium, OTE 61.8–79.2% | (in E02) |
| **E08 Wyckoff** | Spring / upthrust with volume confirmation | (in E02) |
| **E09 Trend** | SuperTrend, ZLSMA position+slope, EMA 21/50/200 stack, ADX direction, **dual-HTF bias** (4h + 1D by default) | 60 |
| **E10 Momentum** | RSI + confirmed-pivot divergence, MACD, WaveTrend, MFI, Stochastic, CCI ±100 | 60 |
| **E11 Regime** | ADX + volatility rank + compression rank + HH/HL structure → TREND UP / TREND DOWN / RANGE / CHOP. **Blocks counter-trend signals** (gate), discounts CHOP (×0.85), boosts aligned trend (×1.08) | gate |
| **E12 Temporal** | UTC killzone gate (Asia 00–03, London 07–10, NY 12:30–15:30) — off by default, auto-off on D+ | gate |
| **Candle Intel** | Displacement body (×ATR), rejection wick (stop-hunt absorption), inside-bar mother-breakout | 25 |

## 3. The confluence math (Station 3)

```
s_i        = score_i / max_i                       (each family normalized to −1…+1)
confScore  = Σ w_i·s_i / Σ w_i · 100               (±100, default weights: trend 1.5,
                                                    struct/liq/volu/mom 1.0, volat/cndl 0.8)
active     = families with |s_i| ≥ 0.20
conflictRatio = (active − agreeing) / active
thinRatio     = actFam ≥ 3 ? 0 : (3 − actFam) / 3
finalScore = confScore · (1 − 0.40·conflictRatio) · (1 − 0.25·thinRatio) · regimeMult
```

- **Conflict penalty 0.40** — APEX SL-2: if half the active families disagree with the direction, the score loses 20%.
- **Thin-evidence penalty 0.25** — a score built on 1–2 families is discounted.
- **Regime multiplier** — ×1.08 when the signal aligns with a confirmed HTF-aligned trend, ×0.85 in CHOP.

**Signal:** `finalScore ≥ +50` (default) with **≥ 3 families agreeing** and **all vetoes clear** → long. Mirror for short.

## 4. Hard vetoes (Station 4 / Risk Kernel, SL-5 style)

| Veto | Rule |
|---|---|
| **REGIME** | No longs in confirmed TREND DOWN, no shorts in TREND UP |
| **VOL-EXTREME** | ATR/ATR-avg < 0.6 (dead tape) or > 3.0 (news spike) |
| **DAY-LOSS** | Equity below day-start − 4% → flat for the day (circuit breaker) |
| **STREAK** | 3 consecutive losses → 8-bar cooldown |
| **SESSION** | Outside selected UTC killzones (if enabled) |
| **COOLDOWN** | 12 bars between signals |
| **WARMUP** | First max(300, POC-bars+100) bars |

The dashboard shows the **current active veto** (or `NONE`) so you always know *why* a bar is clean or blocked.

## 5. Position management (Station 5)

- **Size:** fixed-fractional — `qty = equity · risk% / stopDistance` (default 1% risk).
- **Stop:** structural (last confirmed swing) **floored** at 1.5×ATR and **capped** at 2.5×ATR — the R multiple is always bounded.
- **TP1:** 1.5R → closes 50%.
- **Breakeven:** at +1.0R the stop moves to entry + 0.1R.
- **Trail:** after TP1, chandelier = highest high − 2.5×ATR.
- **TP2:** 3.0R for the remainder.
- **Reversal:** an opposite qualifying signal flips the position (toggleable).

## 6. Install & use

1. TradingView → Pine Editor → paste `APEX_ULTRA.pine` → **Add to chart**.
2. It is a strategy: open the **Strategy Tester** to backtest. Signals are identical to what the labels/alerts show.
3. **Alerts** (no webhook needed): *Long Setup / Short Setup / Any Setup / BOS / CHoCH* — plus toast alerts on each setup. For webhooks, pick any of the five `alertcondition`s.
4. Best starting points: 15m–4h on liquid crypto perps (the APEX core-10 universe). On 1m–5m, consider raising `Min Confluence Score` to 55–60 and `Cooldown` to 18–24.

### Parameter philosophy

Defaults are deliberately conservative (few, high-confluence signals). The three knobs that matter most, in order:

1. **Min Confluence Score** (50) — your primary quality dial.
2. **HTF 1 / HTF 2** (4h / 1D) — your structural reference frames; bias is weighted 0.6/0.4.
3. **Min Independent Families** (3) — how much multi-engine agreement you demand.

Everything else has a tooltip explaining its exact role. Weights (section 0) let you re-balance the engine mix per symbol class — e.g. raise **Liquidity** weight on 5m–15m, raise **Trend** weight on 4h+.

## 7. Non-repainting guarantees

- `calc_on_every_tick = false` (closed bars only).
- Swing pivots are Williams fractals confirmed `k` bars after the peak — a signal can never move to a past bar.
- MTF via `request.security(..., gaps_off, lookahead_off)` — only **closed** HTF bars are read.
- Zone tracking (FVG/OB) only uses closed-bar data; retests are evaluated on the close.
- Entry fills at the **close of the signal bar** (`process_orders_on_close = true`).

## 8. Efficiency notes

- 4 `request.security` calls total (limit is 40).
- 88 inputs (limit is 400).
- All expensive loops bounded (volume profile ≤ 1000 bars, zone arrays ≤ 12, drawing-object ring buffers ≤ 350 labels / 24 boxes / 1 line).
- Every shared primitive (ATR, ZLSMA, SuperTrend, EMA stack, ADX) computed **once** and reused across engines — no duplicate `ta.*` calls, no shared-state corruption between engines.

## 9. Validation checklist (do this before trusting it with money)

1. Backtest ≥ 2 years on 3 symbols × 2 timeframes (e.g. BTCUSDT 15m/4h, ETHUSDT 15m/4h, BNBUSDT 15m/4h).
2. Check **profit factor, max DD, and expectancy per R** in the Strategy Tester — the labels show the score so you can eyeball whether high-score setups outperform low-score ones.
3. Sweep `Min Confluence Score` 45→70 on your symbol — the score that maximizes expectancy, not the one that maximizes trade count, is yours.
4. Paper trade live for ≥ 2 weeks; compare fills vs the backtest (slippage is modeled at 1 tick + 0.05% commission).
5. Only then size risk at 1%+ per trade.

> ⚠️ Not financial advice. No indicator is "the most accurate" in an absolute sense — it is the most *disciplined, transparent, and backtestable* synthesis of your library. Edge decays; re-validate quarterly.
