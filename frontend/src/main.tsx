import { LiveWorkspace } from "./LiveWorkspace";
import { ResearchChart } from "./ResearchChart";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  ArrowDownLeft,
  ArrowRight,
  ArrowUpRight,
  Bell,
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  FlaskConical,
  Globe2,
  LayoutDashboard,
  LogOut,
  Play,
  Plus,
  Search,
  ShieldCheck,
  SkipForward,
  Star,
  TrendingUp,
  Wallet,
  X,
  NotebookPen,
  Pause,
  RefreshCw,
  Eye,
  Clock3,
} from "lucide-react";
import {
  api,
  ApiError,
  type Quote,
  type Candle,
  type Portfolio,
  type Order,
  type Replay,
  type Analysis,
  type Forecast,
  type Lesson,
} from "./api";
import { Spark, PriceChart, ComparisonChart } from "./Charts";
import "./styles.css";
import { Platform } from "./Platform";

const money = (v: number, currency = "INR") =>
  currency.length !== 3
    ? new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(v) +
      " " +
      currency
    : new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency,
        maximumFractionDigits: 2,
      }).format(v);
const number = (v: number) =>
  new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(v);
const pct = (v: number) => (v >= 0 ? "+" : "") + v.toFixed(2) + "%";
const niceDate = (s: string) =>
  new Date(s).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
const tabs = [
  { id: "live", label: "Live investing workspace", icon: Globe2 },
  { id: "overview", label: "Practice overview", icon: LayoutDashboard },
  { id: "markets", label: "Recorded watchlist", icon: Globe2 },
  { id: "explore", label: "Recorded market lab", icon: Globe2 },
  { id: "research", label: "Recorded research", icon: Activity },
  { id: "replay", label: "Market replay", icon: Play },
  { id: "portfolio", label: "Paper portfolio", icon: Wallet },
  { id: "tradebook", label: "Unified trade book", icon: Wallet },
  { id: "models", label: "Model lab", icon: FlaskConical },
  { id: "options", label: "Options chain", icon: Activity },
  { id: "fundamentals", label: "Financial statements", icon: NotebookPen },
  { id: "journal", label: "Decision journal", icon: NotebookPen },
  { id: "alerts", label: "Alerts", icon: Bell },
  { id: "channels", label: "Notification channels", icon: Bell },
  { id: "learn", label: "Learning studio", icon: BookOpen },
  { id: "glossary", label: "Glossary", icon: BookOpen },
  { id: "connections", label: "Broker connections", icon: ShieldCheck },
  { id: "account", label: "Account and recovery", icon: ShieldCheck },
  { id: "operations", label: "System status", icon: Activity },
];
type User = { id: string; name: string; email: string };
function useResource<T>(path: string | null, revision = 0) {
  const [data, setData] = useState<T | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false);
  useEffect(() => {
    let live = true;
    setData(null);
    setError("");
    if (!path) return;
    setLoading(true);
    const refresh=()=>api<T>(path)
      .then((d) => {
        if (live){setData(d);setError("");}
      })
      .catch((e) => {
        if (live) setError(e.message);
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    refresh();
    const timer=/^\/(predictions|candles|analysis)\//.test(path)?setInterval(refresh,60000):undefined;
    return () => {
      clearInterval(timer);
      live = false;
    };
  }, [path, revision]);
  return { data, error, loading, setData };
}
function Empty({
  title,
  children,
}: {
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <CircleHelp size={25} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
function Badge({
  children,
  tone = "",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return <span className={"badge " + tone}>{children}</span>;
}
function Stat({
  label,
  value,
  sub,
  positive,
}: {
  label: string;
  value: string;
  sub?: string;
  positive?: boolean;
}) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong>{value}</strong>
      {sub && (
        <small
          className={positive === undefined ? "" : positive ? "up" : "down"}
        >
          {sub}
        </small>
      )}
    </div>
  );
}
function Load({ error, loading }: { error: string; loading: boolean }) {
  return error ? (
    <div role="alert" className="inline-error">
      {error}
    </div>
  ) : loading ? (
    <div className="loading">
      <RefreshCw size={17} className="spin" />
      Loading observed data…
    </div>
  ) : null;
}
function App() {
  const [user, setUser] = useState<User | null>(null),
    [authChecked, setAuthChecked] = useState(false),
    [authOpen, setAuthOpen] = useState(false),
    [tab, setTab] = useState(
      () =>
        tabs.find((x) => "/" + x.id === location.pathname)?.id || "live",
    ),
    [symbol, setSymbol] = useState(
      () => new URLSearchParams(location.search).get("symbol") || "RELIANCE",
    ),
    [search, setSearch] = useState(""),
    [revision, setRevision] = useState(0),
    [notice, setNotice] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [replay, setReplay] = useState<Replay | null>(null);
  const quotes = useResource<Quote[]>("/quotes", revision),
    watch = useResource<string[]>(user ? "/watchlist" : null, revision),
    wallet = useResource<Portfolio>(user ? "/paper/portfolio" : null, revision);
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let socket: WebSocket | undefined;
    const connect = () => {
      socket = new WebSocket(
        (location.protocol === "https:" ? "wss:" : "ws:") +
          "//" +
          location.host +
          "/ws/stream",
      );
      socket.onmessage = (e) => {
        try {
          const message = JSON.parse(e.data);
          if (alive && message.type === "SNAPSHOT")
            quotes.setData(message.data);
        } catch {
          /* Keep the last valid server observation. */
        }
      };
      socket.onclose = () => {
        if (alive) timer = setTimeout(connect, 5000);
      };
    };
    connect();
    return () => {
      alive = false;
      clearTimeout(timer);
      socket?.close();
    };
  }, [quotes.setData, user?.id, wallet.setData]);
  useEffect(() => {
    const expired = () => {
      setUser(null);
      setReplay(null);
    };
    window.addEventListener("eye-auth-expired", expired);
    return () => window.removeEventListener("eye-auth-expired", expired);
  }, []);
  const bump = useCallback(() => setRevision((x) => x + 1), []);
  useEffect(() => {
    api<User>("/auth/me")
      .then(setUser)
      .catch(() => {})
      .finally(() => setAuthChecked(true));
  }, []);
  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(""), 5500);
    return () => clearTimeout(t);
  }, [notice]);
  async function action<T>(fn: () => Promise<T>, message?: string) {
    setBusy(true);
    setError("");
    try {
      const value = await fn();
      bump();
      if (message) setNotice(message);
      return value;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
      if (e instanceof ApiError && e.status === 401) {
        setUser(null);
        setReplay(null);
        setAuthOpen(true);
      }
      return undefined;
    } finally {
      setBusy(false);
    }
  }
  const requireUser = () => {
    if (user) return true;
    setAuthOpen(true);
    return false;
  };
  const navigate = (id: string) => {
    setTab(id);
    setError("");
    setSearch("");
    window.history.pushState(
      null,
      "",
      id === "live"
        ? "/"
        : "/" +
            id +
            (id === "research" ? "?symbol=" + encodeURIComponent(symbol) : ""),
    );
  };
  const inspect = (sym: string) => {
    setSymbol(sym);
    setTab("research");
    setSearch("");
    setError("");
    window.history.pushState(
      null,
      "",
      "/research?symbol=" + encodeURIComponent(sym),
    );
  };
  useEffect(() => {
    const pop = () => {
      setTab(
        tabs.find((x) => "/" + x.id === location.pathname)?.id || "live",
      );
      const sym = new URLSearchParams(location.search).get("symbol");
      if (sym) setSymbol(sym);
    };
    window.addEventListener("popstate", pop);
    return () => window.removeEventListener("popstate", pop);
  }, []);
  async function toggleWatch(sym: string) {
    if (!requireUser()) return;
    await action(
      () =>
        api("/watchlist/" + sym, watch.data?.includes(sym) ? "DELETE" : "POST"),
      "Watchlist updated",
    );
  }
  const filtered = (quotes.data || [])
    .filter(
      (x) =>
        tab !== "overview" ||
        !user ||
        !watch.data?.length ||
        watch.data.includes(x.symbol),
    )
    .filter((x) =>
      (x.symbol + " " + x.name).toLowerCase().includes(search.toLowerCase()),
    );
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button
          className="brand"
          onClick={() => navigate("live")}
          aria-label="InvestorsEYE live workspace"
        >
          <span className="brand-symbol">
            <Eye size={24} />
          </span>
          <span>
            investors<span className="brand-eye">EYE</span>
            <small>RESEARCH. REPLAY. REFINE.</small>
          </span>
        </button>
        <div className="workspace-label">YOUR WORKSPACE</div>
        <nav>
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              className={tab === id ? "nav-item active" : "nav-item"}
              aria-current={tab === id ? "page" : undefined}
              onClick={() => navigate(id)}
            >
              <Icon size={18} />
              {label}
              {id === "replay" && <span className="new-tag">LAB</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sandbox">
            <ShieldCheck size={19} />
            <strong>A place to build conviction.</strong>
            <p>Real observations. Virtual capital. Room to learn.</p>
            <Badge tone="green">EDUCATIONAL SANDBOX</Badge>
          </div>
          <button
            className="profile"
            onClick={() =>
              user
                ? action(async () => {
                    await api("/auth/logout", "POST");
                    setUser(null);
                    setReplay(null);
                  }, "Signed out")
                : setAuthOpen(true)
            }
          >
            <span className="avatar">
              {user ? user.name.slice(0, 2).toUpperCase() : "IE"}
            </span>
            <span>
              <strong>{user?.name || "Your research workspace"}</strong>
              <small>
                {user ? "Private account" : "Sign in to save your progress"}
              </small>
            </span>
            {user ? <LogOut size={16} /> : <ChevronRight size={17} />}
          </button>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <ChevronRight size={13} />{" "}
            <strong>{tabs.find((x) => x.id === tab)?.label}</strong>
          </div>
          <div className="top-actions">
            <Badge>
              <span className="dot amber" />
              {tab === "live" ? "Provider-connected markets" : "Research and practice"}
            </Badge>
            <button
              className="icon-button"
              title="Open alerts"
              onClick={() => navigate("alerts")}
            >
              <Bell size={18} />
            </button>
            <button
              className="button small"
              onClick={() => (user ? navigate("portfolio") : setAuthOpen(true))}
            >
              {user ? "My portfolio" : "Get started"}
              <ArrowUpRight size={15} />
            </button>
          </div>
        </header>
        <main>
          <div className="mobile-brand">
            <Eye /> investorsEYE
          </div>
          {error && (
            <div className="global-error" role="alert">
              {error}
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div className="toast" role="status">
              <Check size={17} />
              {notice}
            </div>
          )}
          {tab === "live" && <LiveWorkspace key={user?.id||"anonymous"} signedIn={!!user} signIn={()=>setAuthOpen(true)} />}
          {["overview","markets","explore","research","models"].includes(tab)&&<p className="recorded-banner">RECORDED RESEARCH / PRACTICE · These datasets are not a current-market feed. Open Live investing workspace for provider-connected observations.</p>}
          {(tab === "overview" || tab === "markets") && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">THE MARKET, IN PERSPECTIVE</div>
                  <h1>
                    {tab === "overview"
                      ? "Your edge starts here."
                      : "Find your next question."}
                  </h1>
                  <p>
                    Follow the market. Test your thinking. Make every decision
                    count.
                  </p>
                </div>
                <button
                  className="button primary"
                  onClick={() => navigate("replay")}
                >
                  <Play size={16} />
                  Launch market replay
                </button>
              </div>
              {tab === "overview" && (
                <section className="hero">
                  <div className="hero-copy">
                    <Badge tone="green">YOUR PERSONAL MARKET LAB</Badge>
                    <h2>
                      Don’t just watch
                      <br />
                      the market.
                      <br />
                      <em>Experience it.</em>
                    </h2>
                    <p>
                      Step into a past trading session. Put ₹10 lakh of virtual
                      capital behind your ideas and see how they play out.
                    </p>
                    <button
                      className="button light"
                      onClick={() => navigate("replay")}
                    >
                      Enter the replay lab <ArrowRight size={17} />
                    </button>
                    <div className="hero-foot">
                      <ShieldCheck size={14} />
                      Historical prices · No real money · Your decisions
                    </div>
                  </div>
                  <div className="hero-art" aria-hidden="true">
                    <div className="orbit one" />
                    <div className="orbit two" />
                    <div className="art-grid" />
                    <div className="floating-caption">
                      <span className="dot" />
                      THE REPLAY ENGINE
                    </div>
                    <svg viewBox="0 0 500 260">
                      <defs>
                        <linearGradient id="area" x1="0" x2="0" y1="0" y2="1">
                          <stop
                            offset="0%"
                            stopColor="#63dfb0"
                            stopOpacity=".3"
                          />
                          <stop
                            offset="100%"
                            stopColor="#63dfb0"
                            stopOpacity="0"
                          />
                        </linearGradient>
                      </defs>
                      <path
                        d="M0 230 L35 210 L55 220 L80 185 L110 198 L135 150 L160 167 L185 140 L210 160 L240 105 L270 120 L300 78 L330 110 L365 50 L400 70 L440 25 L470 45 L500 10 L500 260 L0 260Z"
                        fill="url(#area)"
                      />
                      <path
                        d="M0 230 L35 210 L55 220 L80 185 L110 198 L135 150 L160 167 L185 140 L210 160 L240 105 L270 120 L300 78 L330 110 L365 50 L400 70 L440 25 L470 45 L500 10"
                        fill="none"
                        stroke="#63dfb0"
                        strokeWidth="3"
                      />
                    </svg>
                    <div className="art-note">
                      <span>YOUR NEXT SESSION</span>
                      <strong>Curiosity → conviction</strong>
                      <small>
                        Illustration · explore actual results in replay
                      </small>
                    </div>
                  </div>
                </section>
              )}
              <div className="section-head">
                <div>
                  <h2>
                    Market pulse <Badge>INDIAN EQUITIES</Badge>
                  </h2>
                  <p>
                    Observed daily closes, clearly dated. Never a simulated live
                    feed.
                  </p>
                </div>
                <button
                  className="text-button"
                  onClick={() => navigate("markets")}
                >
                  Explore markets <ArrowRight size={15} />
                </button>
              </div>
              <Load {...quotes} />
              <div className="quote-grid">
                {(quotes.data || []).slice(0, 4).map((q) => (
                  <button
                    className="quote-card"
                    key={q.symbol}
                    onClick={() => inspect(q.symbol)}
                  >
                    <div className="quote-top">
                      <span className={"asset-icon " + q.symbol.toLowerCase()}>
                        {q.symbol.slice(0, 2)}
                      </span>
                      <div>
                        <strong>{q.symbol}</strong>
                        <small>NSE · INR</small>
                      </div>
                      <ArrowUpRight size={17} />
                    </div>
                    <div className="quote-value">
                      {money(q.price, q.currency)}
                      <span
                        className={(q.change_pct || 0) >= 0 ? "up" : "down"}
                      >
                        {pct(q.change_pct || 0)}
                      </span>
                    </div>
                    <Spark
                      values={q.sparkline || []}
                      color={(q.change_pct || 0) >= 0 ? "#62dfb0" : "#f2818c"}
                    />
                    <div className="quote-date">
                      {q.status} · {niceDate(q.observed_at)}
                    </div>
                  </button>
                ))}
              </div>
              <div className="two-col market-layout">
                <section className="panel">
                  <div className="panel-header">
                    <h2>
                      {tab === "markets"
                        ? "Instrument explorer"
                        : watch.data?.length
                          ? "Your watchlist"
                          : "Build your watchlist"}
                    </h2>
                    <Badge>
                      {user ? `${watch.data?.length || 0} saved` : "PERSONAL"}
                    </Badge>
                  </div>
                  <label className="search">
                    <Search size={17} />
                    <input
                      aria-label="Search instruments"
                      placeholder="Search a company or symbol…"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                    />
                    <span>⌕</span>
                  </label>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Instrument</th>
                          <th>Last close</th>
                          <th>Day change</th>
                          <th>30 sessions</th>
                          <th>
                            <Star size={13} />
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {filtered.map((q) => (
                          <tr key={q.symbol}>
                            <td>
                              <button
                                className="asset-link"
                                onClick={() => inspect(q.symbol)}
                              >
                                <span className="asset-icon">
                                  {q.symbol.slice(0, 2)}
                                </span>
                                <span>
                                  <strong>{q.symbol}</strong>
                                  <small>{q.name}</small>
                                </span>
                              </button>
                            </td>
                            <td>{money(q.price, q.currency)}</td>
                            <td
                              className={
                                (q.change_pct || 0) >= 0 ? "up" : "down"
                              }
                            >
                              {pct(q.change_pct || 0)}
                            </td>
                            <td>
                              <Spark values={q.sparkline || []} />
                            </td>
                            <td>
                              <button
                                className={
                                  "icon-button " +
                                  (watch.data?.includes(q.symbol)
                                    ? "starred"
                                    : "")
                                }
                                aria-label={"Toggle " + q.symbol + " watchlist"}
                                onClick={() => toggleWatch(q.symbol)}
                              >
                                <Star
                                  size={16}
                                  fill={
                                    watch.data?.includes(q.symbol)
                                      ? "currentColor"
                                      : "none"
                                  }
                                />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {!filtered.length && !quotes.loading && (
                    <Empty title="No matching instruments">
                      Try a different company or symbol.
                    </Empty>
                  )}
                  <div className="panel-footer">
                    {quotes.data?.[0]?.source || "Attributed historical data"}
                    <span>
                      Daily observations <Clock3 size={12} />
                    </span>
                  </div>
                </section>
                <div className="stack">
                  <section className="panel portfolio-card">
                    <div className="panel-header">
                      <h2>Your paper portfolio</h2>
                      <Wallet size={18} />
                    </div>
                    <span className="muted">
                      {user
                        ? "Total marked value"
                        : "Start with virtual capital"}
                    </span>
                    <div className="big-number">
                      {money(wallet.data?.total || 1000000)}
                    </div>
                    <p>
                      Build a track record, one considered decision at a time.
                    </p>
                    <div className="mini-stats">
                      <div>
                        <small>Available cash</small>
                        <strong>{money(wallet.data?.cash || 1000000)}</strong>
                      </div>
                      <div>
                        <small>Open positions</small>
                        <strong>{wallet.data?.positions.length || 0}</strong>
                      </div>
                    </div>
                    <button
                      className="button full"
                      onClick={() =>
                        user ? navigate("portfolio") : setAuthOpen(true)
                      }
                    >
                      Open portfolio
                      <ArrowRight size={16} />
                    </button>
                  </section>
                  <section className="learn-card">
                    <BookOpen size={22} />
                    <Badge>LEARN BY DOING</Badge>
                    <h3>
                      A signal is a starting point.
                      <br />
                      Understand what’s behind it.
                    </h3>
                    <button
                      className="text-button"
                      onClick={() => navigate("learn")}
                    >
                      Build your market intuition <ArrowRight size={15} />
                    </button>
                  </section>
                </div>
              </div>
            </>
          )}
          {[
            "options",
            "fundamentals",
            "account",
            "explore",
            "tradebook",
            "connections",
            "channels",
            "operations",
            "glossary",
          ].includes(tab) && (
            <Platform key={tab + ":" + (user?.id || "anonymous")} page={tab} />
          )}
          {tab === "research" && (
            <Research
              symbol={symbol}
              setSymbol={setSymbol}
              quotes={quotes.data || []}
              toggleWatch={toggleWatch}
              starred={watch.data?.includes(symbol) || false}
              user={user}
              requireUser={requireUser}
              action={action}
              busy={busy}
              revision={revision}
              startReplay={() => navigate("replay")}
            />
          )}
          {tab === "replay" && (
            <ReplayLab
              user={user}
              requireUser={requireUser}
              quotes={quotes.data || []}
              symbol={symbol}
              setSymbol={setSymbol}
              replay={replay}
              setReplay={setReplay}
              action={action}
              busy={busy}
              revision={revision}
            />
          )}
          {tab === "portfolio" && (
            <>
              <Heading
                eyebrow="VIRTUAL CAPITAL. REAL DISCIPLINE."
                title="Your paper portfolio"
                text="Your holdings and orders, saved to your private account."
              />
              {!user ? (
                <SignInCard open={() => setAuthOpen(true)} />
              ) : (
                <>
                  <Load {...wallet} />
                  {wallet.data && <PortfolioView wallet={wallet.data} />}
                  <PaperPerformance revision={revision} />
                  <Orders scope="paper" revision={revision} action={action} />
                  <div className="info-banner">
                    <ShieldCheck size={18} />
                    <span>
                      Current-market orders require a fresh authenticated
                      provider quote. Without one, use Market Replay to complete
                      the full trading journey.
                    </span>
                    <button
                      className="text-button"
                      onClick={() => navigate("replay")}
                    >
                      Open replay <ArrowRight size={15} />
                    </button>
                  </div>
                </>
              )}
            </>
          )}
          {tab === "models" && (
            <ModelLab
              symbol={symbol}
              setSymbol={setSymbol}
              quotes={quotes.data || []}
            />
          )}
          {tab === "journal" && (
            <>
              <Heading
                eyebrow="MAKE YOUR REASONING VISIBLE"
                title="Decision journal"
                text="The observation, the thesis, the execution. A record you can learn from."
              />
              {user ? (
                <Journal revision={revision} />
              ) : (
                <SignInCard open={() => setAuthOpen(true)} />
              )}
            </>
          )}
          {tab === "alerts" && (
            <>
              <Heading
                eyebrow="PAY ATTENTION TO WHAT MATTERS"
                title="Your alert desk"
                text="Price crossings with a saved event trail. Replay and current-market rules stay separate."
              />
              {user ? (
                <Alerts
                  symbol={symbol}
                  quotes={quotes.data || []}
                  replay={replay}
                  action={action}
                  revision={revision}
                />
              ) : (
                <SignInCard open={() => setAuthOpen(true)} />
              )}
            </>
          )}
          {tab === "learn" && (
            <>
              <Heading
                eyebrow="TURN CURIOSITY INTO UNDERSTANDING"
                title="Learning studio"
                text="Short lessons. Useful questions. Progress that stays with you."
              />
              {user ? (
                <Learn revision={revision} action={action} />
              ) : (
                <SignInCard open={() => setAuthOpen(true)} />
              )}
            </>
          )}
          <footer>
            <span>
              <Eye size={14} /> InvestorsEYE · Built for better questions.
            </span>
            <span>Educational research · Virtual trading only</span>
          </footer>
        </main>
      </div>
      {authOpen && (
        <Auth
          close={() => setAuthOpen(false)}
          onUser={(u) => {
            setUser(u);
            setAuthOpen(false);
            bump();
            setNotice("Your workspace is ready");
          }}
        />
      )}
      {!authChecked && (
        <div className="connection-status" role="status">
          Connecting to your workspace…
        </div>
      )}
    </div>
  );
}
type Action = <T>(
  fn: () => Promise<T>,
  message?: string,
) => Promise<T | undefined>;
function Heading({
  eyebrow,
  title,
  text,
}: {
  eyebrow: string;
  title: string;
  text: string;
}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{text}</p>
      </div>
    </div>
  );
}
function SignInCard({ open }: { open: () => void }) {
  return (
    <section className="panel sign-in-card">
      <ShieldCheck size={32} />
      <h2>Your ideas deserve their own space.</h2>
      <p>
        Sign in to keep portfolios, replay sessions, alerts, and learning
        progress private and saved.
      </p>
      <button className="button primary" onClick={open}>
        Create your workspace <ArrowRight size={16} />
      </button>
    </section>
  );
}
function Auth({
  close,
  onUser,
}: {
  close: () => void;
  onUser: (u: User) => void;
}) {
  const [register, setRegister] = useState(true),
    [name, setName] = useState(""),
    [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const modal = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const prev = document.activeElement as HTMLElement;
    const el = modal.current;
    el?.querySelector<HTMLInputElement>("input")?.focus();
    const listener = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
      if (e.key === "Tab" && el) {
        const nodes = Array.from(
          el.querySelectorAll<HTMLElement>("button,input"),
        );
        const first = nodes[0],
          last = nodes[nodes.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", listener);
    return () => {
      document.removeEventListener("keydown", listener);
      prev?.focus();
    };
  }, [close]);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      onUser(
        await api<User>("/auth/" + (register ? "register" : "login"), "POST", {
          name,
          email,
          password,
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="modal-overlay" onClick={close}>
      <div
        ref={modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-title"
        className="modal"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          aria-label="Close sign in"
          className="modal-close icon-button"
          onClick={close}
        >
          <X />
        </button>
        <span className="brand-symbol">
          <Eye />
        </span>
        <div className="eyebrow">WELCOME TO YOUR MARKET LAB</div>
        <h2 id="auth-title">
          {register ? "Start building conviction." : "Welcome back."}
        </h2>
        <p>Research, replay, and learn. Your progress is saved.</p>
        <form onSubmit={submit}>
          {register && (
            <label>
              Your name
              <input
                required
                maxLength={80}
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="name"
              />
            </label>
          )}
          <label>
            Email address
            <input
              type="email"
              required
              maxLength={254}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </label>
          <label>
            Password
            <input
              type="password"
              required
              minLength={register ? 10 : 1}
              maxLength={256}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={register ? "new-password" : "current-password"}
            />
          </label>
          {register && (
            <small className="muted">Use at least 10 characters.</small>
          )}
          {error && (
            <p role="alert" className="down">
              {error}
            </p>
          )}
          <button disabled={busy} className="button primary full">
            {busy
              ? "Opening workspace…"
              : register
                ? "Create account"
                : "Sign in"}
            <ArrowRight size={16} />
          </button>
        </form>
        <button
          className="text-button"
          onClick={() => {
            setRegister(!register);
            setError("");
          }}
        >
          {register
            ? "Already have an account? Sign in"
            : "New here? Create an account"}
        </button>
      </div>
    </div>
  );
}
function SelectAsset({
  symbol,
  setSymbol,
  quotes,
}: {
  symbol: string;
  setSymbol: (s: string) => void;
  quotes: Quote[];
}) {
  return (
    <label className="asset-select">
      <span>INSTRUMENT</span>
      <select
        aria-label="Select instrument"
        value={symbol}
        onChange={(e) => setSymbol(e.target.value)}
      >
        {quotes.map((q) => (
          <option key={q.symbol} value={q.symbol}>
            {q.symbol} · {q.name}
          </option>
        ))}
      </select>
      <ChevronDown size={15} />
    </label>
  );
}
function Research({
  symbol,
  setSymbol,
  quotes,
  toggleWatch,
  starred,
  user,
  requireUser,
  action,
  busy,
  revision,
  startReplay,
}: {
  symbol: string;
  setSymbol: (s: string) => void;
  quotes: Quote[];
  toggleWatch: (s: string) => void;
  starred: boolean;
  user: User | null;
  requireUser: () => boolean;
  action: Action;
  busy: boolean;
  revision: number;
  startReplay: () => void;
}) {
  const analysis = useResource<Analysis>("/analysis/technical/" + symbol),
    forecast = useResource<Forecast>("/predictions/" + symbol);
  const q = quotes.find((x) => x.symbol === symbol);
  const base = symbol.replace(/_5m$/, "");
  const choose = (s: string) => {
    setSymbol(s);
    window.history.replaceState(
      null,
      "",
      "/research?symbol=" + encodeURIComponent(s),
    );
  };
  return (
    <>
      <Heading
        eyebrow="FROM OBSERVATION TO UNDERSTANDING"
        title="Go beyond the price."
        text="Explore one instrument, connect the evidence, and record your next decision."
      />
      <div className="toolbar">
        <SelectAsset symbol={symbol} setSymbol={choose} quotes={quotes} />
        <div className="segmented compact">
          <button
            disabled={!quotes.some((q) => q.symbol === base)}
            onClick={() => choose(base)}
          >
            Daily
          </button>
          <button
            disabled={!quotes.some((q) => q.symbol === base + "_5m")}
            onClick={() => choose(base + "_5m")}
          >
            5 minute
          </button>
        </div>
        <button
          className={"button " + (starred ? "starred" : "")}
          onClick={() => toggleWatch(symbol)}
        >
          <Star size={16} />
          {starred ? "Saved to watchlist" : "Save to watchlist"}
        </button>
        <Badge tone="amber">
          {q?.status || "historical"} · {q?.observed_at}
        </Badge>
      </div>
      <div className="research-layout">
        <div className="stack">
          <section className="panel chart-panel">
            <div className="panel-header">
              <div>
                <h2>{q?.name || symbol}</h2>
                <div className="asset-price">
                  {q ? money(q.price, q.currency) : "…"}
                  <span className={(q?.change_pct || 0) >= 0 ? "up" : "down"}>
                    {pct(q?.change_pct || 0)}
                  </span>
                </div>
              </div>
              <Badge>{q?.timeframe || "1d"} CANDLES</Badge>
            </div>
            <ResearchChart key={symbol+":"+(user?.id||"anonymous")} symbol={symbol} choose={choose} />
            <div className="panel-footer">
              {q?.source}
              <span>Observed {q?.observed_at}</span>
            </div>
          </section>
          <section className="panel">
            <div className="panel-header">
              <h2>Read the signals</h2>
              <Badge>CALCULATED FROM OBSERVATIONS</Badge>
            </div>
            <Load {...analysis} />
            <div className="indicator-grid">
              {analysis.data?.indicators.map((i) => (
                <div key={i.name} className="indicator">
                  <span>{i.name}</span>
                  <strong>{number(i.value)}</strong>
                  <p>{i.explanation}</p>
                </div>
              ))}
            </div>
            <div className="info-banner">
              <CircleHelp size={18} />
              {analysis.data?.fundamentals_status}
            </div>
          </section>
        </div>
        <div className="stack">
          <section className="panel forecast-card">
            <div className="panel-header">
              <h2>
                <FlaskConical size={18} />
                Forecast snapshot
              </h2>
            </div>
            <Load {...forecast} />
            {forecast.data && (
              <>
                <Badge tone="purple">
                  {forecast.data.selected_model} · experimental research
                </Badge>
                <span className="muted">
                  {forecast.data.horizon_sessions}-observation estimate · as of{" "}
                  {forecast.data.as_of}
                </span>
                <div className="big-number">
                  {money(forecast.data.predicted_target, q?.currency)}
                </div>
                <span
                  className={
                    forecast.data.expected_return_pct >= 0 ? "up" : "down"
                  }
                >
                  {pct(forecast.data.expected_return_pct)} versus last close
                </span>
                <p>
                  Empirical range:{" "}
                  {money(forecast.data.interval.lower, q?.currency)} to{" "}
                  {money(forecast.data.interval.upper, q?.currency)}.
                </p>
                <Badge tone={forecast.data.beats_baseline ? "green" : "amber"}>
                  {forecast.data.beats_baseline
                    ? "Lower test error than baseline"
                    : "Does not beat baseline on final test"}
                </Badge>
                <small>
                  Historical research output. Compare the full evaluation in
                  Model lab.
                </small>
              </>
            )}
          </section>
          {q && (
            <TradeTicket
              symbol={symbol}
              price={q.price}
              currency={q.currency}
              disabled={!q.tradable}
              onSubmit={async (body) => {
                if (!requireUser()) return false;
                const result = await action(
                  () =>
                    api("/paper/orders", "POST", {
                      ...body,
                      forecast_version: forecast.data?.version,
                    }),
                  "Virtual order submitted",
                );
                return result !== undefined;
              }}
              busy={busy}
            />
          )}
          <button className="button full" onClick={startReplay}>
            <Play size={16} />
            Trade through historical replay
            <ArrowRight size={16} />
          </button>
        </div>
      </div>
    </>
  );
}
function TradeTicket({
  symbol,
  price,
  onSubmit,
  busy,
  disabled = false,
  replay = false,
  currency = "INR",
}: {
  symbol: string;
  price: number;
  onSubmit: (body: Record<string, unknown>) => Promise<boolean>;
  busy: boolean;
  disabled?: boolean;
  replay?: boolean;
  currency?: string;
}) {
  const [side, setSide] = useState<"BUY" | "SELL">("BUY"),
    [qty, setQty] = useState(10),
    [type, setType] = useState("MARKET"),
    [limit, setLimit] = useState(price.toFixed(2)),
    [reason, setReason] = useState("");
  const request = useRef(crypto.randomUUID());
  useEffect(() => {
    setLimit(price.toFixed(2));
    request.current = crypto.randomUUID();
  }, [symbol, price]);
  return (
    <section className="panel trade-ticket">
      <div className="panel-header">
        <h2>Put an idea to the test</h2>
        <Badge>VIRTUAL</Badge>
      </div>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          const ok = await onSubmit({
            symbol,
            side,
            qty,
            order_type: type,
            price: type === "LIMIT" ? limit : null,
            reason,
            request_id: request.current,
          });
          if (ok) request.current = crypto.randomUUID();
        }}
      >
        <div className="segmented">
          <button
            type="button"
            className={side === "BUY" ? "selected" : ""}
            onClick={() => setSide("BUY")}
          >
            Buy
          </button>
          <button
            type="button"
            className={side === "SELL" ? "selected sell" : ""}
            onClick={() => setSide("SELL")}
          >
            Sell
          </button>
        </div>
        <div className="form-row">
          <label>
            Order type
            <select value={type} onChange={(e) => setType(e.target.value)}>
              <option value="MARKET">Market</option>
              <option value="LIMIT">Limit</option>
            </select>
          </label>
          <label>
            Quantity
            <input
              type="number"
              required
              min="1"
              max="100000"
              step="1"
              value={qty}
              onChange={(e) => setQty(Number(e.target.value))}
            />
          </label>
        </div>
        {type === "LIMIT" && (
          <label>
            Limit price ({currency})
            <input
              type="number"
              required
              min="0.01"
              step="0.01"
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
            />
          </label>
        )}
        <label>
          Your reasoning
          <textarea
            maxLength={2000}
            placeholder="What evidence supports this decision?"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </label>
        <div className="ticket-estimate">
          <span>Estimated value</span>
          <strong>
            {money(qty * (type === "LIMIT" ? Number(limit) : price), currency)}
          </strong>
        </div>
        <small className="muted">
          {replay
            ? "Executes on a later bar, never the currently visible close. Gaps can change the fill price."
            : "Requires a fresh executable provider quote. Historical prices cannot fill current-market orders."}
        </small>
        <button disabled={busy || disabled} className="button primary full">
          {busy ? "Saving…" : `Place virtual ${side.toLowerCase()}`}
          <ArrowRight size={16} />
        </button>
        {disabled && (
          <p className="amber-text">
            {replay
              ? "Replay ended. Start another session."
              : "Current-market execution is unavailable for this observation. Use Market Replay."}
          </p>
        )}
      </form>
    </section>
  );
}
function PortfolioView({ wallet }: { wallet: Portfolio }) {
  return (
    <>
      <div className="stats-grid">
        <Stat
          label="Total marked value"
          value={money(wallet.total, wallet.currency)}
          sub={
            pct((wallet.total / wallet.initial - 1) * 100) +
            " from starting capital"
          }
          positive={wallet.total >= wallet.initial}
        />
        <Stat
          label="Cash balance"
          value={money(wallet.cash, wallet.currency)}
          sub={
            money(wallet.reserved_cash, wallet.currency) +
            " reserved for pending orders"
          }
        />
        <Stat
          label="Realized profit / loss"
          value={money(wallet.realized, wallet.currency)}
          positive={wallet.realized >= 0}
        />
        <Stat
          label="Unrealized profit / loss"
          value={money(wallet.unrealized, wallet.currency)}
          positive={wallet.unrealized >= 0}
        />
      </div>
      <section className="panel">
        <div className="panel-header">
          <h2>Open positions</h2>
          <Badge>{wallet.positions.length} POSITIONS</Badge>
        </div>
        {wallet.positions.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Instrument</th>
                  <th>Quantity</th>
                  <th>Average cost</th>
                  <th>Marked price</th>
                  <th>Value</th>
                  <th>Profit / loss</th>
                  <th>Observation</th>
                </tr>
              </thead>
              <tbody>
                {wallet.positions.map((p) => (
                  <tr key={p.symbol}>
                    <td>
                      <strong>{p.symbol}</strong>
                    </td>
                    <td>{p.qty}</td>
                    <td>{money(p.avg_price, wallet.currency)}</td>
                    <td>{money(p.price, wallet.currency)}</td>
                    <td>{money(p.value, wallet.currency)}</td>
                    <td className={p.pnl >= 0 ? "up" : "down"}>
                      {money(p.pnl, wallet.currency)}
                    </td>
                    <td>
                      {p.observed_at} · {p.status}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty title="An open field of possibilities.">
            Your first filled order will appear here.
          </Empty>
        )}
        {wallet.positions.length > 0 && (
          <div className="allocation">
            <h3>Portfolio allocation</h3>
            <div className="allocation-track">
              {wallet.positions.map((p, i) => (
                <div
                  key={p.symbol}
                  title={
                    p.symbol +
                    " " +
                    ((p.value / wallet.total) * 100).toFixed(1) +
                    "%"
                  }
                  style={{
                    width: (p.value / wallet.total) * 100 + "%",
                    background: ["#62dfb0", "#a4a0ff", "#6eabef", "#e0ba7d"][
                      i % 4
                    ],
                  }}
                />
              ))}
              <div
                title="Cash"
                style={{
                  width: (wallet.cash / wallet.total) * 100 + "%",
                  background: "#344557",
                }}
              />
            </div>
            <div className="allocation-key">
              {wallet.positions.map((p) => (
                <span key={p.symbol}>
                  {p.symbol}{" "}
                  <strong>
                    {((p.value / wallet.total) * 100).toFixed(1)}%
                  </strong>
                </span>
              ))}
              <span>
                Cash{" "}
                <strong>
                  {((wallet.cash / wallet.total) * 100).toFixed(1)}%
                </strong>
              </span>
            </div>
          </div>
        )}
        <div className="panel-footer">{wallet.valuation_note}</div>
      </section>
    </>
  );
}
function PaperPerformance({ revision }: { revision: number }) {
  const points = useResource<
    { date: string; value: number; benchmark: number }[]
  >("/paper/performance", revision);
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Saved portfolio performance</h2>
        <Badge>ACTUAL ACCOUNT SNAPSHOTS</Badge>
      </div>
      <Load {...points} />
      {points.data?.length ? (
        <ComparisonChart
          points={points.data}
          labels={["Marked portfolio", "Starting capital"]}
        />
      ) : (
        <Empty title="Your track record starts with the first fill.">
          Daily snapshots are saved after current-market fills and worker
          observations. Historical replay has its own performance chart.
        </Empty>
      )}
    </section>
  );
}
function Orders({
  scope,
  revision,
  action,
}: {
  scope: string;
  revision: number;
  action: Action;
}) {
  const data = useResource<Order[]>("/paper/orders?scope=" + scope, revision);
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Order timeline</h2>
        <Badge>DATABASE SAVED</Badge>
      </div>
      <Load {...data} />
      {data.data?.length ? (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Instrument</th>
                <th>Side</th>
                <th>Quantity</th>
                <th>Order</th>
                <th>Fill price</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {data.data.map((o) => (
                <tr key={o.id}>
                  <td>
                    <strong>{o.symbol}</strong>
                    <small className="block muted">
                      {o.filled_at || "Awaiting a later observation"}
                    </small>
                  </td>
                  <td className={o.side === "BUY" ? "up" : "down"}>{o.side}</td>
                  <td>{o.qty}</td>
                  <td>
                    {o.order_type}
                    {o.order_type === "LIMIT"
                      ? " · " + money(Number(o.price))
                      : ""}
                  </td>
                  <td>{o.fill_price ? money(o.fill_price) : "—"}</td>
                  <td>
                    <Badge
                      tone={
                        o.status === "FILLED"
                          ? "green"
                          : o.status === "PENDING"
                            ? "amber"
                            : ""
                      }
                    >
                      {o.status}
                    </Badge>
                  </td>
                  <td>
                    {o.status === "PENDING" && (
                      <button
                        className="text-button"
                        onClick={() =>
                          action(
                            () => api("/paper/orders/" + o.id, "DELETE"),
                            "Order cancelled",
                          )
                        }
                      >
                        Cancel
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        !data.loading && (
          <Empty title="No orders in this workspace yet.">
            Record a decision and place your first virtual trade.
          </Empty>
        )
      )}
    </section>
  );
}
function ReplayLab({
  user,
  requireUser,
  quotes,
  symbol,
  setSymbol,
  replay,
  setReplay,
  action,
  busy,
  revision,
}: {
  user: User | null;
  requireUser: () => boolean;
  quotes: Quote[];
  symbol: string;
  setSymbol: (s: string) => void;
  replay: Replay | null;
  setReplay: (r: Replay | null) => void;
  action: Action;
  busy: boolean;
  revision: number;
}) {
  const [feeBps, setFeeBps] = useState(10);
  const [date, setDate] = useState(""),
    [playing, setPlaying] = useState(false);
  const sessions = useResource<{ id: string; symbol: string; date: string }[]>(
    user ? "/replays" : null,
    revision,
  );
  const history = useResource<Candle[]>("/candles/" + symbol + "?limit=2000");
  const [replayAnalysis, setReplayAnalysis] = useState<Analysis | null>(null);
  const stepLock = useRef(false);
  useEffect(() => {
    let live = true;
    if (replay)
      api<Replay>("/replays/" + replay.id)
        .then((v) => {
          if (live) setReplay(v);
        })
        .catch(() => {});
    return () => {
      live = false;
    };
  }, [revision, replay?.id]);
  useEffect(() => {
    if (history.data) {
      setDate(
        history.data[Math.max(60, history.data.length - 180)]?.date.slice(
          0,
          10,
        ) || "",
      );
    }
  }, [history.data]);
  useEffect(() => {
    let live = true;
    if (!replay) {
      setReplayAnalysis(null);
      return;
    }
    api<Analysis>("/replays/" + replay.id + "/analysis")
      .then((d) => {
        if (live) setReplayAnalysis(d);
      })
      .catch(() => {
        if (live) setReplayAnalysis(null);
      });
    return () => {
      live = false;
    };
  }, [replay?.id, replay?.date]);
  const next = useCallback(
    async (steps = 1) => {
      if (!replay || stepLock.current) return;
      stepLock.current = true;
      try {
        const r = await action(() =>
          api<Replay>("/replays/" + replay.id + "/advance", "POST", { steps }),
        );
        if (r) setReplay(r);
        else setPlaying(false);
      } finally {
        stepLock.current = false;
      }
    },
    [replay, action, setReplay],
  );
  useEffect(() => {
    if (!playing || !replay || replay.ended || busy) return;
    const t = setTimeout(() => next(), 1400);
    return () => clearTimeout(t);
  }, [playing, replay, busy, next]);
  useEffect(() => {
    if (replay?.ended) setPlaying(false);
  }, [replay?.ended]);
  return (
    <>
      <Heading
        eyebrow="THE PAST IS YOUR PRACTICE GROUND"
        title="Market replay lab"
        text="Step through real history. Make the call before you know what happens next."
      />
      <div className="info-banner">
        <Clock3 size={18} />
        <span>
          Historical replay · Future bars are hidden. Research forecasts are
          disabled here because their training may include later dates.
        </span>
      </div>
      <section className="panel replay-setup">
        <label>
          Simulation costs (basis points per fill)
          <input
            type="number"
            min="0"
            max="100"
            value={feeBps}
            onChange={(e) => setFeeBps(Number(e.target.value))}
          />
        </label>
        <SelectAsset {...{ symbol, setSymbol, quotes }} />
        <label>
          Start date
          <input
            type="date"
            value={date}
            min={history.data?.[150]?.date.slice(0, 10)}
            max={history.data?.[history.data.length - 3]?.date.slice(0, 10)}
            onChange={(e) => setDate(e.target.value)}
          />
        </label>
        <button
          className="button primary"
          disabled={busy || !date}
          onClick={async () => {
            if (!requireUser()) return;
            setPlaying(false);
            const r = await action(
              () =>
                api<Replay>("/replays", "POST", {
                  symbol,
                  start_date: date,
                  fee_bps: feeBps,
                }),
              "Replay ready. Future observations are hidden.",
            );
            if (r) setReplay(r);
          }}
        >
          <Play size={16} />
          {replay ? "New replay session" : "Start a replay"}
        </button>
        {sessions.data && sessions.data.length > 0 && (
          <label>
            Resume saved session
            <select
              aria-label="Resume saved replay"
              value={replay?.id || ""}
              onChange={async (e) => {
                if (!e.target.value) return;
                setPlaying(false);
                const r = await action(() =>
                  api<Replay>("/replays/" + e.target.value),
                );
                if (r) {
                  setReplay(r);
                  setSymbol(r.symbol);
                }
              }}
            >
              <option value="">Choose a session</option>
              {sessions.data.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.symbol} · {s.date} · {s.id.slice(0, 5)}
                </option>
              ))}
            </select>
          </label>
        )}
      </section>
      <Load {...history} />
      {!replay ? (
        <section className="panel replay-intro">
          <div className="replay-visual">
            <Play size={52} />
          </div>
          <h2>One market. A thousand possible decisions.</h2>
          <p>
            Choose a company and a past date. You’ll see only the information
            available up to that session. Submit a virtual order, reveal the
            next session, and watch your decision become a result.
          </p>
          <div className="replay-steps">
            <span>
              <b>01</b>Choose your moment
            </span>
            <span>
              <b>02</b>Record your reasoning
            </span>
            <span>
              <b>03</b>Reveal the outcome
            </span>
          </div>
        </section>
      ) : (
        <>
          <div className="replay-control">
            <div>
              <Badge tone="purple">REPLAY SESSION</Badge>
              <strong>{replay.symbol}</strong>
              <span>{niceDate(replay.date)}</span>
              <span className="up">
                {money(replay.current_price, replay.currency)}
              </span>
            </div>
            <div>
              <button
                className="button"
                disabled={busy || replay.ended}
                onClick={() => setPlaying(!playing)}
              >
                {playing ? <Pause size={16} /> : <Play size={16} />}{" "}
                {playing ? "Pause" : "Play"}
              </button>
              <button
                className="button primary"
                disabled={busy || replay.ended}
                onClick={() => {
                  setPlaying(false);
                  next();
                }}
              >
                Next observation <SkipForward size={16} />
              </button>
              <button
                className="button"
                disabled={busy || replay.ended}
                onClick={() => {
                  setPlaying(false);
                  next(5);
                }}
              >
                +5 observations
              </button>
            </div>
          </div>
          {replay.ended && (
            <div className="info-banner">
              <Check size={18} />
              Replay complete. Compare your outcome below or start another
              session.
            </div>
          )}
          <div className="research-layout">
            <div className="stack">
              <section className="panel chart-panel">
                <div className="panel-header">
                  <h2>
                    {replay.symbol} · observed through {replay.date}
                  </h2>
                  <Badge>NO FUTURE BARS</Badge>
                </div>
                <PriceChart candles={replay.candles} />
                <div className="panel-footer">
                  {replay.source}
                  <span>Historical daily candles</span>
                </div>
              </section>
              <section className="panel">
                <div className="panel-header">
                  <h2>Did your decisions add value?</h2>
                  <a
                    className="button small"
                    href={"/v1/replays/" + replay.id + "/export.csv"}
                  >
                    Export results <ArrowDownLeft size={14} />
                  </a>
                </div>
                <div className="stats-grid two">
                  <Stat
                    label="Your portfolio"
                    value={money(replay.portfolio.total, replay.currency)}
                    sub={pct((replay.portfolio.total / 1000000 - 1) * 100)}
                  />
                  <Stat
                    label="Buy and hold"
                    value={money(replay.benchmark_value, replay.currency)}
                    sub={pct(replay.benchmark_return_pct)}
                  />
                </div>
                <ComparisonChart points={replay.equity} />
                <p className="chart-note">{replay.execution_rule}</p>
              </section>
            </div>
            <div className="stack">
              <TradeTicket
                key={replay.id}
                symbol={replay.symbol}
                price={replay.current_price}
                currency={replay.currency}
                busy={busy}
                disabled={replay.ended}
                replay
                onSubmit={async (body) => {
                  const r = await action(
                    () =>
                      api("/replays/" + replay.id + "/orders", "POST", body),
                    "Order queued. Advance the replay to observe execution.",
                  );
                  if (r) {
                    const v = await action(() =>
                      api<Replay>("/replays/" + replay.id),
                    );
                    if (v) setReplay(v);
                  }
                  return r !== undefined;
                }}
              />
              <section className="panel">
                <div className="panel-header">
                  <h2>Evidence at this moment</h2>
                </div>
                {replayAnalysis?.indicators.slice(0, 3).map((i) => (
                  <div className="evidence" key={i.name}>
                    <span>{i.name}</span>
                    <strong>{number(i.value)}</strong>
                  </div>
                ))}
                <p className="chart-note">
                  Calculated only through {replay.date}. No forecast trained on
                  later observations is used.
                </p>
              </section>
            </div>
          </div>
          <PortfolioView wallet={replay.portfolio} />
          <Orders scope={replay.id} revision={revision} action={action} />
        </>
      )}
    </>
  );
}
function ModelLab({
  symbol,
  setSymbol,
  quotes,
}: {
  symbol: string;
  setSymbol: (s: string) => void;
  quotes: Quote[];
}) {
  const currency = quotes.find((q) => q.symbol === symbol)?.currency || "INR";
  const [horizon, setHorizon] = useState(1);
  const segment = quotes.find((q) => q.symbol === symbol)?.segment;
  const horizons =
    segment === "funds"
      ? [21]
      : segment === "intraday"
        ? [3]
        : segment === "crypto"
          ? [1, 24]
          : [1, 5];
  useEffect(() => setHorizon(horizons[0]), [symbol, segment]);
  const [runVersion, setRunVersion] = useState("");
  const runs =
    useResource<
      { version: string; symbol: string; horizon: number; as_of: string }[]
    >("/models/runs");
  useEffect(() => setRunVersion(""), [symbol, horizon]);
  const data = useResource<Forecast>(
    runVersion
      ? "/models/runs/" + runVersion
      : "/predictions/" + symbol + "?horizon=" + horizon,
  );
  const f = data.data;
  return (
    <>
      <Heading
        eyebrow="EVIDENCE OVER IMPRESSIVE NUMBERS"
        title="Put the models on trial."
        text="Three approaches. The same data. A test period none of them trained on."
      />
      <div className="toolbar">
        <label>
          Saved experiment
          <select
            value={runVersion}
            onChange={(e) => setRunVersion(e.target.value)}
          >
            <option value="">Latest dataset run</option>
            {runs.data
              ?.filter((r) => r.symbol === symbol && r.horizon === horizon)
              .map((r) => (
                <option key={r.version} value={r.version}>
                  {r.as_of} · {r.version.slice(-16)}
                </option>
              ))}
          </select>
        </label>
        <SelectAsset {...{ symbol, setSymbol, quotes }} />
        <div className="segmented compact">
          <button
            className={horizon === horizons[0] ? "selected" : ""}
            onClick={() => setHorizon(horizons[0])}
          >
            {horizons[0]} observations
          </button>
          <button
            className={horizon === (horizons[1] || -1) ? "selected" : ""}
            onClick={() => setHorizon(horizons[1] || horizons[0])}
          >
            {horizons[1] || horizons[0]} observations
          </button>
        </div>
      </div>
      <Load {...data} />
      {f && (
        <>
          <div className="stats-grid">
            <Stat
              label="Selected on validation"
              value={f.selected_model}
              sub="Selection happened before the final test"
            />
            <Stat
              label="Forecast target"
              value={money(f.predicted_target, currency)}
              sub={"As of " + f.as_of}
            />
            <Stat
              label="Final test price error"
              value={money(f.test[f.selected_model].mae, currency)}
              sub="Mean absolute error; lower is better"
            />
            <Stat
              label="Interval test coverage"
              value={f.interval.test_coverage_pct + "%"}
              sub="Empirical coverage; nominal target 80%"
            />
          </div>
          <div className="info-banner">
            <FlaskConical size={18} />
            <span>
              {f.beats_baseline
                ? "The validation-selected model also beats the last-price baseline on final test error."
                : "The validation-selected model does not beat the last-price baseline on final test error. This result is retained, not hidden."}
            </span>
          </div>
          <section className="panel">
            <div className="panel-header">
              <h2>
                The honest scorecard{" "}
                <Badge tone="amber">{f.status || "experimental"}</Badge>
              </h2>
              <a
                className="button small"
                href={
                  "/v1/predictions/" + symbol + "/export.csv?horizon=" + horizon
                }
              >
                Export test results <ArrowDownLeft size={14} />
              </a>
            </div>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Model</th>
                    <th>Validation error ({currency})</th>
                    <th>Test error ({currency})</th>
                    <th>Root mean square error</th>
                    <th>Direction match</th>
                    <th>Strategy return</th>
                    <th>Worst drawdown</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(f.test).map(([name, m]) => (
                    <tr key={name}>
                      <td>
                        <strong>{name}</strong>
                        {name === f.selected_model && (
                          <Badge tone="green">SELECTED</Badge>
                        )}
                      </td>
                      <td>{number(f.validation[name].mae)}</td>
                      <td>{number(m.mae)}</td>
                      <td>{number(m.rmse)}</td>
                      <td>{m.directional_accuracy_pct}%</td>
                      <td
                        className={m.strategy_return_pct >= 0 ? "up" : "down"}
                      >
                        {pct(m.strategy_return_pct)}
                      </td>
                      <td>{m.max_drawdown_pct}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="chart-note">
              The last-price model predicts zero change, so its exact direction
              match is usually zero and its long/cash strategy stays in cash.
              Price error is the primary comparison.
            </p>
          </section>
          <div className="two-col">
            <section className="panel">
              <div className="panel-header">
                <h2>Prediction versus what happened</h2>
                <Badge>FINAL TEST</Badge>
              </div>
              <ComparisonChart
                labels={["Observed close", "Selected forecast"]}
                points={f.test_points.map((p) => ({
                  date: p.date,
                  value: p.actual,
                  benchmark: p.prediction,
                }))}
              />
            </section>
            <section className="panel">
              <div className="panel-header">
                <h2>Experiment provenance</h2>
                <Badge>REPRODUCIBLE</Badge>
              </div>
              <div className="provenance">
                {f.folds?.map((fold) => (
                  <p key={fold.fold}>
                    <span>
                      Fold {fold.fold} · trained through {fold.train_end}
                    </span>
                    <strong>
                      Test {fold.test_start} to {fold.test_end}
                    </strong>
                  </p>
                ))}
                <p>
                  <strong>Version</strong>
                  <code>{f.version}</code>
                </p>
                {Object.entries(f.split).map(([k, v]) => (
                  <p key={k}>
                    <span>{k.replaceAll("_", " ")}</span>
                    <strong>{v}</strong>
                  </p>
                ))}
              </div>
            </section>
          </div>
          <section className="panel">
            <div className="panel-header">
              <h2>What these results mean</h2>
            </div>
            <div className="explanation-grid">
              <div>
                <h3>Execution assumptions</h3>
                <p>{f.strategy_assumptions}</p>
              </div>
              <div>
                <h3>Uncertainty, measured</h3>
                <p>
                  {f.interval.method}. Range:{" "}
                  {money(f.interval.lower, currency)} to{" "}
                  {money(f.interval.upper, currency)}.
                </p>
                <p>{f.interval.caveat}</p>
              </div>
              <div>
                <h3>Training inputs</h3>
                <p>{f.training.features}</p>
                <p>{f.notes.join(" ")}</p>
              </div>
            </div>
          </section>
        </>
      )}
    </>
  );
}
function Journal({ revision }: { revision: number }) {
  const entries = useResource<
    {
      order_id: string;
      symbol: string;
      reason: string;
      observed_at: string;
      observed_price: number;
      forecast_version?: string;
      scope: string;
      order: Order;
      marked_change_pct: number | null;
      outcome_note: string;
    }[]
  >("/journal", revision);
  return (
    <>
      <Load {...entries} />
      {entries.data?.length ? (
        <div className="journal-grid">
          {entries.data.map((e) => (
            <article key={e.order_id} className="panel journal-entry">
              <div className="panel-header">
                <h2>{e.symbol}</h2>
                <Badge tone={e.order?.status === "FILLED" ? "green" : "amber"}>
                  {e.order?.status}
                </Badge>
              </div>
              <div className="eyebrow">
                {e.scope === "paper"
                  ? "CURRENT-MARKET ACCOUNT"
                  : "HISTORICAL REPLAY"}{" "}
                · {e.observed_at}
              </div>
              <h3>
                {e.order?.side} {e.order?.qty} shares
              </h3>
              <p className="journal-reason">
                {e.reason || "No reasoning recorded for this decision."}
              </p>
              <div className="evidence">
                <span>Observed price</span>
                <strong>{money(e.observed_price)}</strong>
              </div>
              <div className="evidence">
                <span>Actual fill</span>
                <strong>
                  {e.order?.fill_price
                    ? money(e.order.fill_price)
                    : "Not filled"}
                </strong>
              </div>
              <div className="evidence">
                <span>Price change since fill</span>
                <strong
                  className={(e.marked_change_pct || 0) >= 0 ? "up" : "down"}
                >
                  {e.marked_change_pct === null
                    ? "Awaiting fill"
                    : pct(e.marked_change_pct)}
                </strong>
              </div>
              <p className="chart-note">{e.outcome_note}</p>
              <small className="muted">
                {e.forecast_version
                  ? "Forecast: " + e.forecast_version
                  : "No forecast attached. Replay decisions use information visible at that time."}
              </small>
            </article>
          ))}
        </div>
      ) : (
        !entries.loading && (
          <Empty title="Your thinking is part of the result.">
            Add your reasoning when placing a virtual order. The journal links
            it to the observed price and actual execution.
          </Empty>
        )
      )}
    </>
  );
}
function Alerts({
  symbol,
  quotes,
  replay,
  action,
  revision,
}: {
  symbol: string;
  quotes: Quote[];
  replay: Replay | null;
  action: Action;
  revision: number;
}) {
  const [kind, setKind] = useState("price");
  const [sym, setSym] = useState(symbol),
    [direction, setDirection] = useState("above"),
    [target, setTarget] = useState(""),
    [scope, setScope] = useState("paper");
  const rules = useResource<
    {
      id: string;
      symbol: string;
      direction: string;
      target: string;
      scope: string;
      active: boolean;
    }[]
  >("/alerts", revision);
  const events = useResource<
    {
      id: string;
      symbol: string;
      price: number;
      observed_at: string;
      direction: string;
      target: number;
    }[]
  >("/alerts/events", revision);
  return (
    <>
      <section className="panel">
        <div className="panel-header">
          <h2>Create a price-crossing alert</h2>
          <Badge>IN-APP NOTIFICATIONS</Badge>
        </div>
        <label className="feature-form">
          Condition
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            {[
              ["price", "Price crossing"],
              ["percent_move", "Percent move"],
              ["rsi", "RSI crossing"],
              ["nav_update", "New fund NAV publication"],
              ["portfolio_loss", "Portfolio loss percentage"],
            ].map(([v, t]) => (
              <option key={v} value={v}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <form
          className="alert-form"
          onSubmit={async (e) => {
            e.preventDefault();
            await action(
              () =>
                api("/alerts", "POST", {
                  symbol: scope === "paper" ? sym : replay?.symbol,
                  kind,
                  direction,
                  target,
                  scope,
                }),
              "Alert saved. It will fire when the observed price crosses the threshold.",
            );
          }}
        >
          <label>
            Workspace
            <select value={scope} onChange={(e) => setScope(e.target.value)}>
              <option value="paper">Current-market account</option>
              {replay && (
                <option value={replay.id}>
                  {replay.symbol} replay · {replay.date}
                </option>
              )}
            </select>
          </label>
          <label>
            Instrument
            <select
              value={scope === "paper" ? sym : replay?.symbol}
              disabled={scope !== "paper"}
              onChange={(e) => setSym(e.target.value)}
            >
              {quotes.map((q) => (
                <option key={q.symbol}>{q.symbol}</option>
              ))}
            </select>
          </label>
          <label>
            Crosses
            <select
              value={direction}
              onChange={(e) => setDirection(e.target.value)}
            >
              <option value="above">Above</option>
              <option value="below">Below</option>
            </select>
          </label>
          <label>
            Condition threshold
            <input
              required
              type="number"
              min={kind === "percent_move" ? "-100" : "0.01"}
              step="0.01"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
            />
          </label>
          <button className="button primary">
            <Plus size={16} />
            Create alert
          </button>
        </form>
        <p className="chart-note">
          Current-market rules need fresh provider observations. To demonstrate
          without credentials, create a replay alert and advance that session. A
          five-minute observation-time cooldown prevents repeated firing.
        </p>
      </section>
      <div className="two-col">
        <section className="panel">
          <div className="panel-header">
            <h2>Saved rules</h2>
          </div>
          <Load {...rules} />
          {rules.data?.length ? (
            rules.data.map((r) => (
              <div className="alert-item" key={r.id}>
                <Bell size={18} />
                <div>
                  <strong>
                    {r.symbol} crosses {r.direction} {money(Number(r.target))}
                  </strong>
                  <small>
                    {r.scope === "paper"
                      ? "Current-market"
                      : "Historical replay"}{" "}
                    · {r.active ? "Active" : "Disabled"}
                  </small>
                </div>
                {r.active && (
                  <button
                    className="icon-button"
                    aria-label="Disable alert"
                    onClick={() =>
                      action(
                        () => api("/alerts/" + r.id, "DELETE"),
                        "Alert disabled",
                      )
                    }
                  >
                    <X size={16} />
                  </button>
                )}
              </div>
            ))
          ) : (
            <Empty title="No rules yet">
              Create your first crossing alert above.
            </Empty>
          )}
        </section>
        <section className="panel">
          <div className="panel-header">
            <h2>Event trail</h2>
          </div>
          <Load {...events} />
          {events.data?.length ? (
            events.data.map((e) => (
              <div className="alert-item" key={e.id}>
                <Check className="up" size={18} />
                <div>
                  <strong>
                    {e.symbol} crossed {e.direction} {money(e.target)}
                  </strong>
                  <small>
                    Observed {money(e.price)} · {e.observed_at}
                  </small>
                </div>
              </div>
            ))
          ) : (
            <Empty title="Nothing has crossed yet.">
              Events appear when a saved rule crosses its threshold, not merely
              when it is already above or below it.
            </Empty>
          )}
        </section>
      </div>
    </>
  );
}
function Learn({ revision, action }: { revision: number; action: Action }) {
  const lessons = useResource<Lesson[]>("/learn/lessons", revision);
  const bookmarks = useResource<string[]>("/learn/bookmarks", revision);
  const [selected, setSelected] = useState<string | null>(null),
    [feedback, setFeedback] = useState(""),
    [segment,setSegment] = useState("all"),
    [level,setLevel] = useState("all"),
    [savedOnly,setSavedOnly] = useState(false);
  const current = lessons.data?.find((x) => x.id === selected);
  return (
    <>
      <Load {...lessons} />
      <div className="learning-progress">
        <span>
          <BookOpen size={18} />
          {lessons.data?.filter((x) => x.progress?.passed).length || 0} of{" "}
          {lessons.data?.length || 0} lessons completed
        </span>
        <div>
          <i
            style={{
              width:
                ((lessons.data?.filter((x) => x.progress?.passed).length || 0) /
                  (lessons.data?.length || 1)) *
                  100 +
                "%",
            }}
          />
        </div>
      </div>
      <div className="toolbar"><label>Learning track<select value={segment} onChange={e=>setSegment(e.target.value)}>{['all','equities','intraday','derivatives','funds','crypto'].map(x=><option key={x} value={x}>{x==='all'?'All tracks':x}</option>)}</select></label><label>Level<select value={level} onChange={e=>setLevel(e.target.value)}>{['all',...new Set(lessons.data?.map(l=>l.level)||[])].map(x=><option key={x} value={x}>{x==='all'?'All levels':x}</option>)}</select></label><label><input type="checkbox" checked={savedOnly} onChange={e=>setSavedOnly(e.target.checked)}/>Bookmarked lessons only</label></div>
      <div className="lesson-grid">
        {lessons.data?.filter(l=>(segment==="all"||l.segment===segment||!l.segment||l.segment==="general")&&(level==="all"||l.level===level)&&(!savedOnly||bookmarks.data?.includes(l.id))).map((l, i) => (
          <button
            className={
              "panel lesson " + (selected === l.id ? "selected-lesson" : "")
            }
            key={l.id}
            onClick={() => {
              setSelected(l.id);
              setFeedback("");
            }}
          >
            <div className="lesson-number">
              0{i + 1}
              {l.progress?.passed && <Check size={20} />}
            </div>
            <Badge>{l.level}</Badge>
            <h2>{l.title}</h2>
            <p>{l.body.slice(0, 112)}…</p>
            <div className="lesson-foot">
              <span>
                <Clock3 size={14} />
                {l.minutes} min
              </span>
              <span>
                {l.progress?.passed ? "Revisit lesson" : "Open lesson"}
                <ArrowRight size={16} />
              </span>
            </div>
          </button>
        ))}
      </div>
      {current && (
        <section className="panel lesson-content">
          <Badge tone="green">{current.level}</Badge>
          <h2>{current.title}</h2>
          <div className="toolbar">
            <button
              className="button"
              onClick={() =>
                action(
                  () =>
                    api(
                      "/learn/bookmarks/" + current.id,
                      bookmarks.data?.includes(current.id) ? "DELETE" : "POST",
                    ),
                  "Lesson bookmark updated",
                )
              }
            >
              {bookmarks.data?.includes(current.id)
                ? "Remove bookmark"
                : "Bookmark lesson"}
            </button>
            <a className="button" href={current.practice || "/replay"}>
              Practice this concept
            </a>
          </div>
          <p>{current.body}</p>
          <h3>{current.question}</h3>
          <div className="quiz-options">
            {current.options.map((o, i) => (
              <button
                key={o}
                className="button"
                onClick={async () => {
                  const r = await action(() =>
                    api<{ correct: boolean; explanation: string }>(
                      "/learn/quiz",
                      "POST",
                      { lesson_id: current.id, answer: i },
                    ),
                  );
                  if (r)
                    setFeedback(
                      (r.correct ? "Correct. " : "Try again. ") + r.explanation,
                    );
                }}
              >
                <span>{String.fromCharCode(65 + i)}</span>
                {o}
              </button>
            ))}
          </div>
          {feedback && (
            <div role="status" className="info-banner">
              <CircleHelp size={18} />
              {feedback}
            </div>
          )}
        </section>
      )}
    </>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
