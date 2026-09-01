import { useState } from "react";
import { login } from "../services/api";

type LoginProps = {
  onLogin: () => void;
  goToRegister: () => void;
};

function Login({
  onLogin,
  goToRegister,
}: LoginProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");

  async function handleLogin() {
    setMessage("");

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

      onLogin();
    } catch {
      setMessage(
        "Impossible de contacter le serveur"
      );
    }
  }

  return (
    <div>
      <h1>WebIA</h1>

      <h2>Connexion</h2>

      <input
        type="email"
        placeholder="Email"
        value={email}
        onChange={(event) =>
          setEmail(event.target.value)
        }
      />

      <br />
      <br />

      <input
        type="password"
        placeholder="Mot de passe"
        value={password}
        onChange={(event) =>
          setPassword(event.target.value)
        }
      />

      <br />
      <br />

      <button onClick={handleLogin}>
        Se connecter
      </button>

      <br />
      <br />

      <button onClick={goToRegister}>
        Créer un compte
      </button>

      {message && <p>{message}</p>}
    </div>
  );
}

export default Login;