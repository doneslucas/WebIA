
import {
  BrowserRouter,
  Navigate,
  Outlet,
  Routes,
  Route,
  useLocation,
} from "react-router-dom";

import Navbar from "./components/Navbar";

import Login from "./pages/Login";
import Register from "./pages/Register";
import Profile from "./pages/Profile";
import Chatbot from "./pages/Chatbot";
import DocumentUpload from "./pages/DocumentUpload";
import Progression from "./pages/Progression";
import Quiz from "./pages/Quiz";
import About from "./pages/About";

import { QuizProvider } from "./contexts/QuizContext";

function hasSavedSession(): boolean {
  return Boolean(
    localStorage.getItem("access_token") ||
    localStorage.getItem("refresh_token")
  );
}

function RootRedirect() {
  return (
    <Navigate
      to={hasSavedSession() ? "/chatbot" : "/login"}
      replace
    />
  );
}

function RequireAuth() {
  const location = useLocation();

  if (!hasSavedSession()) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: location }}
      />
    );
  }

  return <Outlet />;
}

function AuthenticatedLayout() {
  return (
    <>
      <Navbar />
      <Outlet />
    </>
  );
}

function App() {
  return (
    <BrowserRouter>
      <QuizProvider>
        <Routes>
          {/* Pages accessibles sans connexion */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Redirection de la page d'accueil */}
          <Route path="/" element={<RootRedirect />} />

          {/* Pages nécessitant une session */}
          <Route element={<RequireAuth />}>
            <Route element={<AuthenticatedLayout />}>
              <Route path="/profile" element={<Profile />} />
              <Route path="/chat" element={<Chatbot />} />
              <Route path="/chatbot" element={<Chatbot />} />
              <Route
                path="/documents"
                element={<DocumentUpload />}
              />
              <Route
                path="/progression"
                element={<Progression />}
              />
              <Route path="/quiz" element={<Quiz />} />
              <Route path="/about" element={<About />} />
            </Route>
          </Route>

          {/* Toute URL inconnue revient au point d'entrée */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </QuizProvider>
    </BrowserRouter>
  );
}

export default App;
