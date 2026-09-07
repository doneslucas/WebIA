import { useState } from "react";

import Login from "./pages/Login";
import Register from "./pages/Register";
import Profile from "./pages/Profile";
import Chatbot from "./pages/Chatbot";

type Page = "login" | "register" | "profile" | "chatbot";

function App() {
  const [page, setPage] = useState<Page>("chatbot");

  function showLogin() {
    setPage("login");
  }

  function showRegister() {
    setPage("register");
  }

  function showProfile() {
    setPage("profile");
  }

  function showChatbot() {
    setPage("chatbot");
  }

  if (page === "login") {
    return (
      <Login
        onLogin={showProfile}
        goToRegister={showRegister}
      />
    );
  }

  if (page === "register") {
    return (
      <Register
        goToLogin={showLogin}
      />
    );
  }

  if (page === "profile") {
    return (
      <Profile
        onLogout={showLogin}
      />
    );
  }

  if (page === "chatbot") {
    return (
      <Chatbot />
    );
  }
}

export default App;