
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { getProfile } from "../services/api";

import "./Navbar.css";

function Navbar() {
  const navigate = useNavigate();
  const [isUser, setIsUser] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadProfile() {
      try {
        const result = await getProfile();

        if (!result.response.ok) {
          if (!cancelled) {
            setIsUser(false);
          }
          return;
        }

        const profile = result.data;

        const role = String(
          profile?.role ??
          profile?.user?.role ??
          profile?.user_role ??
          profile?.type ??
          profile?.user_type ??
          ""
        ).toLowerCase();

        console.log("Profil récupéré :", profile);
        console.log("Rôle détecté :", role);

        if (!cancelled) {
          setIsUser(
            role === "user" ||
            role === "utilisateur"
          );
        }
      } catch (error) {
        console.error(
          "Erreur de récupération du profil :",
          error
        );

        if (!cancelled) {
          setIsUser(false);
        }
      }
    }

    loadProfile();

    return () => {
      cancelled = true;
    };
  }, []);

  function handleLogout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");

    navigate("/login");
  }

  return (
    <nav className="navbar">
      <div className="navbar-logo">
        <Link to="/chatbot">
          🛡️ CyberIA
        </Link>
      </div>

      <div className="navbar-links">
        <Link to="/chatbot">
          Chatbot
        </Link>

        <Link to="/quiz">
          Quiz & Exercices
        </Link>

        <Link to="/profile">
          Profil
        </Link>

        <Link to="/progression">
          Progression
        </Link>

        {isUser && (
          <Link to="/documents">
            Documents
          </Link>
        )}

        <button onClick={handleLogout}>
          Déconnexion
        </button>
      </div>
    </nav>
  );
}

export default Navbar;
