import {
  createContext,
  useContext,
  useEffect,
  useRef,
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
    return totalSeconds === 1
      ? "environ 1 seconde"
      : `environ ${totalSeconds} secondes`;
  }

  const minutes = Math.ceil(totalSeconds / 60);

  if (minutes < 60) {
    return minutes === 1
      ? "environ 1 minute"
      : `environ ${minutes} minutes`;
  }

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  const hourLabel = hours === 1 ? "heure" : "heures";

  if (remainingMinutes === 0) {
    return `environ ${hours} ${hourLabel}`;
  }

  return `environ ${hours} h ${remainingMinutes} min`;
}


export function QuizProvider({
  children,
}: QuizProviderProps) {
  const waitOperationId = useRef(0);
  const generationIdRef = useRef<string | null>(null);

  async function callGenerationAction(
    action: "cancel-generation" | "release-generation",
    generationId: string,
  ): Promise<void> {
    const accessToken = localStorage.getItem("access_token");

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/quiz/" + action,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(accessToken
              ? { Authorization: `Bearer ${accessToken}` }
              : {}),
          },
          body: JSON.stringify({ generation_id: generationId }),
        },
      );

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        console.error(
          `[Quiz] ${action} refusée :`,
          body.detail || response.statusText,
        );
      }
    } catch (error) {
      console.error(`[Quiz] Erreur ${action} :`, error);
    }
  }
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

  // Informe la barre de navigation lorsqu'un QCM est réellement en cours.
  useEffect(() => {
    const quizIsActive = quizStarted && !finished;

    if (quizIsActive) {
      localStorage.setItem("webia_quiz_active", "true");
    } else {
      localStorage.removeItem("webia_quiz_active");
    }

    window.dispatchEvent(new Event("webia-quiz-state-change"));
  }, [quizStarted, finished]);


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

      if (result.data.status === "no_source_content") {
        setGenerationChoice(null);
        setMessage(
          result.data.message ||
            "Les documents indexés ne contiennent actuellement aucun passage associé à cette catégorie. Importez un PDF pertinent, puis réessayez.",
        );
        return;
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
    const operationId = ++waitOperationId.current;
    generationIdRef.current = null;

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

    const requestedCount = Number(questionCount);
    const initialAvailableCount = Math.max(
      0,
      Number(generationChoice.available_count ?? 0),
    );
    const initialMissingCount = Math.max(
      0,
      requestedCount - initialAvailableCount,
    );
    const estimateStartedAt = Date.now();

    type BankProgress = {
      current: number;
      target: number;
    };

    let initialBankCurrent: number | null = null;
    let latestBankCurrent: number | null = null;
    let initialBankTarget: number | null = null;
    let bankProgressAvailable = false;
    let estimatedQuestionsToGenerate = initialMissingCount;

    /*
     * La progression de la banque est différente du nombre de questions
     * encore jouables par l'utilisateur : les questions déjà jouées restent
     * dans la banque, mais ne sont plus comptées comme disponibles.
     * Cet appel est volontairement facultatif : une erreur de statut ne doit
     * jamais interrompre le lancement ou le suivi de la génération.
     */
    async function readBankProgress(): Promise<BankProgress | null> {
      try {
        const result = await getQuizGenerationStatus(
          categoryIds,
          requestedCount,
          difficulty,
        );

        if (!result.response.ok) {
          return null;
        }

        const data = result.data as {
          categories?: Record<
            string,
            Record<string, { current?: number; target?: number }>
          >;
          status?: Record<string, { current?: number; target?: number }>;
        };

        const categoryStatuses = categoryIds.map(
          (categoryId) => data.categories?.[String(categoryId)]?.[difficulty],
        );

        const completeCategoryStatuses = categoryStatuses.filter(
          (entry): entry is { current: number; target: number } =>
            Boolean(
              entry &&
              typeof entry.current === "number" &&
              Number.isFinite(entry.current) &&
              typeof entry.target === "number" &&
              Number.isFinite(entry.target),
            ),
        );

        if (
          completeCategoryStatuses.length === categoryIds.length &&
          completeCategoryStatuses.length > 0
        ) {
          return {
            current: completeCategoryStatuses.reduce(
              (total, entry) => total + entry.current,
              0,
            ),
            target: completeCategoryStatuses.reduce(
              (total, entry) => total + entry.target,
              0,
            ),
          };
        }

        const aggregateStatus = data.status?.[difficulty];

        if (
          typeof aggregateStatus?.current === "number" &&
          Number.isFinite(aggregateStatus.current) &&
          typeof aggregateStatus.target === "number" &&
          Number.isFinite(aggregateStatus.target)
        ) {
          return {
            current: aggregateStatus.current,
            target: aggregateStatus.target,
          };
        }
      } catch {
        // Le suivi de statut ne doit pas interrompre la génération.
      }

      return null;
    }

    setWaitingForGeneration(true);
    setLoading(true);
    setMessage("Demande de génération des questions...");

    let keepStopAvailable = false;

    try {
      const requestResult = await requestQuizQuestionGeneration(
        categoryIds,
        difficulty,
      );

      if (!requestResult.response.ok) {
        throw new Error(
          requestResult.data.detail ||
          "Impossible de lancer la génération des questions.",
        );
      }

      const generationId =
        typeof requestResult.data.generation_id === "string"
          ? requestResult.data.generation_id
          : null;
      generationIdRef.current = generationId;

      // Stop peut avoir été cliqué pendant la requête initiale.
      if (operationId !== waitOperationId.current) {
        if (generationId) {
          await callGenerationAction("cancel-generation", generationId);
        }
        return;
      }

      // Capture l'état de la banque après la mise en file. Cet appel est
      // facultatif et ne peut pas faire échouer l'option 3.
      const baselineProgress = await readBankProgress();

      if (operationId !== waitOperationId.current) {
        if (generationId) {
          await callGenerationAction("cancel-generation", generationId);
        }
        return;
      }

      if (baselineProgress) {
        initialBankCurrent = baselineProgress.current;
        latestBankCurrent = baselineProgress.current;
        initialBankTarget = baselineProgress.target;
        bankProgressAvailable = true;

        const remainingBankCapacity = Math.max(
          0,
          baselineProgress.target - baselineProgress.current,
        );

        // On ne prévoit pas plus de questions que la banque ne peut encore
        // en produire, même si davantage sont manquantes pour le quiz.
        estimatedQuestionsToGenerate = Math.min(
          initialMissingCount,
          remainingBankCapacity,
        );
      }

      const backendEstimatedSeconds =
        typeof requestResult.data.estimated_seconds === "number" &&
        Number.isFinite(requestResult.data.estimated_seconds) &&
        requestResult.data.estimated_seconds > 0
          ? Math.ceil(requestResult.data.estimated_seconds)
          : null;

      const estimatedSeconds = estimatedQuestionsToGenerate * 2 * 60;
      const estimatedTime = formatEstimatedTime(estimatedSeconds);

      if (initialMissingCount === 0) {
        setMessage(
          "Toutes les questions demandées semblent disponibles. Préparation du quiz...",
        );
      } else if (
        bankProgressAvailable &&
        estimatedQuestionsToGenerate === 0 &&
        initialBankCurrent !== null &&
        initialBankTarget !== null &&
        initialBankCurrent >= initialBankTarget
      ) {
        setMessage(
          "La banque a atteint sa capacité actuelle : aucune nouvelle question n'est prévue pour cette sélection. Vérification des questions jouables...",
        );
      } else {
        setMessage(
          `Génération demandée. Temps estimé : ${estimatedTime} ` +
          "(2 minutes par question à produire).",
        );
      }

      /*
       * Le délai maximal reste une sécurité technique. Il ne contrôle pas
       * l'estimation affichée à l'utilisateur.
       */
      const maxWaitSeconds = Math.min(
        90 * 60,
        Math.max(
          20 * 60,
          (backendEstimatedSeconds ?? estimatedSeconds ?? 15 * 60) + 5 * 60,
        ),
      );
      const maxAttempts = Math.ceil(maxWaitSeconds / 5);
      let idleChecks = 0;

      for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
        await new Promise<void>((resolve) => {
          window.setTimeout(resolve, 5000);
        });

        if (operationId !== waitOperationId.current) {
          return;
        }

        const quizResult = await generateQuiz(
          categoryIds,
          requestedCount,
          difficulty,
          false,
        );

        if (operationId !== waitOperationId.current) {
          return;
        }

        if (!quizResult.response.ok) {
          throw new Error(
            quizResult.data.detail ||
            "Impossible de vérifier les questions générées.",
          );
        }

        if (quizResult.data.status === "ready") {
          if (
            !Array.isArray(quizResult.data.questions) ||
            quizResult.data.questions.length !== requestedCount
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

          if (generationId) {
            await callGenerationAction("release-generation", generationId);
          }
          generationIdRef.current = null;

          if (operationId !== waitOperationId.current) {
            return;
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

        const refreshedChoice = quizResult.data as QuizGenerationData;
        setGenerationChoice(refreshedChoice);

        // L'état de la banque est interrogé périodiquement, mais une erreur
        // sur cet endpoint ne fait jamais arrêter la boucle de génération.
        if (attempt === 1 || attempt % 3 === 0) {
          const currentProgress = await readBankProgress();

          if (operationId !== waitOperationId.current) {
            return;
          }

          if (currentProgress) {
            if (initialBankCurrent === null) {
              // Si le premier état fiable n'arrive qu'en cours de route,
              // on conserve l'avancement estimé depuis le lancement.
              const elapsedQuestionSlots = Math.floor(
                (Date.now() - estimateStartedAt) / (2 * 60 * 1000),
              );
              const inferredCompleted = Math.min(
                initialMissingCount,
                elapsedQuestionSlots,
              );

              initialBankCurrent = currentProgress.current - inferredCompleted;
              initialBankTarget = currentProgress.target;
              estimatedQuestionsToGenerate = Math.min(
                initialMissingCount,
                Math.max(0, initialBankTarget - initialBankCurrent),
              );
            }

            latestBankCurrent = currentProgress.current;
            if (initialBankTarget === null) {
              initialBankTarget = currentProgress.target;
            }
            bankProgressAvailable = true;
          }
        }

        const availableForUser =
          typeof refreshedChoice.available_count === "number"
            ? refreshedChoice.available_count
            : 0;

        const generationActive = Boolean(
          refreshedChoice.generation_active ??
          refreshedChoice.options.wait.generation_active,
        );

        // Nombre de nouvelles questions produites d'après le compteur de la
        // banque. Si ce statut n'est pas accessible, on garde une estimation
        // de deux minutes par question au lieu de bloquer le compteur à zéro
        // simplement parce que l'utilisateur a déjà joué toutes ses questions.
        const elapsedQuestionSlots = Math.floor(
          (Date.now() - estimateStartedAt) / (2 * 60 * 1000),
        );
        const generatedByBank =
          initialBankCurrent !== null && latestBankCurrent !== null
            ? Math.max(0, latestBankCurrent - initialBankCurrent)
            : 0;
        const estimatedCompletedQuestions = Math.min(
          estimatedQuestionsToGenerate,
          bankProgressAvailable
            ? generatedByBank
            : elapsedQuestionSlots,
        );
        const estimateRemainingQuestions = Math.max(
          0,
          estimatedQuestionsToGenerate - estimatedCompletedQuestions,
        );
        const estimateRemainingSeconds = estimateRemainingQuestions * 2 * 60;
        const actualMissingCount = Math.max(
          0,
          requestedCount - availableForUser,
        );

        let estimateMessage: string;
        if (estimatedQuestionsToGenerate === 0) {
          estimateMessage =
            bankProgressAvailable &&
            initialBankCurrent !== null &&
            initialBankTarget !== null &&
            initialBankCurrent >= initialBankTarget
              ? "La banque a atteint sa capacité prévue : aucune autre question ne peut être ajoutée automatiquement pour cette sélection."
              : "Aucune question supplémentaire n'est actuellement prévue pour cette génération.";
        } else if (estimateRemainingQuestions === 0) {
          estimateMessage =
            "L'estimation est écoulée ; vérification de la disponibilité des questions.";
        } else {
          estimateMessage =
            `Estimation restante : ${formatEstimatedTime(estimateRemainingSeconds)} ` +
            "(2 minutes par question estimée restante).";
        }

        const progressMessage = bankProgressAvailable
          ? `Progression de la banque : ${Math.min(estimatedQuestionsToGenerate, generatedByBank)}/${estimatedQuestionsToGenerate} nouvelle(s) question(s) enregistrée(s).`
          : `Estimation indicative : ${estimatedCompletedQuestions}/${estimatedQuestionsToGenerate} question(s) estimée(s) produite(s).`;

        setMessage(
          `Questions utilisables : ${availableForUser}/${requestedCount}. ` +
          `${actualMissingCount} question(s) encore nécessaire(s) pour ton quiz. ` +
          `${progressMessage} ${estimateMessage}`,
        );

        if (generationActive) {
          idleChecks = 0;
        } else {
          idleChecks += 1;
        }

        if (idleChecks >= 2) {
          if (generationId) {
            await callGenerationAction("release-generation", generationId);
          }
          generationIdRef.current = null;

          if (operationId !== waitOperationId.current) {
            return;
          }

          setMessage(
            availableForUser > 0
              ? `La génération est terminée. Il reste ${availableForUser} question(s) jouable(s) pour toi. Tu peux choisir un quiz plus court ou revenir à la configuration.`
              : "La génération est terminée, mais aucune question supplémentaire n'est disponible pour cette sélection. Tu peux choisir une autre difficulté ou modifier les catégories.",
          );

          return;
        }
      }

      // Le suivi s'arrête, mais on garde l'identifiant pour que Stop puisse
      // encore annuler la génération si elle continue en arrière-plan.
      keepStopAvailable = Boolean(generationIdRef.current);
      setMessage(
        "Le délai de suivi est dépassé. Les questions déjà enregistrées sont conservées. La génération peut encore tourner en arrière-plan ; utilise Stop pour l'annuler.",
      );
    } catch (error) {
      if (operationId === waitOperationId.current) {
        if (generationIdRef.current) {
          keepStopAvailable = true;
          setMessage(
            `${getErrorMessage(error, "Erreur lors du suivi de génération.")} La tâche peut continuer en arrière-plan ; le bouton Stop reste disponible pour l'annuler. Les questions déjà enregistrées sont conservées.`,
          );
        } else {
          handleGenerationError(
            error,
            "Erreur lors de la demande ou du suivi de génération.",
          );
        }
      }
    } finally {
      if (operationId === waitOperationId.current) {
        setLoading(false);
        if (!keepStopAvailable) {
          setWaitingForGeneration(false);
        }
      }
    }
  }

  function cancelGenerationChoice() {
    if (waitingForGeneration) {
      // Invalide immédiatement la boucle de suivi côté interface.
      waitOperationId.current += 1;
      const generationId = generationIdRef.current;
      generationIdRef.current = null;
      if (generationId) {
        void callGenerationAction("cancel-generation", generationId);
      }
      setWaitingForGeneration(false);
      setLoading(false);
      setGenerationChoice(null);
      setMessage(
        "Annulation demandée. Les questions déjà enregistrées sont conservées.",
      );
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
    if (waitingForGeneration) {
      waitOperationId.current += 1;
      const generationId = generationIdRef.current;
      generationIdRef.current = null;
      if (generationId) {
        void callGenerationAction("cancel-generation", generationId);
      }
    }

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