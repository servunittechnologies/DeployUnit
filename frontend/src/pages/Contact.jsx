import { useState } from "react";
import { motion } from "framer-motion";
import {
  Mail, MapPin, Phone, MessageSquare, Building2, Send, Loader2, Check,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";
import MarketingLayout from "../components/MarketingLayout";

function Section({ className = "", children }) {
  return <section className={`max-w-5xl mx-auto px-6 lg:px-8 ${className}`}>{children}</section>;
}

function Overline({ children }) {
  return (
    <div className="inline-flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.4em] text-cyan-400">
      <span className="h-px w-6 bg-cyan-500/60" />
      {children}
    </div>
  );
}

const KINDS = [
  { id: "general",     label: "General",     hint: "Just say hi" },
  { id: "sales",       label: "Sales",       hint: "Pricing / agency plan" },
  { id: "support",     label: "Support",     hint: "Existing customer issue" },
  { id: "partnership", label: "Partnership", hint: "Become a partner" },
  { id: "press",       label: "Press",       hint: "Media or interview" },
];

const CONTACT = [
  { icon: Mail,     label: "Email",   value: "hello@deployhub.app", href: "mailto:hello@deployhub.app" },
  { icon: Building2,label: "Office",  value: "ServUnit Technologies BV · Belgium", href: null },
  { icon: MapPin,   label: "Region",  value: "EU datacenters (eu-west · eu-central · eu-north)", href: null },
  { icon: Phone,    label: "Phone",   value: "+32 (0)9 396 39 79 · Mon-Fri 9-17 CET", href: "tel:+3293963979" },
];

export default function Contact() {
  const [form, setForm] = useState({
    name: "", email: "", company: "", kind: "general", subject: "", message: "",
  });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name || !form.email || !form.subject || form.message.length < 10) {
      toast.error("Please fill in name, email, subject and a message (≥10 chars).");
      return;
    }
    setBusy(true);
    try {
      await api.post("/contact", form);
      setDone(true);
      toast.success("Got it — we'll reply within one business day.");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Something went wrong.");
    } finally { setBusy(false); }
  };

  return (
    <MarketingLayout>
      <Section className="pt-24 lg:pt-32 pb-16">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <Overline>Get in touch</Overline>
          <h1 className="mt-4 font-display text-4xl md:text-6xl font-bold tracking-tighter leading-[0.95]">
            Talk to a human. <span className="text-cyan-400">Quickly.</span>
          </h1>
          <p className="mt-6 text-base sm:text-lg text-zinc-400 max-w-2xl leading-relaxed">
            Reach out about a sales question, a support ticket, a partnership idea, or just say hi.
            Most messages get an answer within one business day — no contact-form ghosts here.
          </p>
        </motion.div>
      </Section>

      <Section className="pb-20">
        <div className="grid lg:grid-cols-[1fr_1.3fr] gap-6">
          {/* Contact details */}
          <motion.div initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5 }} className="space-y-3">
            {CONTACT.map((c) => (
              <div
                key={c.label}
                className="border border-zinc-800 bg-zinc-950/40 p-5 flex items-start gap-4 hover:border-cyan-500/40 transition-colors"
                data-testid={`contact-info-${c.label.toLowerCase()}`}
              >
                <div className="p-2 border border-zinc-800 bg-black">
                  <c.icon className="h-4 w-4 text-cyan-400" />
                </div>
                <div className="min-w-0">
                  <div className="text-[10px] uppercase tracking-[0.35em] font-mono text-zinc-500 mb-1">{c.label}</div>
                  {c.href ? (
                    <a href={c.href} className="text-zinc-200 hover:text-cyan-400 transition-colors break-words">{c.value}</a>
                  ) : (
                    <div className="text-zinc-200 break-words">{c.value}</div>
                  )}
                </div>
              </div>
            ))}
            <div className="border border-emerald-500/30 bg-emerald-950/10 p-5">
              <div className="text-[10px] uppercase tracking-[0.35em] font-mono text-emerald-400 mb-2">Response time</div>
              <p className="text-sm text-zinc-300">
                Sales & general: <span className="text-emerald-400 font-mono">~4h</span> · Support tickets: <span className="text-emerald-400 font-mono">≤24h</span> on business days.
              </p>
            </div>
          </motion.div>

          {/* Form */}
          <motion.form
            onSubmit={submit}
            initial={{ opacity: 0, x: 12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5 }}
            className="border border-zinc-800 bg-zinc-950/40 p-6 lg:p-8"
            data-testid="contact-form"
          >
            {done ? (
              <div className="text-center py-10" data-testid="contact-done">
                <div className="inline-flex h-12 w-12 items-center justify-center border border-emerald-500/40 bg-emerald-950/40 mb-4">
                  <Check className="h-6 w-6 text-emerald-400" />
                </div>
                <div className="font-display text-2xl font-bold text-white">Message received</div>
                <p className="mt-2 text-sm text-zinc-400 max-w-md mx-auto">
                  We'll reply to <span className="text-cyan-400">{form.email}</span> within one business day. Talk soon.
                </p>
              </div>
            ) : (
              <>
                <div className="mb-5">
                  <div className="text-[10px] uppercase tracking-[0.35em] font-mono text-zinc-500 mb-2">Kind</div>
                  <div className="flex flex-wrap gap-2">
                    {KINDS.map((k) => (
                      <button
                        key={k.id}
                        type="button"
                        onClick={() => set("kind", k.id)}
                        className={`px-3 py-1.5 text-xs font-mono border transition-colors ${
                          form.kind === k.id ? "border-cyan-400 text-cyan-400 bg-cyan-500/10" : "border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200"
                        }`}
                        data-testid={`contact-kind-${k.id}`}
                      >
                        {k.label}
                      </button>
                    ))}
                  </div>
                  <div className="mt-1.5 text-[10px] font-mono text-zinc-500">
                    {KINDS.find((k) => k.id === form.kind)?.hint}
                  </div>
                </div>

                <div className="grid sm:grid-cols-2 gap-3 mb-3">
                  <Field label="Name" value={form.name} onChange={(v) => set("name", v)} testId="contact-name" />
                  <Field label="Email" type="email" value={form.email} onChange={(v) => set("email", v)} testId="contact-email" />
                </div>
                <Field label="Company (optional)" value={form.company} onChange={(v) => set("company", v)} testId="contact-company" />
                <Field label="Subject" value={form.subject} onChange={(v) => set("subject", v)} testId="contact-subject" />
                <div className="mb-3">
                  <label className="text-[10px] uppercase tracking-[0.35em] font-mono text-zinc-500 mb-1.5 block">Message</label>
                  <textarea
                    rows={5}
                    value={form.message}
                    onChange={(e) => set("message", e.target.value)}
                    placeholder="Tell us what's on your mind…"
                    className="w-full bg-black/40 border border-zinc-800 focus:border-cyan-500 outline-none px-3 py-2 text-sm text-zinc-200 leading-relaxed resize-none"
                    data-testid="contact-message"
                  />
                </div>
                <button
                  type="submit"
                  disabled={busy}
                  className="group inline-flex items-center gap-2 bg-cyan-500 hover:bg-cyan-400 text-black font-semibold px-5 py-2.5 transition-colors disabled:opacity-60"
                  data-testid="contact-submit"
                >
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                  Send message
                </button>
                <p className="mt-3 text-[10px] font-mono text-zinc-600">
                  By submitting, you agree to our privacy policy. We never share your email.
                </p>
              </>
            )}
          </motion.form>
        </div>
      </Section>
    </MarketingLayout>
  );
}

function Field({ label, value, onChange, type = "text", testId }) {
  return (
    <div className="mb-3">
      <label className="text-[10px] uppercase tracking-[0.35em] font-mono text-zinc-500 mb-1.5 block">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-black/40 border border-zinc-800 focus:border-cyan-500 outline-none px-3 py-2 text-sm text-zinc-200"
        data-testid={testId}
      />
    </div>
  );
}
