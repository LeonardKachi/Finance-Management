#!/usr/bin/env python3
"""Fetch market data and write data.json for the Imperium Pecuniae page.

Edit STOCKS, FUNDS and INDICES to change what is ranked. Tickers that return
no data are skipped and listed under "errors" in data.json.
Sources: Yahoo Finance (via yfinance), European Central Bank, Bundesbank.
"""
import csv, io, json, re, sys, urllib.request
import datetime as dt
import pandas as pd
import yfinance as yf

# (Yahoo symbol, display name, market)
STOCKS = [
    ("ADS.DE","Adidas","Germany"),("AIR.DE","Airbus","Germany"),("ALV.DE","Allianz","Germany"),
    ("BAS.DE","BASF","Germany"),("BAYN.DE","Bayer","Germany"),("BMW.DE","BMW","Germany"),
    ("CBK.DE","Commerzbank","Germany"),("CON.DE","Continental","Germany"),("DBK.DE","Deutsche Bank","Germany"),
    ("DB1.DE","Deutsche Boerse","Germany"),("DHL.DE","DHL Group","Germany"),("DTE.DE","Deutsche Telekom","Germany"),
    ("EOAN.DE","E.ON","Germany"),("FRE.DE","Fresenius","Germany"),("HEI.DE","Heidelberg Materials","Germany"),
    ("HEN3.DE","Henkel","Germany"),("IFX.DE","Infineon","Germany"),("MBG.DE","Mercedes-Benz","Germany"),
    ("MRK.DE","Merck KGaA","Germany"),("MTX.DE","MTU Aero Engines","Germany"),("MUV2.DE","Munich Re","Germany"),
    ("P911.DE","Porsche AG","Germany"),("QIA.DE","Qiagen","Germany"),("RHM.DE","Rheinmetall","Germany"),
    ("RWE.DE","RWE","Germany"),("SAP.DE","SAP","Germany"),("SIE.DE","Siemens","Germany"),
    ("ENR.DE","Siemens Energy","Germany"),("SHL.DE","Siemens Healthineers","Germany"),("VOW3.DE","Volkswagen","Germany"),
    ("ZAL.DE","Zalando","Germany"),("AIXA.DE","Aixtron","Germany"),("WAF.DE","Siltronic","Germany"),
    ("SMHN.DE","SUSS MicroTec","Germany"),("NDX1.DE","Nordex","Germany"),("HOT.DE","Hochtief","Germany"),
    ("TKA.DE","thyssenkrupp","Germany"),
    ("ASML.AS","ASML","Netherlands"),("MC.PA","LVMH","France"),("RMS.PA","Hermes","France"),
    ("SU.PA","Schneider Electric","France"),("SOI.PA","Soitec","France"),("ATS.VI","AT&S","Austria"),
    ("TPRO.MI","Technoprobe","Italy"),("SPM.MI","Saipem","Italy"),("MT.AS","ArcelorMittal","Netherlands"),
    ("NOVO-B.CO","Novo Nordisk","Denmark"),
    ("NVDA","NVIDIA","US"),("AVGO","Broadcom","US"),("PLTR","Palantir","US"),("META","Meta Platforms","US"),
    ("MSFT","Microsoft","US"),("AAPL","Apple","US"),("AMZN","Amazon","US"),("GOOGL","Alphabet","US"),
    ("TSLA","Tesla","US"),("LLY","Eli Lilly","US"),("JPM","JPMorgan Chase","US"),("COST","Costco","US"),
    ("GEV","GE Vernova","US"),("AMD","AMD","US"),("MU","Micron","US"),("ORCL","Oracle","US"),("NFLX","Netflix","US"),
]
FUNDS = [
    ("AGG","iShares Core US Aggregate Bond ETF","US"),("BND","Vanguard Total Bond Market ETF","US"),
    ("BNDX","Vanguard Total International Bond ETF","US"),("TLT","iShares 20+ Year Treasury Bond ETF","US"),
    ("IEF","iShares 7-10 Year Treasury Bond ETF","US"),("SHY","iShares 1-3 Year Treasury Bond ETF","US"),
    ("LQD","iShares Investment Grade Corporate Bond ETF","US"),("HYG","iShares High Yield Corporate Bond ETF","US"),
    ("TIP","iShares TIPS Bond ETF","US"),("EMB","iShares JPM USD Emerging Markets Bond ETF","US"),
    ("EUNH.DE","iShares Core Euro Government Bond UCITS ETF","Germany"),
]
INDICES = [("^GDAXI","DAX"),("^STOXX50E","Euro Stoxx 50"),("^GSPC","S&P 500")]

def series_for(df, sym, many):
    for getter in (lambda: df[sym]["Close"], lambda: df["Close"][sym], lambda: df["Close"]):
        try:
            s = getter()
            if isinstance(s, pd.DataFrame):
                s = s.iloc[:, 0]
            s = s.dropna()
            if len(s) > 20:
                idx = pd.DatetimeIndex(s.index)
                if idx.tz is not None:
                    idx = idx.tz_localize(None)
                s.index = idx
                return s
        except Exception:
            continue
    return None

def history(symbols):
    out, errs = {}, []
    try:
        df = yf.download(symbols, period="2y", interval="1d", auto_adjust=True,
                         group_by="ticker", progress=False, threads=True)
    except Exception as e:
        return out, [f"download failed: {e}"]
    for s in symbols:
        ser = series_for(df, s, len(symbols) > 1)
        if ser is None:
            errs.append(s)
        else:
            out[s] = ser
    return out, errs

def pct(ser, ref):
    base = ser[ser.index <= ref]
    if base.empty:
        return None
    b, last = float(base.iloc[-1]), float(ser.iloc[-1])
    return round((last / b - 1) * 100, 2) if b else None

def rank(items, hist, today):
    ytd_ref = pd.Timestamp(today.year - 1, 12, 31)
    rows = []
    for sym, name, market in items:
        ser = hist.get(sym)
        if ser is None:
            continue
        rows.append({"symbol": sym, "name": name, "market": market,
                     "ytd": pct(ser, ytd_ref),
                     "m1": pct(ser, today - pd.Timedelta(days=30)),
                     "y1": pct(ser, today - pd.Timedelta(days=365)),
                     "asOf": ser.index[-1].strftime("%Y-%m-%d")})
    rows = [r for r in rows if r["ytd"] is not None]
    rows.sort(key=lambda r: r["ytd"], reverse=True)
    return rows

def http(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def ecb(tenor):
    url = ("https://data-api.ecb.europa.eu/service/data/YC/"
           f"B.U2.EUR.4F.G_N_A.SV_C_YM.SR_{tenor}?lastNObservations=1&format=csvdata")
    row = next(csv.DictReader(io.StringIO(http(url))))
    return float(row["OBS_VALUE"]), row["TIME_PERIOD"]

def bundesbank():
    txt = http("https://api.statistiken.bundesbank.de/rest/data/BBK01/WT1010?lastNObservations=1&format=csv")
    last = [l for l in txt.splitlines() if l.strip()][-1]
    parts = [p.strip('" ') for p in re.split(r"[;,]", last)]
    date = next((p for p in parts if re.match(r"^\d{4}-\d{2}-\d{2}$", p)), None)
    val = None
    for p in reversed(parts):
        try:
            val = float(p); break
        except ValueError:
            continue
    if date is None or val is None or not (-2 < val < 15):
        raise ValueError("unexpected Bundesbank format")
    return val, date

def main():
    today = pd.Timestamp.utcnow().tz_localize(None).normalize()
    errors = []
    sh, e1 = history([s[0] for s in STOCKS]); errors += e1
    fh, e2 = history([s[0] for s in FUNDS]); errors += e2
    ih, e3 = history([s[0] for s in INDICES] + ["^TNX"]); errors += e3
    stocks = rank(STOCKS, sh, today)
    funds = rank(FUNDS, fh, today)
    indices = rank([(s, n, "Index") for s, n in INDICES], ih, today)
    yields = []
    try:
        v, d = bundesbank()
        yields.append({"name": "German 10-year federal securities", "value": v, "asOf": d, "source": "Bundesbank"})
    except Exception as e:
        errors.append(f"Bundesbank: {e}")
    for t in ("2Y", "5Y", "10Y", "30Y"):
        try:
            v, d = ecb(t)
            yields.append({"name": f"Euro area government bonds, {t.replace('Y','-year')} (AAA issuers)", "value": v, "asOf": d, "source": "European Central Bank"})
        except Exception as e:
            errors.append(f"ECB {t}: {e}")
    tnx = ih.get("^TNX")
    if tnx is not None:
        yields.append({"name": "US 10-year Treasury", "value": round(float(tnx.iloc[-1]), 3), "asOf": tnx.index[-1].strftime("%Y-%m-%d"), "source": "Yahoo Finance"})
    if not stocks and not yields:
        print("No data fetched, leaving data.json unchanged", file=sys.stderr)
        sys.exit(1)
    out = {"updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "stocks": stocks[:10], "funds": funds[:8], "indices": indices, "yields": yields,
           "universe": {"stocks": len(stocks), "funds": len(funds)}, "errors": errors[:40]}
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"Wrote data.json: {len(stocks)} stocks ranked, {len(funds)} funds, {len(yields)} yields, {len(errors)} errors")

if __name__ == "__main__":
    main()
