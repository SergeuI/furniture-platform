import CatalogBreadcrumbTrail from "../CatalogBreadcrumbTrail.jsx";

export default function ReferenceBreadcrumbBar({ items = [] }) {
  return (
    <div className="reference-breadcrumb-bar">
      <CatalogBreadcrumbTrail className="mounting-node-workspace-breadcrumbs" items={items} />
    </div>
  );
}
