import {
  useEffect,
  useRef,
  useState,
} from "react";

import type {
  ChangeEvent,
  DragEvent,
} from "react";

import {
  uploadDocument,
  getDocuments,
  getDocumentPdf,
  deleteDocument,
  getGenerationProgress,
  generateDocumentQuestions,
  streamDocumentProgress,
  getProfile,
} from "../services/api";

import "./DocumentUpload.css";
import API_URL from "../services/apiConfig";

type DifficultyProgress = {
  status: string;
  current: number;
  target: number;
  progress: number;
};

type DocumentItem = {
  id: number;
  file: string;
  chunks: number;
  created_at: string | null;
  processing_status?: string;
  global_progress?: number;
  indexing_progress?: number;
  generation_paused?: boolean;
  pause_status?: string | null;
  easy?: DifficultyProgress;
  medium?: DifficultyProgress;
  hard?: DifficultyProgress;
};

type IndexingProgress = {
  status: string;
  progress: number;
  stage: string;
  details: string;
};

type GenerationProgress = {
  document: string;
  status: string;
  indexing: IndexingProgress;
  indexing_progress: number;
  global_progress: number;
  easy: DifficultyProgress;
  medium: DifficultyProgress;
  hard: DifficultyProgress;
  generation_message?: string;
  generation_paused?: boolean;
  pause_acknowledged?: boolean;
  pause_status?: string;
};

const ACTIVE_DOCUMENT_KEY = "webia_active_document";
const ACTIVE_PROGRESS_KEY = "webia_active_document_progress";

const ACTIVE_PROCESSING_STATUSES = [
  "pending",
  "indexing",
  "generating",
  "queued",
  "running",
  "pausing",
];

type GenerationControlAction = "pause" | "resume";

async function sendGenerationControl(
  filename: string,
  action: GenerationControlAction,
) {
  const endpoint =
    action === "pause" ? "pause-questions" : "resume-questions";

  const url =
    `${API_URL}/documents/${encodeURIComponent(filename)}/${endpoint}`;

  async function postWithToken(token: string | null) {
    const headers = new Headers();

    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    return fetch(url, {
      method: "POST",
      headers,
    });
  }

  let response = await postWithToken(
    localStorage.getItem("access_token"),
  );

  if (response.status === 401) {
    const refreshToken = localStorage.getItem("refresh_token");

    if (refreshToken) {
      try {
        const refreshResponse = await fetch(
          `${API_URL}/auth/refresh`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              refresh_token: refreshToken,
            }),
          },
        );

        if (refreshResponse.ok) {
          const refreshed = await refreshResponse.json();

          if (refreshed.access_token) {
            localStorage.setItem(
              "access_token",
              refreshed.access_token,
            );

            response = await postWithToken(
              refreshed.access_token,
            );
          }
        } else {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
        }
      } catch (error) {
        console.error(
          "Erreur de renouvellement du token :",
          error,
        );
      }
    }
  }

  const data = await response.json().catch(() => ({}));

  return {
    response,
    data,
  };
}

function getProgressPercentage(
  progress: DifficultyProgress | undefined,
): number {
  if (!progress) {
    return 0;
  }

  const current = Math.max(0, Number(progress.current) || 0);
  const target = Math.max(0, Number(progress.target) || 0);

  if (target === 0) {
    return progress.status === "completed" ? 100 : 0;
  }

  const calculatedProgress = Number.isFinite(progress.progress)
    ? progress.progress
    : (current / target) * 100;

  return Math.min(
    100,
    Math.max(0, Math.floor(calculatedProgress)),
  );
}

function DifficultyProgressBar({
  label,
  progress,
  color,
}: {
  label: string;
  progress: DifficultyProgress | undefined;
  color: string;
}) {
  const current = Math.max(0, Number(progress?.current) || 0);
  const target = Math.max(0, Number(progress?.target) || 0);
  const percentage = getProgressPercentage(progress);
  const isPaused = progress?.status === "paused";
  const isError = progress?.status === "error";

  return (
    <div
      style={{
        minWidth: 0,
        padding: "10px",
        border: "1px solid var(--border-color, #e5e7eb)",
        borderRadius: "10px",
        background: "var(--card-background, rgba(128,128,128,0.04))",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "5px",
          marginBottom: "8px",
        }}
      >
        <span
          style={{
            fontSize: "12px",
            fontWeight: 600,
            lineHeight: 1.3,
            overflowWrap: "anywhere",
          }}
        >
          {label}
        </span>

        <span
          style={{
            fontSize: "12px",
            fontWeight: 700,
            color: isError ? "#dc2626" : color,
            flexShrink: 0,
          }}
        >
          {percentage}%
        </span>
      </div>

      <div
        role="progressbar"
        aria-label={`Progression des questions ${label.toLowerCase()}`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percentage}
        style={{
          width: "100%",
          height: "6px",
          overflow: "hidden",
          borderRadius: "999px",
          background: "var(--progress-track, #e5e7eb)",
        }}
      >
        <div
          style={{
            width: `${percentage}%`,
            height: "100%",
            borderRadius: "999px",
            background: isError ? "#dc2626" : color,
            transition: "width 300ms ease",
          }}
        />
      </div>

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "4px",
          marginTop: "7px",
          fontSize: "11px",
          color: "var(--secondary-text, #6b7280)",
        }}
      >
        <span>
          {current} / {target}
        </span>

        {isPaused && <span style={{ fontWeight: 600 }}>En pause</span>}
        {isError && <span style={{ fontWeight: 600 }}>Erreur</span>}

        {progress?.status === "completed" && (
          <span style={{ fontWeight: 600 }}>Terminé</span>
        )}
      </div>
    </div>
  );
}

function isClassificationStillRunning(
  progress: GenerationProgress | null | undefined,
): boolean {
  if (!progress) {
    return false;
  }

  const percentage = Number(
    progress.indexing?.progress ?? progress.indexing_progress ?? 0,
  );

  return (
    progress.indexing?.status === "indexing" ||
    (
      progress.indexing?.stage === "categories" &&
      Number.isFinite(percentage) &&
      percentage < 100
    )
  );
}

function waitBeforeReconnect(signal: AbortSignal, delayMs: number) {
  return new Promise<void>((resolve) => {
    if (signal.aborted) {
      resolve();
      return;
    }

    const timeoutId = window.setTimeout(() => {
      signal.removeEventListener("abort", handleAbort);
      resolve();
    }, delayMs);

    function handleAbort() {
      window.clearTimeout(timeoutId);
      signal.removeEventListener("abort", handleAbort);
      resolve();
    }

    signal.addEventListener("abort", handleAbort, { once: true });
  });
}

function DocumentUpload() {
  const [message, setMessage] = useState("");
  const [viewerMessage, setViewerMessage] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [roleLoading, setRoleLoading] = useState(true);

  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loadingDocuments, setLoadingDocuments] = useState(true);
  const [deletingFiles, setDeletingFiles] = useState<string[]>([]);
  const [viewingFiles, setViewingFiles] = useState<string[]>([]);
  const [generationControlFiles, setGenerationControlFiles] =
    useState<string[]>([]);
  const [externalUploadInProgress, setExternalUploadInProgress] =
    useState(false);

  const [generationProgress, setGenerationProgress] =
    useState<GenerationProgress | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const streamControllerRef = useRef<AbortController | null>(null);
  const streamFilenameRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadUserRole() {
      try {
        const { response, data } = await getProfile();

        if (!response.ok || cancelled) {
          return;
        }

        const role =
          data?.role ??
          data?.user?.role ??
          data?.profile?.role;

        if (!cancelled) {
          setIsAdmin(
            typeof role === "string" &&
              role.trim().toLowerCase() === "admin",
          );
        }
      } catch (error) {
        console.error(
          "Impossible de récupérer le rôle de l'utilisateur :",
          error,
        );

        if (!cancelled) {
          setIsAdmin(false);
        }
      } finally {
        if (!cancelled) {
          setRoleLoading(false);
        }
      }
    }

    void loadUserRole();

    return () => {
      cancelled = true;
    };
  }, []);

  function stopProgressStream() {
    if (streamControllerRef.current) {
      streamControllerRef.current.abort();
      streamControllerRef.current = null;
    }

    streamFilenameRef.current = null;
  }

  function saveActiveDocument(filename: string) {
    localStorage.setItem(ACTIVE_DOCUMENT_KEY, filename);
  }

  function clearActiveDocument() {
    localStorage.removeItem(ACTIVE_DOCUMENT_KEY);
  }

  function removeActiveDocument() {
    localStorage.removeItem(ACTIVE_DOCUMENT_KEY);
    localStorage.removeItem(ACTIVE_PROGRESS_KEY);
  }

  function saveProgress(progress: GenerationProgress) {
    try {
      localStorage.setItem(
        ACTIVE_PROGRESS_KEY,
        JSON.stringify(progress),
      );
    } catch (error) {
      console.error(
        "Impossible de sauvegarder la progression :",
        error,
      );
    }
  }

  function loadSavedProgress(): GenerationProgress | null {
    try {
      const savedProgress = localStorage.getItem(ACTIVE_PROGRESS_KEY);

      if (!savedProgress) {
        return null;
      }

      return JSON.parse(savedProgress) as GenerationProgress;
    } catch (error) {
      console.error(
        "Impossible de récupérer la progression sauvegardée :",
        error,
      );

      return null;
    }
  }

  function updateDocumentProgress(progress: GenerationProgress) {
    setDocuments((currentDocuments) =>
      currentDocuments.map((document) => {
        if (document.file !== progress.document) {
          return document;
        }

        return {
          ...document,
          processing_status: progress.status,
          indexing_progress: progress.indexing_progress,
          global_progress: progress.global_progress,
          generation_paused: progress.generation_paused,
          pause_status: progress.pause_status ?? null,
          easy: progress.easy,
          medium: progress.medium,
          hard: progress.hard,
        };
      }),
    );
  }

  function isGenerationPaused(progress: GenerationProgress | null) {
    return (
      progress !== null &&
      (
        progress.status === "paused" ||
        progress.pause_status === "paused" ||
        progress.generation_paused === true
      )
    );
  }

  function isDocumentProcessing() {
    if (uploading) {
      return true;
    }

    if (isGenerationPaused(generationProgress)) {
      return false;
    }

    return externalUploadInProgress;
  }

  function showProcessingMessage() {
    setMessage(
      "Impossible d’importer un autre document : " +
        "un document est en cours d’importation ou d’indexation. " +
        "Veuillez patienter.",
    );
  }

  function openFilePicker() {
    if (!isAdmin || roleLoading) {
      return;
    }

    if (isDocumentProcessing()) {
      showProcessingMessage();
      return;
    }

    fileInputRef.current?.click();
  }

  function getDocumentStatusLabel(status: string | undefined) {
    switch (status) {
      case "pending":
        return "En attente";
      case "indexing":
        return "Indexation en cours";
      case "generating":
      case "running":
        return "Génération des questions";
      case "queued":
        return "Génération en attente";
      case "pausing":
        return "Pause demandée";
      case "paused":
        return "Génération en pause";
      case "waiting_manual":
        return "Prêt — génération manuelle";
      case "completed":
        return "Disponible";
      case "error":
        return "Erreur";
      case "not_started":
      case undefined:
        return "En attente";
      default:
        return status;
    }
  }

  function getDocumentStatusDescription(document: DocumentItem) {
    switch (document.processing_status) {
      case "pending":
        return "Le traitement va commencer.";
      case "indexing":
        return "Le document est en cours d’indexation.";
      case "generating":
      case "running":
        return "Les questions sont en cours de génération.";
      case "queued":
        return "La génération des questions est dans la file d’attente.";
      case "pausing":
        return "La pause sera effective à la fin du lot en cours.";
      case "paused":
        return "La génération est en pause. Les questions déjà enregistrées sont conservées.";
      case "waiting_manual":
        return "Document indexé. Les questions seront créées uniquement sur demande.";
      case "completed":
        return "Document prêt à être utilisé.";
      case "error":
        return "Une erreur est survenue pendant le traitement.";
      case "not_started":
      case undefined:
        return "En attente du traitement.";
      default:
        return "Traitement du document en cours.";
    }
  }

  function getDocumentStatusClass(status: string | undefined) {
    switch (status) {
      case "pending":
        return "generation-status-pending";
      case "indexing":
        return "generation-status-indexing";
      case "generating":
      case "running":
      case "queued":
      case "pausing":
        return "generation-status-generating";
      case "paused":
      case "completed":
      case "waiting_manual":
        return "generation-status-completed";
      case "error":
        return "generation-status-error";
      default:
        return "generation-status-pending";
    }
  }

  function handleProgressUpdate(progress: GenerationProgress) {
    setGenerationProgress(progress);
    saveProgress(progress);
    updateDocumentProgress(progress);

    const status = progress.status;

    if (
      status === "waiting_manual" &&
      !isClassificationStillRunning(progress)
    ) {
      setMessage(
        `${progress.document} : document indexé. ` +
          "Cliquez sur « Générer les questions » pour lancer la génération.",
      );

      clearActiveDocument();
      setExternalUploadInProgress(false);
      stopProgressStream();
      return;
    }

    if (status === "pausing") {
      setMessage(
        `${progress.document} : pause demandée. Le lot en cours se terminera avant l'arrêt.`,
      );
      return;
    }

    if (isGenerationPaused(progress)) {
      setMessage(
        `${progress.document} : génération en pause. Les questions enregistrées sont conservées.`,
      );

      setExternalUploadInProgress(false);
      clearActiveDocument();
      stopProgressStream();
      return;
    }

    if (status === "completed") {
      setMessage(`${progress.document} : traitement terminé.`);
      clearActiveDocument();
      setExternalUploadInProgress(false);
      stopProgressStream();
      void loadDocuments();
      return;
    }

    if (status === "error") {
      setMessage(
        `${progress.document} : une erreur est survenue pendant le traitement.`,
      );

      clearActiveDocument();
      setExternalUploadInProgress(false);
      stopProgressStream();
      void loadDocuments();
    }
  }

  async function startProgressStream(filename: string) {
    if (
      streamFilenameRef.current === filename &&
      streamControllerRef.current
    ) {
      return;
    }

    stopProgressStream();

    const controller = new AbortController();
    streamControllerRef.current = controller;
    streamFilenameRef.current = filename;
    saveActiveDocument(filename);

    try {
      while (!controller.signal.aborted) {
        try {
          await streamDocumentProgress<GenerationProgress>(
            filename,
            (progress) => {
              if (!controller.signal.aborted) {
                handleProgressUpdate(progress);
              }
            },
            controller.signal,
          );
        } catch (error) {
          if (
            controller.signal.aborted ||
            (
              error instanceof DOMException &&
              error.name === "AbortError"
            )
          ) {
            return;
          }

          console.warn(
            `Flux SSE interrompu pour ${filename}. Nouvelle tentative en cours.`,
            error,
          );
        }

        if (controller.signal.aborted) {
          return;
        }

        // Le SSE peut se fermer lorsque le navigateur suspend l'onglet.
        // Relire l'état serveur avant de rouvrir le flux.
        try {
          const { response, data } = await getGenerationProgress(filename);

          if (controller.signal.aborted) {
            return;
          }

          if (response.ok) {
            handleProgressUpdate(data as GenerationProgress);

            // Une pause ou un statut terminal peut arrêter le suivi.
            if (controller.signal.aborted) {
              return;
            }
          }
        } catch (error) {
          if (controller.signal.aborted) {
            return;
          }

          console.warn(
            `Impossible de rafraîchir la progression de ${filename}.`,
            error,
          );
        }

        if (controller.signal.aborted) {
          return;
        }

        await waitBeforeReconnect(controller.signal, 2500);
      }
    } finally {
      if (streamControllerRef.current === controller) {
        streamControllerRef.current = null;
        streamFilenameRef.current = null;
      }
    }
  }

  async function loadDocuments() {
    setLoadingDocuments(true);

    try {
      const { response, data } = await getDocuments();

      if (!response.ok) {
        throw new Error(
          data.detail || "Impossible de récupérer les documents.",
        );
      }

      if (!Array.isArray(data.documents)) {
        throw new Error(
          "Le serveur n'a pas retourné une liste valide.",
        );
      }

      setDocuments(data.documents);
      setViewerMessage("");
    } catch (error) {
      console.error(
        "Erreur lors du chargement des documents :",
        error,
      );

      const errorMessage = error instanceof Error
        ? error.message
        : "Impossible de récupérer les documents.";

      setMessage(errorMessage);
      setViewerMessage(errorMessage);
    } finally {
      setLoadingDocuments(false);
    }
  }

  useEffect(() => {
    let mounted = true;

    void loadDocuments();

    const savedProgress = loadSavedProgress();

    if (savedProgress) {
      setGenerationProgress(savedProgress);
    }

    async function restoreActiveDocument() {
      const activeDocument = localStorage.getItem(ACTIVE_DOCUMENT_KEY);

      if (!activeDocument) {
        if (mounted) {
          setExternalUploadInProgress(false);
        }
        return;
      }

      try {
        const { response, data } =
          await getGenerationProgress(activeDocument);

        if (!mounted) {
          return;
        }

        if (!response.ok) {
          setExternalUploadInProgress(false);
          clearActiveDocument();
          return;
        }

        const progress = data as GenerationProgress;

        setGenerationProgress(progress);
        saveProgress(progress);
        updateDocumentProgress(progress);

        if (isGenerationPaused(progress)) {
          setExternalUploadInProgress(false);
          clearActiveDocument();
          return;
        }

        if (
          ACTIVE_PROCESSING_STATUSES.includes(progress.status) ||
          isClassificationStillRunning(progress)
        ) {
          setExternalUploadInProgress(true);
          void startProgressStream(activeDocument);
          return;
        }

        setExternalUploadInProgress(false);
        clearActiveDocument();
      } catch (error) {
        if (!mounted) {
          return;
        }

        console.error(
          `Impossible de restaurer la progression de ${activeDocument} :`,
          error,
        );

        setExternalUploadInProgress(false);
        clearActiveDocument();
      }
    }

    async function restoreSpecificDocument(filename: string) {
      try {
        const { response, data } =
          await getGenerationProgress(filename);

        if (!mounted) {
          return;
        }

        if (!response.ok) {
          setExternalUploadInProgress(false);
          clearActiveDocument();
          return;
        }

        const progress = data as GenerationProgress;

        setGenerationProgress(progress);
        saveProgress(progress);
        updateDocumentProgress(progress);

        if (isGenerationPaused(progress)) {
          setExternalUploadInProgress(false);
          clearActiveDocument();
          return;
        }

        if (
          ACTIVE_PROCESSING_STATUSES.includes(progress.status) ||
          isClassificationStillRunning(progress)
        ) {
          setExternalUploadInProgress(true);
          void startProgressStream(filename);
        } else {
          setExternalUploadInProgress(false);
          clearActiveDocument();
        }
      } catch (error) {
        console.error(
          `Impossible de vérifier ${filename} :`,
          error,
        );

        if (mounted) {
          setExternalUploadInProgress(false);
          clearActiveDocument();
        }
      }
    }

    function handleStorageChange(event: StorageEvent) {
      if (event.key === ACTIVE_DOCUMENT_KEY) {
        if (event.newValue) {
          void restoreSpecificDocument(event.newValue);
        } else {
          setExternalUploadInProgress(false);
          stopProgressStream();
        }
      }

      if (event.key === ACTIVE_PROGRESS_KEY && event.newValue) {
        try {
          const progress = JSON.parse(
            event.newValue,
          ) as GenerationProgress;

          if (mounted) {
            setGenerationProgress(progress);
            updateDocumentProgress(progress);

            if (isGenerationPaused(progress)) {
              setExternalUploadInProgress(false);
            }
          }
        } catch (error) {
          console.error(
            "Impossible de lire la progression partagée :",
            error,
          );
        }
      }
    }

    void restoreActiveDocument();

    window.addEventListener("storage", handleStorageChange);

    return () => {
      mounted = false;

      window.removeEventListener("storage", handleStorageChange);
      stopProgressStream();
    };
  }, []);

  async function handleViewPdf(filename: string) {
    setViewerMessage("");

    const previewWindow = window.open("", "_blank");

    if (!previewWindow) {
      const errorMessage =
        "Le navigateur a bloqué l’ouverture du PDF. Autorisez les fenêtres contextuelles puis réessayez.";

      if (isAdmin) {
        setMessage(errorMessage);
      } else {
        setViewerMessage(errorMessage);
      }

      return;
    }

    previewWindow.document.title = `Chargement de ${filename}`;
    previewWindow.document.body.innerHTML = "";
    previewWindow.document.body.style.fontFamily = "sans-serif";
    previewWindow.document.body.style.padding = "24px";
    previewWindow.document.body.textContent =
      `Chargement du PDF « ${filename} »...`;

    setViewingFiles((current) =>
      current.includes(filename) ? current : [...current, filename],
    );

    try {
      const response = await getDocumentPdf(filename);

      if (!response.ok) {
        let errorMessage = "Impossible d’ouvrir ce PDF.";

        try {
          const data = await response.json();
          errorMessage = data.detail || errorMessage;
        } catch {
          // Le serveur n'a pas nécessairement renvoyé du JSON.
        }

        throw new Error(errorMessage);
      }

      const blob = await response.blob();

      if (blob.size === 0) {
        throw new Error("Le fichier PDF reçu est vide.");
      }

      const pdfUrl = URL.createObjectURL(
        new Blob([blob], { type: "application/pdf" }),
      );

      previewWindow.addEventListener(
        "beforeunload",
        () => URL.revokeObjectURL(pdfUrl),
        { once: true },
      );

      previewWindow.location.replace(pdfUrl);
    } catch (error) {
      previewWindow.close();

      const errorMessage = error instanceof Error
        ? error.message
        : `Impossible d’ouvrir ${filename}.`;

      if (isAdmin) {
        setMessage(errorMessage);
      } else {
        setViewerMessage(errorMessage);
      }
    } finally {
      setViewingFiles((current) =>
        current.filter((file) => file !== filename),
      );
    }
  }

  async function processFile(file: File) {
    if (!isAdmin || roleLoading) {
      setMessage("Seuls les administrateurs peuvent importer des documents.");
      return;
    }

    if (!file) {
      return;
    }

    if (isDocumentProcessing()) {
      showProcessingMessage();
      return;
    }

    if (
      file.type !== "application/pdf" &&
      !file.name.toLowerCase().endsWith(".pdf")
    ) {
      setMessage("Veuillez sélectionner un fichier PDF.");
      return;
    }

    const filename = file.name;

    setUploading(true);
    setExternalUploadInProgress(true);
    setMessage(`${filename} : préparation de l’import...`);
    setGenerationProgress(null);

    stopProgressStream();
    saveActiveDocument(filename);
    void startProgressStream(filename);

    try {
      const { response, data } = await uploadDocument(file);

      if (response.ok) {
        const returnedFilename = data.file || data.filename || filename;

        if (returnedFilename !== filename) {
          stopProgressStream();
          saveActiveDocument(returnedFilename);
          void startProgressStream(returnedFilename);
        }

        setMessage(
          data.question_banks?.status === "waiting_manual"
            ? `${returnedFilename} est indexé. Aucune question n’a été générée. Utilisez le bouton « Générer les questions » lorsque vous le souhaitez.`
            : data.skipped
              ? `${returnedFilename} est déjà disponible.`
              : `${returnedFilename} a été importé et indexé.`,
        );

        await loadDocuments();

        const latestProgress = loadSavedProgress();

        if (latestProgress?.document === returnedFilename) {
          setGenerationProgress(latestProgress);
        }
      } else {
        stopProgressStream();
        removeActiveDocument();
        setExternalUploadInProgress(false);
        setGenerationProgress(null);
        setMessage(data.detail || "Une erreur est survenue pendant l’import.");
      }
    } catch (error) {
      console.error("Erreur lors de l’upload :", error);

      stopProgressStream();
      removeActiveDocument();
      setExternalUploadInProgress(false);
      setGenerationProgress(null);

      setMessage(
        error instanceof Error
          ? error.message
          : "Impossible de communiquer avec le serveur.",
      );
    } finally {
      setUploading(false);
    }
  }

  async function handleFileChange(
    event: ChangeEvent<HTMLInputElement>,
  ) {
    const selectedFile = event.target.files?.[0];

    if (!selectedFile) {
      return;
    }

    await processFile(selectedFile);
    event.target.value = "";
  }

  function handleDragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();

    if (isAdmin && !roleLoading) {
      setDragging(!isDocumentProcessing());
    }
  }

  function handleDragLeave(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
  }

  async function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);

    if (!isAdmin || roleLoading) {
      return;
    }

    if (isDocumentProcessing()) {
      showProcessingMessage();
      return;
    }

    const droppedFile = event.dataTransfer.files?.[0];

    if (droppedFile) {
      await processFile(droppedFile);
    }
  }

  async function handleGenerateQuestions(filename: string) {
    if (!isAdmin || roleLoading) {
      setMessage("Seuls les administrateurs peuvent générer des questions.");
      return;
    }

    if (isDocumentProcessing()) {
      showProcessingMessage();
      return;
    }

    const confirmed = window.confirm(
      `Lancer la génération des questions pour « ${filename} » ?\n\n` +
        "Cette action peut prendre du temps. " +
        "Elle lance la génération pour les catégories du document " +
        "et les trois difficultés (facile, moyen, difficile).",
    );

    if (!confirmed) {
      return;
    }

    setMessage(`Mise en file de la génération pour ${filename}...`);
    setExternalUploadInProgress(true);
    saveActiveDocument(filename);

    try {
      const { response, data } =
        await generateDocumentQuestions(filename);

      if (!response.ok) {
        throw new Error(
          data.detail || "Impossible de lancer la génération des questions.",
        );
      }

      setMessage(
        data.message ||
          `La génération des questions pour ${filename} a été lancée.`,
      );

      await loadDocuments();
      void startProgressStream(filename);
    } catch (error) {
      stopProgressStream();
      removeActiveDocument();
      setExternalUploadInProgress(false);

      setMessage(
        error instanceof Error
          ? error.message
          : "Impossible de lancer la génération des questions.",
      );
    }
  }

  async function handleGenerationControl(
    filename: string,
    action: GenerationControlAction,
  ) {
    if (!isAdmin || roleLoading) {
      setMessage("Seuls les administrateurs peuvent contrôler la génération.");
      return;
    }

    setGenerationControlFiles((current) =>
      current.includes(filename) ? current : [...current, filename],
    );

    try {
      const { response, data } =
        await sendGenerationControl(filename, action);

      if (!response.ok) {
        throw new Error(
          data.detail ||
            (action === "pause"
              ? "Impossible de mettre la génération en pause."
              : "Impossible de reprendre la génération."),
        );
      }

      const progress = data as GenerationProgress;

      if (progress.document) {
        setGenerationProgress(progress);
        saveProgress(progress);
        updateDocumentProgress(progress);
      }

      setMessage(
        data.message ||
          (action === "pause"
            ? `Pause demandée pour ${filename}.`
            : `Reprise demandée pour ${filename}.`),
      );

      if (action === "resume") {
        saveActiveDocument(filename);
        setExternalUploadInProgress(true);
        void startProgressStream(filename);
      } else if (isGenerationPaused(progress)) {
        setExternalUploadInProgress(false);
        clearActiveDocument();
        stopProgressStream();
      } else {
        setMessage(
          data.message ||
            `Pause demandée pour ${filename}. Le lot en cours doit se terminer.`,
        );
      }

      await loadDocuments();
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Impossible de modifier l'état de la génération.",
      );
    } finally {
      setGenerationControlFiles((current) =>
        current.filter((file) => file !== filename),
      );
    }
  }

  async function handleDelete(filename: string) {
    if (!isAdmin || roleLoading) {
      setMessage("Seuls les administrateurs peuvent supprimer des documents.");
      return;
    }

    const confirmed = window.confirm(
      `Voulez-vous vraiment supprimer "${filename}" ?\n\n` +
        "Cette action supprimera définitivement le document.",
    );

    if (!confirmed) {
      return;
    }

    setDeletingFiles((current) =>
      current.includes(filename) ? current : [...current, filename],
    );

    setMessage(`Suppression de ${filename} en cours...`);

    try {
      const { response, data } = await deleteDocument(filename);

      if (!response.ok) {
        throw new Error(
          data.detail || "Impossible de supprimer le document.",
        );
      }

      if (generationProgress?.document === filename) {
        stopProgressStream();
        removeActiveDocument();
        setExternalUploadInProgress(false);
        setGenerationProgress(null);
      }

      setMessage(data.message || `${filename} supprimé avec succès.`);
      await loadDocuments();
    } catch (error) {
      console.error("Erreur lors de la suppression :", error);

      setMessage(
        error instanceof Error
          ? error.message
          : "Impossible de supprimer le document.",
      );
    } finally {
      setDeletingFiles((current) =>
        current.filter((file) => file !== filename),
      );
    }
  }

  const documentProcessing = isDocumentProcessing();

  const indexingIsActive =
    isAdmin &&
    !roleLoading &&
    generationProgress !== null &&
    !["completed", "error", "paused"].includes(
      generationProgress.status,
    ) &&
    (
      ["pending", "indexing"].includes(generationProgress.status) ||
      isClassificationStillRunning(generationProgress)
    );

  const rawIndexingPercent = Number(
    generationProgress?.indexing?.progress ??
      generationProgress?.indexing_progress ??
      0,
  );

  const indexingPercent = Math.min(
    100,
    Math.max(
      0,
      Number.isFinite(rawIndexingPercent)
        ? Math.floor(rawIndexingPercent)
        : 0,
    ),
  );

  const indexingDetails =
    generationProgress?.indexing?.details ||
    "Préparation de la classification...";

  const viewerMode = !isAdmin || roleLoading;

  return (
    <div
      className={`document-upload ${
        viewerMode ? "document-upload-viewer" : "document-upload-admin"
      }`}
    >
      {isAdmin && !roleLoading && (
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,application/pdf"
          onChange={handleFileChange}
          style={{ display: "none" }}
        />
      )}

      {isAdmin && !roleLoading && (
        <div
          className={`document-dropzone ${
            dragging ? "document-dropzone-dragging" : ""
          } ${documentProcessing ? "document-dropzone-loading" : ""}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <div className="document-dropzone-icon">📄</div>

          <h3>
            {documentProcessing
              ? "Importation en cours..."
              : dragging
                ? "Déposez votre PDF ici"
                : "Ajoutez un document PDF"}
          </h3>

          <p
            style={{
              color: documentProcessing ? "#888888" : undefined,
            }}
          >
            {documentProcessing
              ? "Impossible d’importer un autre document : un document est en cours d’importation ou d’indexation."
              : "Glissez-déposez votre PDF dans cette zone"}
          </p>

          {!documentProcessing && (
            <span className="document-dropzone-or">ou</span>
          )}

          <button
            type="button"
            className="document-upload-button"
            onClick={openFilePicker}
            disabled={documentProcessing}
            style={
              documentProcessing
                ? { opacity: 0.5, cursor: "not-allowed" }
                : undefined
            }
          >
            {documentProcessing
              ? "Importation en cours..."
              : "📄 Ajouter un PDF"}
          </button>
        </div>
      )}

      {isAdmin && !roleLoading && message && (
        <p className="document-upload-message">{message}</p>
      )}

      {viewerMode && viewerMessage && (
        <p className="document-upload-message">{viewerMessage}</p>
      )}

      {indexingIsActive && generationProgress && (
        <section
          aria-live="polite"
          aria-label="Progression de la classification des chunks"
          style={{
            margin: "16px 0",
            padding: "16px",
            border: "1px solid #d1d5db",
            borderRadius: "10px",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: "12px",
              marginBottom: "10px",
            }}
          >
            <strong>Classification : {generationProgress.document}</strong>
            <strong>{indexingPercent}%</strong>
          </div>

          <div
            role="progressbar"
            aria-label="Progression de la classification"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={indexingPercent}
            style={{
              width: "100%",
              height: "12px",
              overflow: "hidden",
              borderRadius: "999px",
              backgroundColor: "#e5e7eb",
            }}
          >
            <div
              style={{
                width: `${indexingPercent}%`,
                height: "100%",
                borderRadius: "999px",
                backgroundColor: "#16a34a",
                transition: "width 250ms ease",
              }}
            />
          </div>

          <p
            style={{
              margin: "10px 0 0",
              overflowWrap: "anywhere",
            }}
          >
            {indexingDetails}
          </p>
        </section>
      )}

      <section className="document-list">
        <div className="document-list-header">
          <div>
            <h2>
              {viewerMode ? "Bibliothèque de documents" : "Documents disponibles"}
            </h2>

            <p>
              {viewerMode
                ? "Consultez les documents PDF disponibles."
                : "Documents actuellement disponibles sur la plateforme."}
            </p>
          </div>

          {isAdmin && !roleLoading && (
            <span className="document-count">{documents.length}</span>
          )}
        </div>

        {loadingDocuments ? (
          <p className="document-list-empty">Chargement des documents...</p>
        ) : documents.length === 0 ? (
          <p className="document-list-empty">
            Aucun document n'est actuellement disponible.
          </p>
        ) : (
          <div className="document-items">
            {documents.map((document) => {
              const viewing = viewingFiles.includes(document.file);

              if (viewerMode) {
                return (
                  <article
                    className="document-item document-item-viewer"
                    key={document.id}
                  >
                    <div className="document-item-icon" aria-hidden="true">
                      📄
                    </div>

                    <div className="document-item-info">
                      <h3>{document.file}</h3>
                    </div>

                    <button
                      type="button"
                      className="document-view-button"
                      onClick={() => void handleViewPdf(document.file)}
                      disabled={viewing}
                      title={`Consulter ${document.file}`}
                    >
                      {viewing ? "Ouverture..." : "Consulter"}
                    </button>
                  </article>
                );
              }

              const activeFilename = localStorage.getItem(ACTIVE_DOCUMENT_KEY);

              const progressForDocument =
                generationProgress?.document === document.file
                  ? generationProgress
                  : null;

              const generationPaused =
                isGenerationPaused(progressForDocument) ||
                document.generation_paused === true ||
                document.pause_status === "paused";

              const isActiveProcessingDocument =
                activeFilename === document.file &&
                (
                  uploading ||
                  (externalUploadInProgress && !generationPaused) ||
                  (
                    progressForDocument !== null &&
                    ACTIVE_PROCESSING_STATUSES.includes(progressForDocument.status)
                  )
                );

              const status = generationPaused
                ? "paused"
                : isActiveProcessingDocument
                  ? (
                      progressForDocument &&
                      [
                        "pending",
                        "indexing",
                        "generating",
                        "queued",
                        "running",
                        "pausing",
                      ].includes(progressForDocument.status)
                        ? progressForDocument.status
                        : "indexing"
                    )
                  : progressForDocument?.status || document.processing_status;

              const displayedDocument = {
                ...document,
                processing_status: status,
              };

              const statusLabel = getDocumentStatusLabel(status);

              const statusDescription =
                getDocumentStatusDescription(displayedDocument);

              const statusClass = getDocumentStatusClass(status);
              const deleting = deletingFiles.includes(document.file);

              const generationActive = [
                "queued",
                "running",
                "generating",
                "pausing",
                "paused",
              ].includes(status || "");

              const generationPausing = status === "pausing";

              const generationControlPending =
                generationControlFiles.includes(document.file);

              const otherProcessingDocument =
                documentProcessing && activeFilename !== document.file;

              const generationInProgress = [
                "pending",
                "indexing",
                "generating",
                "queued",
                "running",
                "pausing",
                "paused",
              ].includes(status || "");

              const easyProgress = progressForDocument?.easy ?? document.easy;
              const mediumProgress = progressForDocument?.medium ?? document.medium;
              const hardProgress = progressForDocument?.hard ?? document.hard;

              const hasQuestionProgress = [
                easyProgress,
                mediumProgress,
                hardProgress,
              ].some(
                (progress) =>
                  progress !== undefined &&
                  (
                    progress.target > 0 ||
                    progress.current > 0 ||
                    [
                      "running",
                      "queued",
                      "completed",
                      "paused",
                      "incomplete",
                      "error",
                    ].includes(progress.status)
                  ),
              );

              const showQuestionProgress =
                hasQuestionProgress &&
                status !== "waiting_manual" &&
                status !== "indexing" &&
                status !== "pending" &&
                status !== "not_started";

              return (
                <div className="document-item" key={document.id}>
                  <button
                    type="button"
                    className="document-item-icon"
                    onClick={() => void handleViewPdf(document.file)}
                    disabled={viewing || deleting}
                    title={`Consulter le PDF ${document.file}`}
                    aria-label={`Consulter le PDF ${document.file}`}
                    style={{
                      border: "none",
                      cursor: viewing || deleting ? "wait" : "pointer",
                      background: "transparent",
                      padding: 0,
                      font: "inherit",
                      flexShrink: 0,
                    }}
                  >
                    {viewing ? "⏳" : "📄"}
                  </button>

                  <div className="document-item-info">
                    <h3>{document.file}</h3>
                    <p>{statusDescription}</p>

                    <div className="document-item-status">
                      <span className={`generation-status ${statusClass}`}>
                        {statusLabel}
                      </span>
                    </div>

                    <button
                      type="button"
                      className="document-generate-button"
                      onClick={() => void handleGenerateQuestions(document.file)}
                      disabled={
                        deleting ||
                        uploading ||
                        otherProcessingDocument ||
                        generationInProgress
                      }
                      title={`Générer les questions pour ${document.file}`}
                    >
                      {generationPaused
                        ? "Génération en pause"
                        : generationInProgress
                          ? "Génération en cours..."
                          : "▶ Générer les questions"}
                    </button>

                    {showQuestionProgress && (
                      <section
                        aria-label={`Progression des questions pour ${document.file}`}
                        aria-live="polite"
                        style={{
                          width: "100%",
                          marginTop: "12px",
                        }}
                      >
                        <div
                          style={{
                            marginBottom: "8px",
                            fontSize: "12px",
                            fontWeight: 600,
                          }}
                        >
                          Progression des questions
                        </div>

                        <div
                          style={{
                            display: "grid",
                            gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
                            gap: "8px",
                          }}
                        >
                          <DifficultyProgressBar
                            label="Faciles"
                            progress={easyProgress}
                            color="#16A34A"
                          />

                          <DifficultyProgressBar
                            label="Intermédiaires"
                            progress={mediumProgress}
                            color="#D97706"
                          />

                          <DifficultyProgressBar
                            label="Difficiles"
                            progress={hardProgress}
                            color="#7C3AED"
                          />
                        </div>
                      </section>
                    )}

                    {generationActive && (
                      <button
                        type="button"
                        className="document-generate-button"
                        onClick={() =>
                          void handleGenerationControl(
                            document.file,
                            generationPaused ? "resume" : "pause",
                          )
                        }
                        disabled={
                          deleting ||
                          uploading ||
                          generationControlPending ||
                          generationPausing
                        }
                        title={
                          generationPaused
                            ? `Reprendre la génération pour ${document.file}`
                            : `Mettre en pause la génération pour ${document.file}`
                        }
                      >
                        {generationControlPending || generationPausing
                          ? "⏳ Pause en cours..."
                          : generationPaused
                            ? "▶ Reprendre"
                            : "⏸ Mettre en pause"}
                      </button>
                    )}
                  </div>

                  <button
                    type="button"
                    className="document-delete-button"
                    onClick={() => void handleDelete(document.file)}
                    disabled={deleting}
                    title={`Supprimer ${document.file}`}
                  >
                    {deleting ? "⏳" : "🗑️"}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}

export default DocumentUpload;