import {
  BrowserRouter,
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

import { QuizProvider } from "./contexts/QuizContext";


function AppContent() {

  const location =
    useLocation();


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


        <Route
          path="/quiz"
          element={<Quiz />}
        />

      </Routes>
    </>
  );
}


function App() {

  return (
    <BrowserRouter>

      <QuizProvider>

        <AppContent />

      </QuizProvider>

    </BrowserRouter>
  );
}


export default App;