export default function FittingHolesWorkspace({ children, className = "" }) {
  return <div className={`holes-grid${className ? ` ${className}` : ""}`.trim()}>{children}</div>;
}
