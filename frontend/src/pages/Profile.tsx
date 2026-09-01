import { useEffect, useState } from "react";
import { getProfile } from "../services/api";

type ProfileProps = {
  onLogout: () => void;
};

function Profile({ onLogout }: ProfileProps) {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");

  async function loadProfile() {
    try {
      const { response, data } = await getProfile();

      if (!response.ok) {
        setMessage(
          data.detail ||
            "Erreur lors de la récupération du profil"
        );
        return;
      }

      setEmail(data.email);
    } catch {
      setMessage("Impossible de contacter le serveur");
    }
  }

  function logout() {
    localStorage.removeItem("access_token");
    onLogout();
  }

  useEffect(() => {
    loadProfile();
  }, []);

  return (
    <div>
      <h1>WebIA</h1>

      <h2>Mon profil</h2>

      <p>Vous êtes connecté avec :</p>

      <strong>{email}</strong>

      <br />
      <br />

      <button onClick={loadProfile}>
        Actualiser le profil
      </button>

      <br />
      <br />

      <button onClick={logout}>
        Se déconnecter
      </button>

      {message && <p>{message}</p>}
    </div>
  );
}

export default Profile;