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
} from "../services/api";

import "./DocumentUpload.css";


type DocumentItem = {
  id: number;
  file: string;
  chunks: number;
  created_at: string | null;
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

  const fileInputRef =
    useRef<HTMLInputElement>(null);


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


  useEffect(() => {

    loadDocuments();

  }, []);


  function openFilePicker() {

    if (loading) {
      return;
    }

    fileInputRef.current?.click();
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

    try {

      const {
        response,
        data,
      } = await uploadDocument(file);

      if (response.ok) {

        if (data.skipped) {

          setMessage(
            `${data.file} est déjà disponible. ` +
            "Vérification de son contenu en cours..."
          );

        } else {

          setMessage(
            `${data.file} a été ajouté avec succès. ` +
            "La préparation des questions est en cours."
          );
        }

        await loadDocuments();

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