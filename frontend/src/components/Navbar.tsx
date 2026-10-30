
import { useEffect, useState, type MouseEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { getProfile } from "../services/api";
import { useQuiz } from "../contexts/QuizContext";

import "./Navbar.css";

function Navbar() {
  const navigate = useNavigate();

  const [isUser, setIsUser] = useState(false);

  // Lecture directe de l'état réel du quiz.
  const { quizStarted, finished, returnToQuizHome } = useQuiz();

  const quizInProgress = quizStarted && !finished;

  // Récupération du rôle de l'utilisateur.
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

  // Seuls Chatbot et Documents sont bloqués pendant un quiz.
  function isNavigationLocked(to: string) {
    return (
      quizInProgress &&
      (to === "/chatbot" || to === "/documents")
    );
  }

  function handleNavigationClick(
    event: MouseEvent<HTMLAnchorElement>,
    locked: boolean,
  ) {
    if (locked) {
      event.preventDefault();
      event.stopPropagation();
    }
  }

  function renderNavLink(to: string, label: string) {
    const locked = isNavigationLocked(to);

    return (
      <Link
        to={to}
        className={locked ? "navbar-link-disabled" : undefined}
        aria-disabled={locked}
        tabIndex={locked ? -1 : undefined}
        onClick={(event) =>
          handleNavigationClick(event, locked)
        }
      >
        {label}
      </Link>
    );
  }

  function handleLogout() {
    // Réinitialise également l'état réel du quiz.
    returnToQuizHome();

    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("webia_quiz_active");
    localStorage.removeItem("webia_chatbot_messages");

    navigate("/login");
  }

  const chatbotLocked = isNavigationLocked("/chatbot");

  return (
    <nav className="navbar">

      <div className="navbar-logo">

        <Link
          to="/chatbot"
          className={
            chatbotLocked ? "navbar-link-disabled" : undefined
          }
          aria-disabled={chatbotLocked}
          tabIndex={chatbotLocked ? -1 : undefined}
          onClick={(event) =>
            handleNavigationClick(event, chatbotLocked)
          }
        >
          🛡️ CyberIA
        </Link>

      </div>

      <div className="navbar-links">

        {renderNavLink("/chatbot", "Chatbot")}

        {renderNavLink("/quiz", "Quiz")}

        {renderNavLink("/profile", "Profil")}

        {isUser && renderNavLink("/documents", "Documents")}

        {renderNavLink("/progression", "Progression")}

        {renderNavLink("/about", "À propos")}

        <button onClick={handleLogout}>
          Déconnexion
        </button>

      </div>
    </nav>
  );
}

export default Navbar;
