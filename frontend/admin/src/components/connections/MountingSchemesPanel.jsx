import { ArrowLeft, Pencil, Plus, Save, Search, Trash2, X } from "lucide-react";
import { createPortal } from "react-dom";
import { useEffect, useMemo, useState } from "react";

import {
  createMountingScheme,
  getMountingNodes,
  getMountingScheme,
  listMountingSchemes,
  updateMountingScheme,
} from "../../api.js";
import {
  getMountingNodeCategoryLabel,
  normalizeMountingNodeCategoryCode,
} from "../../mountingNodeCategories.js";
import {
  getMountingNodeFunctionalLabel,
  normalizeMountingNodeFunctionalCode,
} from "../../mountingNodeFunctionalCodes.js";
import {
  buildMountingSchemeDraftFromScheme,
  buildMountingSchemeNodeDraft,
  buildMountingSchemePayload,
  buildMountingSchemesRouteUrl,
  collectDistinctGroupKeys,
  createEmptyMountingSchemeDraft,
  getMountingSchemeValidationMessage,
  getMountingSchemesWorkspaceChrome,
  normalizeMountingSchemesRoute,
  parseMountingSchemesRoute,
  syncPlacementRulesWithGroupKeys,
  validateMountingSchemeDraft,
} from "../../mountingSchemesWorkspace.js";

function normalizeText(value) {
  return String(value ?? "").trim();
}

function normalizeNodeId(value) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? String(parsed) : "";
}

function getNodeLabel(node) {
  return normalizeText(node?.node_name || node?.name || node?.node_code || node?.code || node?.article || node?.id);
}

function getNodeCode(node) {
  return normalizeText(node?.node_code || node?.code || node?.article);
}

function getNodeCategoryCode(node) {
  return normalizeMountingNodeCategoryCode(node?.category_code || node?.categoryCode || node?.category || "");
}

function getNodeFunctionalCode(node) {
  return normalizeMountingNodeFunctionalCode(node?.functional_code || node?.functionalCode || node?.functional || "");
}

function getNodeCategoryLabel(node, language) {
  const categoryCode = getNodeCategoryCode(node);
  return (
    getMountingNodeCategoryLabel(categoryCode, language) ||
    normalizeText(node?.category_name || node?.category_label || node?.category || "")
  );
}

function getNodeFunctionalLabel(node, language) {
  const functionalCode = getNodeFunctionalCode(node);
  return (
    getMountingNodeFunctionalLabel(functionalCode, language) ||
    normalizeText(node?.functional_name || node?.functional_label || node?.functional || "")
  );
}

function isSchemeAlreadySelected(node, draftNodes) {
  const nodeId = normalizeNodeId(node?.id || node?.node_id);
  return draftNodes.some((item) => normalizeNodeId(item.node_id) === nodeId);
}

function sortByOrderIndex(left, right) {
  const leftOrder = Number(left?.order_index ?? 0) || 0;
  const rightOrder = Number(right?.order_index ?? 0) || 0;

  if (leftOrder !== rightOrder) {
    return leftOrder - rightOrder;
  }

  return normalizeText(left?.node_name || left?.node_code || left?.name).localeCompare(
    normalizeText(right?.node_name || right?.node_code || right?.name),
    "en",
  );
}

function buildDisplayRoute(route) {
  return buildMountingSchemesRouteUrl(route, window.location.search, window.location.hash || "");
}

function ModalShell({ title, children, onClose, language }) {
  return createPortal(
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <article
        aria-label={title}
        aria-modal="true"
        className="confirm-modal mounting-schemes-modal"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        <header className="confirm-header">
          <div>
            <strong>{title}</strong>
            <p>
              {language === "uk"
                ? "Обирайте вже існуючий монтажний вузол, а сам запис не дублюється."
                : "Pick an existing mounting node record without duplicating it."}
            </p>
          </div>
          <button className="ghost-button compact-button detail-info-button" onClick={onClose} type="button">
            <X size={16} />
          </button>
        </header>
        {children}
      </article>
    </div>,
    document.body,
  );
}

function NodeSelectorModal({
  availableNodes = [],
  existingNodeIds = [],
  isOpen = false,
  language = "uk",
  loading = false,
  onAddNode = () => {},
  onClose = () => {},
  onSearchChange = () => {},
  search = "",
  selectorError = "",
}) {
  const filteredNodes = useMemo(() => {
    const normalizedSearch = normalizeText(search).toLowerCase();

    return (Array.isArray(availableNodes) ? availableNodes : []).filter((node) => {
      if (!normalizedSearch) {
        return true;
      }

      const haystack = [
        getNodeLabel(node),
        getNodeCode(node),
        getNodeCategoryLabel(node, language),
        getNodeFunctionalLabel(node, language),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return haystack.includes(normalizedSearch);
    });
  }, [availableNodes, language, search]);

  if (!isOpen) {
    return null;
  }

  return (
    <ModalShell
      language={language}
      onClose={onClose}
      title={language === "uk" ? "Додати монтажний вузол" : "Add mounting node"}
    >
      <div className="mounting-schemes-selector">
        <label className="service-catalog-search mounting-schemes-selector-search">
          <Search size={16} />
          <input
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder={language === "uk" ? "Пошук вузлів" : "Search nodes"}
            type="search"
            value={search}
          />
        </label>

        {selectorError ? <div className="mounting-schemes-alert error">{selectorError}</div> : null}
        {loading ? <div className="mounting-schemes-alert subtle">{language === "uk" ? "Завантаження вузлів..." : "Loading nodes..."}</div> : null}

        <div className="mounting-schemes-selector-list">
          {filteredNodes.map((node) => {
            const nodeId = normalizeNodeId(node?.id || node?.node_id);
            const selected = existingNodeIds.includes(nodeId);
            const categoryLabel = getNodeCategoryLabel(node, language);
            const functionalLabel = getNodeFunctionalLabel(node, language);

            return (
              <button
                className={`mounting-schemes-selector-row${selected ? " is-selected" : ""}`}
                disabled={selected}
                key={nodeId || getNodeCode(node) || getNodeLabel(node)}
                onClick={() => onAddNode(node)}
                type="button"
              >
                <div className="mounting-schemes-selector-row-main">
                  <strong>{getNodeLabel(node)}</strong>
                  <span>
                    {[categoryLabel, functionalLabel].filter(Boolean).join(" · ") ||
                      (language === "uk" ? "Без додаткового опису" : "No extra details")}
                  </span>
                </div>
                <div className="mounting-schemes-selector-row-meta">
                  {getNodeCode(node) ? <span className="service-tree-badge subtle">{getNodeCode(node)}</span> : null}
                  {selected ? (
                    <span className="service-tree-badge subtle">{language === "uk" ? "Додано" : "Added"}</span>
                  ) : (
                    <span className="service-tree-badge subtle">{language === "uk" ? "Додати" : "Add"}</span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </ModalShell>
  );
}

export default function MountingSchemesPanel({ language = "uk", token = "" }) {
  const [route, setRoute] = useState(() => normalizeMountingSchemesRoute(parseMountingSchemesRoute(window.location.search) || {}));
  const [schemes, setSchemes] = useState([]);
  const [schemesLoading, setSchemesLoading] = useState(false);
  const [schemesError, setSchemesError] = useState("");
  const [currentScheme, setCurrentScheme] = useState(null);
  const [currentSchemeLoading, setCurrentSchemeLoading] = useState(false);
  const [currentSchemeError, setCurrentSchemeError] = useState("");
  const [draft, setDraft] = useState(createEmptyMountingSchemeDraft());
  const [saveError, setSaveError] = useState("");
  const [saving, setSaving] = useState(false);
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [availableNodes, setAvailableNodes] = useState([]);
  const [availableNodesLoading, setAvailableNodesLoading] = useState(false);
  const [availableNodesError, setAvailableNodesError] = useState("");
  const [selectorOpen, setSelectorOpen] = useState(false);
  const [selectorSearch, setSelectorSearch] = useState("");

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }

    const handlePopState = () => {
      const nextRoute = normalizeMountingSchemesRoute(parseMountingSchemesRoute(window.location.search) || {});
      setRoute(nextRoute);
    };

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  function navigate(nextRoute, { replace = false } = {}) {
    const normalizedRoute = normalizeMountingSchemesRoute(nextRoute);
    setRoute(normalizedRoute);

    if (typeof window === "undefined") {
      return;
    }

    const nextUrl = `${window.location.pathname}${buildDisplayRoute(normalizedRoute)}`;
    const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash || ""}`;

    if (nextUrl === currentUrl) {
      return;
    }

    const historyMethod = replace ? window.history.replaceState : window.history.pushState;
    historyMethod.call(window.history, null, document.title, nextUrl);
  }

  async function loadSchemes(includeInactive = false) {
    if (!token) {
      setSchemes([]);
      return;
    }

    setSchemesLoading(true);
    setSchemesError("");

    const result = await listMountingSchemes(token, includeInactive);
    if (result.success) {
      setSchemes(Array.isArray(result.schemes) ? result.schemes : []);
      setSchemesLoading(false);
      return;
    }

    setSchemes([]);
    setSchemesError(result.error || (language === "uk" ? "Не вдалося завантажити схеми." : "Unable to load schemes."));
    setSchemesLoading(false);
  }

  async function loadSchemeDetail(schemeId) {
    const normalizedSchemeId = normalizeText(schemeId);
    if (!token || !normalizedSchemeId) {
      setCurrentScheme(null);
      return;
    }

    setCurrentSchemeLoading(true);
    setCurrentSchemeError("");

    const result = await getMountingScheme(token, normalizedSchemeId);
    if (result.success && result.scheme) {
      setCurrentScheme(result.scheme);
      setCurrentSchemeLoading(false);
      return;
    }

    setCurrentScheme(null);
    setCurrentSchemeError(
      result.error || (language === "uk" ? "Не вдалося завантажити схему." : "Unable to load scheme."),
    );
    setCurrentSchemeLoading(false);
  }

  async function loadAvailableNodes() {
    if (!token) {
      setAvailableNodes([]);
      return;
    }

    setAvailableNodesLoading(true);
    setAvailableNodesError("");

    const result = await getMountingNodes(token, { include_inactive: true });
    if (result.success) {
      setAvailableNodes(Array.isArray(result.nodes) ? result.nodes : []);
      setAvailableNodesLoading(false);
      return;
    }

    setAvailableNodes([]);
    setAvailableNodesError(result.error || (language === "uk" ? "Не вдалося завантажити вузли." : "Unable to load nodes."));
    setAvailableNodesLoading(false);
  }

  useEffect(() => {
    if (!token) {
      setSchemes([]);
      setCurrentScheme(null);
      setAvailableNodes([]);
      return;
    }

    if (route.mode === "list") {
      void loadSchemes(false);
      return;
    }

    if (route.mode === "create") {
      setDraft(createEmptyMountingSchemeDraft());
      setCurrentScheme(null);
      setSubmitAttempted(false);
      void loadAvailableNodes();
      return;
    }

    if (route.mode === "detail" || route.mode === "edit") {
      void loadSchemeDetail(route.schemeId);
      void loadAvailableNodes();
    }
  }, [language, route.mode, route.schemeId, token]);

  useEffect(() => {
    if (route.mode === "create") {
      setDraft(createEmptyMountingSchemeDraft());
      setSaveError("");
      setSubmitAttempted(false);
      return;
    }

    if (route.mode === "edit" && currentScheme) {
      setDraft(buildMountingSchemeDraftFromScheme(currentScheme));
      setSaveError("");
      setSubmitAttempted(false);
    }
  }, [currentScheme, route.mode]);

  const listItems = useMemo(() => {
    return (Array.isArray(schemes) ? schemes : []).slice().sort((left, right) => {
      const leftName = normalizeText(left?.name || left?.code);
      const rightName = normalizeText(right?.name || right?.code);
      if (leftName !== rightName) {
        return leftName.localeCompare(rightName, language === "uk" ? "uk" : "en");
      }
      return Number(left?.id || 0) - Number(right?.id || 0);
    });
  }, [language, schemes]);

  const draftNodes = Array.isArray(draft.nodes) ? draft.nodes.slice().sort(sortByOrderIndex) : [];
  const draftRules = Array.isArray(draft.placement_rules) ? draft.placement_rules : [];
  const draftValidationMessage = getMountingSchemeValidationMessage(
    { ...draft, nodes: draftNodes, placement_rules: draftRules },
    {
      language,
      visible: submitAttempted,
    },
  );
  const workspaceChrome = getMountingSchemesWorkspaceChrome(route.mode);
  const canSave = route.mode === "create" || route.mode === "edit";

  const detailScheme = route.mode === "detail" ? currentScheme : route.mode === "edit" ? currentScheme : null;

  function applyDraft(updater) {
    setDraft((current) => {
      const nextDraft = typeof updater === "function" ? updater(current) : updater;
      const nextNodes = Array.isArray(nextDraft.nodes) ? nextDraft.nodes : [];
      const nextGroupKeys = collectDistinctGroupKeys(nextNodes);
      const nextRules = syncPlacementRulesWithGroupKeys(nextDraft.placement_rules, nextGroupKeys);
      return {
        ...nextDraft,
        nodes: nextNodes,
        placement_rules: nextRules,
      };
    });
  }

  function addNodeToDraft(node) {
    const nodeId = normalizeNodeId(node?.id || node?.node_id);
    if (!nodeId) {
      return;
    }

    setDraft((current) => {
      if (current.nodes.some((item) => normalizeNodeId(item.node_id) === nodeId)) {
        return current;
      }

      const defaultGroupKey = current.nodes.length
        ? normalizeText(current.nodes[0]?.group_key || "primary")
        : "primary";

      const nextNodes = [
        ...current.nodes,
        buildMountingSchemeNodeDraft(
          {
            node_id: nodeId,
            group_key: defaultGroupKey,
            quantity_per_group: 1,
            order_index: current.nodes.length,
            is_required: true,
            node_code: getNodeCode(node),
            node_name: getNodeLabel(node),
            category_code: getNodeCategoryCode(node),
            functional_code: getNodeFunctionalCode(node),
          },
          current.nodes.length,
        ),
      ];

      return {
        ...current,
        nodes: nextNodes,
        placement_rules: syncPlacementRulesWithGroupKeys(current.placement_rules, collectDistinctGroupKeys(nextNodes)),
      };
    });

    setSelectorOpen(false);
  }

  async function handleSave(event) {
    event.preventDefault();
    setSubmitAttempted(true);
    const nextErrors = validateMountingSchemeDraft({ ...draft, nodes: draftNodes, placement_rules: draftRules });
    if (nextErrors.length) {
      setSaveError("");
      return;
    }

    const payload = buildMountingSchemePayload({
      ...draft,
      nodes: draftNodes,
      placement_rules: draftRules,
    });

    setSaving(true);
    setSaveError("");

    const result =
      route.mode === "edit" && route.schemeId
        ? await updateMountingScheme(token, route.schemeId, payload)
        : await createMountingScheme(token, payload);

    setSaving(false);

    if (!result.success || !result.scheme) {
      setSaveError(result.error || (language === "uk" ? "Не вдалося зберегти схему." : "Unable to save the scheme."));
      return;
    }

    setCurrentScheme(result.scheme);
    setDraft(buildMountingSchemeDraftFromScheme(result.scheme));
    setSubmitAttempted(false);
    navigate({ mode: "detail", schemeId: result.scheme.id }, { replace: true });
    void loadSchemes(false);
  }

  function handleStartCreate() {
    setCurrentScheme(null);
    setSaveError("");
    setSubmitAttempted(false);
    setSelectorSearch("");
    setDraft(createEmptyMountingSchemeDraft());
    navigate({ mode: "create", schemeId: "" });
  }

  function handleOpenDetail(schemeId) {
    setSaveError("");
    setSubmitAttempted(false);
    navigate({ mode: "detail", schemeId });
  }

  function handleStartEdit() {
    if (!detailScheme) {
      return;
    }

    setDraft(buildMountingSchemeDraftFromScheme(detailScheme));
    setSaveError("");
    setSubmitAttempted(false);
    navigate({ mode: "edit", schemeId: detailScheme.id });
  }

  function handleBackToList() {
    setCurrentScheme(null);
    setSaveError("");
    setSubmitAttempted(false);
    navigate({ mode: "list", schemeId: "" });
  }

  function handleNodeFieldChange(index, field, value) {
    applyDraft((current) => {
      const nextNodes = current.nodes.map((item, currentIndex) => {
        if (currentIndex !== index) {
          return item;
        }

        return {
          ...item,
          [field]: field === "is_required" ? Boolean(value) : value,
        };
      });

      return {
        ...current,
        nodes: nextNodes,
      };
    });
  }

  function handleRuleFieldChange(index, field, value) {
    setDraft((current) => {
      const nextRules = current.placement_rules.map((item, currentIndex) => {
        if (currentIndex !== index) {
          return item;
        }

        return {
          ...item,
          [field]: value,
        };
      });

      return {
        ...current,
        placement_rules: nextRules,
      };
    });
  }

  function handleRemoveNode(index) {
    applyDraft((current) => ({
      ...current,
      nodes: current.nodes.filter((_, currentIndex) => currentIndex !== index),
    }));
  }

  function handleAddEmptyRule() {
    applyDraft((current) => ({
      ...current,
      placement_rules: [
        ...current.placement_rules,
        {
          id: `rule-${current.placement_rules.length + 1}`,
          group_key: current.nodes[0]?.group_key || "primary",
          distribution_mode: "equal",
          min_group_count: 1,
          max_group_count: "",
          fixed_group_count: "",
          start_offset_mm: "",
          end_offset_mm: "",
          max_spacing_mm: "",
          fixed_spacing_mm: "",
        },
      ],
    }));
  }

  function handleDeleteRule(index) {
    setDraft((current) => ({
      ...current,
      placement_rules: current.placement_rules.filter((_, currentIndex) => currentIndex !== index),
    }));
  }

  return (
    <section className="dashboard-layout mounting-schemes-workspace">
      {route.mode === "list" ? (
        <article className="table-panel full-panel mounting-schemes-table-panel">
          <div className="dashboard-panel-head mounting-schemes-panel-head">
            <div>
              <h3>{language === "uk" ? "Схеми кріплення" : "Mounting schemes"}</h3>
              <p>
                {language === "uk"
                  ? "Створюйте схеми з монтажних вузлів і задавайте правила їх розстановки."
                  : "Create schemes from mounting nodes and define their placement rules."}
              </p>
            </div>
            {workspaceChrome.listCreateActionCount ? (
              <button className="primary-button" onClick={handleStartCreate} type="button">
                <Plus size={16} />
                {language === "uk" ? "Створити схему кріплення" : "Create mounting scheme"}
              </button>
            ) : null}
          </div>

          {schemesError ? <div className="mounting-schemes-alert error">{schemesError}</div> : null}
          {schemesLoading ? <div className="mounting-schemes-alert subtle">{language === "uk" ? "Завантаження..." : "Loading..."}</div> : null}

          {!schemesLoading && !schemesError && !listItems.length ? (
            <div className="empty-state mounting-schemes-empty-state">
              <h4>{language === "uk" ? "Схем ще немає" : "No schemes yet"}</h4>
              <p>
                {language === "uk"
                  ? "Створіть першу схему кріплення, щоб пов’язати монтажні вузли та правила їх розстановки."
                  : "Create the first mounting scheme to connect nodes and placement rules."}
              </p>
            </div>
          ) : null}

          <div className="mounting-schemes-list">
            {listItems.map((scheme) => (
              <button
                className="mounting-schemes-list-item"
                key={scheme.id}
                onClick={() => handleOpenDetail(scheme.id)}
                type="button"
              >
                <div className="mounting-schemes-list-item-main">
                  <strong>{scheme.name}</strong>
                  <span>{scheme.code}</span>
                </div>
                <div className="mounting-schemes-list-item-meta">
                  <span className="service-tree-badge subtle">
                    {scheme.nodes_count || 0} {language === "uk" ? "вузлів" : "nodes"}
                  </span>
                  <span className="service-tree-badge subtle">
                    {scheme.placement_rules_count || 0} {language === "uk" ? "правил" : "rules"}
                  </span>
                  <span className={`service-tree-badge ${scheme.is_active ? "live" : "inactive"}`}>
                    {scheme.is_active ? (language === "uk" ? "Активна" : "Active") : language === "uk" ? "Неактивна" : "Inactive"}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </article>
      ) : route.mode === "detail" ? (
        <article className="table-panel full-panel mounting-schemes-detail-panel">
          <div className="dashboard-panel-head mounting-schemes-panel-head">
            <div>
              <h3>{detailScheme?.name || (language === "uk" ? "Деталі схеми" : "Scheme details")}</h3>
              <p>{detailScheme?.description || (language === "uk" ? "Перегляд схеми без редагування." : "Read-only scheme view.")}</p>
            </div>
            <div className="mounting-schemes-panel-head-actions">
              {workspaceChrome.backActionCount ? (
                <button className="ghost-button mounting-node-return-button" onClick={handleBackToList} type="button">
                  <ArrowLeft size={16} />
                  {language === "uk" ? "Повернутися до списку" : "Back to list"}
                </button>
              ) : null}
              {workspaceChrome.editActionCount ? (
                <button className="primary-button" onClick={handleStartEdit} type="button">
                  <Pencil size={16} />
                  {language === "uk" ? "Редагувати схему" : "Edit scheme"}
                </button>
              ) : null}
            </div>
          </div>

          {currentSchemeLoading ? (
            <div className="mounting-schemes-alert subtle">{language === "uk" ? "Завантаження схеми..." : "Loading scheme..."}</div>
          ) : null}
          {currentSchemeError ? <div className="mounting-schemes-alert error">{currentSchemeError}</div> : null}

          {detailScheme ? (
            <>
              <div className="mounting-schemes-summary-grid">
                <div className="mounting-schemes-summary-card">
                  <strong>{language === "uk" ? "Код" : "Code"}</strong>
                  <span>{detailScheme.code}</span>
                </div>
                <div className="mounting-schemes-summary-card">
                  <strong>{language === "uk" ? "Статус" : "Status"}</strong>
                  <span>{detailScheme.is_active ? (language === "uk" ? "Активна" : "Active") : language === "uk" ? "Неактивна" : "Inactive"}</span>
                </div>
                <div className="mounting-schemes-summary-card">
                  <strong>{language === "uk" ? "Вузли" : "Nodes"}</strong>
                  <span>{detailScheme.nodes_count || 0}</span>
                </div>
                <div className="mounting-schemes-summary-card">
                  <strong>{language === "uk" ? "Правила" : "Rules"}</strong>
                  <span>{detailScheme.placement_rules_count || 0}</span>
                </div>
              </div>

              <div className="mounting-schemes-detail-sections">
                <section className="mounting-schemes-detail-section">
                  <h4>{language === "uk" ? "Монтажні вузли схеми" : "Scheme nodes"}</h4>
                  <div className="mounting-schemes-detail-list">
                    {(Array.isArray(detailScheme.nodes) ? detailScheme.nodes : []).map((node) => (
                      <div className="mounting-schemes-detail-row" key={`${node.id}-${node.node_id}`}>
                        <div className="mounting-schemes-detail-row-main">
                          <strong>{node.node_name || node.node_code || node.node_id}</strong>
                          <span>{[node.group_key, node.role_code].filter(Boolean).join(" · ") || (language === "uk" ? "Без ролі" : "No role")}</span>
                        </div>
                        <div className="mounting-schemes-detail-row-meta">
                          <span className="service-tree-badge subtle">
                            {language === "uk" ? "К-сть у групі" : "Per group"}: {node.quantity_per_group}
                          </span>
                          <span className="service-tree-badge subtle">
                            {node.is_required ? (language === "uk" ? "Обов’язковий" : "Required") : language === "uk" ? "Опційний" : "Optional"}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="mounting-schemes-detail-section">
                  <h4>{language === "uk" ? "Правила розстановки" : "Placement rules"}</h4>
                  <div className="mounting-schemes-detail-list">
                    {(Array.isArray(detailScheme.placement_rules) ? detailScheme.placement_rules : []).map((rule) => (
                      <div className="mounting-schemes-detail-row" key={`${rule.id}-${rule.group_key}`}>
                        <div className="mounting-schemes-detail-row-main">
                          <strong>{rule.group_key}</strong>
                          <span>{rule.distribution_mode}</span>
                        </div>
                        <div className="mounting-schemes-detail-row-meta">
                          <span className="service-tree-badge subtle">
                            {language === "uk" ? "Мін." : "Min"}: {rule.min_group_count}
                          </span>
                          <span className="service-tree-badge subtle">
                            {language === "uk" ? "Макс." : "Max"}: {rule.max_group_count || "—"}
                          </span>
                          <span className="service-tree-badge subtle">
                            {language === "uk" ? "Фікс." : "Fixed"}: {rule.fixed_group_count || "—"}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              </div>
            </>
          ) : null}
        </article>
      ) : (
        <form className="table-panel full-panel mounting-schemes-editor-panel" onSubmit={handleSave}>
          <div className="dashboard-panel-head mounting-schemes-panel-head">
            <div>
              <h3>{route.mode === "create" ? (language === "uk" ? "Створення схеми" : "Create scheme") : (currentScheme?.name || (language === "uk" ? "Редагування схеми" : "Edit scheme"))}</h3>
              <p>
                {language === "uk"
                  ? "Одна форма для основних даних, вибору монтажних вузлів і правил їх розстановки."
                  : "One form for basic data, node selection, and placement rules."}
              </p>
            </div>
            <div className="mounting-schemes-panel-head-actions">
              {workspaceChrome.backActionCount ? (
                <button className="ghost-button mounting-node-return-button" onClick={handleBackToList} type="button">
                  <ArrowLeft size={16} />
                  {language === "uk" ? "Повернутися до списку" : "Back to list"}
                </button>
              ) : null}
              {workspaceChrome.saveActionCount ? (
                <button className="primary-button" disabled={saving} type="submit">
                  <Save size={16} />
                  {saving ? (language === "uk" ? "Збереження..." : "Saving...") : language === "uk" ? "Зберегти" : "Save"}
                </button>
              ) : null}
            </div>
          </div>

          {saveError ? <div className="mounting-schemes-alert error">{saveError}</div> : null}
          {draftValidationMessage ? <div className="mounting-schemes-alert subtle">{draftValidationMessage}</div> : null}

          <section className="mounting-schemes-form-section">
            <h4>{language === "uk" ? "Основне" : "Basic info"}</h4>
            <div className="mounting-schemes-form-grid">
              <label className="mounting-schemes-field">
                <span>{language === "uk" ? "Назва" : "Name"}</span>
                <input
                  onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
                  value={draft.name}
                />
              </label>
              {route.mode === "create" ? (
                <div className="mounting-schemes-alert subtle">
                  {language === "uk"
                    ? "Код буде згенеровано автоматично."
                    : "The technical code will be generated automatically."}
                </div>
              ) : (
                <label className="mounting-schemes-field">
                  <span>{language === "uk" ? "Код" : "Code"}</span>
                  <input
                    onChange={(event) => setDraft((current) => ({ ...current, code: event.target.value }))}
                    value={draft.code}
                  />
                </label>
              )}
              <label className="mounting-schemes-field mounting-schemes-field-wide">
                <span>{language === "uk" ? "Опис" : "Description"}</span>
                <textarea
                  onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))}
                  rows={3}
                  value={draft.description}
                />
              </label>
              <label className="toggle-label mounting-schemes-toggle">
                <input
                  checked={Boolean(draft.is_active)}
                  onChange={(event) => setDraft((current) => ({ ...current, is_active: event.target.checked }))}
                  type="checkbox"
                />
                <span>{language === "uk" ? "Активна" : "Active"}</span>
              </label>
            </div>
          </section>

          <section className="mounting-schemes-form-section">
            <div className="mounting-schemes-section-head">
              <div>
                <h4>{language === "uk" ? "Монтажні вузли схеми" : "Scheme nodes"}</h4>
                <p>
                  {language === "uk"
                    ? "Додавайте вже існуючі вузли та налаштовуйте group_key, кількість у групі, роль і порядок."
                    : "Add existing nodes and configure the group key, quantity, role, and order."}
                </p>
              </div>
              <button className="primary-button" onClick={() => setSelectorOpen(true)} type="button">
                <Plus size={16} />
                {language === "uk" ? "Додати вузол" : "Add node"}
              </button>
            </div>

            {draftNodes.length ? (
              <div className="mounting-schemes-node-list">
                {draftNodes.map((node, index) => (
                  <div className="mounting-schemes-node-card" key={`${node.node_id}-${index}`}>
                    <div className="mounting-schemes-node-card-head">
                      <div className="mounting-schemes-node-card-title">
                        <strong>{node.node_name || node.node_code || node.node_id}</strong>
                        <span>{[node.category_code && getMountingNodeCategoryLabel(node.category_code, language), node.functional_code && getMountingNodeFunctionalLabel(node.functional_code, language)].filter(Boolean).join(" · ")}</span>
                      </div>
                      <button className="ghost-button compact-button" onClick={() => handleRemoveNode(index)} type="button">
                        <Trash2 size={16} />
                        {language === "uk" ? "Видалити" : "Remove"}
                      </button>
                    </div>
                    <div className="mounting-schemes-node-grid">
                      <label className="mounting-schemes-field">
                        <span>{language === "uk" ? "Група розстановки" : "Placement group"}</span>
                        <input
                          onChange={(event) => {
                            const value = event.target.value;
                            applyDraft((current) => {
                              const nextNodes = current.nodes.map((item, currentIndex) =>
                                currentIndex === index ? { ...item, group_key: value } : item,
                              );
                              return {
                                ...current,
                                nodes: nextNodes,
                                placement_rules: syncPlacementRulesWithGroupKeys(
                                  current.placement_rules,
                                  collectDistinctGroupKeys(nextNodes),
                                ),
                              };
                            });
                          }}
                          value={node.group_key}
                        />
                      </label>
                      <label className="mounting-schemes-field">
                        <span>{language === "uk" ? "К-сть у групі" : "Quantity per group"}</span>
                        <input
                          min="1"
                          onChange={(event) => handleNodeFieldChange(index, "quantity_per_group", event.target.value)}
                          type="number"
                          value={node.quantity_per_group}
                        />
                      </label>
                      <label className="mounting-schemes-field">
                        <span>{language === "uk" ? "Роль" : "Role"}</span>
                        <input
                          onChange={(event) => handleNodeFieldChange(index, "role_code", event.target.value)}
                          placeholder={language === "uk" ? "Необов’язково" : "Optional"}
                          value={node.role_code}
                        />
                      </label>
                      <label className="mounting-schemes-field">
                        <span>{language === "uk" ? "Порядок" : "Order"}</span>
                        <input
                          onChange={(event) => handleNodeFieldChange(index, "order_index", event.target.value)}
                          type="number"
                          value={node.order_index}
                        />
                      </label>
                      <label className="toggle-label mounting-schemes-toggle">
                        <input
                          checked={Boolean(node.is_required)}
                          onChange={(event) => handleNodeFieldChange(index, "is_required", event.target.checked)}
                          type="checkbox"
                        />
                        <span>{language === "uk" ? "Обов’язковий" : "Required"}</span>
                      </label>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state mounting-schemes-empty-state">
                <h4>{language === "uk" ? "Немає вузлів" : "No nodes yet"}</h4>
                <p>
                  {language === "uk"
                    ? "Додайте існуючі монтажні вузли, щоб почати збирати схему."
                    : "Add existing mounting nodes to start building the scheme."}
                </p>
                <button className="primary-button" onClick={() => setSelectorOpen(true)} type="button">
                  <Plus size={16} />
                  {language === "uk" ? "Додати вузол" : "Add node"}
                </button>
              </div>
            )}
          </section>

          <section className="mounting-schemes-form-section">
            <div className="mounting-schemes-section-head">
              <div>
                <h4>{language === "uk" ? "Правила розстановки" : "Placement rules"}</h4>
                <p>
                  {language === "uk"
                    ? "Для кожної групи з вузлів задайте режим розподілу та інші параметри розстановки."
                    : "Define distribution mode and placement parameters for each node group."}
                </p>
              </div>
              <button className="ghost-button compact-button" onClick={handleAddEmptyRule} type="button">
                <Plus size={16} />
                {language === "uk" ? "Додати правило" : "Add rule"}
              </button>
            </div>

            <div className="mounting-schemes-rule-list">
              {draftRules.map((rule, index) => (
                <div className="mounting-schemes-rule-card" key={`${rule.id}-${index}`}>
                  <div className="mounting-schemes-node-card-head">
                    <div className="mounting-schemes-node-card-title">
                      <strong>{rule.group_key || (language === "uk" ? "Група" : "Group")}</strong>
                      <span>{rule.distribution_mode}</span>
                    </div>
                    <button className="ghost-button compact-button" onClick={() => handleDeleteRule(index)} type="button">
                      <Trash2 size={16} />
                      {language === "uk" ? "Видалити" : "Remove"}
                    </button>
                  </div>
                  <div className="mounting-schemes-rule-grid">
                    <label className="mounting-schemes-field">
                      <span>{language === "uk" ? "Група розстановки" : "Placement group"}</span>
                      <select onChange={(event) => handleRuleFieldChange(index, "group_key", event.target.value)} value={rule.group_key}>
                        {collectDistinctGroupKeys(draft.nodes).map((groupKey) => (
                          <option key={groupKey} value={groupKey}>
                            {groupKey}
                          </option>
                        ))}
                        {!collectDistinctGroupKeys(draft.nodes).length ? <option value="primary">primary</option> : null}
                      </select>
                    </label>
                    <label className="mounting-schemes-field">
                      <span>{language === "uk" ? "Режим розподілу" : "Distribution mode"}</span>
                      <select onChange={(event) => handleRuleFieldChange(index, "distribution_mode", event.target.value)} value={rule.distribution_mode}>
                        <option value="equal">{language === "uk" ? "Рівномірно" : "Equal"}</option>
                        <option value="fixed_spacing">{language === "uk" ? "Фіксований крок" : "Fixed spacing"}</option>
                        <option value="centered">{language === "uk" ? "По центру" : "Centered"}</option>
                      </select>
                    </label>
                    <label className="mounting-schemes-field">
                      <span>{language === "uk" ? "Мінімальна кількість груп" : "Minimum group count"}</span>
                      <input
                        min="1"
                        onChange={(event) => handleRuleFieldChange(index, "min_group_count", event.target.value)}
                        type="number"
                        value={rule.min_group_count}
                      />
                    </label>
                    <label className="mounting-schemes-field">
                      <span>{language === "uk" ? "Максимальна кількість груп" : "Maximum group count"}</span>
                      <input
                        min="1"
                        onChange={(event) => handleRuleFieldChange(index, "max_group_count", event.target.value)}
                        type="number"
                        value={rule.max_group_count}
                      />
                    </label>
                    <label className="mounting-schemes-field">
                      <span>{language === "uk" ? "Фіксована кількість груп" : "Fixed group count"}</span>
                      <input
                        min="1"
                        onChange={(event) => handleRuleFieldChange(index, "fixed_group_count", event.target.value)}
                        type="number"
                        value={rule.fixed_group_count}
                      />
                    </label>
                    <label className="mounting-schemes-field">
                      <span>{language === "uk" ? "Відступ від початку, мм" : "Start offset, mm"}</span>
                      <input
                        min="0"
                        onChange={(event) => handleRuleFieldChange(index, "start_offset_mm", event.target.value)}
                        type="number"
                        value={rule.start_offset_mm}
                      />
                    </label>
                    <label className="mounting-schemes-field">
                      <span>{language === "uk" ? "Відступ від кінця, мм" : "End offset, mm"}</span>
                      <input
                        min="0"
                        onChange={(event) => handleRuleFieldChange(index, "end_offset_mm", event.target.value)}
                        type="number"
                        value={rule.end_offset_mm}
                      />
                    </label>
                    <label className="mounting-schemes-field">
                      <span>{language === "uk" ? "Максимальний крок, мм" : "Maximum spacing, mm"}</span>
                      <input
                        min="1"
                        onChange={(event) => handleRuleFieldChange(index, "max_spacing_mm", event.target.value)}
                        type="number"
                        value={rule.max_spacing_mm}
                      />
                    </label>
                    <label className="mounting-schemes-field">
                      <span>{language === "uk" ? "Фіксований крок, мм" : "Fixed spacing, mm"}</span>
                      <input
                        min="1"
                        onChange={(event) => handleRuleFieldChange(index, "fixed_spacing_mm", event.target.value)}
                        type="number"
                        value={rule.fixed_spacing_mm}
                      />
                    </label>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </form>
      )}

      <NodeSelectorModal
        availableNodes={availableNodes}
        existingNodeIds={draft.nodes.map((node) => normalizeNodeId(node.node_id))}
        isOpen={selectorOpen}
        language={language}
        loading={availableNodesLoading}
        onAddNode={addNodeToDraft}
        onClose={() => setSelectorOpen(false)}
        onSearchChange={setSelectorSearch}
        search={selectorSearch}
        selectorError={availableNodesError}
      />
    </section>
  );
}
