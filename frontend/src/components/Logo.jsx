export default function Logo({ className = "", small = false }) {
  return (
    <div className={`flex items-center gap-2 ${className}`} data-testid="logo">
      <div className={`relative ${small ? "h-7 w-7" : "h-9 w-9"} bg-brand text-brand-fg font-display font-bold flex items-center justify-center`}>
        <span className="absolute inset-0 bg-brand opacity-30 blur-md" aria-hidden />
        <span className="relative">/</span>
      </div>
      <span className={`font-display font-semibold tracking-tight ${small ? "text-base" : "text-lg"}`}>
        deploy<span className="text-brand">hub</span>
      </span>
    </div>
  );
}
