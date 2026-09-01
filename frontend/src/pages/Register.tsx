import { useState } from "react";
import { register } from "../services/api";

type RegisterProps = {
  goToLogin: () => void;
};

function Register({
  goToLogin,
}: RegisterProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");

  async function handleRegister() {
    setMessage("");

    try {
      const { response, data } =
        await register(email, password);

      if (!response.ok) {
        setMessage(
          data.detail ||
            "Erreur lors de l'inscription"
        );
        return;
      }

      setMessage(
        "Compte créé avec succès !"
      );

      setEmail("");
      setPassword("");

      setTimeout(() => {
        goToLogin();
      }, 1000);
    } catch {
      setMessage(
        "Impossible de contacter le serveur"
      );
    }
  }

  return (
    <div>
      <h1>WebIA</h1>

      <h2>Créer un compte</h2>

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

      <button onClick={handleRegister}>
        S'inscrire
      </button>

      <br />
      <br />

      <button onClick={goToLogin}>
        Retour à la connexion
      </button>

      {message && <p>{message}</p>}
    </div>
  );
}

export default Register;