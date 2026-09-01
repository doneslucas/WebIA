import { useState } from "react";

import Login from "./pages/Login";
import Register from "./pages/Register";
import Profile from "./pages/Profile";

type Page = "login" | "register" | "profile";

function App() {
  const [page, setPage] = useState<Page>("login");

  function showLogin() {
    setPage("login");
  }

  function showRegister() {
    setPage("register");
  }

  function showProfile() {
    setPage("profile");
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

  return (
    <Profile
      onLogout={showLogin}
    />
  );
}

export default App;