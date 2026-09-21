import React from "react";
import { createRoot } from "react-dom/client";

import App from "./App.jsx";
import AssistantShell from "./assistant/index.js";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
    <AssistantShell />
  </React.StrictMode>,
);
