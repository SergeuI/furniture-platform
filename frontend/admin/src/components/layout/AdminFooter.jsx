import "./AdminFooter.css";

export default function AdminFooter({ language = "uk" }) {
  const isUk = language === "uk";

  return (
    <footer className="admin-footer" aria-label={isUk ? "Нижня частина адмінпанелі" : "Admin footer"}>
      <div className="admin-footer-inner">
        <div className="admin-footer-brand">
          <strong>MP Furniture</strong>
          <span>{isUk ? "Адмінпанель меблевої платформи" : "Furniture platform admin"}</span>
        </div>
        <div className="admin-footer-meta">
          <span>{isUk ? "Робоче середовище" : "Workspace"}</span>
          <span>© 2026 MP Furniture</span>
        </div>
      </div>
    </footer>
  );
}
