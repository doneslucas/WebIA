import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { register } from "../services/api";
import "./Login.css";

function Register() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  function isValidEmail(value: string) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
  }

  const passwordRules = {
    length: password.length >= 8,
    uppercase: /[A-Z]/.test(password),
    lowercase: /[a-z]/.test(password),
    number: /[0-9]/.test(password),
    special: /[^A-Za-z0-9]/.test(password),
  };

  const passwordIsValid =
    passwordRules.length &&
    passwordRules.uppercase &&
    passwordRules.lowercase &&
    passwordRules.number &&
    passwordRules.special;

  async function handleRegister() {
    setMessage("");

    if (!email.trim() || !password) {
      setMessage("Veuillez remplir tous les champs.");
      return;
    }

    if (!isValidEmail(email.trim())) {
      setMessage(
        "Veuillez entrer une adresse email valide."
      );
      return;
    }

    if (!passwordIsValid) {
      setMessage(
        "Le mot de passe ne respecte pas les critères de sécurité."
      );
      return;
    }

    setLoading(true);

    try {
      const { response, data } = await register(
        email.trim().toLowerCase(),
        password
      );

      if (!response.ok) {
        if (response.status === 422) {
          if (typeof data.detail === "string") {
            setMessage(data.detail);
          } else if (Array.isArray(data.detail)) {
            const emailError = data.detail.find(
              (error: any) =>
                error.loc?.includes("email")
            );

            if (emailError) {
              setMessage(
                "Veuillez entrer une adresse email valide."
              );
            } else {
              setMessage(
                "Les informations saisies sont invalides."
              );
            }
          } else {
            setMessage(
              "Les informations saisies sont invalides."
            );
          }
        } else {
          setMessage(
            typeof data.detail === "string"
              ? data.detail
              : "Erreur lors de l'inscription."
          );
        }

        return;
      }

      setMessage("Compte créé avec succès !");

      setEmail("");
      setPassword("");

      setTimeout(() => {
        navigate("/login");
      }, 1000);
    } catch (error) {
      console.error(error);

      setMessage(
        "Impossible de contacter le serveur."
      );
    } finally {
      setLoading(false);
    }
  }

  function renderRule(
    valid: boolean,
    text: string
  ) {
    return (
      <div
        className={`password-rule ${
          valid ? "password-rule-valid" : ""
        }`}
      >
        <span>
          {valid ? "✓" : "✗"}
        </span>

        <span>{text}</span>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-container">

        <div className="auth-brand">
          <div className="auth-logo">
            🛡️
          </div>

          <h1>WebIA</h1>

          <p>
            Assistant intelligent en cybersécurité
          </p>
        </div>

        <div className="auth-card">
          <h2>Créer un compte</h2>

          <p className="auth-description">
            Rejoignez WebIA et accédez à votre assistant
            en cybersécurité.
          </p>

          <div className="auth-form">
            <div className="form-group">
              <label htmlFor="email">
                Adresse email
              </label>

              <input
                id="email"
                type="email"
                placeholder="exemple@email.com"
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value);
                  setMessage("");
                }}
              />
            </div>

            <div className="form-group">
              <label htmlFor="password">
                Mot de passe
              </label>

              <input
                id="password"
                type="password"
                placeholder="Votre mot de passe"
                value={password}
                onChange={(event) => {
                  setPassword(event.target.value);
                  setMessage("");
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    handleRegister();
                  }
                }}
              />

              <div className="password-rules">
                {renderRule(
                  passwordRules.length,
                  "8 caractères minimum"
                )}

                {renderRule(
                  passwordRules.uppercase,
                  "Une lettre majuscule"
                )}

                {renderRule(
                  passwordRules.lowercase,
                  "Une lettre minuscule"
                )}

                {renderRule(
                  passwordRules.number,
                  "Un chiffre"
                )}

                {renderRule(
                  passwordRules.special,
                  "Un caractère spécial"
                )}
              </div>
            </div>

            <button
              className="auth-button"
              onClick={handleRegister}
              disabled={loading}
            >
              {loading
                ? "Création..."
                : "Créer mon compte"}
            </button>
          </div>

          {message && (
            <p className="auth-message">
              {message}
            </p>
          )}

          <div className="auth-separator">
            <span>OU</span>
          </div>

          <div className="auth-footer">
            <span>
              Vous avez déjà un compte ?
            </span>

            <Link to="/login">
              Se connecter
            </Link>
          </div>
        </div>

        <p className="auth-security">
          🔒 Vos données sont protégées
        </p>

      </div>
    </div>
  );
}

export default Register;