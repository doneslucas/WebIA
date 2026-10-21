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
  deleteDocument,
  getGenerationProgress,
  generateDocumentQuestions,
  streamDocumentProgress,
} from "../services/api";

import "./DocumentUpload.css";

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
const API_URL = "http://127.0.0.1:8000";

type GenerationControlAction = "pause" | "resume";

const ACTIVE_PROCESSING_STATUSES = [
  "pending",
  "indexing",
  "generating",
  "queued",
  "running",
  "pausing",
];

async function sendGenerationControl(
  filename: string,
  action: GenerationControlAction,
) {
  const endpoint =
    action === "pause"
      ? "pause-questions"
      : "resume-questions";

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

function DocumentUpload() {
  const [message, setMessage] = useState("");
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loadingDocuments, setLoadingDocuments] = useState(true);
  const [deletingFiles, setDeletingFiles] = useState<string[]>([]);
  const [generationControlFiles, setGenerationControlFiles] =
    useState<string[]>([]);
  const [externalUploadInProgress, setExternalUploadInProgress] =
    useState(false);

  const [generationProgress, setGenerationProgress] =
    useState<GenerationProgress | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const streamControllerRef = useRef<AbortController | null>(null);
  const streamFilenameRef = useRef<string | null>(null);

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
      const savedProgress = localStorage.getItem(
        ACTIVE_PROGRESS_KEY,
      );

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

  function isGenerationPaused(
    progress: GenerationProgress | null,
  ) {
    return (
      progress !== null &&
      (
        progress.status === "paused" ||
        progress.pause_status === "paused" ||
        progress.generation_paused === true
      )
    );
  }

  // Une génération en pause n'est pas une indexation active.
  // Une ancienne clé localStorage ne suffit pas à bloquer l'import.
  function isDocumentProcessing() {
    if (uploading) {
      return true;
    }

    if (isGenerationPaused(generationProgress)) {
      return false;
    }

    if (externalUploadInProgress) {
      return true;
    }

    return (
      generationProgress !== null &&
      ACTIVE_PROCESSING_STATUSES.includes(
        generationProgress.status,
      )
    );
  }

  function showProcessingMessage() {
    setMessage(
      "Impossible d’importer un autre document : " +
        "un document est en cours d’importation ou d’indexation. " +
        "Veuillez patienter.",
    );
  }

  function openFilePicker() {
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
        return "generation-status-completed";

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

    if (status === "waiting_manual") {
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
      await streamDocumentProgress<GenerationProgress>(
        filename,
        (progress) => {
          if (controller.signal.aborted) {
            return;
          }

          handleProgressUpdate(progress);
        },
        controller.signal,
      );
    } catch (error) {
      if (
        error instanceof DOMException &&
        error.name === "AbortError"
      ) {
        return;
      }

      if (controller.signal.aborted) {
        return;
      }

      console.error(
        `Erreur du flux SSE pour ${filename} :`,
        error,
      );

      setMessage(
        `Le suivi en temps réel de ${filename} a été interrompu. ` +
          "La progression enregistrée est conservée.",
      );
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
          data.detail ||
            "Impossible de récupérer les documents.",
        );
      }

      if (!Array.isArray(data.documents)) {
        throw new Error(
          "Le serveur n'a pas retourné une liste valide.",
        );
      }

      setDocuments(data.documents);
    } catch (error) {
      console.error(
        "Erreur lors du chargement des documents :",
        error,
      );

      setMessage(
        error instanceof Error
          ? error.message
          : "Impossible de récupérer les documents.",
      );
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
      const activeDocument = localStorage.getItem(
        ACTIVE_DOCUMENT_KEY,
      );

      if (!activeDocument) {
        if (mounted) {
          setExternalUploadInProgress(false);
        }
        return;
      }

      try {
        // On vérifie l'état réel du backend avant de verrouiller
        // à nouveau l'interface après un redémarrage.
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
          ACTIVE_PROCESSING_STATUSES.includes(progress.status)
        ) {
          setExternalUploadInProgress(true);
          void startProgressStream(activeDocument);
          return;
        }

        // Le backend confirme qu'il n'y a pas de traitement actif.
        // On retire uniquement le verrou du navigateur, pas la progression.
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

        // Une ancienne clé ne doit pas bloquer indéfiniment
        // l'interface lorsque le statut ne peut pas être récupéré.
        setExternalUploadInProgress(false);
        clearActiveDocument();
      }
    }

    void restoreActiveDocument();

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
          ACTIVE_PROCESSING_STATUSES.includes(progress.status)
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

    window.addEventListener("storage", handleStorageChange);

    return () => {
      mounted = false;

      window.removeEventListener(
        "storage",
        handleStorageChange,
      );

      stopProgressStream();
    };
  }, []);

  async function processFile(file: File) {
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

    // Le flux suit l'indexation dès que le serveur expose sa progression.
    void startProgressStream(filename);

    try {
      const { response, data } = await uploadDocument(file);

      if (response.ok) {
        const returnedFilename =
          data.file ||
          data.filename ||
          filename;

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

        if (
          latestProgress &&
          latestProgress.document === returnedFilename
        ) {
          setGenerationProgress(latestProgress);
        }
      } else {
        stopProgressStream();
        removeActiveDocument();

        setExternalUploadInProgress(false);
        setGenerationProgress(null);

        setMessage(
          data.detail ||
            "Une erreur est survenue pendant l’import.",
        );
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
    setDragging(!isDocumentProcessing());
  }

  function handleDragLeave(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
  }

  async function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);

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
          data.detail ||
            "Impossible de lancer la génération des questions.",
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
    setGenerationControlFiles((current) =>
      current.includes(filename)
        ? current
        : [...current, filename],
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
        // La pause est demandée, mais le lot actuel peut encore finir.
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
    const confirmed = window.confirm(
      `Voulez-vous vraiment supprimer "${filename}" ?\n\n` +
        "Cette action supprimera définitivement le document.",
    );

    if (!confirmed) {
      return;
    }

    setDeletingFiles((current) =>
      current.includes(filename)
        ? current
        : [...current, filename],
    );

    setMessage(`Suppression de ${filename} en cours...`);

    try {
      const { response, data } = await deleteDocument(filename);

      if (!response.ok) {
        throw new Error(
          data.detail ||
            "Impossible de supprimer le document.",
        );
      }

      if (generationProgress?.document === filename) {
        stopProgressStream();
        removeActiveDocument();

        setExternalUploadInProgress(false);
        setGenerationProgress(null);
      }

      setMessage(
        data.message ||
          `${filename} supprimé avec succès.`,
      );

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
    generationProgress !== null &&
    generationProgress.indexing?.status === "indexing" &&
    generationProgress.indexing?.stage === "categories" &&
    ["pending", "indexing"].includes(generationProgress.status);

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

  return (
    <div className="document-upload">
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,application/pdf"
        onChange={handleFileChange}
        style={{ display: "none" }}
      />

      <div
        className={`document-dropzone ${
          dragging ? "document-dropzone-dragging" : ""
        } ${
          documentProcessing ? "document-dropzone-loading" : ""
        }`}
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
              ? {
                  opacity: 0.5,
                  cursor: "not-allowed",
                }
              : undefined
          }
        >
          {documentProcessing
            ? "Importation en cours..."
            : "📄 Ajouter un PDF"}
        </button>
      </div>

      {message && (
        <p className="document-upload-message">
          {message}
        </p>
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
            <strong>
              Classification : {generationProgress.document}
            </strong>

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
            <h2>Documents disponibles</h2>
            <p>
              Documents actuellement disponibles sur la plateforme.
            </p>
          </div>

          <span className="document-count">
            {documents.length}
          </span>
        </div>

        {loadingDocuments ? (
          <p className="document-list-empty">
            Chargement des documents...
          </p>
        ) : documents.length === 0 ? (
          <p className="document-list-empty">
            Aucun document n'est actuellement disponible.
          </p>
        ) : (
          <div className="document-items">
            {documents.map((document) => {
              const activeFilename = localStorage.getItem(
                ACTIVE_DOCUMENT_KEY,
              );

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
                  (
                    externalUploadInProgress &&
                    !generationPaused
                  ) ||
                  (
                    progressForDocument !== null &&
                    ACTIVE_PROCESSING_STATUSES.includes(
                      progressForDocument.status,
                    )
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
                  : progressForDocument?.status ||
                    document.processing_status;

              const displayedDocument = {
                ...document,
                processing_status: status,
              };

              const statusLabel =
                getDocumentStatusLabel(status);

              const statusDescription =
                getDocumentStatusDescription(displayedDocument);

              const statusClass =
                getDocumentStatusClass(status);

              const deleting =
                deletingFiles.includes(document.file);

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
                documentProcessing &&
                activeFilename !== document.file;

              const generationInProgress =
                [
                  "pending",
                  "indexing",
                  "generating",
                  "queued",
                  "running",
                  "pausing",
                  "paused",
                ].includes(status || "");

              return (
                <div
                  className="document-item"
                  key={document.id}
                >
                  <div className="document-item-icon">📄</div>

                  <div className="document-item-info">
                    <h3>{document.file}</h3>

                    <p>{statusDescription}</p>

                    <div className="document-item-status">
                      <span
                        className={`generation-status ${statusClass}`}
                      >
                        {statusLabel}
                      </span>
                    </div>

                    <button
                      type="button"
                      className="document-generate-button"
                      onClick={() =>
                        void handleGenerateQuestions(document.file)
                      }
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