import React, { useState, useEffect, useCallback } from "react";
import { createRoot } from "react-dom/client";
import { InvestorResearch } from "../../frontend/src/InvestorResearch";
import "../../frontend/src/styles.css";
declare const chrome: any;
function Companion() {
  const [base, setBase] = useState("https://investoreye.harkiratsingh.tech"),
    [token, setToken] = useState(""),
    [saved, setSaved] = useState(false),
    [quotes, setQuotes] = useState<any[]>([]),
    [watch, setWatch] = useState<string[]>([]),
    [search, setSearch] = useState(""),
    [error, setError] = useState(""),
    [selected,setSelected]=useState(""),
    [provider,setProvider]=useState("binance");
  useEffect(() => {
    chrome.storage.session.get(["base", "token"]).then((x: any) => {
      if (x.base) setBase(x.base);
      if (x.token) {
        setToken(x.token);
        setSaved(true);
      }
    });
  }, []);
  const request=useCallback(async (path: string, method = "GET", body?: unknown) => {
    const r = await fetch(base + "/v1" + path, {
      method,
      credentials: "omit",
      headers: {
        Authorization: "Bearer " + token,
        "X-Eye-Client": "workspace",
        "Content-Type": "application/json",
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const j = await r.json();
    if (!r.ok) throw Error(j.detail || "Request failed");
    return j;
  },[base,token]);
  async function refresh() {
    try {
      const result=await request("/live/instruments?provider="+provider+"&q="+encodeURIComponent(search));
      setQuotes(result.instruments);
      setWatch((await request("/live/saved")).instrument_ids);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    if (!saved) return;
    refresh();
    const timer = setInterval(refresh, 15000);
    return () => clearInterval(timer);
  }, [saved, base, token,provider,search]);
  async function connect() {
    try {
      const url = new URL(base);
      if (
        url.protocol !== "https:" &&
        !["localhost", "127.0.0.1"].includes(url.hostname)
      )
        throw Error("Use HTTPS except for localhost");
      const ok = await chrome.permissions.request({
        origins: [url.origin + "/*"],
      });
      if (!ok) throw Error("Host permission was not granted");
      await request("/auth/me");
      await chrome.storage.session.set({ base: url.origin, token });
      setSaved(true);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function detect() {
    try {
      const [tab] = await chrome.tabs.query({
        active: true,
        currentWindow: true,
      });
      const r = await chrome.tabs.sendMessage(tab.id, {
        action: "detect-symbol",
      });
      setSearch(r.symbol || "");
      if (!r.symbol)
        throw Error("No supported symbol detected. Search manually.");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <main style={{ padding: 20, minWidth: 320 }}>
      <h2>investorsEYE</h2>
      <p>Your research companion · no real-money orders.</p>
      {error && (
        <p role="alert" className="down">
          {error}
        </p>
      )}
      {!saved ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            connect();
          }}
        >
          <label>
            Workspace URL
            <input value={base} onChange={(e) => setBase(e.target.value)} />
          </label>
          <label>
            Extension pairing token
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
          </label>
          <p>
            Generate a token in the workspace Broker connections page. It is
            stored in extension session storage, never page storage.
          </p>
          <button className="button primary">Pair workspace</button>
        </form>
      ) : (
        <>
          <button
            className="button"
            onClick={() =>
              chrome.tabs
                .query({ active: true, currentWindow: true })
                .then(([t]: any) => chrome.sidePanel.open({ tabId: t.id }))
            }
          >
            Open side panel
          </button>
          <button className="button" onClick={detect}>
            Detect supported page symbol
          </button>
          <label>
            Search instruments
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value.toUpperCase())}
            />
          </label>
          <label>Market provider<select value={provider} onChange={e=>{setProvider(e.target.value);setSelected("");}}><option value="binance">Public crypto</option><option value="kite">My Zerodha connection</option></select></label>
          {selected&&<InvestorResearch key={selected} identity={selected} signedIn={true} signIn={()=>{}} request={request}/>}
          {quotes
            .filter((q) => q.symbol.includes(search))
            .map((q) => (
              <section className="panel feature-form" key={q.instrument_id}>
                <button className="text-button" onClick={()=>setSelected(q.instrument_id)}>{q.symbol} · open research and alerts</button>
                <strong>
                  {q.currency} {q.price}
                </strong>
                <small>
                  {q.status} · {q.observed_at}
                </small>

                <button
                  className="button"
                  onClick={async () => {
                    try {
                      await request("/live/saved","PUT",{instrument_ids:watch.includes(q.instrument_id)?watch.filter(x=>x!==q.instrument_id):[...watch,q.instrument_id]});
                      refresh();
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  {watch.includes(q.instrument_id)
                    ? "Remove saved instrument"
                    : "Save to watchlist"}
                </button>
              </section>
            ))}
          <button
            className="text-button"
            onClick={async () => {
              await request("/auth/logout", "POST").catch(() => {});
              await chrome.storage.session.clear();
              setToken("");
              setSaved(false);
            }}
          >
            Unpair this session
          </button>
        </>
      )}
    </main>
  );
}
createRoot(document.getElementById("root")!).render(<Companion />);
