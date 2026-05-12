import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Ticket, Plus, ArrowLeft, MessageSquare, Send, Loader2, Check, AlertCircle,
  CheckCircle2, Clock, X, Filter,
} from "lucide-react";
import { toast } from "sonner";
import { api, getApiErrorMessage } from "../../lib/api";
import { useAuth } from "../../contexts/AuthContext";

const STATUS_META = {
  open:              { label: "Open",              cls: "text-cyan-400 border-cyan-500/30 bg-cyan-500/5" },
  awaiting_support:  { label: "Awaiting support",  cls: "text-yellow-400 border-yellow-500/30 bg-yellow-500/5" },
  awaiting_user:     { label: "Awaiting you",      cls: "text-fuchsia-400 border-fuchsia-500/30 bg-fuchsia-500/5" },
  resolved:          { label: "Resolved",          cls: "text-emerald-400 border-emerald-500/30 bg-emerald-500/5" },
  closed:            { label: "Closed",            cls: "text-zinc-500 border-zinc-700 bg-zinc-900/40" },
};
const PRIORITY_META = {
  low:    { label: "Low",    cls: "text-zinc-500" },
  normal: { label: "Normal", cls: "text-zinc-300" },
  high:   { label: "High",   cls: "text-yellow-400" },
  urgent: { label: "Urgent", cls: "text-red-400" },
};
const CATEGORIES = [
  { id: "deploy",          label: "Deploy" },
  { id: "billing",         label: "Billing" },
  { id: "account",         label: "Account" },
  { id: "technical",       label: "Technical" },
  { id: "feature_request", label: "Feature request" },
  { id: "other",           label: "Other" },
];

export function StatusPill({ s }) {
  const m = STATUS_META[s] || STATUS_META.open;
  return <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-mono uppercase tracking-[0.25em] border ${m.cls}`} data-testid={`ticket-status-${s}`}>{m.label}</span>;
}

function PriorityTag({ p }) {
  const m = PRIORITY_META[p] || PRIORITY_META.normal;
  return <span className={`text-[10px] font-mono uppercase tracking-[0.25em] ${m.cls}`}>{m.label}</span>;
}

function timeago(iso) {
  if (!iso) return "—";
  const ms = Date.now() - new Date(iso).getTime();
  const min = Math.round(ms / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const h = Math.round(min / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

/* ─────────────────────── List view ─────────────────────── */
function TicketsList({ onOpen, onNew, tickets, loading }) {
  return (
    <div data-testid="tickets-list">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-display text-3xl font-bold tracking-tight">Support tickets</h1>
          <p className="text-sm text-zinc-400 mt-1">Open a ticket — we typically reply within one business day.</p>
        </div>
        <button
          onClick={onNew}
          className="inline-flex items-center gap-2 bg-cyan-500 hover:bg-cyan-400 text-black font-semibold px-4 py-2 transition-colors"
          data-testid="ticket-new-btn"
        >
          <Plus className="h-4 w-4" /> New ticket
        </button>
      </div>

      {loading ? (
        <div className="p-10 text-center text-zinc-500"><Loader2 className="h-5 w-5 animate-spin mx-auto" /></div>
      ) : tickets.length === 0 ? (
        <div className="border border-dashed border-zinc-800 p-10 text-center" data-testid="tickets-empty">
          <Ticket className="h-8 w-8 text-zinc-600 mx-auto mb-3" />
          <div className="font-display text-lg">No tickets yet</div>
          <div className="text-sm text-zinc-500 mt-1 mb-5">Need a hand? Start one below.</div>
          <button onClick={onNew} className="inline-flex items-center gap-2 bg-cyan-500 hover:bg-cyan-400 text-black font-semibold px-4 py-2">
            <Plus className="h-4 w-4" /> Open your first ticket
          </button>
        </div>
      ) : (
        <div className="border border-zinc-800 divide-y divide-zinc-900">
          {tickets.map((t) => (
            <button
              key={t.id}
              onClick={() => onOpen(t.id)}
              className="w-full text-left p-4 hover:bg-zinc-950/60 transition-colors grid grid-cols-[1fr_auto] gap-4 items-center"
              data-testid={`ticket-row-${t.id}`}
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <StatusPill s={t.status} />
                  <span className="text-[10px] font-mono uppercase tracking-[0.25em] text-zinc-500">{t.category}</span>
                  <PriorityTag p={t.priority} />
                </div>
                <div className="mt-1.5 font-display text-base font-semibold truncate">{t.subject}</div>
                <div className="text-xs text-zinc-500 mt-0.5">
                  {t.message_count} message{t.message_count !== 1 ? "s" : ""} · last update {timeago(t.last_msg_at)}
                </div>
              </div>
              <div className="text-xs font-mono text-zinc-500 text-right shrink-0">
                #{t.id.slice(0, 8)}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─────────────────────── New ticket form ─────────────────────── */
function NewTicket({ onCancel, onCreated }) {
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [category, setCategory] = useState("other");
  const [priority, setPriority] = useState("normal");
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    if (!subject.trim() || message.trim().length < 10) {
      toast.error("Subject + at least 10 chars of description required.");
      return;
    }
    setBusy(true);
    try {
      const r = await api.post("/tickets", { subject, message, category, priority });
      toast.success("Ticket opened — we're on it.");
      onCreated(r.data);
    } catch (err) { toast.error(getApiErrorMessage(err)); }
    finally { setBusy(false); }
  };
  return (
    <form onSubmit={submit} className="space-y-4" data-testid="ticket-new-form">
      <div className="flex items-center justify-between mb-4">
        <button type="button" onClick={onCancel} className="inline-flex items-center gap-2 text-xs font-mono text-zinc-400 hover:text-cyan-400">
          <ArrowLeft className="h-3.5 w-3.5" /> back
        </button>
      </div>
      <h2 className="font-display text-2xl font-bold tracking-tight">Open a new ticket</h2>
      <div>
        <label className="text-[10px] uppercase tracking-[0.35em] font-mono text-zinc-500 block mb-1.5">Subject</label>
        <input
          type="text" value={subject} onChange={(e) => setSubject(e.target.value)}
          placeholder="Brief one-liner"
          className="w-full bg-zinc-950 border border-zinc-800 focus:border-cyan-500 outline-none px-3 py-2 text-sm"
          data-testid="ticket-new-subject"
        />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="text-[10px] uppercase tracking-[0.35em] font-mono text-zinc-500 block mb-1.5">Category</label>
          <select value={category} onChange={(e) => setCategory(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-800 focus:border-cyan-500 outline-none px-3 py-2 text-sm"
            data-testid="ticket-new-category"
          >
            {CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
          </select>
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-[0.35em] font-mono text-zinc-500 block mb-1.5">Priority</label>
          <select value={priority} onChange={(e) => setPriority(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-800 focus:border-cyan-500 outline-none px-3 py-2 text-sm"
            data-testid="ticket-new-priority"
          >
            {Object.entries(PRIORITY_META).map(([id, m]) => <option key={id} value={id}>{m.label}</option>)}
          </select>
        </div>
      </div>
      <div>
        <label className="text-[10px] uppercase tracking-[0.35em] font-mono text-zinc-500 block mb-1.5">Describe the issue</label>
        <textarea
          rows={8} value={message} onChange={(e) => setMessage(e.target.value)}
          placeholder="What were you trying to do? What did you expect? What did you see?"
          className="w-full bg-zinc-950 border border-zinc-800 focus:border-cyan-500 outline-none px-3 py-2 text-sm leading-relaxed"
          data-testid="ticket-new-message"
        />
      </div>
      <button
        type="submit" disabled={busy}
        className="inline-flex items-center gap-2 bg-cyan-500 hover:bg-cyan-400 text-black font-semibold px-5 py-2.5 transition-colors disabled:opacity-60"
        data-testid="ticket-new-submit"
      >
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        Open ticket
      </button>
    </form>
  );
}

/* ─────────────────────── Thread view ─────────────────────── */
export function TicketThread({ ticketId, isAdmin = false, onBack, basePath }) {
  const [data, setData] = useState(null);
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [editingMeta, setEditingMeta] = useState(false);
  const [meta, setMeta] = useState({ status: "", priority: "" });
  const scrollRef = useRef(null);

  const reload = async () => {
    try {
      const r = isAdmin
        ? await api.get(`/admin/tickets/${ticketId}`)
        : await api.get(`/tickets/${ticketId}`);
      setData(r.data);
      setMeta({ status: r.data.ticket.status, priority: r.data.ticket.priority });
    } catch (e) { toast.error(getApiErrorMessage(e)); }
  };
  useEffect(() => { reload(); /* eslint-disable-next-line */ }, [ticketId]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [data?.messages?.length]);

  const send = async (e) => {
    e?.preventDefault();
    if (!reply.trim()) return;
    setBusy(true);
    try {
      const url = isAdmin ? `/admin/tickets/${ticketId}/messages` : `/tickets/${ticketId}/messages`;
      await api.post(url, { body: reply });
      setReply("");
      await reload();
    } catch (err) { toast.error(getApiErrorMessage(err)); }
    finally { setBusy(false); }
  };

  const closeTicket = async () => {
    if (!window.confirm("Close this ticket? You can always open a new one.")) return;
    try {
      await api.post(`/tickets/${ticketId}/close`);
      toast.success("Ticket closed.");
      reload();
    } catch (e) { toast.error(getApiErrorMessage(e)); }
  };

  const saveMeta = async () => {
    try {
      await api.patch(`/admin/tickets/${ticketId}`, meta);
      toast.success("Updated.");
      setEditingMeta(false);
      reload();
    } catch (e) { toast.error(getApiErrorMessage(e)); }
  };

  if (!data) return <div className="p-10 text-center text-zinc-500"><Loader2 className="h-5 w-5 animate-spin mx-auto" /></div>;

  const { ticket, messages } = data;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6" data-testid="ticket-thread">
      <div>
        <button onClick={onBack} className="inline-flex items-center gap-2 text-xs font-mono text-zinc-400 hover:text-cyan-400 mb-4" data-testid="ticket-back">
          <ArrowLeft className="h-3.5 w-3.5" /> back to tickets
        </button>

        <div className="border border-zinc-800 bg-zinc-950/30 p-5 mb-4">
          <div className="flex items-center gap-2 flex-wrap mb-2">
            <StatusPill s={ticket.status} />
            <span className="text-[10px] font-mono uppercase tracking-[0.25em] text-zinc-500">{ticket.category}</span>
            <PriorityTag p={ticket.priority} />
            <span className="ml-auto text-[10px] font-mono text-zinc-600">#{ticket.id.slice(0, 8)}</span>
          </div>
          <div className="font-display text-xl font-bold">{ticket.subject}</div>
          {isAdmin && (
            <div className="mt-2 text-[11px] font-mono text-zinc-500">
              {ticket.user_name} · {ticket.user_email}
            </div>
          )}
        </div>

        <div ref={scrollRef} className="space-y-3 max-h-[55vh] overflow-y-auto pr-1" data-testid="ticket-messages">
          {messages.map((m) => {
            const isSupport = m.author_role === "admin";
            return (
              <motion.div
                key={m.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className={`border p-4 ${isSupport ? "border-cyan-500/30 bg-cyan-500/[0.04]" : "border-zinc-800 bg-zinc-950/40"}`}
                data-testid={`ticket-msg-${m.id}`}
              >
                <div className="flex items-center justify-between gap-3 mb-2 text-[11px] font-mono">
                  <span className={isSupport ? "text-cyan-400" : "text-zinc-300"}>
                    {isSupport ? "★ Support" : m.author_name}
                  </span>
                  <span className="text-zinc-600">{new Date(m.created_at).toLocaleString()}</span>
                </div>
                <div className="text-sm text-zinc-200 whitespace-pre-wrap leading-relaxed">{m.body}</div>
              </motion.div>
            );
          })}
        </div>

        {ticket.status !== "closed" ? (
          <form onSubmit={send} className="mt-4 border border-zinc-800 bg-zinc-950/30 p-3" data-testid="ticket-reply-form">
            <textarea
              value={reply} onChange={(e) => setReply(e.target.value)}
              placeholder={isAdmin ? "Reply as support…" : "Reply to support…"}
              rows={3}
              className="w-full bg-transparent outline-none text-sm leading-relaxed resize-none"
              data-testid="ticket-reply-body"
            />
            <div className="flex items-center justify-between mt-2 pt-2 border-t border-zinc-900">
              {!isAdmin ? (
                <button type="button" onClick={closeTicket} className="text-[11px] font-mono text-zinc-500 hover:text-red-400 inline-flex items-center gap-1" data-testid="ticket-close">
                  <X className="h-3 w-3" /> close ticket
                </button>
              ) : <span />}
              <button
                type="submit" disabled={busy || !reply.trim()}
                className="inline-flex items-center gap-2 bg-cyan-500 hover:bg-cyan-400 text-black text-xs font-semibold px-4 py-1.5 disabled:opacity-50"
                data-testid="ticket-reply-send"
              >
                {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                Send
              </button>
            </div>
          </form>
        ) : (
          <div className="mt-4 border border-zinc-800 bg-zinc-950/30 p-4 text-center text-xs font-mono text-zinc-500">
            This ticket is closed. Open a new one if you need more help.
          </div>
        )}
      </div>

      {/* Sidebar */}
      <aside className="space-y-3">
        <div className="border border-zinc-800 bg-zinc-950/30 p-4">
          <div className="text-[10px] uppercase tracking-[0.35em] font-mono text-zinc-500 mb-2">Details</div>
          <dl className="space-y-2 text-xs font-mono">
            <div className="flex justify-between"><dt className="text-zinc-500">Opened</dt><dd className="text-zinc-300">{new Date(ticket.created_at).toLocaleString()}</dd></div>
            <div className="flex justify-between"><dt className="text-zinc-500">Last update</dt><dd className="text-zinc-300">{timeago(ticket.last_msg_at)}</dd></div>
            <div className="flex justify-between"><dt className="text-zinc-500">Messages</dt><dd className="text-zinc-300">{ticket.message_count}</dd></div>
          </dl>
        </div>

        {isAdmin && (
          <div className="border border-zinc-800 bg-zinc-950/30 p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="text-[10px] uppercase tracking-[0.35em] font-mono text-zinc-500">Manage</div>
              {!editingMeta ? (
                <button onClick={() => setEditingMeta(true)} className="text-[10px] font-mono text-cyan-400 hover:underline" data-testid="ticket-admin-edit">edit</button>
              ) : (
                <div className="flex gap-1.5">
                  <button onClick={() => setEditingMeta(false)} className="text-[10px] font-mono text-zinc-500 hover:text-zinc-300">cancel</button>
                  <button onClick={saveMeta} className="text-[10px] font-mono text-cyan-400 hover:underline" data-testid="ticket-admin-save">save</button>
                </div>
              )}
            </div>
            {editingMeta ? (
              <div className="space-y-2">
                <select value={meta.status} onChange={(e) => setMeta((m) => ({ ...m, status: e.target.value }))}
                  className="w-full bg-zinc-950 border border-zinc-800 text-xs font-mono px-2 py-1.5"
                  data-testid="ticket-admin-status"
                >
                  {Object.entries(STATUS_META).map(([id, m]) => <option key={id} value={id}>{m.label}</option>)}
                </select>
                <select value={meta.priority} onChange={(e) => setMeta((m) => ({ ...m, priority: e.target.value }))}
                  className="w-full bg-zinc-950 border border-zinc-800 text-xs font-mono px-2 py-1.5"
                  data-testid="ticket-admin-priority"
                >
                  {Object.entries(PRIORITY_META).map(([id, m]) => <option key={id} value={id}>{m.label}</option>)}
                </select>
              </div>
            ) : (
              <dl className="space-y-2 text-xs font-mono">
                <div className="flex justify-between"><dt className="text-zinc-500">Status</dt><dd><StatusPill s={ticket.status} /></dd></div>
                <div className="flex justify-between items-center"><dt className="text-zinc-500">Priority</dt><dd><PriorityTag p={ticket.priority} /></dd></div>
              </dl>
            )}
          </div>
        )}
      </aside>
    </div>
  );
}

/* ─────────────────────── User page ─────────────────────── */
export default function Tickets() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/tickets");
      setTickets(r.data.tickets || []);
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setLoading(false); }
  };
  // Re-fetch the list whenever we land on /app/tickets (id undefined),
  // including returning from /app/tickets/:id via the in-page back button.
  useEffect(() => { if (!id) load(); }, [id]);

  if (id) {
    return (
      <div className="px-4 py-6 sm:p-8 max-w-5xl">
        <TicketThread ticketId={id} onBack={() => navigate("/app/tickets")} />
      </div>
    );
  }

  if (creating) {
    return (
      <div className="px-4 py-6 sm:p-8 max-w-3xl">
        <NewTicket
          onCancel={() => setCreating(false)}
          onCreated={(t) => { setCreating(false); navigate(`/app/tickets/${t.id}`); }}
        />
      </div>
    );
  }

  return (
    <div className="px-4 py-6 sm:p-8 max-w-5xl">
      <TicketsList
        tickets={tickets}
        loading={loading}
        onOpen={(tid) => navigate(`/app/tickets/${tid}`)}
        onNew={() => setCreating(true)}
      />
    </div>
  );
}
