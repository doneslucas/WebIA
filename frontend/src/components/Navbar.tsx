import { Link, useNavigate } from "react-router-dom";
import "./Navbar.css";

function Navbar() {
  const navigate = useNavigate();

  function handleLogout() {
    localStorage.removeItem("access_token");
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

        <Link to="/profile">
          Profil
        </Link>

        <Link to="/progression">
          Progression
        </Link>

        <button onClick={handleLogout}>
          Déconnexion
        </button>
      </div>
    </nav>
  );
}

export default Navbar;