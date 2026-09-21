import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { api, errorMessage } from "./api";
import type { Answer, EventInfo, Question, QuestionPage, Session } from "./api";

type Tab = "agenda" | "questions" | "suggestions";
type Language = "en" | "fr";

const copy = {
  en: {
    language: "Language", english: "English", french: "Français",
    joinConversation: "JOIN THE CONVERSATION", questionsTitle: "Your questions, live.",
    updates: "Updates every 5s", questionsHelp: "Questions appear immediately and are visible to everyone. Please keep them relevant and avoid personal information.",
    askQuestion: "Ask a question about this session", questionPlaceholder: "What would you like to ask?",
    posting: "Posting...", postQuestion: "Post question", storageWarning: "Browser storage is unavailable. Your voting identity lasts only this tab.",
    loadingQuestions: "Loading questions...", startConversation: "Start the conversation", firstQuestion: "The first question could be yours.",
    askedAt: "Asked at", upvote: "Upvote", loadMore: "Load more questions",
    shape: "HELP SHAPE WHAT COMES NEXT", suggestionsTitle: "One idea can start a change.",
    suggestionHelp: "Suggest a feature for this companion. Ideas go privately to the demo team, not onto the public question board.",
    ideaSaved: "Your idea is saved.", receipt: "Receipt", ideaTitle: "Your idea in a few words",
    ideaTitlePlaceholder: "What would make this companion better?", ideaDescription: "Tell us a little more",
    ideaDescriptionPlaceholder: "Who would it help, and what should it do?",
    privacy: "Please do not include names, contact details, or confidential information.", saving: "Saving...", sendIdea: "Send your idea",
    guideEyebrow: "A LITTLE HELP, GROUNDED IN THE AGENDA", guideTitle: "Ask the event guide.",
    guideHelp: "Find a room or a session time. Answers use the published event information and show their sources.",
    eventQuestion: "Your event question", eventQuestionPlaceholder: "When does the live demo start?",
    checking: "Checking the agenda...", askGuide: "Ask the guide", sources: "SOURCES",
    readOnly: "A read-only assistant. It cannot see private feature suggestions. Please avoid personal information.",
    companion: "YOUR EVENT COMPANION", heroEyebrow: "21 SEPTEMBER 2026 · CAMPUS BIOTECH",
    heroTitle: "Cloud & AI Day.", heroAccent: "Made for connection.",
    heroHelp: "Your agenda. Your questions. Your next idea.\nMake the most of a day of cloud and AI in Geneva.",
    monday: "MONDAY", september: "SEPTEMBER", loading: "Loading your event companion...",
    sections: "Event sections", agenda: "The agenda", questions: "Live questions", suggestions: "Suggest a feature",
    agendaEyebrow: "MAKE THE DAY YOURS", agendaTitle: "Explore the sessions.", allTimes: "All times Europe/Zurich",
    filterRooms: "Filter rooms", allRooms: "All rooms", sample: "SAMPLE SESSION", join: "Join the conversation",
    chooseSession: "Choose a session", sampleSuffix: " (sample)",
    footer: "Cloud & AI Day Geneva · 21 September 2026", footerTagline: "Built to learn. Ready to evolve.",
  },
  fr: {
    language: "Langue", english: "English", french: "Français",
    joinConversation: "REJOIGNEZ LA CONVERSATION", questionsTitle: "Vos questions, en direct.",
    updates: "Mise à jour toutes les 5 s", questionsHelp: "Les questions apparaissent immédiatement et sont visibles par tous. Veuillez rester dans le sujet et éviter les informations personnelles.",
    askQuestion: "Posez une question sur cette session", questionPlaceholder: "Que souhaitez-vous demander ?",
    posting: "Publication...", postQuestion: "Publier la question", storageWarning: "Le stockage du navigateur est indisponible. Votre identité de vote ne dure que cet onglet.",
    loadingQuestions: "Chargement des questions...", startConversation: "Lancez la conversation", firstQuestion: "La première question pourrait être la vôtre.",
    askedAt: "Posée à", upvote: "Voter pour", loadMore: "Charger plus de questions",
    shape: "CONTRIBUEZ À LA SUITE", suggestionsTitle: "Une idée peut amorcer un changement.",
    suggestionHelp: "Suggérez une fonctionnalité pour ce compagnon. Les idées sont transmises en privé à l’équipe de démonstration, pas au tableau public des questions.",
    ideaSaved: "Votre idée est enregistrée.", receipt: "Reçu", ideaTitle: "Votre idée en quelques mots",
    ideaTitlePlaceholder: "Qu’est-ce qui améliorerait ce compagnon ?", ideaDescription: "Dites-nous-en un peu plus",
    ideaDescriptionPlaceholder: "Qui cela aiderait-il, et que faudrait-il faire ?",
    privacy: "N’incluez pas de noms, coordonnées ou informations confidentielles.", saving: "Enregistrement...", sendIdea: "Envoyer votre idée",
    guideEyebrow: "UNE AIDE FONDÉE SUR LE PROGRAMME", guideTitle: "Interrogez le guide de l’événement.",
    guideHelp: "Trouvez une salle ou l’horaire d’une session. Les réponses utilisent les informations publiées et affichent leurs sources.",
    eventQuestion: "Votre question sur l’événement", eventQuestionPlaceholder: "Quand commence la démonstration en direct ?",
    checking: "Vérification du programme...", askGuide: "Interroger le guide", sources: "SOURCES",
    readOnly: "Un assistant en lecture seule. Il ne peut pas voir les suggestions privées. Évitez les informations personnelles.",
    companion: "VOTRE COMPAGNON D’ÉVÉNEMENT", heroEyebrow: "21 SEPTEMBRE 2026 · CAMPUS BIOTECH",
    heroTitle: "Cloud & AI Day.", heroAccent: "Créé pour les échanges.",
    heroHelp: "Votre programme. Vos questions. Votre prochaine idée.\nProfitez au mieux d’une journée consacrée au cloud et à l’IA à Genève.",
    monday: "LUNDI", september: "SEPTEMBRE", loading: "Chargement de votre compagnon d’événement...",
    sections: "Sections de l’événement", agenda: "Le programme", questions: "Questions en direct", suggestions: "Suggérer une fonctionnalité",
    agendaEyebrow: "FAITES DE CETTE JOURNÉE LA VÔTRE", agendaTitle: "Explorez les sessions.", allTimes: "Tous les horaires Europe/Zurich",
    filterRooms: "Filtrer les salles", allRooms: "Toutes les salles", sample: "SESSION D’EXEMPLE", join: "Rejoindre la conversation",
    chooseSession: "Choisir une session", sampleSuffix: " (exemple)",
    footer: "Cloud & AI Day Geneva · 21 septembre 2026", footerTagline: "Conçu pour apprendre. Prêt à évoluer.",
  },
} as const;

type Copy = { [Key in keyof typeof copy.en]: string };

function time(value: string, timezone: string, language: Language) {
  return new Intl.DateTimeFormat(language === "fr" ? "fr-FR" : "en-GB", {
    hour: "2-digit", minute: "2-digit", timeZone: timezone,
  }).format(new Date(value));
}

function Alert({ children }: { children: string }) {
  return <p className="alert" role="alert">{children}</p>;
}

function QuestionBoard({ session, text: t, language }: { session: Session; text: Copy; language: Language }) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [text, setText] = useState("");
  const key = useRef(crypto.randomUUID());
  const [busy, setBusy] = useState(false);
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
      setStorageWarning(t.storageWarning);
    }
  }, [t.storageWarning]);

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
    try {
      const question = await api<Question>(`/api/sessions/${session.id}/questions`, {
        method: "POST", body: JSON.stringify({ text, idempotency_key: key.current }),
      });
      setQuestions(current => [...current.filter(item => item.id !== question.id), question]);
      setText("");
      key.current = crypto.randomUUID();
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
      <div><p className="eyebrow">{t.joinConversation}</p><h2 id="questions-title">{t.questionsTitle}</h2></div>
      <span className="live-label"><span />{t.updates}</span>
    </div>
    <p className="muted">{t.questionsHelp}</p>
    <form onSubmit={submit} className="question-form">
      <label htmlFor="question">{t.askQuestion}</label>
      <textarea id="question" required maxLength={500} value={text} disabled={busy}
        onChange={event => { setText(event.target.value); key.current = crypto.randomUUID(); }}
        placeholder={t.questionPlaceholder} rows={3} />
      <div className="form-footer"><span className="muted">{text.length}/500</span>
        <button className="primary" disabled={busy || !text.trim()}>{busy ? t.posting : t.postQuestion}</button>
      </div>
    </form>
    {error && <Alert>{error}</Alert>}
    {pollError && <Alert>{pollError}</Alert>}
    {storageWarning && <p className="notice">{storageWarning}</p>}
    <div className="question-list" aria-live="polite">
      {loading && questions.length === 0 && <p className="muted">{t.loadingQuestions}</p>}
      {!loading && !pollError && questions.length === 0 && <div className="empty-state">
        <span className="empty-icon" aria-hidden="true">?</span><h3>{t.startConversation}</h3>
        <p>{t.firstQuestion}</p>
      </div>}
      {questions.map(question => <article className="question-card" key={question.id}>
        <div><p>{question.text}</p><span className="muted">{t.askedAt} {time(question.created_at, "Europe/Zurich", language)}</span></div>
        <button className={`vote ${voted.has(question.id) ? "voted" : ""}`}
          aria-label={`${t.upvote}: ${question.text}`} aria-pressed={voted.has(question.id)}
          disabled={!voter || voteBusy === question.id || voted.has(question.id)} onClick={() => void vote(question)}>
          <span aria-hidden="true">↑</span><strong>{question.votes}</strong>
        </button>
      </article>)}
    </div>
    {cursor && <button className="secondary" disabled={loading} onClick={() => void loadMore()}>{t.loadMore}</button>}
  </section>;
}

function Suggestions({ text }: { text: Copy }) {
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
    <p className="eyebrow">{text.shape}</p>
    <h2 id="suggestions-title">{text.suggestionsTitle}</h2>
    <p className="muted">{text.suggestionHelp}</p>
    {receipt && <div className="success" role="status"><strong>{text.ideaSaved}</strong><br />{text.receipt}: {receipt}</div>}
    <form className="suggestion-form" onSubmit={submit}>
      <label htmlFor="idea-title">{text.ideaTitle}</label>
      <input id="idea-title" maxLength={100} required value={title} disabled={busy}
        onChange={event => { setTitle(event.target.value); key.current = crypto.randomUUID(); }}
        placeholder={text.ideaTitlePlaceholder} />
      <label htmlFor="idea-description">{text.ideaDescription}</label>
      <textarea id="idea-description" maxLength={2000} rows={6} required value={description} disabled={busy}
        onChange={event => { setDescription(event.target.value); key.current = crypto.randomUUID(); }}
        placeholder={text.ideaDescriptionPlaceholder} />
      <p className="small muted">{text.privacy}</p>
      {error && <Alert>{error}</Alert>}
      <button className="primary" disabled={busy || !title.trim() || !description.trim()}>{busy ? text.saving : text.sendIdea}</button>
    </form>
  </section>;
}

function Assistant({ onSource, text }: { onSource: (id: string) => void; text: Copy }) {
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
    <p className="eyebrow">{text.guideEyebrow}</p>
    <h2 id="assistant-title">{text.guideTitle}</h2>
    <p className="muted">{text.guideHelp}</p>
    <form onSubmit={submit}>
      <label htmlFor="assistant-question">{text.eventQuestion}</label>
      <textarea id="assistant-question" rows={3} required maxLength={1000} disabled={busy}
        value={message} onChange={event => setMessage(event.target.value)}
        placeholder={text.eventQuestionPlaceholder} />
      <button className="secondary" disabled={busy || !message.trim()}>{busy ? text.checking : text.askGuide}</button>
    </form>
    <div aria-live="polite" aria-busy={busy}>
      {error && <Alert>{error}</Alert>}
      {answer && <div className={`assistant-answer ${answer.refused ? "refusal" : ""}`}>
        <p>{answer.answer}</p>
        {answer.citations.length > 0 && <div className="sources"><span className="eyebrow">{text.sources}</span>
          {answer.citations.map(citation => <button key={citation.source_id} onClick={() => onSource(citation.source_id)}>
            {citation.title} <span aria-hidden="true">↗</span>
          </button>)}
        </div>}
      </div>}
    </div>
    <div className="powered"><span aria-hidden="true">◇</span> GitHub Copilot SDK + Microsoft Foundry</div>
    <p className="small muted">{text.readOnly}</p>
  </aside>;
}

export default function App() {
  const [event, setEvent] = useState<EventInfo | null>(null);
  const [error, setError] = useState("");
  const [language, setLanguage] = useState<Language>(() => {
    try {
      return localStorage.getItem("geneva-language") === "fr" ? "fr" : "en";
    } catch {
      return "en";
    }
  });
  const [tab, setTab] = useState<Tab>("agenda");
  const [room, setRoom] = useState("all");
  const [selected, setSelected] = useState("meeting-to-pull-request");
  const text = copy[language];
  useEffect(() => {
    document.documentElement.lang = language;
    try {
      localStorage.setItem("geneva-language", language);
    } catch {}
  }, [language]);
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
      <span>GENEVA <strong>2026</strong></span></div><div className="header-actions"><span className="edition">{text.companion}</span>
      <div className="language-switcher" aria-label={text.language}>
        <button type="button" aria-pressed={language === "en"} onClick={() => setLanguage("en")}>{text.english}</button>
        <button type="button" aria-pressed={language === "fr"} onClick={() => setLanguage("fr")}>{text.french}</button>
      </div></div></header>
    <main>
      <section className="hero">
        <div className="hero-copy"><p className="eyebrow">{text.heroEyebrow}</p>
          <h1>{text.heroTitle}<br /><span>{text.heroAccent}</span></h1>
          <p>{text.heroHelp}</p>
        </div>
        <div className="date-tile" aria-label={`${text.monday}, 21 ${text.september}`}><span>{text.monday}</span><strong>21</strong><span>{text.september}</span></div>
      </section>
      {error && <Alert>{error}</Alert>}
      {!event && !error && <p role="status" className="loading">{text.loading}</p>}
      {event && <>
        <nav className="tabs" aria-label={text.sections}>
          {(["agenda", "questions", "suggestions"] as const).map(id =>
            <button key={id} aria-current={tab === id ? "page" : undefined} onClick={() => setTab(id)}>{text[id]}</button>)}
        </nav>
        <div className="content-grid"><div className="main-panel">
          {tab === "agenda" && <section aria-labelledby="agenda-title">
            <div className="section-heading"><div><p className="eyebrow">{text.agendaEyebrow}</p><h2 id="agenda-title">{text.agendaTitle}</h2></div>
              <span className="timezone">{text.allTimes}</span></div>
            <p className="notice">{event.notice}</p>
            <div className="room-filter" aria-label={text.filterRooms}>
              {["all", ...new Set(event.sessions.map(item => item.room))].map(item =>
                <button key={item} aria-pressed={room === item} onClick={() => setRoom(item)}>{item === "all" ? text.allRooms : item}</button>)}
            </div>
            <div className="session-list">{event.sessions.filter(item => room === "all" || item.room === room).map(item =>
              <article className="session-card" id={`session-${item.id}`} key={item.id}>
                <div className="session-time"><strong>{time(item.start, event.timezone, language)}</strong><span>{time(item.end, event.timezone, language)}</span></div>
                <div className="session-detail"><div className="session-meta"><span>{item.room}</span>{item.sample && <span className="sample-badge">{text.sample}</span>}</div>
                  <h3>{item.title}</h3><p>{item.description}</p>
                  <button className="text-button" onClick={() => openQuestions(item.id)}>{text.join} <span aria-hidden="true">→</span></button>
                </div>
              </article>)}</div>
          </section>}
          {tab === "questions" && session && <>
            <div className="session-picker"><label htmlFor="session">{text.chooseSession}</label>
              <select id="session" value={session.id} onChange={event => setSelected(event.target.value)}>
                {event.sessions.map(item => <option key={item.id} value={item.id}>{item.title}{item.sample ? text.sampleSuffix : ""}</option>)}
              </select></div>
            <QuestionBoard key={session.id} session={session} text={text} language={language} />
          </>}
          {tab === "suggestions" && <Suggestions text={text} />}
        </div>
        <Assistant text={text} onSource={id => {
          if (id.startsWith("session:")) setSelected(id.slice(8));
          setRoom("all"); setTab("agenda");
          requestAnimationFrame(() => document.getElementById(id.replace(":", "-"))?.scrollIntoView({ behavior: "smooth" }));
        }} />
        </div>
      </>}
    </main>
    <footer><span>{text.footer}</span><span>{text.footerTagline}</span></footer>
  </>;
}
