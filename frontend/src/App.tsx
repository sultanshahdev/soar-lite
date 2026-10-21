const sections = ["Dashboard", "Alerts", "Incidents", "Playbooks", "Audit Log"];

export default function App() {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto grid min-h-screen max-w-7xl grid-cols-[14rem_1fr]">
        <aside className="border-r border-slate-800 bg-slate-900/50 p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-400">Security operations</p>
          <h1 className="mt-3 text-2xl font-semibold">SOAR Lite</h1>
          <nav className="mt-10 space-y-1">{sections.map((section, index) => <a className={index === 0 ? "block rounded-md bg-slate-800 px-3 py-2 text-sm" : "block rounded-md px-3 py-2 text-sm text-slate-400"} href="#workspace" key={section}>{section}</a>)}</nav>
        </aside>
        <section id="workspace" className="p-8 sm:p-12">
          <p className="text-sm text-slate-400">Local-first incident response workspace</p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight">Dashboard</h2>
          <div className="mt-8 rounded-xl border border-slate-800 bg-slate-900 p-8 shadow-2xl shadow-black/20">
            <p className="text-sm font-medium text-cyan-300">Foundation initialized</p>
            <p className="mt-3 max-w-xl text-slate-400">Alert handling, investigations, approvals, playbooks, and audit trails are not yet implemented.</p>
          </div>
        </section>
      </div>
    </main>
  );
}
