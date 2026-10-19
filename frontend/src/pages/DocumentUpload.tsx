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
};

const ACTIVE_DOCUMENT_KEY = "webia_active_document";
const ACTIVE_PROGRESS_KEY = "webia_active_document_progress";

function DocumentUpload() {
  const [message, setMessage] = useState("");
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loadingDocuments, setLoadingDocuments] = useState(true);
  const [deletingFiles, setDeletingFiles] = useState<string[]>([]);
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
          easy: progress.easy,
          medium: progress.medium,
          hard: progress.hard,
        };
      }),
    );
  }

  function isDocumentProcessing() {
    if (uploading || externalUploadInProgress) {
      return true;
    }

    return (
      generationProgress !== null &&
      ["pending", "indexing", "generating", "queued", "running"].includes(
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
        return "generation-status-generating";
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

    const activeDocument = localStorage.getItem(
      ACTIVE_DOCUMENT_KEY,
    );

    if (activeDocument) {
      setExternalUploadInProgress(true);

      // Reprise après actualisation de la page.
      void startProgressStream(activeDocument);
    }

    function handleStorageChange(event: StorageEvent) {
      if (event.key === ACTIVE_DOCUMENT_KEY) {
        if (event.newValue) {
          setExternalUploadInProgress(true);
          void startProgressStream(event.newValue);
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
          }
        } catch (error) {
          console.error(
            "Impossible de lire la progression partagée :",
            error,
          );
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

    // Ouvre le flux avant d'attendre la réponse HTTP de l'upload :
    // l'indexation peut déjà être en cours côté serveur.
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

        // Ne pas interrompre le flux ici : il est responsable de
        // confirmer la progression finale et de sauvegarder son état.
        await loadDocuments();

        // Le flux peut avoir terminé avant que l'upload ne réponde.
        // Dans ce cas, on conserve son dernier état connu.
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

  // La barre est affichée uniquement pendant la classification des chunks.
  const indexingIsActive =
    generationProgress !== null &&
    generationProgress.indexing?.status === "indexing" &&
    generationProgress.indexing?.stage === "categories" &&
    ["pending", "indexing"].includes(generationProgress.status);

  // Le pourcentage est toujours un entier entre 0 et 100.
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

              const isActiveProcessingDocument =
                activeFilename === document.file &&
                (
                  uploading ||
                  externalUploadInProgress ||
                  (
                    generationProgress?.document === document.file &&
                    [
                      "pending",
                      "indexing",
                      "generating",
                      "queued",
                      "running",
                    ].includes(generationProgress.status)
                  )
                );

              const progressForDocument =
                generationProgress?.document === document.file
                  ? generationProgress
                  : null;

              const status = isActiveProcessingDocument
                ? (
                    progressForDocument &&
                    [
                      "pending",
                      "indexing",
                      "generating",
                      "queued",
                      "running",
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

              const statusLabel = getDocumentStatusLabel(status);

              const statusDescription =
                getDocumentStatusDescription(displayedDocument);

              const statusClass = getDocumentStatusClass(status);

              const deleting = deletingFiles.includes(document.file);

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
                        externalUploadInProgress ||
                        [
                          "pending",
                          "indexing",
                          "generating",
                          "queued",
                          "running",
                        ].includes(status || "")
                      }
                      title={`Générer les questions pour ${document.file}`}
                    >
                      {[
                        "pending",
                        "indexing",
                        "generating",
                        "queued",
                        "running",
                      ].includes(status || "")
                        ? "Génération en cours..."
                        : "▶ Générer les questions"}
                    </button>
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