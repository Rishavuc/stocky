import { KiteWorkspace } from "./KiteWorkspace";
import { CryptoBoard, FundRolling, ImportPresets, OptionInterest } from "./SegmentTools";
import { MarketWorkbench } from "./MarketWorkbench";
import { useState, useEffect } from "react";
import { api } from "./api";
import type { ImportRequest as ImportContract } from "./contracts";
const pretty = (v: unknown) => JSON.stringify(v, null, 2);
export function Platform({ page }: { page: string }) {
  const [data, setData] = useState<any>(null),
    [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false),
    [revision, setRevision] = useState(0);
  const [csv, setCsv] = useState(
      "external_id,symbol,side,qty,price,fees,executed_at,currency\n",
    ),
    [broker, setBroker] = useState("csv"),
    [preview, setPreview] = useState<any>(null),
    [mapping, setMapping] = useState<Record<string, string>>({});
  const [quietStart, setQuietStart] = useState(""),
    [quietEnd, setQuietEnd] = useState("");
  const [provider, setProvider] = useState("upstox"),
    [credentials, setCredentials] = useState<Record<string, string>>({}),
    [channel, setChannel] = useState("telegram"),
    [code, setCode] = useState(""),
    [segment, setSegment] = useState("equities"),
    [symbols, setSymbols] = useState("RELIANCE,TCS");
  const path =
    page === "tradebook"
      ? "/portfolio/unified"
      : page === "connections"
        ? "/connections"
        : page === "channels"
          ? "/channels"
          : page === "explore"
            ? "/instruments/search?segment=" + segment
            : page === "operations"
              ? "/operations"
              : page === "account"
                ? "/auth/account"
                : page === "options"
                  ? "/analysis/options"
                  : page === "fundamentals"
                    ? "/analysis/fundamentals/RELIANCE"
                    : page === "resources"
                      ? "/learn/resources"
                      : "/learn/glossary";
  useEffect(() => {
    let live = true;
    setError("");
    const refresh=()=>api<any>(path)
      .then((d) => {
        if (live) setData(d);
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    refresh();const timer=page==="operations"?setInterval(refresh,15000):undefined;
    return () => {
      clearInterval(timer);
      live = false;
    };
  }, [path, revision,page]);
  async function run(fn: () => Promise<any>, text = "Saved") {
    setBusy(true);
    setError("");
    try {
      const r = await fn();
      setMessage(text);
      setRevision((x) => x + 1);
      return r;
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const importBody = (): ImportContract => ({
    csv,
    broker,
    mapping: Object.keys(mapping).length ? mapping : undefined,
  });
  const field = (key: string, label = key) => (
    <label key={key}>
      {label}
      <input
        type={/token|secret|password/.test(key) ? "password" : "text"}
        value={credentials[key] || ""}
        onChange={(e) =>
          setCredentials({ ...credentials, [key]: e.target.value })
        }
        autoComplete="off"
      />
    </label>
  );
  const headings: Record<string, string> = {
    tradebook: "Your unified trade book",
    connections: "Broker connections",
    channels: "Notification channels",
    explore: "Explore every market",
    operations: "Data and job status",
    options: "Observed options chain",
    fundamentals: "Financial statement analysis",
    account: "Account and recovery",
    glossary: "Your market glossary",
    resources: "Further learning",
  };
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">CONNECTED INVESTING WORKSPACE</div>
          <h1>{headings[page]}</h1>
          <p>
            Real observations, owned records, and explicit connection status.
          </p>
        </div>
      </div>
      {error && (
        <div className="global-error" role="alert">
          {error}
        </div>
      )}
      {message && (
        <div className="info-banner" role="status">
          {message}
        </div>
      )}
      {page === "tradebook" && (
        <>
          <section className="panel">
            <div className="panel-header">
              <h2>Import transaction history</h2>
              <a href="/v1/trades/export.csv" className="button">
                Export saved trades
              </a>
            </div>
            <form
              className="feature-form"
              onSubmit={async (e) => {
                e.preventDefault();
                const p = await run(
                  () => api("/imports/preview", "POST", importBody()),
                  "Preview ready; nothing imported yet.",
                );
                if (p) setPreview(p);
              }}
            >
              <label>
                Source / broker
                <input
                  value={broker}
                  onChange={(e) => {setBroker(e.target.value);setPreview(null);}}
                />
              </label>
              <ImportPresets broker={broker} mapping={mapping} apply={(b,m)=>{setBroker(b);setMapping(m);setPreview(null);}} />
              <label>
                Upload CSV
                <input
                  type="file"
                  accept=".csv,text/csv"
                  onChange={async (e) => {
                    const f = e.target.files?.[0];
                    if (f) {setCsv(await f.text());setPreview(null);}
                  }}
                />
              </label>
              <label>
                Transactions
                <textarea
                  rows={7}
                  value={csv}
                  onChange={(e) => {setCsv(e.target.value);setPreview(null);}}
                />
              </label>
              <p>
                Required: symbol, BUY/SELL side, positive quantity/price, and an
                ISO execution timestamp with timezone. Preserve external IDs for
                duplicate detection. Fees and currencies stay separate.
              </p>
              <button className="button primary" disabled={busy}>
                Preview and validate
              </button>
            </form>
            {preview && (
              <div className="feature-form">
                <h3>Column mapping</h3>
                <div className="indicator-grid">
                  {[
                    "external_id",
                    "symbol",
                    "side",
                    "qty",
                    "price",
                    "fees",
                    "executed_at",
                    "currency",
                  ].map((k) => (
                    <label key={k}>
                      {k}
                      <select
                        value={mapping[k] || k}
                        onChange={(e) =>
                          {setMapping({ ...mapping, [k]: e.target.value });setPreview({...preview,valid:false});}
                        }
                      >
                        <option value="">Not supplied</option>
                        {preview.columns.map((x: string) => (
                          <option key={x}>{x}</option>
                        ))}
                      </select>
                    </label>
                  ))}
                </div>
                <p>
                  {preview.rows.length} valid rows · {preview.duplicates}{" "}
                  duplicates · {preview.errors.length} errors. Re-preview after
                  changing mappings.
                </p>
                {preview.errors.length > 0 && (
                  <pre>{pretty(preview.errors)}</pre>
                )}
                <button
                  disabled={busy || !preview.valid}
                  className="button primary"
                  onClick={() =>
                    run(
                      () => api("/imports/commit", "POST", importBody()),
                      "Import committed without changing virtual portfolios.",
                    )
                  }
                >
                  Commit validated import
                </button>
              </div>
            )}
          </section>
          {data && (
            <section className="panel">
              <div className="panel-header">
                <h2>FIFO holdings and reconciliation</h2>
              </div>
              <div className="feature-form">
                <p>{data.method}</p>
                <h3>Realized profit by currency</h3>
                {data.fee_status === "incomplete" && (
                  <p className="amber-text">
                    Provisional: some fees are unknown. Import fee-complete CSV
                    with the same broker name and trade IDs to enrich these
                    records without duplicating them.
                  </p>
                )}
                <pre>{pretty(data.realized_by_currency)}</pre>
                <table>
                  <thead>
                    <tr>
                      <th>Instrument</th>
                      <th>Currency</th>
                      <th>Units</th>
                      <th>Average cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.holdings.map((h: any) => (
                      <tr key={h.symbol + h.currency}>
                        <td>{h.symbol}</td>
                        <td>{h.currency}</td>
                        <td>{h.qty}</td>
                        <td>{h.avg_cost}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {data.issues.length > 0 && <pre>{pretty(data.issues)}</pre>}
                {data.reconciliation.length > 0 && (
                  <pre>{pretty(data.reconciliation)}</pre>
                )}
              </div>
            </section>
          )}
        </>
      )}
      {page === "tradebook" && <TradeHistory revision={revision} />}
      {page === "connections" && (
        <>
          <section className="panel feature-form">
            <h2>Pair the browser extension</h2>
            <button
              className="button"
              onClick={async () => {
                const p = await run(
                  () => api<{ token: string }>("/extensions/pair", "POST"),
                  "Pairing token generated. Copy it only into your extension.",
                );
                if (p) setPreview(p);
              }}
            >
              Generate seven-day extension token
            </button>
            {preview?.token && (
              <label>
                Pairing token
                <input readOnly type="password" value={preview.token} />
                <button
                  type="button"
                  className="button"
                  onClick={() => navigator.clipboard.writeText(preview.token)}
                >
                  Copy token
                </button>
              </label>
            )}
          </section>
          <KiteWorkspace signedIn={true} signIn={()=>{}} />
          <section className="panel">
            <div className="panel-header">
              <h2>Connect a read-only data source</h2>
              <span className="badge">NO REAL ORDER EXECUTION</span>
            </div>
            <form
              className="feature-form"
              onSubmit={async (e) => {
                e.preventDefault();
                await run(
                  () => api("/connections/" + provider, "PUT", { credentials }),
                  "Credentials encrypted and saved. Sync to verify provider access.",
                );
                setCredentials({});
              }}
            >
              <label>
                Broker
                <select
                  value={provider}
                  onChange={(e) => {
                    setProvider(e.target.value);
                    setCredentials({});
                  }}
                >
                  <option value="upstox">Upstox</option>
                </select>
              </label>
              {(provider === "kite"
                ? ["api_key", "api_secret"]
                : ["client_id", "client_secret"]
              ).map((k) => field(k))}
              {field("access_token", "Current broker access token")}
              <p>
                Use the provider's authorized login flow to obtain your own
                session. Tokens are encrypted on the server. They are never
                returned by this page. Daily trade data may lack final fees;
                import contract-note CSV for net accounting.
              </p>
              <button disabled={busy} className="button primary">
                Save encrypted connection
              </button>
            </form>
          </section>
          {Array.isArray(data) &&
            data.filter((c:any)=>c.provider!=="kite").map((c: any) => (
              <section className="panel feature-form" key={c.provider}>
                <h2>
                  {c.provider} · {c.status}
                </h2>
                <p>Last sync: {c.last_sync || "Not yet verified"}</p>
                {c.error && <p className="down">{c.error}</p>}
                <button
                  className="button"
                  onClick={async () => {
                    const a = await run(
                      () =>
                        api(
                          "/connections/" + c.provider + "/authorize",
                          "POST",
                        ),
                      "Authorization link ready",
                    );
                    if (a) setPreview(a);
                  }}
                >
                  Prepare broker authorization
                </button>
                {preview?.url && (
                  <a className="button" href={preview.url}>
                    Continue on broker website
                  </a>
                )}
                <button
                  className="button"
                  disabled={busy}
                  onClick={() =>
                    run(
                      () => api("/connections/" + c.provider + "/sync", "POST"),
                      "Sync finished. Inspect its status and reconciliation.",
                    )
                  }
                >
                  Sync read-only records
                </button>
                <button
                  className="text-button"
                  onClick={() =>
                    run(
                      () => api("/connections/" + c.provider, "DELETE"),
                      "Disconnected",
                    )
                  }
                >
                  Disconnect
                </button>
              </section>
            ))}
        </>
      )}
      {page === "channels" && (
        <>
          <section className="panel">
            <div className="panel-header">
              <h2>Add and verify a notification channel</h2>
            </div>
            <form
              className="feature-form"
              onSubmit={async (e) => {
                e.preventDefault();
                await run(
                  () =>
                    api("/channels", "POST", {
                      provider: channel,
                      credentials,
                      quiet_start:
                        quietStart === "" ? null : Number(quietStart),
                      quiet_end: quietEnd === "" ? null : Number(quietEnd),
                    }),
                  "Channel saved. Send a verification code next.",
                );
                setCredentials({});
              }}
            >
              <label>
                Channel
                <select
                  value={channel}
                  onChange={(e) => {
                    setChannel(e.target.value);
                    setCredentials({});
                  }}
                >
                  <option value="telegram">Telegram</option>
                  <option value="email">Email (SMTP)</option>
                  <option value="whatsapp">WhatsApp Business</option>
                </select>
              </label>
              <div className="indicator-grid">
                <label>
                  Quiet start hour (IST, optional)
                  <input
                    type="number"
                    min="0"
                    max="23"
                    value={quietStart}
                    onChange={(e) => setQuietStart(e.target.value)}
                  />
                </label>
                <label>
                  Quiet end hour (IST, optional)
                  <input
                    type="number"
                    min="0"
                    max="23"
                    value={quietEnd}
                    onChange={(e) => setQuietEnd(e.target.value)}
                  />
                </label>
                {(channel === "telegram"
                  ? ["bot_token", "chat_id"]
                  : channel === "email"
                    ? ["host", "port", "username", "password", "from", "to"]
                    : [
                        "access_token",
                        "phone_number_id",
                        "to",
                        "template",
                        "language",
                      ]
                ).map((k) => field(k))}
              </div>
              <p>
                Recipient verification is required before alerts can be sent.
                WhatsApp needs your configured business number and approved
                template. Provider acceptance is not a delivery receipt.
              </p>
              <button className="button primary" disabled={busy}>
                Save channel
              </button>
            </form>
          </section>
          {Array.isArray(data) &&
            data.filter((c:any)=>c.provider!=="kite").map((c: any) => (
              <section className="panel feature-form" key={c.id}>
                <h2>
                  {c.provider} · {c.verified ? "Verified" : "Unverified"} ·{" "}
                  {c.enabled ? "Enabled" : "Disabled"}
                </h2>
                {!c.verified ? (
                  <>
                    <button
                      className="button"
                      disabled={busy}
                      onClick={() =>
                        run(
                          () => api("/channels/" + c.id + "/challenge", "POST"),
                          "Verification requested. Check the recipient and enter the received code.",
                        )
                      }
                    >
                      Send verification code
                    </button>
                    <label>
                      Received code
                      <input
                        value={code}
                        onChange={(e) => setCode(e.target.value)}
                      />
                    </label>
                    <button
                      className="button"
                      disabled={busy}
                      onClick={() =>
                        run(
                          () =>
                            api("/channels/" + c.id + "/verify", "POST", {
                              code,
                            }),
                          "Recipient verified",
                        )
                      }
                    >
                      Verify recipient
                    </button>
                  </>
                ) : (
                  <button
                    className="button"
                    onClick={() =>
                      run(
                        () => api("/channels/" + c.id + "/test", "POST"),
                        "Test notification queued",
                      )
                    }
                  >
                    Queue test notification
                  </button>
                )}
                <button
                  className="text-button"
                  onClick={() =>
                    run(
                      () => api("/channels/" + c.id, "DELETE"),
                      "Channel disabled",
                    )
                  }
                >
                  Disable
                </button>
              </section>
            ))}
          <DeliveryHistory revision={revision} />
        </>
      )}
      {page === "explore" && segment === "crypto" && Array.isArray(data) && <CryptoBoard key={data.map((x:any)=>x.symbol).join(":")} instruments={data.filter((x:any)=>x.segment==="crypto")} />}
      {page === "explore" && segment === "funds" && Array.isArray(data) && (
        <FundExplorer key={data.map((x:any)=>x.symbol).join(":")} instruments={data.filter((x:any)=>x.segment==="funds")} />
      )}
      {page === "explore" && (
        <>
          <div className="toolbar">
            <label>
              Market segment
              <select
                value={segment}
                onChange={(e) => setSegment(e.target.value)}
              >
                {[
                  "equities",
                  "indices",
                  "intraday",
                  "derivatives",
                  "funds",
                  "crypto",
                ].map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
          </div>
          {Array.isArray(data) && data.length > 0 ? (
            <div className="journal-grid">
              {data.map((m: any) => (
                <a
                  className="panel feature-form instrument-card"
                  href={"/research?symbol=" + encodeURIComponent(m.symbol)}
                  key={m.symbol}
                >
                  <span className="badge">
                    {m.segment || "equities"} · {m.currency}
                  </span>
                  <h2>{m.symbol}</h2>
                  <p>{m.name}</p>
                  <small>
                    Observed through {m.end} · {m.timeframe || "1d"}
                  </small>
                  <p>{m.source}</p>
                  <span className="up">Open research →</span>
                </a>
              ))}
            </div>
          ) : (
            <div className="empty">
              <h3>No observed instruments in this segment yet.</h3>
              <p>
                Connect an eligible provider or refresh supported market data.
                No sample prices are substituted.
              </p>
            </div>
          )}
          <MarketWorkbench />
        </>
      )}
      {page === "operations" && data && (
        <section className="panel feature-form">
          <h2>Observed system state</h2>
          <pre>{pretty(data)}</pre>
          <p>
            Provider failures retain last valid datasets. Dataset versions pin
            historical replay inputs.
          </p>
        </section>
      )}
      {page === "options" && (
        <section className="panel feature-form">
          <h2>Index option contracts</h2>
          <p>
            Uses your Upstox read connection. Premiums and open interest are
            observations; provider Greeks are model-derived.
          </p>
          <label>
            Underlying
            <select
              value={provider}
              onChange={async (e) => {
                setProvider(e.target.value);
                const r = await run(
                  () => api("/analysis/options?underlying=" + e.target.value),
                  "Contracts retrieved",
                );
                if (r) setData(r);
              }}
            >
              <option value="kite">Choose underlying</option>
              <option value="NIFTY">NIFTY</option>
              <option value="BANKNIFTY">BANKNIFTY</option>
            </select>
          </label>
          {data?.expiries && (
            <label>
              Expiry
              <select
                onChange={async (e) => {
                  const r = await run(
                    () =>
                      api(
                        "/analysis/options?underlying=" +
                          provider +
                          "&expiry=" +
                          e.target.value,
                      ),
                    "Observed chain retrieved",
                  );
                  if (r) setData(r);
                }}
              >
                <option value="">Choose expiry</option>
                {data.expiries.map((x: string) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
            </label>
          )}
          {data?.rows?.length>0 && <OptionInterest key={data.underlying+":"+data.expiry} data={data} />}
          {data?.analytics && <div className="sector-grid">{[['Max pain (calculated)',data.analytics.max_pain],['Largest call open interest strike',data.analytics.largest_call_oi_strike],['Largest put open interest strike',data.analytics.largest_put_oi_strike]].map(([label,value])=><div className="sector-tile" key={String(label)}><small>{label}</small><strong>{value??'Unavailable'}</strong></div>)}<small>{data.analytics.note}</small></div>}
          {data?.rows && (
            <>
              <h3>
                Put/call open-interest ratio:{" "}
                {data.put_call_ratio?.toFixed(3) || "Unavailable"}
              </h3>
              <p>
                {data.source} · retrieved {data.retrieved_at}
              </p>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Strike</th>
                      <th>Call premium</th>
                      <th>Call OI</th>
                      <th>Put premium</th>
                      <th>Put OI</th><th>Call delta / IV</th><th>Put delta / IV</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.rows.map((r: any) => (
                      <tr key={r.strike_price}>
                        <td>{r.strike_price}</td>
                        <td>{r.call_options?.market_data?.ltp}</td>
                        <td>{r.call_options?.market_data?.oi}</td>
                        <td>{r.put_options?.market_data?.ltp}</td>
                        <td>{r.put_options?.market_data?.oi}</td><td>{r.call_options?.option_greeks?.delta??'Unavailable'} / {r.call_options?.option_greeks?.iv??'Unavailable'}</td><td>{r.put_options?.option_greeks?.delta??'Unavailable'} / {r.put_options?.option_greeks?.iv??'Unavailable'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}
      {page === "fundamentals" && (
        <section className="panel feature-form">
          <h2>Import attributed financial facts</h2>
          <p>
            Enter per-share EPS/book value and debt/equity in the same monetary
            unit from a dated statement. These inputs remain labeled
            user-supplied.
          </p>
          <label>
            Symbol
            <input
              value={symbols}
              onChange={(e) => setSymbols(e.target.value)}
            />
          </label>
          {[
            "source_url",
            "statement_date",
            "eps",
            "book_value_per_share",
            "debt",
            "equity",
          ].map((k) => field(k))}
          <button
            className="button"
            onClick={async () => {
              const r = await run(
                () =>
                  api("/analysis/fundamentals/" + symbols, "POST", credentials),
                "Statement facts saved",
              );
              if (r) setData(await api("/analysis/fundamentals/" + symbols));
            }}
          >
            Save and calculate
          </button>
          <pre>{pretty(data)}</pre>
        </section>
      )}
      {page === "account" && (
        <section className="panel feature-form">
          <h2>Email verification</h2>
          <p>
            {data?.email} · {data?.verified ? "Verified" : "Not verified"}
          </p>
          <button
            className="button"
            onClick={() =>
              run(
                () => api("/auth/request-verification", "POST"),
                "Verification submitted to your email provider",
              )
            }
          >
            Send verification token
          </button>
          <label>
            Received verification/recovery token
            <input
              type="password"
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
          </label>
          <button
            className="button"
            onClick={() =>
              run(
                () => api("/auth/verify-email", "POST", { token: code }),
                "Email verified",
              )
            }
          >
            Verify email
          </button>
          <h2>Password recovery</h2>
          <label>
            Account email
            <input
              type="email"
              value={credentials.email || ""}
              onChange={(e) =>
                setCredentials({ ...credentials, email: e.target.value })
              }
            />
          </label>
          <button
            className="button"
            onClick={() =>
              run(
                () =>
                  api("/auth/request-recovery", "POST", {
                    email: credentials.email,
                  }),
                "Recovery request accepted. Delivery requires configured SMTP.",
              )
            }
          >
            Request recovery token
          </button>
          <label>
            New password
            <input
              type="password"
              minLength={10}
              value={credentials.password || ""}
              onChange={(e) =>
                setCredentials({ ...credentials, password: e.target.value })
              }
            />
          </label>
          <button
            className="button"
            onClick={() =>
              run(
                () =>
                  api("/auth/reset-password", "POST", {
                    token: code,
                    password: credentials.password,
                  }),
                "Password reset. Sign in again.",
              )
            }
          >
            Reset password with received token
          </button>
          <p>
            If SMTP is not configured, verification is unavailable. This does
            not indicate that a message was delivered.
          </p>
        </section>
      )}
      {page === "resources" && Array.isArray(data) && (
        <div className="lesson-grid">
          {data.map((r: any) => (
            <article key={r.link + r.title} className="panel feature-form">
              <small>{r.provider} · {r.topic} · {r.language}</small>
              <h2>{r.title}</h2>
              <a className="button" href={r.link} target="_blank" rel="noopener noreferrer">Open external site</a>
            </article>
          ))}
          <p>External sites are independent of InvestorsEYE and are not endorsements.</p>
        </div>
      )}
      {page === "glossary" && Array.isArray(data) && (
        <div className="lesson-grid">
          {data.map((g: any) => (
            <article key={g.term} className="panel feature-form">
              <h2>{g.term}</h2>
              <p>{g.definition}</p>
            </article>
          ))}
        </div>
      )}
    </>
  );
}
function DeliveryHistory({ revision }: { revision: number }) {
  const [rows, setRows] = useState<any[]>([]);
  const [local, setLocal] = useState(0),
    [error, setError] = useState("");
  useEffect(() => {
    let live=true;
    const refresh=()=>api<any[]>("/deliveries").then(data=>{if(live)setRows(data)}).catch(e=>{if(live)setError(e.message)});
    refresh();const timer=setInterval(refresh,15000);
    return()=>{live=false;clearInterval(timer)};
  }, [revision, local]);
  return (
    <section className="panel feature-form">
      <h2>Delivery history</h2>
      {error && <p role="alert">{error}</p>}
      {rows.length ? (
        rows.map((r) => (
          <div className="evidence" key={r.id}>
            <span>
              {r.event.symbol || "Test"} · {r.status}
            </span>
            <span>{r.error || r.updated_at || r.created_at}</span>
            {["failed", "uncertain"].includes(r.status) && (
              <button
                className="button small"
                onClick={async () => {
                  try {
                    await api("/deliveries/" + r.id + "/retry", "POST");
                    setLocal((x) => x + 1);
                    setError("");
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                Retry after checking recipient
              </button>
            )}
          </div>
        ))
      ) : (
        <p>No external deliveries have been queued.</p>
      )}
    </section>
  );
}

function TradeHistory({ revision }: { revision: number }) {
  const [broker, setBroker] = useState(""),
    [start, setStart] = useState(""),
    [end, setEnd] = useState(""),
    [segment, setSegment] = useState(""),
    [rows, setRows] = useState<any[]>([]),
    [error, setError] = useState("");
  useEffect(() => {
    const params = new URLSearchParams();
    if (broker) params.set("broker", broker);
    if (start) params.set("start", start);
    if (end) params.set("end", end);
    if (segment) params.set("segment", segment);
    api<any[]>("/trades?" + params)
      .then(setRows)
      .catch((e) => setError(e.message));
  }, [broker, start, end, segment, revision]);
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Imported transactions</h2>
      </div>
      <div className="alert-form">
        <label>
          Broker
          <input value={broker} onChange={(e) => setBroker(e.target.value)} />
        </label>
        <label>
          From
          <input
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </label>
        <label>
          To
          <input
            type="date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </label>
        <label>
          Segment
          <select value={segment} onChange={(e) => setSegment(e.target.value)}>
            <option value="">All</option>
            {["equities", "intraday", "derivatives", "funds", "crypto"].map(
              (x) => (
                <option key={x}>{x}</option>
              ),
            )}
          </select>
        </label>
      </div>
      {error && <p role="alert">{error}</p>}
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Broker</th>
              <th>Instrument</th>
              <th>Side</th>
              <th>Units</th>
              <th>Price</th>
              <th>Fees</th>
              <th>Executed</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.broker + t.external_id}>
                <td>{t.broker}</td>
                <td>{t.symbol}</td>
                <td>{t.side}</td>
                <td>{t.qty}</td>
                <td>
                  {t.currency} {t.price}
                </td>
                <td>{t.fees}</td>
                <td>{t.executed_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function FundExplorer({ instruments }: { instruments: any[] }) {
  const [symbol, setSymbol] = useState(instruments[0]?.symbol || ""),
    [details, setDetails] = useState<any>(null),
    [amount, setAmount] = useState("5000"),
    [start, setStart] = useState("2024-01-01"),
    [result, setResult] = useState<any>(null),
    [error, setError] = useState("");
  useEffect(() => {
    setDetails(null);setError("");setResult(null);
    if (symbol)
      api("/analysis/funds/" + symbol)
        .then(setDetails)
        .catch((e) => setError(e.message));
  }, [symbol]);
  return (
    <section className="panel feature-form">
      <h2>Fund explorer and historical SIP</h2>
      <label>
        Scheme
        <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
          {instruments.map((m) => (
            <option key={m.symbol} value={m.symbol}>
              {m.name}
            </option>
          ))}
        </select>
      </label>
      {details && (
        <>
          <h3>{details.name}</h3>
          <p>
            NAV ₹{details.nav} · published {details.as_of} · {details.source}
          </p>
          <div className="sector-grid">{Object.entries({...details.returns, "Annualized volatility %":details.risk?.annualized_volatility_pct,"Maximum drawdown %":details.risk?.max_drawdown_pct,"Sharpe (zero risk-free rate)":details.risk?.sharpe_zero_rf,"Annual growth %":details.risk?.cagr_pct,"Beta versus Nifty":details.benchmark?.beta}).map(([label,value])=><div className="sector-tile" key={label}><small>{label}</small><strong>{typeof value==='number'?value.toFixed(2):'Unavailable'}</strong></div>)}</div><small>{details.risk?.assumptions} {details.benchmark?.assumptions}</small>
        </>
      )}
      {symbol && <FundRolling symbol={symbol} />}
      <div className="form-row">
        <label>
          Monthly contribution (₹)
          <input
            type="number"
            min="1"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </label>
        <label>
          Start date
          <input
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </label>
      </div>
      <button
        className="button"
        onClick={async () => {
          try {
            setResult(
              await api("/analysis/funds/" + symbol + "/sip", "POST", {
                monthly_amount: amount,
                start_date: start,
              }),
            );
            setError("");
          } catch (e) {
            setError((e as Error).message);
          }
        }}
      >
        Calculate from observed NAVs
      </button>
      {error && <p role="alert">{error}</p>}
      {result && (
        <>
          <h3>
            Invested ₹{result.invested} · observed value ₹{result.value}
          </h3>
          <p>
            {result.assumptions} As of {result.as_of}.
          </p>
        </>
      )}
    </section>
  );
}
