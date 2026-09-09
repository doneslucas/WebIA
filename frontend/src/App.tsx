import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";

import Navbar from "./components/Navbar";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Profile from "./pages/Profile";
import Chatbot from "./pages/Chatbot";
import DocumentUpload from "./pages/DocumentUpload";
import Progression from "./pages/Progression";


function AppContent() {
  const location = useLocation();

  const hideNavbar =
    location.pathname === "/login" ||
    location.pathname === "/register";

  return (
    <>
      {!hideNavbar && <Navbar />}

      <Routes>
        <Route
          path="/"
          element={<Chatbot />}
        />

        <Route
          path="/login"
          element={<Login />}
        />

        <Route
          path="/register"
          element={<Register />}
        />

        <Route
          path="/profile"
          element={<Profile />}
        />

        <Route
          path="/chat"
          element={<Chatbot />}
        />

        <Route
          path="/chatbot"
          element={<Chatbot />}
        />

        <Route
          path="/documents"
          element={<DocumentUpload />}
        />

        <Route
          path="/progression"
          element={<Progression />}
        />
      </Routes>
    </>
  );
}


function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}


export default App;