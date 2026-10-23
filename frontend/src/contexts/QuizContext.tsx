import {
  createContext,
  useContext,
  useState,
  type ReactNode,
} from "react";

import {
  generateQuiz,
  generateMixedQuiz,
  getQuizGenerationStatus,
  requestQuizQuestionGeneration,
  checkQuizAnswer,
  submitQuiz,
} from "../services/api";


export type QuizQuestion = {
  id: number;
  question: string;
  options: string[];
  difficulty: string;
};


export type QuizGenerationOption = {
  difficulty: string;
  available_count: number;
  questions_needed: number;
  enabled?: boolean;
};


export type QuizGenerationData = {
  category_ids: number[];
  difficulty: string;
  requested_count: number;
  available_count: number;
  missing_count: number;
  target_count: number;
  capacity: number;
  generation_active: boolean;
  estimated_seconds?: number | null;

  options: {
    available: {
      enabled: boolean;
      question_count: number;
    };

    mixed: {
      enabled: boolean;
      difficulties: QuizGenerationOption[];
    };

    wait: {
      enabled: boolean;
      missing_count: number;
      generation_active: boolean;
    };
  };
};


type QuizContextType = {
  categoryIds: number[];
  questionCount: string;
  difficulty: string;

  questions: QuizQuestion[];

  quizStarted: boolean;
  currentQuestion: number;

  answers: number[];

  showCorrection: boolean;
  finished: boolean;

  loading: boolean;
  message: string;

  currentAnswerCorrect: boolean | null;
  currentCorrectAnswer: number | null;
  currentExplanation: string;

  generationChoice: QuizGenerationData | null;
  waitingForGeneration: boolean;

  setCategoryIds: (value: number[]) => void;
  setQuestionCount: (value: string) => void;
  setDifficulty: (value: string) => void;

  startQuiz: () => Promise<void>;
  startWithAvailableQuestions: () => Promise<void>;
  startMixedQuiz: (fallbackDifficulty: string) => Promise<void>;
  waitForQuestions: () => Promise<void>;

  cancelGenerationChoice: () => void;

  selectAnswer: (answerIndex: number) => void;
  showQuestionCorrection: () => Promise<void>;
  nextQuestion: () => Promise<void>;

  returnToQuizHome: () => void;

  score: number;
};


const QuizContext =
  createContext<QuizContextType | undefined>(undefined);


type QuizProviderProps = {
  children: ReactNode;
};


function isValidQuestion(question: unknown): question is QuizQuestion {
  if (!question || typeof question !== "object") {
    return false;
  }

  const candidate = question as QuizQuestion;

  return (
    typeof candidate.id === "number" &&
    typeof candidate.question === "string" &&
    Array.isArray(candidate.options) &&
    candidate.options.length === 4 &&
    candidate.options.every(
      (option) => typeof option === "string",
    ) &&
    typeof candidate.difficulty === "string"
  );
}


function getErrorMessage(
  error: unknown,
  fallback: string,
): string {
  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
}


function formatEstimatedTime(
  seconds: unknown,
): string | null {
  if (
    typeof seconds !== "number" ||
    !Number.isFinite(seconds) ||
    seconds <= 0
  ) {
    return null;
  }

  const totalSeconds = Math.ceil(seconds);

  if (totalSeconds < 60) {
    return `environ ${totalSeconds} seconde(s)`;
  }

  const minutes = Math.ceil(totalSeconds / 60);

  if (minutes < 60) {
    return `environ ${minutes} minute(s)`;
  }

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;

  if (remainingMinutes === 0) {
    return `environ ${hours} heure(s)`;
  }

  return `environ ${hours} h ${remainingMinutes} min`;
}


export function QuizProvider({
  children,
}: QuizProviderProps) {
  const [categoryIds, setCategoryIds] =
    useState<number[]>([]);

  const [questionCount, setQuestionCount] =
    useState("10");

  const [difficulty, setDifficulty] =
    useState("medium");


  const [questions, setQuestions] =
    useState<QuizQuestion[]>([]);

  const [quizStarted, setQuizStarted] =
    useState(false);

  const [currentQuestion, setCurrentQuestion] =
    useState(0);

  const [answers, setAnswers] =
    useState<number[]>([]);

  const [showCorrection, setShowCorrection] =
    useState(false);

  const [finished, setFinished] =
    useState(false);

  const [loading, setLoading] =
    useState(false);

  const [message, setMessage] =
    useState("");


  const [
    currentAnswerCorrect,
    setCurrentAnswerCorrect,
  ] = useState<boolean | null>(null);

  const [
    currentCorrectAnswer,
    setCurrentCorrectAnswer,
  ] = useState<number | null>(null);

  const [
    currentExplanation,
    setCurrentExplanation,
  ] = useState("");

  const [score, setScore] =
    useState(0);


  const [
    generationChoice,
    setGenerationChoice,
  ] = useState<QuizGenerationData | null>(null);

  const [
    waitingForGeneration,
    setWaitingForGeneration,
  ] = useState(false);


  function initializeQuiz(
    receivedQuestions: QuizQuestion[],
  ) {
    const validQuestions =
      receivedQuestions.filter(isValidQuestion);

    if (validQuestions.length === 0) {
      setMessage(
        "Aucune question valide n'a été retournée par le serveur.",
      );
      return;
    }

    setQuestions(validQuestions);
    setCurrentQuestion(0);
    setAnswers([]);
    setScore(0);
    setShowCorrection(false);
    setFinished(false);

    setCurrentAnswerCorrect(null);
    setCurrentCorrectAnswer(null);
    setCurrentExplanation("");

    setGenerationChoice(null);
    setWaitingForGeneration(false);

    setMessage("");
    setQuizStarted(true);
  }


  function validateSelectedCategories(): boolean {
    if (categoryIds.length === 0) {
      setMessage(
        "Veuillez sélectionner au moins une catégorie.",
      );
      return false;
    }

    return true;
  }


  function handleGenerationError(
    error: unknown,
    fallback: string,
  ) {
    console.error(error);
    setMessage(getErrorMessage(error, fallback));
  }


  // -------------------------------------------------
  // Démarrage normal du quiz
  // -------------------------------------------------

  async function startQuiz() {
    if (!validateSelectedCategories()) {
      return;
    }

    setMessage("");
    setLoading(true);
    setGenerationChoice(null);

    try {
      const result = await generateQuiz(
        categoryIds,
        Number(questionCount),
        difficulty,
      );

      if (!result.response.ok) {
        throw new Error(
          result.data.detail ||
          "Erreur lors de la préparation du quiz.",
        );
      }

      if (result.data.status === "insufficient_questions") {
        setGenerationChoice(result.data as QuizGenerationData);
        return;
      }

      if (result.data.status !== "ready") {
        throw new Error(
          "Réponse inattendue du serveur lors de la préparation du quiz.",
        );
      }

      if (
        !Array.isArray(result.data.questions) ||
        result.data.questions.length === 0
      ) {
        throw new Error(
          "Le serveur n'a pas retourné de questions valides.",
        );
      }

      const receivedQuestions: unknown[] =
        result.data.questions;

      const validQuestions =
        receivedQuestions.filter(isValidQuestion);

      if (validQuestions.length !== receivedQuestions.length) {
        throw new Error(
          "Certaines questions reçues du serveur sont invalides.",
        );
      }

      initializeQuiz(validQuestions);
    } catch (error) {
      handleGenerationError(
        error,
        "Une erreur est survenue lors de la préparation du quiz.",
      );
    } finally {
      setLoading(false);
    }
  }


  // -------------------------------------------------
  // OPTION 1 : jouer avec les questions disponibles
  // -------------------------------------------------

  async function startWithAvailableQuestions() {
    if (!generationChoice) {
      return;
    }

    if (!validateSelectedCategories()) {
      return;
    }

    const availableCount = Math.min(
      generationChoice.options.available.question_count,
      generationChoice.available_count,
      Number(questionCount),
    );

    if (
      !generationChoice.options.available.enabled ||
      availableCount <= 0
    ) {
      setMessage(
        "Aucune question non encore jouée n'est disponible dans cette difficulté.",
      );
      return;
    }

    setLoading(true);
    setMessage("");

    try {
      /*
       * allowShortQuiz=true est indispensable :
       * cette option autorise le backend à démarrer un quiz
       * avec moins de questions que le nombre demandé.
       */
      const result = await generateQuiz(
        categoryIds,
        availableCount,
        difficulty,
        true,
      );

      if (!result.response.ok) {
        throw new Error(
          result.data.detail ||
          "Impossible de récupérer les questions disponibles.",
        );
      }

      if (result.data.status !== "ready") {
        if (result.data.status === "insufficient_questions") {
          setGenerationChoice(result.data as QuizGenerationData);

          setMessage(
            "La disponibilité a changé. Les trois choix ont été actualisés.",
          );

          return;
        }

        throw new Error(
          "Les questions disponibles ont changé. Veuillez réessayer.",
        );
      }

      if (
        !Array.isArray(result.data.questions) ||
        result.data.questions.length === 0
      ) {
        throw new Error(
          "Aucune question valide n'a été retournée.",
        );
      }

      const validQuestions: QuizQuestion[] =
        result.data.questions.filter(isValidQuestion);

      if (validQuestions.length !== result.data.questions.length) {
        throw new Error(
          "Certaines questions reçues du serveur sont invalides.",
        );
      }

      initializeQuiz(validQuestions);
    } catch (error) {
      handleGenerationError(
        error,
        "Impossible de démarrer le quiz avec les questions disponibles.",
      );
    } finally {
      setLoading(false);
    }
  }


  // -------------------------------------------------
  // OPTION 2 : compléter avec une autre difficulté
  // -------------------------------------------------

  async function startMixedQuiz(
    fallbackDifficulty: string,
  ) {
    if (!generationChoice) {
      return;
    }

    if (!validateSelectedCategories()) {
      return;
    }

    const fallbackOption =
      generationChoice.options.mixed.difficulties.find(
        (option) => option.difficulty === fallbackDifficulty,
      );

    /*
     * Chaque difficulté est vérifiée séparément.
     * Une option insuffisante ne peut pas être lancée.
     */
    if (
      !generationChoice.options.mixed.enabled ||
      !fallbackOption ||
      fallbackOption.enabled === false ||
      fallbackOption.available_count < fallbackOption.questions_needed
    ) {
      setMessage(
        "Cette combinaison de difficultés ne possède pas assez de questions non encore jouées.",
      );
      return;
    }

    setLoading(true);
    setMessage("");

    try {
      const result = await generateMixedQuiz(
        categoryIds,
        Number(questionCount),
        difficulty,
        fallbackDifficulty,
        false,
      );

      if (!result.response.ok) {
        throw new Error(
          result.data.detail ||
          "Impossible de compléter le quiz avec une autre difficulté.",
        );
      }

      if (result.data.status === "insufficient_questions") {
        setGenerationChoice(result.data as QuizGenerationData);

        setMessage(
          "La disponibilité a changé. Les possibilités ont été actualisées.",
        );

        return;
      }

      if (result.data.status !== "ready") {
        throw new Error(
          "Le serveur n'a pas pu préparer le quiz mixte.",
        );
      }

      if (
        !Array.isArray(result.data.questions) ||
        result.data.questions.length !== Number(questionCount)
      ) {
        throw new Error(
          "Le quiz mixte ne contient pas le nombre de questions demandé.",
        );
      }

      const validQuestions: QuizQuestion[] =
        result.data.questions.filter(isValidQuestion);

      if (validQuestions.length !== result.data.questions.length) {
        throw new Error(
          "Certaines questions reçues du serveur sont invalides.",
        );
      }

      initializeQuiz(validQuestions);
    } catch (error) {
      handleGenerationError(
        error,
        "Impossible de compléter le quiz avec une autre difficulté.",
      );
    } finally {
      setLoading(false);
    }
  }


  // -------------------------------------------------
  // OPTION 3 : demander la génération puis patienter
  // -------------------------------------------------

  async function waitForQuestions() {
    if (!generationChoice) {
      return;
    }

    if (!validateSelectedCategories()) {
      return;
    }

    if (
      !generationChoice.options.wait.enabled &&
      !generationChoice.options.wait.generation_active
    ) {
      setMessage(
        "Aucune génération supplémentaire n'est possible actuellement pour cette sélection.",
      );
      return;
    }

    setWaitingForGeneration(true);
    setLoading(true);
    setMessage("Demande de génération des questions...");

    try {
      /*
       * L'option 3 ne se contente pas d'attendre :
       * elle demande au backend de mettre en file les tâches
       * nécessaires pour les catégories et la difficulté choisies.
       */
      const requestResult =
        await requestQuizQuestionGeneration(
          categoryIds,
          difficulty,
        );

      if (!requestResult.response.ok) {
        throw new Error(
          requestResult.data.detail ||
          "Impossible de lancer la génération des questions.",
        );
      }

      const estimatedTime =
        formatEstimatedTime(
          requestResult.data.estimated_seconds,
        );

      if (estimatedTime) {
        setMessage(
          `Génération demandée. Temps estimé par le serveur : ${estimatedTime}.`,
        );
      } else {
        setMessage(
          "Génération demandée. Recherche des nouvelles questions en cours...",
        );
      }

      /*
       * Limite d'attente : 20 minutes.
       * Une demande de génération peut concerner plusieurs catégories.
       * Chaque contrôle vérifie les questions réellement utilisables
       * par l'utilisateur, et non uniquement le total de la banque.
       */
      const maxAttempts = 400;
      let idleChecks = 0;

      for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
        await new Promise<void>((resolve) => {
          window.setTimeout(resolve, 3000);
        });

        const statusResult =
          await getQuizGenerationStatus(
            categoryIds,
            Number(questionCount),
            difficulty,
          );

        if (!statusResult.response.ok) {
          throw new Error(
            statusResult.data.detail ||
            "Impossible de suivre la progression de la génération.",
          );
        }

        /*
         * On tente de préparer le quiz à chaque vérification.
         * C'est le backend /quiz/generate qui détermine si suffisamment
         * de questions non encore jouées sont désormais disponibles.
         */
        const quizResult = await generateQuiz(
          categoryIds,
          Number(questionCount),
          difficulty,
          false,
        );

        if (!quizResult.response.ok) {
          throw new Error(
            quizResult.data.detail ||
            "Impossible de vérifier les questions générées.",
          );
        }

        if (quizResult.data.status === "ready") {
          if (
            !Array.isArray(quizResult.data.questions) ||
            quizResult.data.questions.length !== Number(questionCount)
          ) {
            throw new Error(
              "Le serveur n'a pas retourné le nombre de questions attendu.",
            );
          }

          const validQuestions: QuizQuestion[] =
            quizResult.data.questions.filter(isValidQuestion);

          if (validQuestions.length !== quizResult.data.questions.length) {
            throw new Error(
              "Certaines questions générées sont invalides.",
            );
          }

          initializeQuiz(validQuestions);
          return;
        }

        if (quizResult.data.status !== "insufficient_questions") {
          throw new Error(
            quizResult.data.detail ||
            "Le serveur a retourné un statut de génération inattendu.",
          );
        }

        const refreshedChoice =
          quizResult.data as QuizGenerationData;

        setGenerationChoice(refreshedChoice);

        const bankStatus =
          statusResult.data.status?.[difficulty];

        const bankCurrent =
          typeof bankStatus?.current === "number"
            ? bankStatus.current
            : null;

        const bankTarget =
          typeof bankStatus?.target === "number"
            ? bankStatus.target
            : null;

        const availableForUser =
          typeof refreshedChoice.available_count === "number"
            ? refreshedChoice.available_count
            : 0;

        const generationActive =
          Boolean(
            statusResult.data.generation_active ??
            statusResult.data.active ??
            statusResult.data.status?.[difficulty]?.generation_active ??
            refreshedChoice.generation_active ??
            refreshedChoice.options.wait.generation_active,
          );

        if (bankCurrent !== null && bankTarget !== null) {
          setMessage(
            `Questions utilisables par toi : ${availableForUser} / ${Number(questionCount)}. ` +
            `Banque : ${bankCurrent} / ${bankTarget}.`,
          );
        } else {
          setMessage(
            `Questions utilisables par toi : ${availableForUser} / ${Number(questionCount)}. ` +
            "Génération et disponibilité vérifiées régulièrement.",
          );
        }

        if (generationActive) {
          idleChecks = 0;
        } else {
          idleChecks += 1;
        }

        /*
         * Deux contrôles consécutifs sans tâche active signifient
         * que la génération demandée semble terminée.
         * On ne prétend pas que des questions supplémentaires arriveront
         * si le backend n'a plus de tâches à traiter.
         */
        if (idleChecks >= 2) {
          setMessage(
            availableForUser > 0
              ? `La génération est terminée. Il reste ${availableForUser} question(s) jouable(s) pour toi. Tu peux choisir un quiz plus court ou revenir à la configuration.`
              : "La génération est terminée, mais aucune question supplémentaire n'est disponible pour cette sélection. Tu peux choisir une autre difficulté ou modifier les catégories.",
          );

          return;
        }
      }

      setMessage(
        "La génération n'est pas terminée après 20 minutes. Les questions déjà enregistrées sont conservées ; tu peux réessayer ou choisir une autre option.",
      );
    } catch (error) {
      handleGenerationError(
        error,
        "Erreur lors de la demande ou du suivi de génération.",
      );
    } finally {
      setLoading(false);
      setWaitingForGeneration(false);
    }
  }


  function cancelGenerationChoice() {
    if (waitingForGeneration) {
      return;
    }

    setGenerationChoice(null);
    setLoading(false);
    setMessage("");
  }


  // -------------------------------------------------
  // Réponse à une question
  // -------------------------------------------------

  function selectAnswer(answerIndex: number) {
    if (showCorrection || finished) {
      return;
    }

    if (answerIndex < 0 || answerIndex > 3) {
      return;
    }

    setAnswers((previous) => {
      const updated = [...previous];
      updated[currentQuestion] = answerIndex;
      return updated;
    });

    setMessage("");
  }


  async function showQuestionCorrection() {
    const selectedAnswer = answers[currentQuestion];

    if (selectedAnswer === undefined) {
      setMessage(
        "Veuillez sélectionner une réponse avant de continuer.",
      );
      return;
    }

    const question = questions[currentQuestion];

    if (!question) {
      setMessage("Question introuvable.");
      return;
    }

    setLoading(true);
    setMessage("");

    try {
      const result = await checkQuizAnswer(
        question.id,
        selectedAnswer,
      );

      if (!result.response.ok) {
        throw new Error(
          result.data.detail ||
          "Impossible de vérifier la réponse.",
        );
      }

      setCurrentAnswerCorrect(result.data.is_correct);
      setCurrentCorrectAnswer(result.data.correct_answer);
      setCurrentExplanation(result.data.explanation || "");
      setShowCorrection(true);
    } catch (error) {
      handleGenerationError(
        error,
        "Erreur lors de la vérification de la réponse.",
      );
    } finally {
      setLoading(false);
    }
  }


  // -------------------------------------------------
  // Question suivante et enregistrement du résultat
  // -------------------------------------------------

  async function nextQuestion() {
    if (currentQuestion === questions.length - 1) {
      setLoading(true);
      setMessage("");

      try {
        const formattedAnswers = questions.map(
          (question, index) => {
            const answer = answers[index];

            if (answer === undefined) {
              throw new Error(
                "Toutes les questions doivent avoir une réponse.",
              );
            }

            return {
              question_id: question.id,
              answer,
            };
          },
        );

        const result = await submitQuiz(formattedAnswers);

        if (!result.response.ok) {
          throw new Error(
            result.data.detail ||
            "Impossible d'enregistrer le quiz.",
          );
        }

        if (typeof result.data.score !== "number") {
          throw new Error(
            "Le serveur n'a pas retourné de score valide.",
          );
        }

        setScore(result.data.score);
        setFinished(true);
        setShowCorrection(false);
        setMessage("");
      } catch (error) {
        handleGenerationError(
          error,
          "Erreur lors de l'enregistrement du quiz.",
        );
      } finally {
        setLoading(false);
      }

      return;
    }

    setCurrentQuestion((previous) => previous + 1);
    setShowCorrection(false);
    setCurrentAnswerCorrect(null);
    setCurrentCorrectAnswer(null);
    setCurrentExplanation("");
    setMessage("");
  }


  // -------------------------------------------------
  // Retour à l'accueil des quiz
  // -------------------------------------------------

  function returnToQuizHome() {
    setQuizStarted(false);
    setCurrentQuestion(0);
    setAnswers([]);
    setScore(0);

    setShowCorrection(false);
    setFinished(false);
    setQuestions([]);

    setCurrentAnswerCorrect(null);
    setCurrentCorrectAnswer(null);
    setCurrentExplanation("");

    setGenerationChoice(null);
    setWaitingForGeneration(false);

    setLoading(false);
    setMessage("");
  }


  return (
    <QuizContext.Provider
      value={{
        categoryIds,
        questionCount,
        difficulty,

        questions,

        quizStarted,
        currentQuestion,
        answers,

        showCorrection,
        finished,

        loading,
        message,

        currentAnswerCorrect,
        currentCorrectAnswer,
        currentExplanation,

        generationChoice,
        waitingForGeneration,

        setCategoryIds,
        setQuestionCount,
        setDifficulty,

        startQuiz,
        startWithAvailableQuestions,
        startMixedQuiz,
        waitForQuestions,

        cancelGenerationChoice,

        selectAnswer,
        showQuestionCorrection,
        nextQuestion,

        returnToQuizHome,

        score,
      }}
    >
      {children}
    </QuizContext.Provider>
  );
}


export function useQuiz() {
  const context = useContext(QuizContext);

  if (!context) {
    throw new Error(
      "useQuiz doit être utilisé à l'intérieur de QuizProvider.",
    );
  }

  return context;
}