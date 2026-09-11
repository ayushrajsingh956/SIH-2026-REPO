import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { useAuthStore } from "./stores/authStore";
import "./index.css";

// Restore session from localStorage before first render
useAuthStore.getState().initialize();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
