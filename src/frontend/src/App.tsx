import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { api, errorMessage } from "./api";
import type { Answer, EventInfo, Question, QuestionPage, Session } from "./api";

type Tab = "agenda" | "questions" | "suggestions";

function time(value: string, timezone: string) {
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit", minute: "2-digit", timeZone: timezone,
  }).format(new Date(value));
}

function Alert({ children }: { children: string }) {
  return <p className="alert" role="alert">{children}</p>;
}

function QuestionBoard({ session }: { session: Session }) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [text, setText] = useState("");
  const key = useRef(crypto.randomUUID());
  const [busy, setBusy] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pollError, setPollError] = useState("");
  const [voteBusy, setVoteBusy] = useState<string | null>(null);
  const [voted, setVoted] = useState<Set<string>>(new Set());
  const [voter, setVoter] = useState("");
  const [storageWarning, setStorageWarning] = useState("");
  const pagesToRefresh = useRef(4);

  useEffect(() => {
    try {
      let id = localStorage.getItem("geneva-2026-voter");
      if (!id || !/^[0-9a-f-]{36}$/i.test(id)) {
        id = crypto.randomUUID();
        localStorage.setItem("geneva-2026-voter", id);
      }
      setVoter(id);
    } catch {
      setVoter(crypto.randomUUID());
      setStorageWarning("Browser storage is unavailable. Your voting identity lasts only this tab.");
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let inFlight = false;
    async function refresh() {
      if (inFlight || document.visibilityState === "hidden") return;
      inFlight = true;
      try {
        const items: Question[] = [];
        let next: string | null = null;
        do {
          const query = next ? `?cursor=${encodeURIComponent(next)}` : "";
          const page: QuestionPage = await api(
            `/api/sessions/${session.id}/questions${query}`, { signal: controller.signal },
          );
          items.push(...page.items);
          next = page.next_cursor;
        } while (next && items.length < pagesToRefresh.current * 50);
        if (!controller.signal.aborted) {
          setQuestions(items);
          setCursor(next);
          setPollError("");
          setLoading(false);
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setPollError(errorMessage(error));
          setLoading(false);
        }
      } finally {
        inFlight = false;
      }
    }
    void refresh();
    const interval = setInterval(() => void refresh(), 5000);
    return () => { controller.abort(); clearInterval(interval); };
  }, [session.id]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSubmitted(false);
    try {
      await api<Question>(`/api/sessions/${session.id}/questions`, {
        method: "POST", body: JSON.stringify({ text, idempotency_key: key.current }),
      });
      setText("");
      key.current = crypto.randomUUID();
      setSubmitted(true);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function vote(question: Question) {
    setVoteBusy(question.id);
    setError("");
    try {
      const updated = await api<Question>(
        `/api/questions/${question.id}/votes/${voter}?session_id=${session.id}`, { method: "PUT" },
      );
      setQuestions(current => current.map(item => item.id === updated.id ? updated : item));
      setVoted(current => new Set([...current, question.id]));
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setVoteBusy(null);
    }
  }

  async function loadMore() {
    if (!cursor) return;
    setLoading(true);
    try {
      const page = await api<QuestionPage>(
        `/api/sessions/${session.id}/questions?cursor=${encodeURIComponent(cursor)}`,
      );
      setQuestions(current => {
        const combined = new Map(current.map(item => [item.id, item]));
        page.items.forEach(item => combined.set(item.id, item));
        return [...combined.values()];
      });
      setCursor(page.next_cursor);
      pagesToRefresh.current += 1;
    } catch (error) {
      setPollError(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  return <section aria-labelledby="questions-title">
    <div className="section-heading">
      <div><p className="eyebrow">JOIN THE CONVERSATION</p><h2 id="questions-title">Your questions, live.</h2></div>
      <span className="live-label"><span />Updates every 5s</span>
    </div>
    <p className="muted">Approved questions are visible to everyone. Please keep them relevant and avoid personal information.</p>
    <form onSubmit={submit} className="question-form">
      <label htmlFor="question">Ask a question about this session</label>
      <textarea id="question" required maxLength={500} value={text} disabled={busy}
        onChange={event => { setText(event.target.value); key.current = crypto.randomUUID(); }}
        placeholder="What would you like to ask?" rows={3} />
      <div className="form-footer"><span className="muted">{text.length}/500</span>
        <button className="primary" disabled={busy || !text.trim()}>{busy ? "Posting..." : "Post question"}</button>
      </div>
      {submitted && <p className="muted">Submitted questions appear after moderator approval.</p>}
    </form>
    {error && <Alert>{error}</Alert>}
    {pollError && <Alert>{pollError}</Alert>}
    {storageWarning && <p className="notice">{storageWarning}</p>}
    <div className="question-list" aria-live="polite">
      {loading && questions.length === 0 && <p className="muted">Loading questions...</p>}
      {!loading && !pollError && questions.length === 0 && <div className="empty-state">
        <span className="empty-icon" aria-hidden="true">?</span><h3>Start the conversation</h3>
        <p>The first question could be yours.</p>
      </div>}
      {questions.map(question => <article className="question-card" key={question.id}>
        <div><p>{question.text}</p><span className="muted">Asked at {time(question.created_at, "Europe/Zurich")}</span></div>
        <button className={`vote ${voted.has(question.id) ? "voted" : ""}`}
          aria-label={`Upvote: ${question.text}`} aria-pressed={voted.has(question.id)}
          disabled={!voter || voteBusy === question.id || voted.has(question.id)} onClick={() => void vote(question)}>
          <span aria-hidden="true">↑</span><strong>{question.votes}</strong>
        </button>
      </article>)}
    </div>
    {cursor && <button className="secondary" disabled={loading} onClick={() => void loadMore()}>Load more questions</button>}
  </section>;
}

function Suggestions() {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const key = useRef(crypto.randomUUID());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [receipt, setReceipt] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await api<{ id: string }>("/api/suggestions", {
        method: "POST", body: JSON.stringify({ title, description, idempotency_key: key.current }),
      });
      setReceipt(response.id);
      setTitle("");
      setDescription("");
      key.current = crypto.randomUUID();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return <section aria-labelledby="suggestions-title">
    <p className="eyebrow">HELP SHAPE WHAT COMES NEXT</p>
    <h2 id="suggestions-title">One idea can start a change.</h2>
    <p className="muted">Suggest a feature for this companion. Ideas go privately to the demo team, not onto the public question board.</p>
    {receipt && <div className="success" role="status"><strong>Your idea is saved.</strong><br />Receipt: {receipt}</div>}
    <form className="suggestion-form" onSubmit={submit}>
      <label htmlFor="idea-title">Your idea in a few words</label>
      <input id="idea-title" maxLength={100} required value={title} disabled={busy}
        onChange={event => { setTitle(event.target.value); key.current = crypto.randomUUID(); }}
        placeholder="What would make this companion better?" />
      <label htmlFor="idea-description">Tell us a little more</label>
      <textarea id="idea-description" maxLength={2000} rows={6} required value={description} disabled={busy}
        onChange={event => { setDescription(event.target.value); key.current = crypto.randomUUID(); }}
        placeholder="Who would it help, and what should it do?" />
      <p className="small muted">Please do not include names, contact details, or confidential information.</p>
      {error && <Alert>{error}</Alert>}
      <button className="primary" disabled={busy || !title.trim() || !description.trim()}>{busy ? "Saving..." : "Send your idea"}</button>
    </form>
  </section>;
}

function Assistant({ onSource }: { onSource: (id: string) => void }) {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setAnswer(null);
    try {
      setAnswer(await api<Answer>("/api/assistant", {
        method: "POST", body: JSON.stringify({ message, request_id: crypto.randomUUID() }),
      }));
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return <aside className="assistant-panel" aria-labelledby="assistant-title">
    <div className="assistant-mark" aria-hidden="true">✦</div>
    <p className="eyebrow">A LITTLE HELP, GROUNDED IN THE AGENDA</p>
    <h2 id="assistant-title">Ask the event guide.</h2>
    <p className="muted">Find a room or a session time. Answers use the published event information and show their sources.</p>
    <form onSubmit={submit}>
      <label htmlFor="assistant-question">Your event question</label>
      <textarea id="assistant-question" rows={3} required maxLength={1000} disabled={busy}
        value={message} onChange={event => setMessage(event.target.value)}
        placeholder="When does the live demo start?" />
      <button className="secondary" disabled={busy || !message.trim()}>{busy ? "Checking the agenda..." : "Ask the guide"}</button>
    </form>
    <div aria-live="polite" aria-busy={busy}>
      {error && <Alert>{error}</Alert>}
      {answer && <div className={`assistant-answer ${answer.refused ? "refusal" : ""}`}>
        <p>{answer.answer}</p>
        {answer.citations.length > 0 && <div className="sources"><span className="eyebrow">SOURCES</span>
          {answer.citations.map(citation => <button key={citation.source_id} onClick={() => onSource(citation.source_id)}>
            {citation.title} <span aria-hidden="true">↗</span>
          </button>)}
        </div>}
      </div>}
    </div>
    <div className="powered"><span aria-hidden="true">◇</span> GitHub Copilot SDK + Microsoft Foundry</div>
    <p className="small muted">A read-only assistant. It cannot see private feature suggestions. Please avoid personal information.</p>
  </aside>;
}

export default function App() {
  const [event, setEvent] = useState<EventInfo | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<Tab>("agenda");
  const [room, setRoom] = useState("all");
  const [selected, setSelected] = useState("meeting-to-pull-request");
  useEffect(() => {
    const controller = new AbortController();
    api<EventInfo>("/api/event", { signal: controller.signal }).then(setEvent).catch(error => {
      if (!controller.signal.aborted) setError(errorMessage(error));
    });
    return () => controller.abort();
  }, []);
  const session = event?.sessions.find(item => item.id === selected) ?? event?.sessions[0];
  function openQuestions(id: string) { setSelected(id); setTab("questions"); }
  return <>
    <header className="masthead"><div className="brand"><span className="brand-symbol" aria-hidden="true">C<span>+</span>AI</span>
      <span>GENEVA <strong>2026</strong></span></div><span className="edition">YOUR EVENT COMPANION</span></header>
    <main>
      <section className="hero">
        <div className="hero-copy"><p className="eyebrow">21 SEPTEMBER 2026 · CAMPUS BIOTECH</p>
          <h1>Cloud &amp; AI Day.<br /><span>Made for connection.</span></h1>
          <p>Your agenda. Your questions. Your next idea.<br />Make the most of a day of cloud and AI in Geneva.</p>
        </div>
        <div className="date-tile" aria-label="Monday, 21 September"><span>MONDAY</span><strong>21</strong><span>SEPTEMBER</span></div>
      </section>
      {error && <Alert>{error}</Alert>}
      {!event && !error && <p role="status" className="loading">Loading your event companion...</p>}
      {event && <>
        <nav className="tabs" aria-label="Event sections">
          {([["agenda", "The agenda"], ["questions", "Live questions"], ["suggestions", "Suggest a feature"]] as const).map(([id, label]) =>
            <button key={id} aria-current={tab === id ? "page" : undefined} onClick={() => setTab(id)}>{label}</button>)}
        </nav>
        <div className="content-grid"><div className="main-panel">
          {tab === "agenda" && <section aria-labelledby="agenda-title">
            <div className="section-heading"><div><p className="eyebrow">MAKE THE DAY YOURS</p><h2 id="agenda-title">Explore the sessions.</h2></div>
              <span className="timezone">All times Europe/Zurich</span></div>
            <p className="notice">{event.notice}</p>
            <div className="room-filter" aria-label="Filter rooms">
              {["all", ...new Set(event.sessions.map(item => item.room))].map(item =>
                <button key={item} aria-pressed={room === item} onClick={() => setRoom(item)}>{item === "all" ? "All rooms" : item}</button>)}
            </div>
            <div className="session-list">{event.sessions.filter(item => room === "all" || item.room === room).map(item =>
              <article className="session-card" id={`session-${item.id}`} key={item.id}>
                <div className="session-time"><strong>{time(item.start, event.timezone)}</strong><span>{time(item.end, event.timezone)}</span></div>
                <div className="session-detail"><div className="session-meta"><span>{item.room}</span>{item.sample && <span className="sample-badge">SAMPLE SESSION</span>}</div>
                  <h3>{item.title}</h3><p>{item.description}</p>
                  <button className="text-button" onClick={() => openQuestions(item.id)}>Join the conversation <span aria-hidden="true">→</span></button>
                </div>
              </article>)}</div>
          </section>}
          {tab === "questions" && session && <>
            <div className="session-picker"><label htmlFor="session">Choose a session</label>
              <select id="session" value={session.id} onChange={event => setSelected(event.target.value)}>
                {event.sessions.map(item => <option key={item.id} value={item.id}>{item.title}{item.sample ? " (sample)" : ""}</option>)}
              </select></div>
            <QuestionBoard key={session.id} session={session} />
          </>}
          {tab === "suggestions" && <Suggestions />}
        </div>
        <Assistant onSource={id => {
          if (id.startsWith("session:")) setSelected(id.slice(8));
          setRoom("all"); setTab("agenda");
          requestAnimationFrame(() => document.getElementById(id.replace(":", "-"))?.scrollIntoView({ behavior: "smooth" }));
        }} />
        </div>
      </>}
    </main>
    <footer><span>Cloud &amp; AI Day Geneva · 21 September 2026</span><span>Built to learn. Ready to evolve.</span></footer>
  </>;
}
