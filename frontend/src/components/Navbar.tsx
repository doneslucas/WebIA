import { useEffect, useState, type MouseEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { getProfile } from "../services/api";

import "./Navbar.css";

function Navbar() {
  const navigate = useNavigate();
  const [isUser, setIsUser] = useState(false);
  const [quizInProgress, setQuizInProgress] = useState(
    () => localStorage.getItem("webia_quiz_active") === "true",
  );

  useEffect(() => {
    function updateQuizState() {
      setQuizInProgress(
        localStorage.getItem("webia_quiz_active") === "true",
      );
    }

    window.addEventListener("webia-quiz-state-change", updateQuizState);
    window.addEventListener("storage", updateQuizState);

    updateQuizState();

    return () => {
      window.removeEventListener("webia-quiz-state-change", updateQuizState);
      window.removeEventListener("storage", updateQuizState);
    };
  }, []);

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
          "",
        ).toLowerCase();

        if (!cancelled) {
          setIsUser(role === "user" || role === "utilisateur");
        }
      } catch (error) {
        console.error("Erreur de récupération du profil :", error);

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

  const navigationLocked = isUser && quizInProgress;

  function handleNavigationClick(
    event: MouseEvent<HTMLAnchorElement>,
  ) {
    if (navigationLocked) {
      event.preventDefault();
    }
  }

  function handleLogout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("webia_quiz_active");
    localStorage.removeItem("webia_chatbot_messages");
    navigate("/login");
  }

  function navLinkClassName() {
    return navigationLocked ? "navbar-link-disabled" : undefined;
  }

  return (
    <nav className="navbar">
      <div className="navbar-logo">
        <Link
          to="/chatbot"
          className={navLinkClassName()}
          aria-disabled={navigationLocked}
          tabIndex={navigationLocked ? -1 : undefined}
          onClick={handleNavigationClick}
        >
          🛡️ CyberIA
        </Link>
      </div>

      <div className="navbar-links">
        <Link
          to="/chatbot"
          className={navLinkClassName()}
          aria-disabled={navigationLocked}
          tabIndex={navigationLocked ? -1 : undefined}
          onClick={handleNavigationClick}
        >
          Chatbot
        </Link>

        <Link
          to="/quiz"
          className={navLinkClassName()}
          aria-disabled={navigationLocked}
          tabIndex={navigationLocked ? -1 : undefined}
          onClick={handleNavigationClick}
        >
          Quiz
        </Link>

        <Link
          to="/profile"
          className={navLinkClassName()}
          aria-disabled={navigationLocked}
          tabIndex={navigationLocked ? -1 : undefined}
          onClick={handleNavigationClick}
        >
          Profil
        </Link>

        <Link
          to="/progression"
          className={navLinkClassName()}
          aria-disabled={navigationLocked}
          tabIndex={navigationLocked ? -1 : undefined}
          onClick={handleNavigationClick}
        >
          Progression
        </Link>

        {isUser && (
          <Link
            to="/documents"
            className={navLinkClassName()}
            aria-disabled={navigationLocked}
            tabIndex={navigationLocked ? -1 : undefined}
            onClick={handleNavigationClick}
          >
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
