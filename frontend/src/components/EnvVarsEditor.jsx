import { useEffect, useMemo, useState } from "react";
import { Eye, EyeOff, Plus, Trash2, FileUp, Save, Loader2 } from "lucide-react";
import { toast } from "sonner";

function Row({ idx, k, v, masked, onChange, onRemove, onToggleMask }) {
  return (
    <div className="grid grid-cols-12 gap-2 items-center" data-testid={`env-row-${idx}`}>
      <input
        value={k}
        onChange={(e) => onChange("k", e.target.value)}
        placeholder="KEY"
        className="col-span-4 bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
        data-testid={`env-key-${idx}`}
      />
      <div className="col-span-7 relative">
        <input
          value={v}
          onChange={(e) => onChange("v", e.target.value)}
          placeholder="value"
          type={masked ? "password" : "text"}
          className="w-full bg-black border border-white/10 pl-3 pr-9 py-2 text-sm font-mono focus:border-brand outline-none"
          data-testid={`env-value-${idx}`}
        />
        <button
          type="button"
          onClick={onToggleMask}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-brand"
          aria-label="Toggle visibility"
          data-testid={`env-mask-${idx}`}
        >
          {masked ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
        </button>
      </div>
      <button
        type="button"
        onClick={onRemove}
        className="col-span-1 inline-flex items-center justify-center text-zinc-500 hover:text-signal-failed"
        aria-label="Remove"
        data-testid={`env-remove-${idx}`}
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </div>
  );
}

export default function EnvVarsEditor({ envVars, onSave }) {
  const [rows, setRows] = useState(() => Object.entries(envVars || {}).map(([k, v]) => ({ k, v, masked: true })));
  const [pasting, setPasting] = useState(false);
  const [bulk, setBulk] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setRows(Object.entries(envVars || {}).map(([k, v]) => ({ k, v, masked: true })));
  }, [envVars]);

  const dirty = useMemo(() => {
    const out = {};
    for (const r of rows) {
      const key = (r.k || "").trim();
      if (!key) continue;
      out[key] = r.v;
    }
    const a = JSON.stringify(envVars || {});
    const b = JSON.stringify(out);
    return a !== b;
  }, [rows, envVars]);

  const update = (i, field, value) => {
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, [field === "k" ? "k" : "v"]: value } : r)));
  };

  const addRow = () => setRows((rs) => [...rs, { k: "", v: "", masked: false }]);
  const removeRow = (i) => setRows((rs) => rs.filter((_, idx) => idx !== i));
  const toggleMask = (i) => setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, masked: !r.masked } : r)));
  const toggleAllMasks = () => {
    const allMasked = rows.every((r) => r.masked);
    setRows((rs) => rs.map((r) => ({ ...r, masked: !allMasked })));
  };

  const parseBulk = () => {
    const next = [...rows];
    const seenIdx = (key) => next.findIndex((r) => r.k.trim() === key);
    let added = 0;
    bulk.split(/\r?\n/).forEach((line) => {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) return;
      const eq = trimmed.indexOf("=");
      if (eq <= 0) return;
      const key = trimmed.slice(0, eq).trim();
      let val = trimmed.slice(eq + 1).trim();
      if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
        val = val.slice(1, -1);
      }
      const i = seenIdx(key);
      if (i >= 0) next[i] = { ...next[i], v: val };
      else { next.push({ k: key, v: val, masked: true }); added += 1; }
    });
    setRows(next);
    setBulk("");
    setPasting(false);
    toast.success(`Imported ${added} new variables · ${next.length} total`);
  };

  const save = async () => {
    setSaving(true);
    const out = {};
    for (const r of rows) {
      const key = (r.k || "").trim();
      if (!key) continue;
      out[key] = r.v;
    }
    try {
      await onSave(out);
      toast.success(`Saved ${Object.keys(out).length} variables`);
    } catch (e) {
      toast.error("Save failed: " + (e?.response?.data?.detail || e.message));
    } finally { setSaving(false); }
  };

  return (
    <div className="space-y-3" data-testid="env-vars-editor">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="text-xs font-mono text-zinc-500">
          {rows.length} variable{rows.length === 1 ? "" : "s"}
          {dirty && <span className="ml-2 text-signal-queued">· unsaved changes</span>}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={toggleAllMasks} type="button" className="text-xs font-mono text-zinc-400 hover:text-brand inline-flex items-center gap-1" data-testid="env-toggle-all">
            <Eye className="h-3 w-3" /> {rows.every((r) => r.masked) ? "show" : "hide"} all
          </button>
          <button onClick={() => setPasting((p) => !p)} type="button" className="text-xs font-mono text-zinc-400 hover:text-brand inline-flex items-center gap-1" data-testid="env-toggle-bulk">
            <FileUp className="h-3 w-3" /> {pasting ? "cancel" : "paste .env"}
          </button>
        </div>
      </div>

      {pasting && (
        <div className="border border-white/10 p-3 space-y-2 bg-elevated/30">
          <textarea
            rows={6}
            value={bulk}
            onChange={(e) => setBulk(e.target.value)}
            placeholder={"# Paste your .env file here\nDATABASE_URL=postgres://...\nAPI_KEY=...\n"}
            className="w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
            data-testid="env-bulk-input"
          />
          <button onClick={parseBulk} type="button" className="px-3 py-1.5 bg-brand text-brand-fg text-sm font-medium hover:bg-brand/90" data-testid="env-bulk-parse">
            Parse & merge
          </button>
        </div>
      )}

      <div className="space-y-2">
        {rows.length === 0 ? (
          <div className="border border-dashed border-white/10 p-8 text-center text-sm text-zinc-500">
            No environment variables yet. Add one below.
          </div>
        ) : (
          rows.map((r, i) => (
            <Row
              key={i}
              idx={i}
              k={r.k}
              v={r.v}
              masked={r.masked}
              onChange={(field, value) => update(i, field, value)}
              onRemove={() => removeRow(i)}
              onToggleMask={() => toggleMask(i)}
            />
          ))
        )}
      </div>

      <div className="flex items-center gap-2">
        <button onClick={addRow} type="button" className="inline-flex items-center gap-2 px-3 py-2 border border-white/15 hover:border-brand hover:text-brand text-sm" data-testid="env-add-row">
          <Plus className="h-3.5 w-3.5" /> Add variable
        </button>
        <button
          onClick={save}
          type="button"
          disabled={!dirty || saving}
          className="inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90 disabled:opacity-50"
          data-testid="env-save"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save & sync
        </button>
      </div>
    </div>
  );
}
