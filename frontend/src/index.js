import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

// Detect if the HTML was prerendered (postbuild script wrote a snapshot
// into the root div before the bundle loaded). If so, hydrate it instead
// of throwing it away and re-rendering — that way no-JS visitors see the
// page immediately and JS visitors just get a hydration pass.
const container = document.getElementById("root");
const tree = (
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

if (container && container.firstElementChild) {
  ReactDOM.hydrateRoot(container, tree);
} else {
  ReactDOM.createRoot(container).render(tree);
}
