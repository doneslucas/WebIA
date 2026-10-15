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

  generationChoice:
    QuizGenerationData | null;

  waitingForGeneration: boolean;

  setCategoryIds: (value: number[]) => void;
  setQuestionCount: (value: string) => void;
  setDifficulty: (value: string) => void;

  startQuiz: () => Promise<void>;

  startWithAvailableQuestions: () => Promise<void>;

  startMixedQuiz: (
    fallbackDifficulty: string
  ) => Promise<void>;

  waitForQuestions: () => Promise<void>;

  cancelGenerationChoice: () => void;

  selectAnswer: (answerIndex: number) => void;
  showQuestionCorrection: () => Promise<void>;
  nextQuestion: () => Promise<void>;

  returnToQuizHome: () => void;

  score: number;
};


const QuizContext =
  createContext<QuizContextType | undefined>(
    undefined
  );


type QuizProviderProps = {
  children: ReactNode;
};


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
    setCurrentAnswerCorrect
  ] = useState<boolean | null>(null);


  const [
    currentCorrectAnswer,
    setCurrentCorrectAnswer
  ] = useState<number | null>(null);


  const [
    currentExplanation,
    setCurrentExplanation
  ] = useState("");


  const [score, setScore] =
    useState(0);


  const [
    generationChoice,
    setGenerationChoice
  ] = useState<QuizGenerationData | null>(
    null
  );


  const [
    waitingForGeneration,
    setWaitingForGeneration
  ] = useState(false);


  function initializeQuiz(
    receivedQuestions: QuizQuestion[]
  ) {

    setQuestions(
      receivedQuestions
    );

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


  async function startQuiz() {

    if (categoryIds.length === 0) {

      setMessage(
        "Veuillez sélectionner au moins une catégorie."
      );

      return;
    }

    setMessage("");
    setLoading(true);
    setGenerationChoice(null);

    try {

      const result =
        await generateQuiz(
          categoryIds,
          Number(questionCount),
          difficulty
        );


      if (!result.response.ok) {

        throw new Error(
          result.data.detail ||
          "Erreur lors de la préparation du quiz."
        );
      }


      if (
        result.data.status ===
        "insufficient_questions"
      ) {

        setGenerationChoice(
          result.data
        );

        return;
      }


      if (
        result.data.status !==
        "ready"
      ) {

        throw new Error(
          "Réponse inattendue du serveur."
        );
      }


      if (
        !result.data.questions ||
        !Array.isArray(result.data.questions)
      ) {

        throw new Error(
          "Le serveur n'a pas retourné de questions valides."
        );
      }


      const validQuestions =
        result.data.questions.filter(
          (
            question: QuizQuestion
          ) =>
            typeof question.id === "number" &&
            typeof question.question === "string" &&
            Array.isArray(question.options) &&
            question.options.length === 4 &&
            typeof question.difficulty === "string"
        );


      if (
        validQuestions.length !==
        result.data.questions.length
      ) {

        throw new Error(
          "Certaines questions reçues du serveur sont invalides."
        );
      }


      initializeQuiz(
        validQuestions
      );

    } catch (error) {

      console.error(error);


      if (error instanceof Error) {

        setMessage(
          error.message
        );

      } else {

        setMessage(
          "Une erreur est survenue lors de la préparation du quiz."
        );
      }

    } finally {

      setLoading(false);
    }
  }


  async function startWithAvailableQuestions() {

    if (!generationChoice) {
      return;
    }

    if (categoryIds.length === 0) {

      setMessage(
        "Veuillez sélectionner au moins une catégorie."
      );

      return;
    }

    setLoading(true);
    setMessage("");

    try {

      const availableCount =
        generationChoice.available_count;

      if (availableCount <= 0) {

        throw new Error(
          "Aucune question n'est actuellement disponible."
        );
      }

      const result =
        await generateQuiz(
          categoryIds,
          Math.min(
            availableCount,
            Number(questionCount)
          ),
          difficulty
        );


      if (!result.response.ok) {

        throw new Error(
          result.data.detail ||
          "Impossible de récupérer les questions disponibles."
        );
      }


      if (
        result.data.status !==
        "ready"
      ) {

        throw new Error(
          "Les questions disponibles ont changé. Veuillez réessayer."
        );
      }


      if (
        !result.data.questions ||
        !Array.isArray(result.data.questions)
      ) {

        throw new Error(
          "Le serveur n'a pas retourné de questions valides."
        );
      }


      initializeQuiz(
        result.data.questions
      );

    } catch (error) {

      console.error(error);

      if (error instanceof Error) {

        setMessage(
          error.message
        );

      } else {

        setMessage(
          "Impossible de démarrer le quiz."
        );
      }

    } finally {

      setLoading(false);
    }
  }


  async function startMixedQuiz(
    fallbackDifficulty: string
  ) {

    if (!generationChoice) {
      return;
    }

    if (categoryIds.length === 0) {

      setMessage(
        "Veuillez sélectionner au moins une catégorie."
      );

      return;
    }

    setLoading(true);
    setMessage("");

    try {

      const result =
        await generateMixedQuiz(
          categoryIds,
          Number(questionCount),
          difficulty,
          fallbackDifficulty
        );


      if (!result.response.ok) {

        throw new Error(
          result.data.detail ||
          "Impossible de compléter le quiz."
        );
      }


      if (
        result.data.status !==
        "ready"
      ) {

        throw new Error(
          "Le serveur n'a pas pu compléter le quiz."
        );
      }


      if (
        !result.data.questions ||
        !Array.isArray(result.data.questions)
      ) {

        throw new Error(
          "Le serveur n'a pas retourné de questions valides."
        );
      }


      if (
        result.data.questions.length !==
        Number(questionCount)
      ) {

        throw new Error(
          "Le quiz mixte ne contient pas le nombre demandé de questions."
        );
      }


      initializeQuiz(
        result.data.questions
      );

    } catch (error) {

      console.error(error);

      if (error instanceof Error) {

        setMessage(
          error.message
        );

      } else {

        setMessage(
          "Impossible de compléter le quiz."
        );
      }

    } finally {

      setLoading(false);
    }
  }


  async function waitForQuestions() {

    if (!generationChoice) {
      return;
    }

    if (categoryIds.length === 0) {

      setMessage(
        "Veuillez sélectionner au moins une catégorie."
      );

      return;
    }

    setWaitingForGeneration(true);
    setLoading(true);
    setMessage(
      "En attente de nouvelles questions..."
    );


    try {

      let attempts = 0;

      const maxAttempts = 120;

      while (
        attempts < maxAttempts
      ) {

        attempts += 1;

        const result =
          await getQuizGenerationStatus(
            categoryIds,
            Number(questionCount),
            difficulty
          );


        if (!result.response.ok) {

          throw new Error(
            result.data.detail ||
            "Impossible de suivre la génération."
          );
        }


        const status =
          result.data;

        const difficultyStatus =
          status.status?.[difficulty];


        if (
          difficultyStatus &&
          difficultyStatus.current >=
          Number(questionCount)
        ) {

          const quizResult =
            await generateQuiz(
              categoryIds,
              Number(questionCount),
              difficulty
            );


          if (
            quizResult.response.ok &&
            quizResult.data.status ===
            "ready"
          ) {

            initializeQuiz(
              quizResult.data.questions
            );

            return;
          }
        }


        const availableCount =
          difficultyStatus?.current ?? 0;


        setMessage(
          `Génération en cours : ${
            availableCount
          } / ${
            Number(questionCount)
          } questions disponibles.`
        );


        await new Promise(
          (resolve) =>
            setTimeout(
              resolve,
              3000
            )
        );
      }


      throw new Error(
        "La génération prend plus de temps que prévu. Vous pouvez réessayer dans quelques instants."
      );

    } catch (error) {

      console.error(error);

      if (error instanceof Error) {

        setMessage(
          error.message
        );

      } else {

        setMessage(
          "Erreur lors du suivi de la génération."
        );
      }

    } finally {

      setLoading(false);
      setWaitingForGeneration(false);
    }
  }


  function cancelGenerationChoice() {

    setGenerationChoice(null);
    setWaitingForGeneration(false);
    setLoading(false);
    setMessage("");
  }


  function selectAnswer(
    answerIndex: number
  ) {

    if (
      showCorrection ||
      finished
    ) {
      return;
    }


    if (
      answerIndex < 0 ||
      answerIndex > 3
    ) {
      return;
    }


    setAnswers((previous) => {

      const updated = [
        ...previous
      ];

      updated[currentQuestion] =
        answerIndex;

      return updated;
    });


    setMessage("");
  }


  async function showQuestionCorrection() {

    const selectedAnswer =
      answers[currentQuestion];


    if (
      selectedAnswer === undefined
    ) {

      setMessage(
        "Veuillez sélectionner une réponse avant de continuer."
      );

      return;
    }


    const question =
      questions[currentQuestion];


    if (!question) {

      setMessage(
        "Question introuvable."
      );

      return;
    }


    setLoading(true);
    setMessage("");


    try {

      const result =
        await checkQuizAnswer(
          question.id,
          selectedAnswer
        );


      if (!result.response.ok) {

        throw new Error(
          result.data.detail ||
          "Impossible de vérifier la réponse."
        );
      }


      setCurrentAnswerCorrect(
        result.data.is_correct
      );

      setCurrentCorrectAnswer(
        result.data.correct_answer
      );

      setCurrentExplanation(
        result.data.explanation ||
        ""
      );

      setShowCorrection(true);

    } catch (error) {

      console.error(
        "Erreur lors de la vérification de la réponse :",
        error
      );


      if (
        error instanceof Error
      ) {

        setMessage(
          error.message
        );

      } else {

        setMessage(
          "Erreur lors de la vérification de la réponse."
        );
      }

    } finally {

      setLoading(false);
    }
  }


  async function nextQuestion() {

    if (
      currentQuestion ===
      questions.length - 1
    ) {

      setLoading(true);
      setMessage("");

      try {

        const formattedAnswers =
          questions.map(
            (
              question,
              index
            ) => {

              const answer =
                answers[index];

              if (
                answer === undefined
              ) {

                throw new Error(
                  "Toutes les questions doivent avoir une réponse."
                );
              }

              return {
                question_id:
                  question.id,
                answer,
              };
            }
          );


        const result =
          await submitQuiz(
            formattedAnswers
          );


        if (!result.response.ok) {

          throw new Error(
            result.data.detail ||
            "Impossible d'enregistrer le quiz."
          );
        }


        if (
          typeof result.data.score !==
          "number"
        ) {

          throw new Error(
            "Le serveur n'a pas retourné de score valide."
          );
        }


        setScore(
          result.data.score
        );

        setFinished(true);

        setShowCorrection(false);

        setMessage("");

      } catch (error) {

        console.error(
          "Erreur lors de l'enregistrement du quiz :",
          error
        );


        if (
          error instanceof Error
        ) {

          setMessage(
            error.message
          );

        } else {

          setMessage(
            "Erreur lors de l'enregistrement du quiz."
          );
        }

      } finally {

        setLoading(false);
      }

      return;
    }


    setCurrentQuestion(
      (previous) =>
        previous + 1
    );

    setShowCorrection(false);

    setCurrentAnswerCorrect(null);

    setCurrentCorrectAnswer(null);

    setCurrentExplanation("");

    setMessage("");
  }


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

  const context =
    useContext(
      QuizContext
    );


  if (!context) {

    throw new Error(
      "useQuiz doit être utilisé à l'intérieur de QuizProvider."
    );
  }


  return context;
}