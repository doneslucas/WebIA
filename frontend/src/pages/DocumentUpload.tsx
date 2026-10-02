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
};


const ACTIVE_DOCUMENT_KEY =
  "webia_active_document";


const ACTIVE_PROGRESS_KEY =
  "webia_active_document_progress";


function DocumentUpload() {

  const [message, setMessage] =
    useState("");

  const [loading, setLoading] =
    useState(false);

  const [dragging, setDragging] =
    useState(false);

  const [documents, setDocuments] =
    useState<DocumentItem[]>([]);

  const [loadingDocuments, setLoadingDocuments] =
    useState(true);

  const [
    generationProgress,
    setGenerationProgress,
  ] = useState<GenerationProgress | null>(
    null
  );

  const fileInputRef =
    useRef<HTMLInputElement>(null);

  const pollingRef =
    useRef<number | null>(null);

  const pollingRequestInProgressRef =
    useRef(false);


  function stopProgressPolling() {

    if (
      pollingRef.current !== null
    ) {

      window.clearInterval(
        pollingRef.current
      );

      pollingRef.current = null;
    }

    pollingRequestInProgressRef.current =
      false;
  }


  function saveActiveDocument(
    filename: string
  ) {

    localStorage.setItem(
      ACTIVE_DOCUMENT_KEY,
      filename
    );
  }


  function removeActiveDocument() {

    localStorage.removeItem(
      ACTIVE_DOCUMENT_KEY
    );

    localStorage.removeItem(
      ACTIVE_PROGRESS_KEY
    );
  }


  function saveProgress(
    progress: GenerationProgress
  ) {

    try {

      localStorage.setItem(
        ACTIVE_PROGRESS_KEY,
        JSON.stringify(progress)
      );

    } catch (error) {

      console.error(
        "Impossible de sauvegarder la progression :",
        error
      );
    }
  }


  function loadSavedProgress(): GenerationProgress | null {

    try {

      const savedProgress =
        localStorage.getItem(
          ACTIVE_PROGRESS_KEY
        );

      if (!savedProgress) {
        return null;
      }

      return JSON.parse(
        savedProgress
      ) as GenerationProgress;

    } catch (error) {

      console.error(
        "Impossible de récupérer la progression sauvegardée :",
        error
      );

      return null;
    }
  }


  useEffect(() => {

    loadDocuments();

    const activeDocument =
      localStorage.getItem(
        ACTIVE_DOCUMENT_KEY
      );

    const savedProgress =
      loadSavedProgress();

    if (savedProgress) {

      setGenerationProgress(
        savedProgress
      );
    }

    if (activeDocument) {

      startProgressPolling(
        activeDocument
      );
    }

    return () => {

      stopProgressPolling();

    };

  }, []);


  async function loadDocuments() {

    setLoadingDocuments(true);

    try {

      const {
        response,
        data,
      } = await getDocuments();

      if (!response.ok) {

        throw new Error(
          data.detail ||
          "Impossible de récupérer les documents."
        );
      }

      if (
        !Array.isArray(
          data.documents
        )
      ) {

        throw new Error(
          "Le serveur n'a pas retourné une liste valide."
        );
      }

      setDocuments(
        data.documents
      );

    } catch (error) {

      console.error(
        "Erreur lors du chargement des documents :",
        error
      );

      setMessage(
        error instanceof Error
          ? error.message
          : "Impossible de récupérer les documents."
      );

    } finally {

      setLoadingDocuments(false);
    }
  }


  function updateDocumentProgress(
    progress: GenerationProgress
  ) {

    setDocuments(
      (currentDocuments) => {

        return currentDocuments.map(
          (document) => {

            if (
              document.file !==
              progress.document
            ) {

              return document;
            }

            const progressValue =
              progress.status === "indexing"
                ? progress.indexing_progress
                : progress.global_progress;

            return {
              ...document,

              processing_status:
                progress.status,

              indexing_progress:
                progress.indexing_progress,

              global_progress:
                progressValue,

              easy:
                progress.easy,

              medium:
                progress.medium,

              hard:
                progress.hard,
            };
          }
        );
      }
    );
  }


  function openFilePicker() {

    if (loading) {
      return;
    }

    fileInputRef.current?.click();
  }


  function getStatusLabel(
    status: string
  ) {

    switch (status) {

      case "pending":
        return "En attente";

      case "indexing":
        return "Indexation en cours";

      case "generating":
        return "Génération en cours";

      case "completed":
        return "Terminé";

      case "error":
        return "Erreur";

      case "not_started":
        return "Non démarré";

      default:
        return status;
    }
  }


  function getIndexingStageLabel(
    stage: string
  ) {

    switch (stage) {

      case "starting":
        return "Préparation";

      case "hash":
        return "Calcul du hash";

      case "verification":
        return "Vérification";

      case "pdf":
        return "Lecture du PDF";

      case "chunks":
        return "Découpage en chunks";

      case "categories":
        return "Classification des catégories";

      case "embeddings":
        return "Génération des embeddings";

      case "chroma":
        return "Indexation ChromaDB";

      case "postgresql":
        return "Enregistrement PostgreSQL";

      case "completed":
        return "Indexation terminée";

      case "error":
        return "Erreur";

      default:
        return stage || "Traitement";
    }
  }


  function getDocumentStatusLabel(
    status: string | undefined
  ) {

    switch (status) {

      case "pending":
        return "En attente";

      case "indexing":
        return "Indexation en cours";

      case "generating":
        return "Génération des questions";

      case "completed":
        return "Disponible";

      case "error":
        return "Erreur de traitement";

      case "not_started":
      case undefined:
        return "Disponible";

      default:
        return status;
    }
  }


  function getDocumentStatusDescription(
    document: DocumentItem
  ) {

    switch (document.processing_status) {

      case "pending":
        return "Le traitement va commencer.";

      case "indexing":
        return "Le document est en cours d'indexation.";

      case "generating":
        return "Les questions sont en cours de génération.";

      case "completed":
        return "Document prêt à être utilisé.";

      case "error":
        return "Une erreur est survenue pendant le traitement.";

      case "not_started":
      case undefined:
        return "Document prêt à être utilisé.";

      default:
        return "Traitement du document en cours.";
    }
  }


  function getDocumentStatusClass(
    status: string | undefined
  ) {

    switch (status) {

      case "pending":
        return "generation-status-pending";

      case "indexing":
        return "generation-status-indexing";

      case "generating":
        return "generation-status-generating";

      case "completed":
        return "generation-status-completed";

      case "error":
        return "generation-status-error";

      default:
        return "generation-status-completed";
    }
  }


  async function checkGenerationProgress(
    filename: string
  ) {

    /*
     * Empêche plusieurs requêtes de progression
     * de s'exécuter en même temps.
     */
    if (
      pollingRequestInProgressRef.current
    ) {

      return;
    }

    pollingRequestInProgressRef.current =
      true;

    try {

      const {
        response,
        data,
      } = await getGenerationProgress(
        filename
      );

      if (!response.ok) {

        console.error(
          "Erreur progression :",
          data
        );

        return;
      }

      setGenerationProgress(
        data
      );

      saveProgress(
        data
      );

      /*
       * IMPORTANT :
       *
       * On ne recharge PLUS toute la liste des documents
       * à chaque seconde.
       *
       * On met uniquement à jour le document actuellement
       * suivi.
       */
      updateDocumentProgress(
        data
      );

      if (
        data.status === "completed"
      ) {

        setMessage(
          `${filename} : traitement terminé.`
        );

        stopProgressPolling();

        removeActiveDocument();

        setGenerationProgress(
          data
        );

        /*
         * Une seule actualisation finale de la liste.
         */
        await loadDocuments();

        return;
      }

      if (
        data.status === "error"
      ) {

        setMessage(
          `${filename} : une erreur est survenue pendant le traitement.`
        );

        stopProgressPolling();

        removeActiveDocument();

        /*
         * Une seule actualisation finale de la liste.
         */
        await loadDocuments();

        return;
      }

    } catch (error) {

      console.error(
        "Erreur lors de la récupération de la progression :",
        error
      );

    } finally {

      pollingRequestInProgressRef.current =
        false;
    }
  }


  function startProgressPolling(
    filename: string
  ) {

    stopProgressPolling();

    saveActiveDocument(
      filename
    );

    checkGenerationProgress(
      filename
    );

    pollingRef.current =
      window.setInterval(
        () => {

          checkGenerationProgress(
            filename
          );

        },
        1000
      );
  }


  async function processFile(
    file: File
  ) {

    if (!file) {
      return;
    }

    if (
      file.type !== "application/pdf" &&
      !file.name
        .toLowerCase()
        .endsWith(".pdf")
    ) {

      setMessage(
        "Veuillez sélectionner un fichier PDF."
      );

      return;
    }

    const filename =
      file.name;

    setLoading(true);

    setMessage(
      `${filename} : préparation de l'import...`
    );

    setGenerationProgress(
      null
    );

    stopProgressPolling();

    saveActiveDocument(
      filename
    );

    try {

      /*
       * Le suivi démarre avant l'upload.
       */
      startProgressPolling(
        filename
      );

      const {
        response,
        data,
      } = await uploadDocument(file);

      if (response.ok) {

        const returnedFilename =
          data.file ||
          data.filename ||
          filename;

        if (
          returnedFilename !== filename
        ) {

          saveActiveDocument(
            returnedFilename
          );

          stopProgressPolling();

          startProgressPolling(
            returnedFilename
          );
        }

        if (data.skipped) {

          setMessage(
            `${returnedFilename} est déjà disponible. ` +
            "Vérification de son contenu en cours..."
          );

        } else {

          setMessage(
            `${returnedFilename} a été ajouté avec succès. ` +
            "La génération des questions commence..."
          );
        }

        /*
         * Un seul rechargement après l'upload.
         */
        await loadDocuments();

      } else {

        stopProgressPolling();

        removeActiveDocument();

        setGenerationProgress(
          null
        );

        setMessage(
          data.detail ||
          "Une erreur est survenue."
        );
      }

    } catch (error) {

      console.error(
        "Erreur lors de l'upload :",
        error
      );

      stopProgressPolling();

      removeActiveDocument();

      setMessage(
        "Impossible de communiquer avec le serveur."
      );

    } finally {

      setLoading(false);
    }
  }


  async function handleFileChange(
    event: ChangeEvent<HTMLInputElement>
  ) {

    const selectedFile =
      event.target.files?.[0];

    if (!selectedFile) {
      return;
    }

    await processFile(
      selectedFile
    );

    event.target.value = "";
  }


  function handleDragOver(
    event: DragEvent<HTMLDivElement>
  ) {

    event.preventDefault();

    if (!loading) {
      setDragging(true);
    }
  }


  function handleDragLeave(
    event: DragEvent<HTMLDivElement>
  ) {

    event.preventDefault();

    setDragging(false);
  }


  async function handleDrop(
    event: DragEvent<HTMLDivElement>
  ) {

    event.preventDefault();

    setDragging(false);

    if (loading) {
      return;
    }

    const droppedFile =
      event.dataTransfer.files?.[0];

    if (!droppedFile) {
      return;
    }

    await processFile(
      droppedFile
    );
  }


  async function handleDelete(
    filename: string
  ) {

    const confirmed =
      window.confirm(
        `Voulez-vous vraiment supprimer "${filename}" ?\n\n` +
        "Cette action supprimera définitivement le document."
      );

    if (!confirmed) {
      return;
    }

    setLoading(true);

    setMessage(
      `Suppression de ${filename} en cours...`
    );

    try {

      const {
        response,
        data,
      } = await deleteDocument(
        filename
      );

      if (!response.ok) {

        throw new Error(
          data.detail ||
          "Impossible de supprimer le document."
        );
      }

      if (
        generationProgress?.document ===
        filename
      ) {

        stopProgressPolling();

        removeActiveDocument();

        setGenerationProgress(
          null
        );
      }

      setMessage(
        data.message ||
        `${filename} supprimé avec succès.`
      );

      await loadDocuments();

    } catch (error) {

      console.error(
        "Erreur lors de la suppression :",
        error
      );

      setMessage(
        error instanceof Error
          ? error.message
          : "Impossible de supprimer le document."
      );

    } finally {

      setLoading(false);
    }
  }


  function renderDifficultyProgress(
    title: string,
    progress: DifficultyProgress
  ) {

    return (
      <div className="generation-difficulty">

        <div className="generation-difficulty-header">

          <h3>
            {title}
          </h3>

          <span
            className={
              `generation-status generation-status-${progress.status}`
            }
          >
            {getStatusLabel(
              progress.status
            )}
          </span>

        </div>


        <div className="generation-progress-info">

          <span>
            {progress.current} / {progress.target}
          </span>

          <strong>
            {progress.progress}%
          </strong>

        </div>


        <div className="generation-progress-bar">

          <div
            className="generation-progress-bar-fill"
            style={{
              width:
                `${progress.progress}%`,
            }}
          />

        </div>

      </div>
    );
  }


  return (
    <div className="document-upload">

      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,application/pdf"
        onChange={handleFileChange}
        style={{
          display: "none",
        }}
      />


      <div
        className={`document-dropzone ${
          dragging
            ? "document-dropzone-dragging"
            : ""
        } ${
          loading
            ? "document-dropzone-loading"
            : ""
        }`}
        onDragOver={
          handleDragOver
        }
        onDragLeave={
          handleDragLeave
        }
        onDrop={
          handleDrop
        }
      >

        <div className="document-dropzone-icon">
          📄
        </div>


        <h3>

          {loading
            ? "Traitement du document..."
            : dragging
            ? "Déposez votre PDF ici"
            : "Ajoutez un document PDF"}

        </h3>


        <p>

          {loading
            ? "Votre document est en cours de préparation..."
            : "Glissez-déposez votre PDF dans cette zone"}

        </p>


        <span className="document-dropzone-or">
          ou
        </span>


        <button
          type="button"
          className="document-upload-button"
          onClick={
            openFilePicker
          }
          disabled={loading}
        >

          {loading
            ? "Traitement..."
            : "📄 Ajouter un PDF"}

        </button>

      </div>


      {message && (

        <p className="document-upload-message">
          {message}
        </p>

      )}


      {generationProgress && (

        <section className="generation-section">

          <div className="generation-section-header">

            <div>

              <h2>
                {generationProgress.indexing.status ===
                "indexing"
                  ? "Indexation du document"
                  : "Traitement du document"}
              </h2>

              <p>
                {generationProgress.document}
              </p>

            </div>

            <div className="generation-global-value">

              {generationProgress.indexing.status ===
              "indexing"
                ? generationProgress.indexing_progress
                : generationProgress.status ===
                  "completed"
                ? 100
                : generationProgress.global_progress}%

            </div>

          </div>


          <div className="generation-global-bar">

            <div
              className="generation-global-bar-fill"
              style={{
                width:
                  `${
                    generationProgress.indexing.status ===
                    "indexing"
                      ? generationProgress.indexing_progress
                      : generationProgress.status ===
                        "completed"
                      ? 100
                      : generationProgress.global_progress
                  }%`,
              }}
            />

          </div>


          {generationProgress.indexing.status ===
            "indexing" && (

            <div className="generation-global-status">

              <span>
                Étape :
              </span>

              <strong>
                {
                  getIndexingStageLabel(
                    generationProgress.indexing.stage
                  )
                }
              </strong>

              {generationProgress.indexing.details && (

                <span>
                  {" "}
                  —
                  {" "}
                  {generationProgress.indexing.details}
                </span>

              )}

            </div>

          )}


          {generationProgress.indexing.status ===
            "completed" &&

            generationProgress.status !==
              "completed" && (

            <div className="generation-global-status">

              <span>
                État :
              </span>

              <strong>
                Génération des questions
              </strong>

            </div>

          )}


          {generationProgress.status ===
            "completed" && (

            <div className="generation-global-status">

              <span>
                État :
              </span>

              <strong>
                Traitement terminé
              </strong>

            </div>

          )}


          {generationProgress.status ===
            "error" && (

            <div className="generation-global-status">

              <span>
                État :
              </span>

              <strong>
                Une erreur est survenue
              </strong>

            </div>

          )}


          {generationProgress.indexing.status ===
            "completed" &&

            generationProgress.status !==
              "completed" &&

            generationProgress.status !==
              "error" && (

            <div className="generation-difficulties">

              {renderDifficultyProgress(
                "Facile",
                generationProgress.easy
              )}

              {renderDifficultyProgress(
                "Moyen",
                generationProgress.medium
              )}

              {renderDifficultyProgress(
                "Difficile",
                generationProgress.hard
              )}

            </div>

          )}

        </section>

      )}


      <section className="document-list">

        <div className="document-list-header">

          <div>

            <h2>
              Documents disponibles
            </h2>

            <p>
              Documents actuellement disponibles
              sur la plateforme.
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
            Aucun document n'est actuellement
            disponible.
          </p>

        ) : (

          <div className="document-items">

            {documents.map(
              (document) => {

                const status =
                  document.processing_status;

                const statusLabel =
                  getDocumentStatusLabel(
                    status
                  );

                const statusDescription =
                  getDocumentStatusDescription(
                    document
                  );

                const statusClass =
                  getDocumentStatusClass(
                    status
                  );

                /*
                 * La barre n'est affichée que pour
                 * un document réellement en traitement.
                 */
                const isProcessing =
                  status === "pending" ||
                  status === "indexing" ||
                  status === "generating";

                const documentProgress =
                  isProcessing
                    ? (
                        status === "indexing"
                          ? document.indexing_progress
                          : document.global_progress
                      )
                    : null;

                return (

                  <div
                    className="document-item"
                    key={document.id}
                  >

                    <div className="document-item-icon">
                      📄
                    </div>


                    <div className="document-item-info">

                      <h3>
                        {document.file}
                      </h3>


                      <p>
                        {statusDescription}
                      </p>


                      <div className="document-item-status">

                        <span
                          className={
                            `generation-status ${statusClass}`
                          }
                        >
                          {statusLabel}
                        </span>

                        {documentProgress !== null && (

                          <span>
                            {documentProgress}%
                          </span>

                        )}

                      </div>


                      {documentProgress !== null && (

                        <div className="generation-progress-bar">

                          <div
                            className="generation-progress-bar-fill"
                            style={{
                              width:
                                `${documentProgress}%`,
                            }}
                          />

                        </div>

                      )}

                    </div>


                    <button
                      type="button"
                      className="document-delete-button"
                      onClick={() =>
                        handleDelete(
                          document.file
                        )
                      }
                      disabled={loading}
                      title={
                        `Supprimer ${document.file}`
                      }
                    >
                      🗑️
                    </button>

                  </div>

                );
              }
            )}

          </div>

        )}

      </section>

    </div>
  );
}


export default DocumentUpload;