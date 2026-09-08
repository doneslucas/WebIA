import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getProfile } from "../services/api";
import Navbar from "../components/Navbar";
import DocumentUpload from "./DocumentUpload";
import "./Profile.css";

function Profile() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [role, setRole] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function loadProfile() {
    setMessage("");
    setLoading(true);

    try {
      const { response, data } = await getProfile();

      if (!response.ok) {
        if (response.status === 401) {
          localStorage.removeItem("access_token");
          navigate("/login");
          return;
        }

        setMessage(
          data.detail ||
            "Erreur lors de la récupération du profil"
        );
        return;
      }

      setEmail(data.email);
      setRole(data.role);
    } catch {
      setMessage("Impossible de contacter le serveur");
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    localStorage.removeItem("access_token");
    navigate("/login");
  }

  useEffect(() => {
    loadProfile();
  }, []);

  return (
    <div className="profile-page">
      <Navbar />

      <main className="profile-container">
        <div className="profile-header">
          <h1>Mon profil</h1>

          <p>
            Gérez les informations de votre compte.
          </p>
        </div>

        <div className="profile-card">
          <div className="profile-avatar">
            👤
          </div>

          <div className="profile-info">
            <span className="profile-label">
              Adresse email
            </span>

            <strong className="profile-email">
              {email || "Chargement..."}
            </strong>

            <span className="profile-label">
              Rôle
            </span>

            <strong className="profile-email">
              {role === "admin"
                ? "Administrateur"
                : role === "user"
                ? "Utilisateur"
                : "Chargement..."}
            </strong>
          </div>
        </div>

        {message && (
          <p className="profile-message">
            {message}
          </p>
        )}

        <div className="profile-actions">
          <button
            className="profile-refresh-button"
            onClick={loadProfile}
            disabled={loading}
          >
            {loading
              ? "Actualisation..."
              : "Actualiser le profil"}
          </button>

          {role === "admin" && (
            <DocumentUpload />
          )}

          <button
            className="profile-logout-button"
            onClick={logout}
          >
            Se déconnecter
          </button>
        </div>
      </main>
    </div>
  );
}

export default Profile;