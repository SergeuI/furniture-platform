import { useCallback, useEffect, useState } from "react";

import {
  listUnknownPhrases,
  mapUnknownPhrase,
} from "../assistant/phrases/assistantPhraseClient.js";
import "./AssistantPhraseMappingPage.css";

const ACTIONS = [
  ["materials.open", "Матеріали"],
  ["fittings.open", "Фурнітура"],
  ["fittings.hinges.open", "Навіси меблеві"],
  ["mounting_nodes.open", "Монтажні вузли"],
];

export default function AssistantPhraseMappingPage({ language = "uk" }) {
  const [items, setItems] = useState([]);
  const [actions, setActions] = useState({});
  const [loading, setLoading] = useState(true);
  const [mappingId, setMappingId] = useState("");
  const [error, setError] = useState("");
  const uk = language === "uk";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await listUnknownPhrases("new");
      const next = Array.isArray(result?.items) ? result.items : [];
      setItems(next);
      setActions((current) => {
        const copy = { ...current };
        next.forEach((item) => {
          if (!copy[item.id]) copy[item.id] = ACTIONS[0][0];
        });
        return copy;
      });
    } catch {
      setError(uk ? "Не вдалося завантажити фрази." : "Unable to load phrases.");
    } finally {
      setLoading(false);
    }
  }, [uk]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleMap(item) {
    setMappingId(item.id);
    setError("");
    try {
      await mapUnknownPhrase(item.id, actions[item.id] || ACTIONS[0][0]);
      setItems((current) => current.filter((entry) => entry.id !== item.id));
    } catch {
      setError(uk ? "Не вдалося прив’язати фразу." : "Unable to map phrase.");
    } finally {
      setMappingId("");
    }
  }

  return (
    <section className="assistant-phrase-mapping table-panel full-panel">
      <div className="assistant-phrase-mapping__header">
        <div>
          <h3>{uk ? "Фрази асистента" : "Assistant phrases"}</h3>
          <p>
            {uk
              ? "Прив’язуйте нерозпізнані команди до безпечних дій MPFC Assistant."
              : "Map unrecognized commands to safe MPFC Assistant actions."}
          </p>
        </div>
        <button className="ghost-button" disabled={loading || Boolean(mappingId)} onClick={() => void load()} type="button">
          {uk ? "Оновити" : "Refresh"}
        </button>
      </div>

      {error ? <p className="assistant-phrase-mapping__error" role="alert">{error}</p> : null}

      {loading ? (
        <p className="empty-inline-note">{uk ? "Завантаження..." : "Loading..."}</p>
      ) : items.length === 0 ? (
        <div className="assistant-phrase-mapping__empty">
          <strong>{uk ? "Нових фраз немає" : "No new phrases"}</strong>
          <span>{uk ? "Нова нерозпізнана команда з’явиться тут автоматично." : "A new unrecognized command will appear here automatically."}</span>
        </div>
      ) : (
        <div className="assistant-phrase-mapping__table-wrap">
          <table>
            <thead>
              <tr>
                <th>{uk ? "Фраза" : "Phrase"}</th>
                <th>{uk ? "Повтори" : "Count"}</th>
                <th>{uk ? "Дія" : "Action"}</th>
                <th>{uk ? "Керування" : "Control"}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <strong>{item.original_phrase || item.normalized_phrase}</strong>
                    {item.normalized_phrase && item.normalized_phrase !== item.original_phrase ? <small>{item.normalized_phrase}</small> : null}
                  </td>
                  <td>{item.count ?? 1}</td>
                  <td>
                    <select
                      disabled={mappingId === item.id}
                      onChange={(event) => setActions((current) => ({ ...current, [item.id]: event.target.value }))}
                      value={actions[item.id] || ACTIONS[0][0]}
                    >
                      {ACTIONS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
                    </select>
                  </td>
                  <td>
                    <button className="primary-button" disabled={Boolean(mappingId)} onClick={() => void handleMap(item)} type="button">
                      {mappingId === item.id ? (uk ? "Прив’язування..." : "Mapping...") : (uk ? "Прив’язати" : "Map")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
