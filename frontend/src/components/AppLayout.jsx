import { useNavigate } from "react-router-dom";

/**
 * Struttura comune delle aree protette: barra superiore con logout, indice delle sezioni
 * a sinistra e una sezione vuota per ogni voce di `sections` ({ id, label }).
 */
export default function AppLayout({ title, sections }) {
  const navigate = useNavigate();

  return (
    <div className="shell">
      <header className="topbar">
        <span className="brand">RPM</span>
        <span className="topbar-title">{title}</span>
      <button type="button" className="btn btn-quiet" onClick={() => navigate("/login")}>
        Sign out
      </button>
      </header>
      <nav className="sidebar" aria-label="Sections">
        {sections.map((section) => (
          <a key={section.id} href={`#${section.id}`}>{section.label}</a>
        ))}
      </nav>
      <main className="content">
        {sections.map((section) => (
          <section key={section.id} id={section.id} className="panel" aria-labelledby={`${section.id}-title`}>
            <h2 id={`${section.id}-title`}>{section.label}</h2>
          </section>
        ))}
      </main>
    </div>
  );
}