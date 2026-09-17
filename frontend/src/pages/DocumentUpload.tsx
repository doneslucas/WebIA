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


type DocumentItem = {
  id: number;
  file: string;
  chunks: number;
  created_at: string | null;
};


type DifficultyProgress = {
  status: string;
  current: number;
  target: number;
  progress: number;
};


type GenerationProgress = {
  document: string;
  status: string;
  global_progress: number;
  easy: DifficultyProgress;
  medium: DifficultyProgress;
  hard: DifficultyProgress;
};


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


  function stopProgressPolling() {

    if (
      pollingRef.current !== null
    ) {

      window.clearInterval(
        pollingRef.current
      );

      pollingRef.current = null;
    }
  }


  useEffect(() => {

    loadDocuments();

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


  function openFilePicker() {

    if (loading) {
      return;
    }

    fileInputRef.current?.click();
  }


  async function checkGenerationProgress(
    filename: string
  ) {

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

      if (
        data.status === "completed"
      ) {

        setMessage(
          `${filename} : génération des questions terminée.`
        );

        stopProgressPolling();

        await loadDocuments();

        return;
      }

      if (
        data.status === "error"
      ) {

        setMessage(
          `${filename} : une erreur est survenue pendant la génération des questions.`
        );

        stopProgressPolling();
      }

    } catch (error) {

      console.error(
        "Erreur lors de la récupération de la progression :",
        error
      );
    }
  }


  function startProgressPolling(
    filename: string
  ) {

    stopProgressPolling();

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

    setLoading(true);

    setMessage(
      "Ajout du document en cours..."
    );

    setGenerationProgress(
      null
    );

    stopProgressPolling();

    try {

      const {
        response,
        data,
      } = await uploadDocument(file);

      if (response.ok) {

        const filename =
          data.file ||
          data.filename ||
          file.name;

        if (data.skipped) {

          setMessage(
            `${filename} est déjà disponible. ` +
            "Vérification de son contenu en cours..."
          );

        } else {

          setMessage(
            `${filename} a été ajouté avec succès. ` +
            "La génération des questions commence..."
          );
        }

        await loadDocuments();

        startProgressPolling(
          filename
        );

      } else {

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


  function getStatusLabel(
    status: string
  ) {

    switch (status) {

      case "pending":
        return "En attente";

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
                Génération des questions
              </h2>

              <p>
                {generationProgress.document}
              </p>

            </div>

            <div className="generation-global-value">

              {generationProgress.global_progress}%

            </div>

          </div>


          <div className="generation-global-bar">

            <div
              className="generation-global-bar-fill"
              style={{
                width:
                  `${generationProgress.global_progress}%`,
              }}
            />

          </div>


          <div className="generation-global-status">

            <span>
              État :
            </span>

            <strong>
              {getStatusLabel(
                generationProgress.status
              )}
            </strong>

          </div>


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
              (document) => (

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
                      Document disponible
                    </p>

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
              )
            )}

          </div>

        )}

      </section>

    </div>
  );
}


export default DocumentUpload;