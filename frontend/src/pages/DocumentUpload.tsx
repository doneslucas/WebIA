import { useRef, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import { uploadDocument } from "../services/api";
import "./DocumentUpload.css";

function DocumentUpload() {
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [dragging, setDragging] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  function openFilePicker() {
    if (loading) {
      return;
    }

    fileInputRef.current?.click();
  }

  async function processFile(file: File) {
    if (!file) {
      return;
    }

    if (
      file.type !== "application/pdf" &&
      !file.name.toLowerCase().endsWith(".pdf")
    ) {
      setMessage("Veuillez sélectionner un fichier PDF.");
      return;
    }

    setLoading(true);
    setMessage("Upload et indexation en cours...");

    try {
      const { response, data } = await uploadDocument(file);

      if (response.ok) {
        if (data.skipped) {
          setMessage(
            `${data.file} est déjà présent dans la base.`
          );
        } else {
          setMessage(
            `${data.file} ajouté avec succès (${data.chunks} chunks).`
          );
        }
      } else {
        setMessage(
          data.detail || "Une erreur est survenue."
        );
      }
    } catch (error) {
      console.error(error);

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
    const selectedFile = event.target.files?.[0];

    if (!selectedFile) {
      return;
    }

    await processFile(selectedFile);

    event.target.value = "";
  }

  function handleDragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();

    if (!loading) {
      setDragging(true);
    }
  }

  function handleDragLeave(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
  }

  async function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);

    if (loading) {
      return;
    }

    const droppedFile = event.dataTransfer.files?.[0];

    if (!droppedFile) {
      return;
    }

    await processFile(droppedFile);
  }

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
          loading ? "document-dropzone-loading" : ""
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className="document-dropzone-icon">
          📄
        </div>

        <h3>
          {loading
            ? "Traitement du PDF..."
            : dragging
            ? "Déposez votre PDF ici"
            : "Ajoutez un document PDF"}
        </h3>

        <p>
          {loading
            ? "Upload, extraction et indexation en cours..."
            : "Glissez-déposez votre PDF dans cette zone"}
        </p>

        <span className="document-dropzone-or">
          ou
        </span>

        <button
          type="button"
          className="document-upload-button"
          onClick={openFilePicker}
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
    </div>
  );
}

export default DocumentUpload;