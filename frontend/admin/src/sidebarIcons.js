import { createElement, useEffect, useState } from "react";

function iconUrl(filename) {
  return new URL(`./assets/sidebar-icons/mpfc_sidebar_icons/mpfc_sidebar_icons/${filename}`, import.meta.url).href;
}

export const SIDEBAR_NAV_ICON_ASSETS = {
  home: iconUrl("home.png"),
  projects: iconUrl("projects.png"),
  createProject: iconUrl("create_project.png"),
  users: iconUrl("users.png"),
  audit: iconUrl("audit.png"),
  entitlements: iconUrl("tariffs_rights.png"),
  processing: iconUrl("processing_operations.png"),
  connections: iconUrl("fastening_schemes.png"),
  catalog: iconUrl("values_guide.png"),
  settings: iconUrl("settings.png"),
};

export const SIDEBAR_CONTROL_ICON_ASSETS = {
  collapse: iconUrl("sidebar_collapse.png"),
  expand: iconUrl("sidebar_expand.png"),
  next: iconUrl("next_arrow.png"),
};

export const SIDEBAR_FLYOUT_ICON_ASSETS = {
  processing: {
    overview: iconUrl("overview_eye.png"),
    operations: iconUrl("processing_operations.png"),
    templates: iconUrl("processing_templates.png"),
    "services-prices": iconUrl("services_prices.png"),
    "pricing-rules": iconUrl("calculation_rules.png"),
    testing: iconUrl("testing_lab.png"),
  },
  connections: {
    connectionsOverview: iconUrl("overview_eye.png"),
    mountingNodes: iconUrl("mounting_nodes.png"),
    mountingSchemes: iconUrl("fastening_schemes.png"),
    connectionTypes: iconUrl("connection_types.png"),
    mountingCompatibility: iconUrl("compatibility.png"),
    connectionsTesting: iconUrl("testing_checklist.png"),
  },
  catalog: {
    catalogMaterials: iconUrl("materials.png"),
    catalogEdges: iconUrl("materials.png"),
    catalogMaterialCategories: iconUrl("materials.png"),
    catalogMaterialManufacturers: iconUrl("materials.png"),
    catalogMaterialSuppliers: iconUrl("materials.png"),
    catalogFittings: iconUrl("hardware_hinge.png"),
    catalogFittingManufacturers: iconUrl("hardware_catalog.png"),
    catalogFittingSeries: iconUrl("hardware_catalog.png"),
    catalogFittingCategories: iconUrl("hardware_catalog.png"),
    catalogFittingProducts: iconUrl("hardware_catalog.png"),
    catalogSuppliers: iconUrl("hardware_catalog.png"),
    catalogFasteners: iconUrl("fastening_schemes.png"),
    catalogBundles: iconUrl("hardware_kits.png"),
    catalogDrillingRules: iconUrl("drilling_service_rules.png"),
    catalogViyar: iconUrl("viyar_guide.png"),
    catalogManual: iconUrl("manual_services.png"),
    catalogValues: iconUrl("values_guide.png"),
  },
};

export function getSidebarNavIconAsset(key) {
  return SIDEBAR_NAV_ICON_ASSETS[key] || null;
}

export function getSidebarControlIconAsset(key) {
  return SIDEBAR_CONTROL_ICON_ASSETS[key] || null;
}

export function getSidebarFlyoutIconAsset(groupKey, itemKey) {
  return SIDEBAR_FLYOUT_ICON_ASSETS[groupKey]?.[itemKey] || null;
}

export function SidebarAssetIcon({
  asset = "",
  className = "",
  fallback: FallbackIcon = null,
  fallbackSize = 16,
}) {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [asset]);

  if (asset && !failed) {
    return createElement("img", {
      alt: "",
      "aria-hidden": "true",
      className,
      onError: () => setFailed(true),
      src: asset,
    });
  }

  if (!FallbackIcon) {
    return null;
  }

  return createElement(FallbackIcon, { className, size: fallbackSize });
}
