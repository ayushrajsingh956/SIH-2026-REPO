import { apiClient } from "@/services/api";

export interface OutboxFile {
  name: string;
  type: string;
  base64: string;
}

export interface PendingScan {
  id: string;
  files: OutboxFile[];
  mode: string;
  fontCheckMode: string;
  surfaceAreaCm2?: number | null;
  createdAt: string;
  status: "pending" | "uploading" | "failed";
  errorMessage?: string;
}

const DB_NAME = "LegalMetroOutboxDB";
const STORE_NAME = "pending_scans";
const DB_VERSION = 1;

let dbPromise: Promise<IDBDatabase> | null = null;

function getDB(): Promise<IDBDatabase> {
  if (!dbPromise) {
    dbPromise = new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, { keyPath: "id" });
        }
      };

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }
  return dbPromise;
}

type OutboxChangeListener = (count: number) => void;
const listeners = new Set<OutboxChangeListener>();

export function subscribeOutboxChanges(listener: OutboxChangeListener): () => void {
  listeners.add(listener);
  void notifyListeners();
  return () => listeners.delete(listener);
}

async function notifyListeners(): Promise<void> {
  try {
    const items = await getPendingScans();
    listeners.forEach((fn) => fn(items.length));
  } catch {
    // Ignore error in non-browser/test env
  }
}

export async function fileToOutboxFile(file: File): Promise<OutboxFile> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = (reader.result as string).split(",")[1];
      resolve({
        name: file.name,
        type: file.type || "image/jpeg",
        base64,
      });
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function outboxFileToFile(outboxFile: OutboxFile): File {
  const byteCharacters = atob(outboxFile.base64);
  const byteNumbers = new Array(byteCharacters.length);
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i);
  }
  const byteArray = new Uint8Array(byteNumbers);
  return new File([byteArray], outboxFile.name, { type: outboxFile.type });
}

export async function enqueuePendingScan(
  item: Omit<PendingScan, "id" | "createdAt" | "status">
): Promise<PendingScan> {
  const db = await getDB();
  const pendingScan: PendingScan = {
    ...item,
    id: `offline-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
    createdAt: new Date().toISOString(),
    status: "pending",
  };

  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const store = tx.objectStore(STORE_NAME);
    const req = store.add(pendingScan);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });

  void notifyListeners();
  return pendingScan;
}

export async function getPendingScans(): Promise<PendingScan[]> {
  const db = await getDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readonly");
    const store = tx.objectStore(STORE_NAME);
    const req = store.getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
}

export async function removePendingScan(id: string): Promise<void> {
  const db = await getDB();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const store = tx.objectStore(STORE_NAME);
    const req = store.delete(id);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
  void notifyListeners();
}

export async function updatePendingScanStatus(
  id: string,
  status: PendingScan["status"],
  errorMessage?: string
): Promise<void> {
  const db = await getDB();
  const scan = await new Promise<PendingScan | null>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readonly");
    const store = tx.objectStore(STORE_NAME);
    const req = store.get(id);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });

  if (!scan) return;

  scan.status = status;
  if (errorMessage !== undefined) scan.errorMessage = errorMessage;

  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const store = tx.objectStore(STORE_NAME);
    const req = store.put(scan);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });

  void notifyListeners();
}

let isSyncing = false;

export async function syncOutbox(): Promise<{ synced: number; failed: number }> {
  if (isSyncing || typeof navigator === "undefined" || !navigator.onLine) {
    return { synced: 0, failed: 0 };
  }

  isSyncing = true;
  let synced = 0;
  let failed = 0;

  try {
    const pending = await getPendingScans();
    for (const item of pending) {
      try {
        await updatePendingScanStatus(item.id, "uploading");

        const formData = new FormData();
        item.files.forEach((f) => {
          formData.append("files", outboxFileToFile(f));
        });
        formData.append("mode", item.mode);
        formData.append("font_check_mode", item.fontCheckMode);
        if (item.surfaceAreaCm2) {
          formData.append("surface_area_cm2", item.surfaceAreaCm2.toString());
        }

        await apiClient.post("/api/v1/scans", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });

        await removePendingScan(item.id);
        synced++;
      } catch (err: any) {
        failed++;
        await updatePendingScanStatus(
          item.id,
          "failed",
          err.response?.data?.detail || "Upload error during outbox sync"
        );
      }
    }
  } finally {
    isSyncing = false;
    void notifyListeners();
  }

  return { synced, failed };
}

// Auto-sync when network reconnects
if (typeof window !== "undefined") {
  window.addEventListener("online", () => {
    void syncOutbox();
  });
}
