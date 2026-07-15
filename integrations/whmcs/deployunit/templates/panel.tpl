<div class="du-panel">
{literal}
<style>
.du-panel {
    position: relative;
    background:
        radial-gradient(900px 340px at 15% -10%, rgba(37, 99, 235, 0.22), transparent 60%),
        radial-gradient(650px 280px at 95% 0%, rgba(34, 211, 238, 0.10), transparent 55%),
        #070b16;
    border: 1px solid rgba(56, 189, 248, 0.18);
    border-radius: 18px;
    padding: 26px;
    color: #dbe4f3;
    font-size: 14px;
    overflow: hidden;
}
.du-panel::before {
    content: ""; position: absolute; inset: 0; pointer-events: none;
    background-image:
        linear-gradient(rgba(148, 163, 184, 0.045) 1px, transparent 1px),
        linear-gradient(90deg, rgba(148, 163, 184, 0.045) 1px, transparent 1px);
    background-size: 34px 34px;
    mask-image: linear-gradient(to bottom, rgba(0,0,0,.9), transparent 70%);
    -webkit-mask-image: linear-gradient(to bottom, rgba(0,0,0,.9), transparent 70%);
}
.du-panel > * { position: relative; }
.du-kicker {
    display: flex; align-items: center; gap: 10px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 10px; font-weight: 600; letter-spacing: 0.34em; text-transform: uppercase;
    color: #38bdf8; margin-bottom: 8px;
}
.du-kicker::before { content: ""; width: 26px; height: 1px; background: #38bdf8; }
.du-title { font-size: 24px; font-weight: 800; color: #fff; margin: 0 0 4px; letter-spacing: -0.02em; }
.du-sub { color: #8fa3bf; font-size: 13px; margin: 0 0 20px; }
.du-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin: 0 0 20px; }
.du-stat { background: rgba(13, 21, 38, 0.85); border: 1px solid rgba(148, 163, 184, 0.14); border-radius: 12px; padding: 13px 15px 11px; }
.du-stat b { display: block; font-size: 19px; font-weight: 800; color: #fff; }
.du-stat b small { color: #3d5273; font-size: 13px; font-weight: 700; }
.du-stat span {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 9.5px; letter-spacing: 0.22em; text-transform: uppercase; color: #8fa3bf;
}
.du-stat i { display: block; width: 26px; height: 2px; margin-top: 8px; border-radius: 2px; background: linear-gradient(90deg, #2563eb, #22d3ee); }
.du-cta {
    display: inline-block; padding: 14px 26px; border: none; border-radius: 12px; cursor: pointer;
    background: linear-gradient(135deg, #38bdf8, #22d3ee); color: #051120;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 12px; font-weight: 800; letter-spacing: 0.18em; text-transform: uppercase;
    box-shadow: 0 0 26px rgba(34, 211, 238, 0.3);
}
.du-cta:hover { background: linear-gradient(135deg, #5cc9f9, #4adcf1); color: #051120; }
.du-chip {
    display: inline-block; padding: 3px 11px; border-radius: 999px; margin-right: 6px;
    border: 1px solid rgba(56, 189, 248, 0.35); color: #a5e3fb; background: rgba(56, 189, 248, 0.06);
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 9.5px; font-weight: 600; letter-spacing: 0.16em; text-transform: uppercase;
}
.du-chip-bad { border-color: rgba(248, 113, 113, 0.4); color: #fca5a5; background: rgba(248, 113, 113, 0.06); }
.du-note { color: #8fa3bf; font-size: 12px; margin-top: 16px; }
.du-warn {
    border: 1px solid rgba(251, 191, 36, 0.35); background: rgba(251, 191, 36, 0.07);
    color: #fcd34d; border-radius: 10px; padding: 11px 15px; margin-bottom: 16px; font-size: 13px;
}
</style>
{/literal}

<div class="du-kicker">Servunit · DeployUnit</div>
<h2 class="du-title">DeployUnit</h2>
<p class="du-sub">
    {if $planName}<span class="du-chip">{$planName|escape} plan</span>{/if}
    {if !$isActive}<span class="du-chip du-chip-bad">suspended</span>{/if}
</p>

{if $apiError}
    <div class="du-warn">The DeployUnit dashboard is temporarily unreachable. Please try again in a few minutes.</div>
{else}
    <div class="du-stats">
        {if isset($usage.apps)}
            <div class="du-stat"><b>{$usage.apps}{if isset($limits.apps) && $limits.apps != -1}<small> / {$limits.apps}</small>{/if}</b><span>Applications</span><i></i></div>
        {/if}
        {if isset($usage.databases)}
            <div class="du-stat"><b>{$usage.databases}</b><span>Databases</span><i></i></div>
        {/if}
        {if isset($usage.domains)}
            <div class="du-stat"><b>{$usage.domains}{if isset($limits.domains) && $limits.domains != -1}<small> / {$limits.domains}</small>{/if}</b><span>Domains</span><i></i></div>
        {/if}
        <div class="du-stat"><b>{$credits}</b><span>Credits</span><i></i></div>
    </div>

    {if $isActive}
        <form method="post" action="clientarea.php?action=productdetails&amp;id={$serviceid}">
            <input type="hidden" name="modop" value="custom">
            <input type="hidden" name="a" value="openPanel">
            <button type="submit" class="du-cta">Open DeployUnit →</button>
        </form>
        <p class="du-note">Deployments, logs, domains, databases and monitoring all live in the DeployUnit dashboard — one click, no separate login.</p>
    {else}
        <div class="du-warn">This service is suspended. Check your unpaid invoices or contact support to restore access.</div>
    {/if}
{/if}
</div>
