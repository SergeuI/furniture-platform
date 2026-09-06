export default function CatalogBreadcrumbTrail({
  ariaLabel = "",
  className = "",
  items = [],
}) {
  const trailClassName = [
    "fitting-category-breadcrumb",
    "fitting-category-breadcrumb-top",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <nav aria-label={ariaLabel || undefined} className={trailClassName}>
      {items.map((item, index) => {
        const isLast = index === items.length - 1;
        const isCurrent = Boolean(item?.current);
        const label = String(item?.label || "").trim();
        const title = String(item?.title || label || "").trim();

        return (
          <span className="fitting-category-breadcrumb-item" key={`${label || "crumb"}-${index}`}>
            <h3 className="catalog-breadcrumb-title">
              {isCurrent || !item?.onClick ? (
                <span aria-current={isCurrent ? "page" : undefined} title={title || label}>
                  {label}
                </span>
              ) : (
                <button className="catalog-breadcrumb-link" onClick={item.onClick} title={title || label} type="button">
                  {label}
                </button>
              )}
            </h3>
            {!isLast ? (
              <span aria-hidden="true" className="fitting-breadcrumb-separator">
                /
              </span>
            ) : null}
          </span>
        );
      })}
    </nav>
  );
}
