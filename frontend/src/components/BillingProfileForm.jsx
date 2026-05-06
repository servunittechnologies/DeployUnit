import { useEffect, useState } from "react";
import { api, getApiErrorMessage } from "../lib/api";
import { Loader2, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

/** Inline billing-profile form. onSaved(profile) fires after the profile is persisted + VAT validated. */
export default function BillingProfileForm({
  workspaceId,
  initial,
  onSaved,
  submitLabel = "Save & continue",
  disabled = false,
}) {
  const [countries, setCountries] = useState([]);
  const [form, setForm] = useState({
    company_name: "",
    address: "",
    postal_code: "",
    city: "",
    country: "NL",
    email: "",
    is_business: false,
    vat_id: "",
  });
  const [vatCheck, setVatCheck] = useState(null);
  const [checking, setChecking] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/billing/countries").then((r) => setCountries(r.data));
  }, []);

  useEffect(() => {
    if (initial) {
      setForm((f) => ({ ...f, ...initial }));
    }
  }, [initial]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const verifyVat = async () => {
    if (!form.vat_id) return;
    setChecking(true);
    try {
      const { data } = await api.get("/billing/vat/validate", { params: { vat_id: form.vat_id } });
      setVatCheck(data);
      if (data.valid) toast.success(`VAT ID valid · ${data.name || "confirmed by VIES"}`);
      else toast.error(data.error === "format" ? "Malformed VAT ID" : "VAT ID is invalid");
    } catch (e) {
      toast.error(getApiErrorMessage(e));
    } finally { setChecking(false); }
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!workspaceId) return;
    setError("");
    setSaving(true);
    try {
      const payload = { ...form };
      if (!payload.is_business) payload.vat_id = null;
      const { data } = await api.put(`/billing/profile?workspace_id=${workspaceId}`, payload);
      toast.success(`Profile saved · ${data.vat_note}`);
      onSaved?.(data);
    } catch (err) {
      const msg = getApiErrorMessage(err);
      setError(msg);
      toast.error(msg);
    } finally { setSaving(false); }
  };

  return (
    <form onSubmit={submit} className="space-y-4" data-testid="billing-profile-form">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="md:col-span-2">
          <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Company / individual</label>
          <input required value={form.company_name} onChange={(e) => set("company_name", e.target.value)}
            className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
            placeholder="Acme B.V."
            data-testid="profile-company-input"
          />
        </div>
        <div className="md:col-span-2">
          <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Address</label>
          <input required value={form.address} onChange={(e) => set("address", e.target.value)}
            className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
            placeholder="Keizersgracht 123"
            data-testid="profile-address-input"
          />
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Postal code</label>
          <input required value={form.postal_code} onChange={(e) => set("postal_code", e.target.value)}
            className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
            placeholder="1015CJ"
            data-testid="profile-postal-input"
          />
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">City</label>
          <input required value={form.city} onChange={(e) => set("city", e.target.value)}
            className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
            placeholder="Amsterdam"
            data-testid="profile-city-input"
          />
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Country</label>
          <select required value={form.country} onChange={(e) => set("country", e.target.value)}
            className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
            data-testid="profile-country-select"
          >
            {countries.map((c) => (
              <option key={c.code} value={c.code}>
                {c.name} {c.eu ? `· ${c.vat_rate}% VAT` : "· Non-EU"}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Billing email</label>
          <input type="email" required value={form.email} onChange={(e) => set("email", e.target.value)}
            className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
            placeholder="billing@acme.com"
            data-testid="profile-email-input"
          />
        </div>
      </div>

      <div className="p-3 border border-white/10 bg-elevated/30 space-y-3">
        <label className="inline-flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" checked={form.is_business} onChange={(e) => set("is_business", e.target.checked)} data-testid="profile-is-business" />
          I'm a business and can provide a valid EU VAT ID (eligible for reverse charge)
        </label>
        {form.is_business && (
          <div className="flex gap-2">
            <input value={form.vat_id || ""} onChange={(e) => set("vat_id", e.target.value)}
              placeholder="NL123456789B01"
              className="flex-1 bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
              data-testid="profile-vat-input"
            />
            <button type="button" onClick={verifyVat} disabled={checking || !form.vat_id}
              className="px-3 py-2 border border-white/15 hover:border-brand text-xs font-mono uppercase tracking-wider disabled:opacity-50"
              data-testid="profile-vat-verify"
            >
              {checking ? <Loader2 className="h-3 w-3 animate-spin" /> : "Verify with VIES"}
            </button>
          </div>
        )}
        {vatCheck && (
          <div className={`text-xs font-mono ${vatCheck.valid ? "text-signal-live" : "text-signal-failed"}`}>
            {vatCheck.valid ? (
              <span className="inline-flex items-center gap-1"><CheckCircle2 className="h-3 w-3" /> Valid · {vatCheck.name || "confirmed"}</span>
            ) : (
              <span>Invalid · {vatCheck.error || "not recognised by VIES"}</span>
            )}
          </div>
        )}
      </div>

      {error && <div className="text-signal-failed text-sm">{error}</div>}

      <button type="submit" disabled={saving || disabled}
        className="inline-flex items-center gap-2 px-5 py-2.5 bg-brand text-brand-fg font-medium hover:bg-brand/90 active:scale-95 transition disabled:opacity-50 shadow-[0_0_20px_rgba(0,229,255,0.25)]"
        data-testid="profile-submit"
      >
        {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : submitLabel}
      </button>
    </form>
  );
}
