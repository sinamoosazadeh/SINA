"""Canonical 74-feature registry with executable producers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from apex.quality import Quality
from apex.nonfinite import sanitize_number


@dataclass(frozen=True)
class FeatureDef:
    feature_id: str
    name: str
    domain: str
    classification: str  # NATIVE | DERIVED | PROXY | EXTERNAL
    runtime_admitted: bool
    warmup: int
    producer: str


def _ohlc(candles: list[dict]) -> tuple[list[float], list[float], list[float], list[float], list[float]]:
    o = [c["open"] for c in candles]
    h = [c["high"] for c in candles]
    l = [c["low"] for c in candles]
    cl = [c["close"] for c in candles]
    v = [c["volume"] for c in candles]
    return o, h, l, cl, v


def _sma(xs: list[float], n: int) -> float | None:
    if len(xs) < n:
        return None
    return sum(xs[-n:]) / n


def _ema(xs: list[float], n: int) -> float | None:
    if len(xs) < n:
        return None
    k = 2 / (n + 1)
    e = xs[0]
    for x in xs[1:]:
        e = x * k + e * (1 - k)
    return e


def _stdev(xs: list[float], n: int) -> float | None:
    if len(xs) < n:
        return None
    w = xs[-n:]
    m = sum(w) / n
    var = sum((x - m) ** 2 for x in w) / n
    return math.sqrt(var)


def _atr(h: list[float], l: list[float], c: list[float], n: int) -> float | None:
    if len(c) < n + 1:
        return None
    trs = []
    for i in range(1, len(c)):
        tr = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        trs.append(tr)
    return _sma(trs, n)


def _rsi(c: list[float], n: int = 14) -> float | None:
    if len(c) < n + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(c)):
        d = c[i] - c[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag = _sma(gains, n)
    al = _sma(losses, n)
    if ag is None or al is None:
        return None
    if al == 0:
        return 100.0
    rs = ag / al
    return 100 - (100 / (1 + rs))


def compute_feature(feature_id: str, candles: list[dict]) -> tuple[object, Quality]:
    if not candles:
        return None, Quality.INSUFFICIENT_HISTORY
    o, h, l, c, v = _ohlc(candles)
    last = c[-1]
    defs: dict[str, Callable[[], float | None]] = {
        "F01": lambda: last,
        "F02": lambda: o[-1],
        "F03": lambda: h[-1],
        "F04": lambda: l[-1],
        "F05": lambda: v[-1],
        "F06": lambda: h[-1] - l[-1],
        "F07": lambda: abs(c[-1] - o[-1]),
        "F08": lambda: (c[-1] - o[-1]) / o[-1] if o[-1] else None,
        "F09": lambda: _sma(c, 20),
        "F10": lambda: _sma(c, 50),
        "F11": lambda: _sma(c, 200),
        "F12": lambda: _ema(c, 12),
        "F13": lambda: _ema(c, 26),
        "F14": lambda: (lambda e12, e26: None if e12 is None or e26 is None else e12 - e26)(_ema(c, 12), _ema(c, 26)),
        "F15": lambda: _rsi(c, 14),
        "F16": lambda: _atr(h, l, c, 14),
        "F17": lambda: _stdev(c, 20),
        "F18": lambda: (lambda m, s: None if m is None or s is None or s == 0 else (last - m) / s)(_sma(c, 20), _stdev(c, 20)),
        "F19": lambda: _sma(v, 20),
        "F20": lambda: v[-1] / _sma(v, 20) if _sma(v, 20) else None,
        "F21": lambda: max(h[-20:]) if len(h) >= 20 else None,
        "F22": lambda: min(l[-20:]) if len(l) >= 20 else None,
        "F23": lambda: (last - min(l[-20:])) / (max(h[-20:]) - min(l[-20:])) if len(h) >= 20 and max(h[-20:]) != min(l[-20:]) else None,
        "F24": lambda: sum(1 for i in range(-min(10, len(c) - 1), 0) if c[i] > c[i - 1]),
        "F25": lambda: (c[-1] - c[-10]) / c[-10] if len(c) >= 10 and c[-10] else None,
        "F26": lambda: (c[-1] - c[-20]) / c[-20] if len(c) >= 20 and c[-20] else None,
        "F27": lambda: (h[-1] - max(o[-1], c[-1])),
        "F28": lambda: (min(o[-1], c[-1]) - l[-1]),
        "F29": lambda: v[-1] * last,
        "F30": lambda: candles[-1].get("open_interest"),
        "F31": lambda: None if len(candles) < 2 or candles[-1].get("open_interest") is None or candles[-2].get("open_interest") is None else candles[-1]["open_interest"] - candles[-2]["open_interest"],
        "F32": lambda: _sma([x.get("open_interest") or 0 for x in candles if x.get("open_interest") is not None], 20) if sum(1 for x in candles if x.get("open_interest") is not None) >= 20 else None,
        "F33": lambda: 1.0 if c[-1] > o[-1] else (-1.0 if c[-1] < o[-1] else 0.0),
        "F34": lambda: sum(v[i] for i in range(len(c)) if c[i] >= o[i]) / sum(v) if sum(v) else None,
        "F35": lambda: max(h) - min(l) if h and l else None,
        "F36": lambda: _sma([h[i] - l[i] for i in range(len(h))], 14),
        "F37": lambda: (lambda a: None if a is None or a == 0 else (h[-1] - l[-1]) / a)(_atr(h, l, c, 14)),
        "F38": lambda: _ema(c, 9),
        "F39": lambda: _ema(c, 21),
        "F40": lambda: _sma(c, 10),
        "F41": lambda: (c[-1] - _sma(c, 20)) if _sma(c, 20) else None,
        "F42": lambda: 1.0 if _sma(c, 20) and last > _sma(c, 20) else 0.0,
        "F43": lambda: 1.0 if _sma(c, 50) and _sma(c, 20) and _sma(c, 20) > _sma(c, 50) else 0.0,
        "F44": lambda: abs(c[-1] - o[-1]) / (h[-1] - l[-1]) if h[-1] != l[-1] else None,
        "F45": lambda: (h[-1] - l[-1]) / last if last else None,
        "F46": lambda: _stdev([math.log(c[i] / c[i - 1]) for i in range(1, len(c))], 20) if len(c) >= 21 else None,
        "F47": lambda: max(h[-14:]) - min(l[-14:]) if len(h) >= 14 else None,
        "F48": lambda: (c[-1] - min(l[-14:])) / (max(h[-14:]) - min(l[-14:])) * 100 if len(h) >= 14 and max(h[-14:]) != min(l[-14:]) else None,
        "F49": lambda: sum(c[i] > c[i - 1] for i in range(-min(5, len(c) - 1), 0)),
        "F50": lambda: sum(c[i] < c[i - 1] for i in range(-min(5, len(c) - 1), 0)),
        "F51": lambda: v[-1] - (_sma(v, 20) or 0),
        "F52": lambda: 1.0 if _sma(v, 20) and v[-1] > 1.5 * _sma(v, 20) else 0.0,
        "F53": lambda: (o[-1] + h[-1] + l[-1] + c[-1]) / 4,
        "F54": lambda: (h[-1] + l[-1]) / 2,
        "F55": lambda: (h[-1] + l[-1] + c[-1]) / 3,
        "F56": lambda: last - l[-1],
        "F57": lambda: h[-1] - last,
        "F58": lambda: min((h[i] - l[i]) for i in range(-min(20, len(h)), 0)),
        "F59": lambda: max((h[i] - l[i]) for i in range(-min(20, len(h)), 0)),
        "F60": lambda: 1.0 if len(c) >= 3 and c[-1] > h[-2] else 0.0,
        "F61": lambda: 1.0 if len(c) >= 3 and c[-1] < l[-2] else 0.0,
        "F62": lambda: (c[-1] - c[0]) / c[0] if c[0] else None,
        "F63": lambda: len(c),
        "F64": lambda: sum(v),
        "F65": lambda: max(v[-20:]) if len(v) >= 20 else max(v) if v else None,
        "F66": lambda: 1.0 if last == h[-1] else 0.0,
        "F67": lambda: 1.0 if last == l[-1] else 0.0,
        "F68": lambda: abs(_ema(c, 12) - _ema(c, 26)) if _ema(c, 12) is not None and _ema(c, 26) is not None else None,
        "F69": lambda: (_rsi(c, 14) - 50) / 50 if _rsi(c, 14) is not None else None,
        "F70": lambda: 1.0 if _rsi(c, 14) is not None and _rsi(c, 14) > 70 else ( -1.0 if _rsi(c, 14) is not None and _rsi(c, 14) < 30 else 0.0),
        "F71": lambda: None,  # external evidence placeholder → UNAVAILABLE not fabricated
        "F72": lambda: None,  # L2 microstructure not available from OHLCV
        "F73": lambda: 0.0,  # funding rate forbidden at runtime — explicit zero-weight analytical unused
        "F74": lambda: 1.0 if candles[-1]["quality"] == "VALID" else 0.0,
    }
    if feature_id not in defs:
        return None, Quality.NOT_ADMITTED
    # F71/F72 are not admitted as native
    if feature_id in {"F71", "F72"}:
        return None, Quality.NOT_ADMITTED
    if feature_id == "F73":
        return None, Quality.NOT_ADMITTED  # funding-rate excluded from runtime
    if feature_id in {"F30", "F31", "F32"}:
        oi_ok = candles[-1].get("open_interest") is not None and candles[-1].get("oi_quality") == "VALID"
        if not oi_ok:
            return None, Quality.UNAVAILABLE
    raw = defs[feature_id]()
    if raw is None:
        return None, Quality.INSUFFICIENT_HISTORY
    bound = sanitize_number(raw)
    if not bound.is_value():
        return None, bound.quality
    return bound.value, Quality.VALID


def registry_74() -> list[FeatureDef]:
    domains = [
        "PRICE", "PRICE", "PRICE", "PRICE", "VOLUME", "RANGE", "RANGE", "RETURN",
        "TREND", "TREND", "TREND", "TREND", "TREND", "MOMENTUM", "MOMENTUM", "VOLATILITY",
        "VOLATILITY", "VOLATILITY", "VOLUME", "VOLUME", "STRUCTURE", "STRUCTURE", "STRUCTURE", "MOMENTUM",
        "RETURN", "RETURN", "RANGE", "RANGE", "VOLUME", "OI", "OI", "OI",
        "IMBALANCE", "VOLUME", "RANGE", "VOLATILITY", "VOLATILITY", "TREND", "TREND", "TREND",
        "TREND", "TREND", "TREND", "RANGE", "VOLATILITY", "VOLATILITY", "RANGE", "MOMENTUM",
        "MOMENTUM", "MOMENTUM", "VOLUME", "VOLUME", "PRICE", "PRICE", "PRICE", "RANGE",
        "RANGE", "RANGE", "RANGE", "STRUCTURE", "STRUCTURE", "RETURN", "META", "VOLUME",
        "VOLUME", "STRUCTURE", "STRUCTURE", "MOMENTUM", "MOMENTUM", "MOMENTUM",
        "EXTERNAL", "MICROSTRUCTURE", "FORBIDDEN", "QUALITY",
    ]
    classes = ["NATIVE"] * 70 + ["EXTERNAL", "PROXY", "RESEARCH_ONLY", "DERIVED"]
    admitted = [True] * 70 + [False, False, False, True]
    warm = [1] * 74
    items = []
    for i in range(1, 75):
        fid = f"F{i:02d}"
        items.append(
            FeatureDef(
                feature_id=fid,
                name=fid,
                domain=domains[i - 1],
                classification=classes[i - 1],
                runtime_admitted=admitted[i - 1],
                warmup=warm[i - 1],
                producer="feature_engine",
            )
        )
    return items


def compute_all_features(candles: list[dict]) -> dict[str, dict]:
    out = {}
    for f in registry_74():
        if not f.runtime_admitted:
            out[f.feature_id] = {"value": None, "quality": Quality.NOT_ADMITTED.value, "classification": f.classification}
            continue
        val, q = compute_feature(f.feature_id, candles)
        out[f.feature_id] = {"value": val, "quality": q.value, "classification": f.classification}
    return out
