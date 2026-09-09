import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  changePassword,
  getProfile
} from "../services/api";

import DocumentUpload from "./DocumentUpload";
import "./Profile.css";


function Profile() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [role, setRole] = useState("");
  const [message, setMessage] = useState("");

  const [showPasswordForm, setShowPasswordForm] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [passwordMessage, setPasswordMessage] = useState("");
  const [passwordSuccess, setPasswordSuccess] = useState(false);
  const [passwordLoading, setPasswordLoading] = useState(false);


  async function loadProfile() {
    setMessage("");

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
      setMessage(
        "Impossible de contacter le serveur"
      );
    }
  }


  function logout() {
    localStorage.removeItem("access_token");
    navigate("/login");
  }


  function openPasswordForm() {
    setPasswordMessage("");
    setPasswordSuccess(false);
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setShowPasswordForm(true);
  }


  function closePasswordForm() {
    if (passwordLoading) {
      return;
    }

    setPasswordMessage("");
    setPasswordSuccess(false);
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setShowPasswordForm(false);
  }


  async function handlePasswordChange() {
    setPasswordMessage("");
    setPasswordSuccess(false);

    if (!currentPassword) {
      setPasswordMessage(
        "Veuillez saisir votre ancien mot de passe."
      );
      return;
    }

    if (!newPassword) {
      setPasswordMessage(
        "Veuillez saisir un nouveau mot de passe."
      );
      return;
    }

    if (newPassword.length < 8) {
      setPasswordMessage(
        "Le nouveau mot de passe doit contenir au moins 8 caractères."
      );
      return;
    }

    if (!/[A-Z]/.test(newPassword)) {
      setPasswordMessage(
        "Le nouveau mot de passe doit contenir au moins une majuscule."
      );
      return;
    }

    if (!/[a-z]/.test(newPassword)) {
      setPasswordMessage(
        "Le nouveau mot de passe doit contenir au moins une minuscule."
      );
      return;
    }

    if (!/[0-9]/.test(newPassword)) {
      setPasswordMessage(
        "Le nouveau mot de passe doit contenir au moins un chiffre."
      );
      return;
    }

    if (!/[^a-zA-Z0-9]/.test(newPassword)) {
      setPasswordMessage(
        "Le nouveau mot de passe doit contenir au moins un caractère spécial."
      );
      return;
    }

    if (newPassword !== confirmPassword) {
      setPasswordMessage(
        "Les deux nouveaux mots de passe ne correspondent pas."
      );
      return;
    }

    if (currentPassword === newPassword) {
      setPasswordMessage(
        "Le nouveau mot de passe doit être différent de l'ancien."
      );
      return;
    }

    setPasswordLoading(true);

    try {
      const { response, data } = await changePassword(
        currentPassword,
        newPassword
      );

      if (!response.ok) {
        setPasswordMessage(
          data.detail ||
            "Erreur lors du changement de mot de passe."
        );
        return;
      }

      setPasswordSuccess(true);

      setPasswordMessage(
        "Mot de passe modifié avec succès."
      );

      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setShowPasswordForm(false);

    } catch {
      setPasswordMessage(
        "Impossible de contacter le serveur."
      );

    } finally {
      setPasswordLoading(false);
    }
  }


  useEffect(() => {
    loadProfile();
  }, []);


  const passwordRules = [
    {
      label: "Au moins 8 caractères",
      valid: newPassword.length >= 8
    },
    {
      label: "Au moins une majuscule",
      valid: /[A-Z]/.test(newPassword)
    },
    {
      label: "Au moins une minuscule",
      valid: /[a-z]/.test(newPassword)
    },
    {
      label: "Au moins un chiffre",
      valid: /[0-9]/.test(newPassword)
    },
    {
      label: "Au moins un caractère spécial",
      valid: /[^a-zA-Z0-9]/.test(newPassword)
    }
  ];


  const passwordIsValid =
    passwordRules.every((rule) => rule.valid) &&
    newPassword === confirmPassword &&
    newPassword !== currentPassword;


  return (
    <div className="profile-page">

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


        {passwordSuccess && passwordMessage && (
          <p className="password-message success">
            {passwordMessage}
          </p>
        )}


        <div className="profile-actions">

          {!showPasswordForm && (
            <button
              className="profile-refresh-button"
              onClick={openPasswordForm}
            >
              Modifier mon mot de passe
            </button>
          )}


          {showPasswordForm && (
            <div className="password-form">

              <h2>
                Modifier mon mot de passe
              </h2>


              <div className="password-field">

                <label htmlFor="current-password">
                  Ancien mot de passe
                </label>

                <input
                  id="current-password"
                  type="password"
                  value={currentPassword}
                  onChange={(event) =>
                    setCurrentPassword(event.target.value)
                  }
                  disabled={passwordLoading}
                />

              </div>


              <div className="password-field">

                <label htmlFor="new-password">
                  Nouveau mot de passe
                </label>

                <input
                  id="new-password"
                  type="password"
                  value={newPassword}
                  onChange={(event) =>
                    setNewPassword(event.target.value)
                  }
                  disabled={passwordLoading}
                />

              </div>


              <div className="password-rules">

                <span className="password-rules-title">
                  Votre mot de passe doit contenir :
                </span>

                {passwordRules.map((rule) => (
                  <span
                    key={rule.label}
                    className={
                      rule.valid
                        ? "password-rule valid"
                        : "password-rule"
                    }
                  >
                    {rule.valid ? "✓" : "○"} {rule.label}
                  </span>
                ))}

              </div>


              <div className="password-field">

                <label htmlFor="confirm-password">
                  Confirmer le nouveau mot de passe
                </label>

                <input
                  id="confirm-password"
                  type="password"
                  value={confirmPassword}
                  onChange={(event) =>
                    setConfirmPassword(event.target.value)
                  }
                  disabled={passwordLoading}
                />

              </div>


              {confirmPassword && (
                <p
                  className={
                    newPassword === confirmPassword
                      ? "password-confirm valid"
                      : "password-confirm invalid"
                  }
                >
                  {newPassword === confirmPassword
                    ? "✓ Les mots de passe correspondent."
                    : "✗ Les mots de passe ne correspondent pas."}
                </p>
              )}


              {passwordMessage && !passwordSuccess && (
                <p className="password-message">
                  {passwordMessage}
                </p>
              )}


              <div className="password-actions">

                <button
                  type="button"
                  className="password-submit-button"
                  onClick={handlePasswordChange}
                  disabled={
                    passwordLoading ||
                    !currentPassword ||
                    !passwordIsValid
                  }
                >
                  {passwordLoading
                    ? "Enregistrement..."
                    : "Enregistrer le nouveau mot de passe"}
                </button>


                <button
                  type="button"
                  className="password-cancel-button"
                  onClick={closePasswordForm}
                  disabled={passwordLoading}
                >
                  Annuler
                </button>

              </div>

            </div>
          )}


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