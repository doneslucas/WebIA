import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { login } from "../services/api";
import "./Login.css";

function Login() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin() {
    setMessage("");

    if (!email || !password) {
      setMessage("Veuillez remplir tous les champs.");
      return;
    }

    setLoading(true);

    try {
      const { response, data } = await login(
        email,
        password
      );

      if (!response.ok) {
        setMessage(
          data.detail || "Erreur de connexion"
        );
        return;
      }

      localStorage.setItem(
        "access_token",
        data.access_token
      );

      navigate("/profile");
    } catch {
      setMessage(
        "Impossible de contacter le serveur"
      );
    } finally {
      setLoading(false);
    }
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
          <h2>Bienvenue</h2>

          <p className="auth-description">
            Connectez-vous à votre espace WebIA.
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
                onChange={(event) =>
                  setEmail(event.target.value)
                }
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
                onChange={(event) =>
                  setPassword(event.target.value)
                }
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    handleLogin();
                  }
                }}
              />
            </div>

            <button
              className="auth-button"
              onClick={handleLogin}
              disabled={loading}
            >
              {loading
                ? "Connexion..."
                : "Se connecter"}
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
              Vous n'avez pas encore de compte ?
            </span>

            <Link to="/register">
              Créer un compte
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

export default Login;